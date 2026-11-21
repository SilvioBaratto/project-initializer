"""Integration tests of the Entra variant's token validation.

Real RS256 tokens, signed by a key the tests generate, go through the real
dependency chain (bearer extraction, verifier, error handlers). Only the key
source is a stub, so no tenant and no network are involved. The verifier's own
rules are unit-tested; these tests pin how its outcomes reach the HTTP caller.
"""

import json
import logging
from collections.abc import Callable, Iterator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from jwt.exceptions import PyJWKClientConnectionError

from app.api.auth_deps import get_token_verifier
from app.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ExternalServiceError,
)
from app.infrastructure.auth.entra import EntraTokenVerifier
from app.main import app
from tests import http_helpers
from tests.auth_test_env import TEST_TENANT_ID
from tests.entra_tokens import (
    OBJECT_ID,
    USER_EMAIL,
    USERNAME,
    StubKeySource,
    build_verifier,
    make_token,
    sign_token,
    tenant_signing_key,
    unpublished_signing_key,
    valid_claims,
)
from tests.http_helpers import HANDLER_LOGGER, bearer

pytestmark = pytest.mark.integration

# Binding the shared fixture to a name of this module is what makes pytest see it;
# a plain import would turn every test parameter into a redefined unused import.
me_url = http_helpers.me_url

PAST_ISSUED_AT = 1_700_000_000
PAST_EXPIRY = PAST_ISSUED_AT + 3600
ITEM_BODY = {"name": "Widget", "price": 1.0}
OTHER_TENANT_ID = "0f9e8d7c-6b5a-4c3d-8e2f-1a0b9c8d7e6f"
KEY_ENDPOINT_FAILURES = [
    pytest.param(PyJWKClientConnectionError("unreachable"), id="unreachable"),
    pytest.param(ConnectionResetError("reset"), id="connection-reset"),
    pytest.param(json.JSONDecodeError("not json", "<html>", 0), id="not-json"),
]
REJECTED_TOKENS = [
    pytest.param(
        lambda: make_token(iat=PAST_ISSUED_AT, exp=PAST_EXPIRY, email=USER_EMAIL),
        "expired",
        id="expired",
    ),
    pytest.param(
        lambda: make_token(aud="api://someone-else", email=USER_EMAIL),
        "wrong_audience",
        id="wrong-audience",
    ),
    pytest.param(
        lambda: make_token(tid=OTHER_TENANT_ID, email=USER_EMAIL),
        "wrong_tenant",
        id="wrong-tenant",
    ),
    pytest.param(
        lambda: sign_token(valid_claims(email=USER_EMAIL), unpublished_signing_key()),
        "bad_signature",
        id="bad-signature",
    ),
]
PROTECTED_REQUESTS = [
    pytest.param("post", "/items", {"json": ITEM_BODY}, id="item-write"),
    pytest.param("get", "/auth/me", {}, id="current-user"),
]


@pytest.fixture
def use_entra_client(client: TestClient) -> Callable[..., TestClient]:
    """Factory of a client whose token checks use a verifier over a stub key source."""

    def use(key_source: StubKeySource | None = None) -> TestClient:
        """Route the application's token checks to a verifier over ``key_source``."""
        verifier = build_verifier(key_source)
        app.dependency_overrides[get_token_verifier] = lambda: verifier
        return client

    return use


def test_when_a_valid_token_is_sent_then_me_returns_the_entra_identity(
    use_entra_client, me_url
):
    """when a fully valid token is sent, /auth/me answers with the principal.

    Validates app.api.auth_deps.get_current_user().
    """
    token = make_token(email=USER_EMAIL, roles=["Reader"])

    response = use_entra_client().get(me_url, headers=bearer(token))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "id": OBJECT_ID,
        "email": USER_EMAIL,
        "username": USERNAME,
        "roles": ["Reader"],
        "auth_method": "entra",
    }


@pytest.mark.parametrize(("build_token", "reason"), REJECTED_TOKENS)
def test_when_a_token_is_invalid_then_401_is_generic_and_the_log_holds_only_the_reason(
    use_entra_client, me_url, caplog, build_token, reason
):
    """when a check fails, the caller gets the fixed 401 and the log holds no token.

    Validates app.api.auth_deps.get_current_user().
    """
    token = build_token()

    with caplog.at_level(logging.WARNING, logger=HANDLER_LOGGER):
        response = use_entra_client().get(me_url, headers=bearer(token))

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.headers["WWW-Authenticate"] == "Bearer"
    error = response.json()["error"]
    assert error["code"] == AuthenticationError.error_code
    assert error["message"] == AuthenticationError.default_message
    assert reason not in response.text
    (record,) = [r for r in caplog.records if r.name == HANDLER_LOGGER]
    assert record.context["reason"] == reason
    for private_value in (token, USER_EMAIL, USERNAME):
        assert private_value not in caplog.text


def test_when_the_token_lacks_the_scope_then_403_hides_it_and_the_log_holds_the_ids(
    use_entra_client, me_url, caplog
):
    """when scp lacks the scope, 403 hides it and the log holds oid and tid only.

    Validates app.api.auth_deps.get_current_user().
    """
    token = make_token(scp="other_scope", email=USER_EMAIL)

    with caplog.at_level(logging.WARNING, logger=HANDLER_LOGGER):
        response = use_entra_client().get(me_url, headers=bearer(token))

    assert response.status_code == HTTPStatus.FORBIDDEN
    error = response.json()["error"]
    assert error["code"] == AuthorizationError.error_code
    assert error["message"] == AuthorizationError.default_message
    assert "access_as_user" not in response.text
    (record,) = [r for r in caplog.records if r.name == HANDLER_LOGGER]
    assert record.context == {
        "reason": "missing_scope",
        "oid": OBJECT_ID,
        "tid": TEST_TENANT_ID,
    }
    assert USER_EMAIL not in caplog.text


@pytest.mark.parametrize("failure", KEY_ENDPOINT_FAILURES)
def test_when_the_key_endpoint_fails_then_503_with_retry_after_and_the_class_logged(
    use_entra_client, me_url, caplog, failure
):
    """when the signing keys cannot be fetched, the answer is 503 and not 401.

    Validates app.api.auth_deps.get_current_user().
    """
    client = use_entra_client(StubKeySource({}, error=failure))

    with caplog.at_level(logging.ERROR, logger=HANDLER_LOGGER):
        response = client.get(me_url, headers=bearer(make_token()))

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["error"]["code"] == ExternalServiceError.error_code
    assert "Retry-After" in response.headers
    (record,) = [r for r in caplog.records if r.name == HANDLER_LOGGER]
    assert record.context == {"service": "entra_jwks", "error": type(failure).__name__}


def test_when_strangers_send_unknown_kids_then_the_key_endpoint_is_asked_once(
    use_entra_client, me_url
):
    """when tokens name random kids, the API reloads the key set once, not per request.

    Validates app.api.auth_deps.get_current_user().
    """
    key_source = StubKeySource({"published": tenant_signing_key().public_key()})
    client = use_entra_client(key_source)
    stranger_tokens = [
        sign_token(valid_claims(), tenant_signing_key(), kid=f"stranger-{number}")
        for number in range(5)
    ]

    statuses = {
        client.get(me_url, headers=bearer(token)).status_code
        for token in stranger_tokens
    }

    assert statuses == {HTTPStatus.UNAUTHORIZED}
    assert key_source.refreshes == 1


@pytest.mark.parametrize(("method", "path", "options"), PROTECTED_REQUESTS)
def test_when_no_authorization_header_is_sent_then_401_before_the_verifier_is_built(
    client, api_prefix, method, path, options
):
    """when the header is missing, 401 is answered and no verifier is even built.

    Validates app.api.auth_deps.get_current_user().
    """

    def fail_if_built():
        """Fail the test when a request reaches the verifier."""
        raise AssertionError("the verifier must not be built without a token")

    app.dependency_overrides[get_token_verifier] = fail_if_built

    response = getattr(client, method)(f"{api_prefix}{path}", **options)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"]["code"] == AuthenticationError.error_code


def test_when_a_valid_token_creates_an_item_then_201(use_entra_client, api_prefix):
    """when the token is valid, a protected item write succeeds.

    Validates app.api.auth_deps.CurrentUser.
    """
    response = use_entra_client().post(
        f"{api_prefix}/items", json=ITEM_BODY, headers=bearer(make_token())
    )

    assert response.status_code == HTTPStatus.CREATED


def test_when_the_token_is_expired_then_an_item_write_is_401(
    use_entra_client, api_prefix
):
    """when the token is expired, a protected item write answers 401.

    Validates app.api.auth_deps.CurrentUser.
    """
    token = make_token(iat=PAST_ISSUED_AT, exp=PAST_EXPIRY)

    response = use_entra_client().post(
        f"{api_prefix}/items", json=ITEM_BODY, headers=bearer(token)
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.fixture
def fresh_verifier_cache() -> Iterator[None]:
    """Start and leave the process-wide verifier cache empty."""
    get_token_verifier.cache_clear()
    yield
    get_token_verifier.cache_clear()


def test_when_the_verifier_is_requested_twice_then_one_instance_is_built_from_settings(
    fresh_verifier_cache,
):
    """when get_token_verifier is called twice, one configured verifier is returned.

    Validates app.api.auth_deps.get_token_verifier().
    """
    first = get_token_verifier()

    assert isinstance(first, EntraTokenVerifier)
    assert get_token_verifier() is first
