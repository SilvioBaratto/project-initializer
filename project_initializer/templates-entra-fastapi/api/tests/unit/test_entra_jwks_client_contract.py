"""Contract tests of the resolver against the pinned ``PyJWKClient``.

The real client runs, and only the network below it is replaced: every call of
``urllib.request.OpenerDirector.open`` is answered from a script. These tests pin
what the installed PyJWT really raises for each answer of the key endpoint, which
is the assumption the resolver's failure mapping rests on.
"""

import io
import json
import urllib.request
from collections.abc import Callable
from email.message import Message
from typing import Any
from urllib.error import HTTPError, URLError

import jwt
import pytest
from jwt import PyJWKClient
from jwt.algorithms import RSAAlgorithm

from app.domain.exceptions import ExternalServiceError
from app.infrastructure.auth.entra_jwks import (
    SERVICE_NAME,
    CooldownSigningKeyResolver,
)
from tests.entra_tokens import (
    REFRESH_COOLDOWN_SECONDS,
    SIGNING_KID,
    make_token,
    sign_token,
    tenant_signing_key,
    valid_claims,
)

pytestmark = pytest.mark.unit

KEY_URL = "https://login.example.test/tenant/discovery/v2.0/keys"
KEY_TIMEOUT_SECONDS = 5
SERVER_ERROR_CODE = 500
UNKNOWN_KID = "never-published"
INITIAL_LOAD_AND_ONE_RELOAD = 2


def published_key_set(*key_ids: str) -> dict[str, Any]:
    """JWKS document that publishes the tenant's public key under each ``kid``."""
    public_jwk = RSAAlgorithm.to_jwk(tenant_signing_key().public_key(), as_dict=True)
    return {"keys": [{**public_jwk, "kid": kid, "use": "sig"} for kid in key_ids]}


def as_body(document: object) -> bytes:
    """Serialise a JSON document the way the endpoint would answer."""
    return json.dumps(document).encode()


def server_error() -> HTTPError:
    """The error ``urllib`` raises for an HTTP 500."""
    return HTTPError(
        KEY_URL, SERVER_ERROR_CODE, "Internal Server Error", Message(), io.BytesIO()
    )


class ScriptedKeyEndpoint:
    """Answers each request in turn; the last answer repeats."""

    def __init__(self, *answers: bytes | BaseException) -> None:
        self._answers = answers
        self.requests = 0

    def answer(self) -> io.BytesIO:
        """Return the next scripted body, or raise the next scripted error."""
        scripted = self._answers[min(self.requests, len(self._answers) - 1)]
        self.requests += 1
        if isinstance(scripted, BaseException):
            raise scripted
        return io.BytesIO(scripted)


@pytest.fixture
def serve_keys(monkeypatch: pytest.MonkeyPatch) -> Callable[..., ScriptedKeyEndpoint]:
    """Factory that scripts the key endpoint for the real client."""

    def serve(*answers: bytes | BaseException) -> ScriptedKeyEndpoint:
        """Replace the network below ``PyJWKClient`` with ``answers``."""
        endpoint = ScriptedKeyEndpoint(*answers)
        monkeypatch.setattr(
            urllib.request.OpenerDirector,
            "open",
            lambda opener, fullurl, data=None, timeout=None: endpoint.answer(),
        )
        return endpoint

    return serve


def real_resolver() -> CooldownSigningKeyResolver:
    """Resolver over a real ``PyJWKClient`` pointed at the scripted endpoint."""
    return CooldownSigningKeyResolver(
        PyJWKClient(KEY_URL, timeout=KEY_TIMEOUT_SECONDS),
        refresh_cooldown_seconds=REFRESH_COOLDOWN_SECONDS,
    )


ENDPOINT_FAILURES = [
    pytest.param(
        URLError("unreachable"), "PyJWKClientConnectionError", id="unreachable"
    ),
    pytest.param(server_error(), "PyJWKClientConnectionError", id="http-500"),
    pytest.param(TimeoutError("slow"), "PyJWKClientConnectionError", id="timeout"),
    pytest.param(
        ConnectionResetError("reset"), "ConnectionResetError", id="connection-reset"
    ),
    pytest.param(b"<html>bad gateway</html>", "JSONDecodeError", id="not-json"),
    pytest.param(as_body({"keys": []}), "PyJWKSetError", id="empty-key-set"),
    pytest.param(
        as_body({"error": "invalid_tenant"}), "PyJWKSetError", id="error-object"
    ),
    pytest.param(as_body(["not", "an", "object"]), None, id="json-array"),
    pytest.param(
        as_body({"keys": [{"kty": "RSA", "use": "enc", "kid": "x"}]}),
        None,
        id="no-usable-signing-key",
    ),
]


def test_when_the_endpoint_publishes_the_kid_then_the_real_client_yields_the_key(
    serve_keys,
):
    """when the JWKS holds the token's kid, the key that verifies the token is returned.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    endpoint = serve_keys(as_body(published_key_set(SIGNING_KID)))

    key = real_resolver().get_signing_key_from_jwt(make_token())

    assert jwt.decode(
        make_token(),
        key.key,
        algorithms=["RS256"],
        audience=None,
        options={"verify_aud": False},
    )
    assert endpoint.requests == 1


def test_when_the_kid_is_unknown_then_the_real_client_is_reloaded_once_per_cooldown(
    serve_keys,
):
    """when tokens name unpublished kids, the real client is asked once more, only once.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    endpoint = serve_keys(as_body(published_key_set(SIGNING_KID)))
    resolver = real_resolver()
    token = sign_token(valid_claims(), tenant_signing_key(), kid=UNKNOWN_KID)

    answers = [resolver.get_signing_key_from_jwt(token) for _ in range(3)]

    assert answers == [None, None, None]
    assert endpoint.requests == INITIAL_LOAD_AND_ONE_RELOAD


@pytest.mark.parametrize(("answer", "error_class"), ENDPOINT_FAILURES)
def test_when_the_endpoint_misbehaves_then_the_real_client_ends_in_a_503(
    serve_keys, answer, error_class
):
    """when the endpoint fails or answers junk, every case becomes ExternalServiceError.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    serve_keys(answer)

    with pytest.raises(ExternalServiceError) as raised:
        real_resolver().get_signing_key_from_jwt(make_token())

    assert raised.value.log_context["service"] == SERVICE_NAME
    if error_class is not None:
        assert raised.value.log_context["error"] == error_class


def test_when_a_reload_fails_after_a_good_load_then_a_published_kid_still_resolves(
    serve_keys,
):
    """when a stranger's kid forces a reload during an outage, known keys still verify.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    serve_keys(as_body(published_key_set(SIGNING_KID)), URLError("down"))
    resolver = real_resolver()
    strange_token = sign_token(valid_claims(), tenant_signing_key(), kid=UNKNOWN_KID)

    with pytest.raises(ExternalServiceError):
        resolver.get_signing_key_from_jwt(strange_token)

    assert resolver.get_signing_key_from_jwt(make_token()) is not None
