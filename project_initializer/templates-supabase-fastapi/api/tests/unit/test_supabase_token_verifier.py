"""Unit tests of the Supabase token verifier, with fake and real auth clients.

The fake client pins the mapping from Supabase answers to domain errors. The
real client, wired to an in-process HTTP transport, pins that the pinned
``supabase`` release raises the error types the verifier relies on.
"""

from collections.abc import Callable
from http import HTTPStatus

import httpx
import pytest
from supabase import (
    AuthApiError,
    AuthRetryableError,
    AuthUnknownError,
    ClientOptions,
    create_client,
)

from app.domain.exceptions import AuthenticationError, ExternalServiceError
from app.infrastructure.auth import supabase as supabase_module
from app.infrastructure.auth.supabase import (
    ANONYMOUS_ROLE,
    RejectionReason,
    SupabaseTokenVerifier,
)
from app.infrastructure.auth_settings import AuthSettings
from tests.supabase_fakes import (
    ACCESS_TOKEN,
    PROJECT_API_KEY,
    PROJECT_URL,
    SUPABASE_USER_EMAIL,
    SUPABASE_USER_ID,
    FakeSupabaseClient,
    make_malformed_user_error,
    make_user_response,
)

pytestmark = pytest.mark.unit

REJECTED_CODE = "bad_jwt"
AUTH_TIMEOUT_SECONDS = 2.5
USER_PAYLOAD = make_user_response().user.model_dump(mode="json")
RATE_LIMIT_BODY = {
    "code": 429,
    "error_code": "over_request_rate_limit",
    "msg": "slow down",
}
SESSION_GONE_BODY = {
    "code": 403,
    "error_code": "session_not_found",
    "msg": "Session from session_id claim in JWT does not exist",
}
USER_GONE_BODY = {
    "code": 404,
    "error_code": "user_not_found",
    "msg": "User from sub claim in JWT does not exist",
}


UNAVAILABLE_ERRORS = [
    pytest.param(AuthRetryableError("bad gateway", 502), id="retryable-gateway-error"),
    pytest.param(AuthApiError("boom", 500, None), id="supabase-server-error"),
    pytest.param(AuthApiError("slow down", 429, "over_request_rate_limit"), id="429"),
    pytest.param(AuthUnknownError("unreadable", ValueError()), id="unreadable-answer"),
    pytest.param(httpx.ConnectError("refused"), id="connection-refused"),
    pytest.param(httpx.ReadTimeout("slow"), id="timeout"),
    pytest.param(make_malformed_user_error(), id="200-that-is-not-a-user"),
]


def refuse_connection(request: httpx.Request) -> httpx.Response:
    """Transport handler that behaves like an unreachable server."""
    raise httpx.ConnectError("refused", request=request)


REAL_CLIENT_OUTCOMES = [
    pytest.param(
        lambda request: httpx.Response(HTTPStatus.OK, json=USER_PAYLOAD),
        None,
        id="valid-token",
    ),
    pytest.param(
        lambda request: httpx.Response(
            HTTPStatus.UNAUTHORIZED,
            json={"code": 401, "error_code": REJECTED_CODE, "msg": "invalid JWT"},
        ),
        AuthenticationError,
        id="rejected-token",
    ),
    pytest.param(
        lambda request: httpx.Response(HTTPStatus.BAD_GATEWAY, text="upstream down"),
        ExternalServiceError,
        id="bad-gateway",
    ),
    pytest.param(
        lambda request: httpx.Response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            json={"code": 500, "error_code": "unexpected_failure", "msg": "boom"},
        ),
        ExternalServiceError,
        id="server-error",
    ),
    pytest.param(
        lambda request: httpx.Response(
            HTTPStatus.TOO_MANY_REQUESTS, json=RATE_LIMIT_BODY
        ),
        ExternalServiceError,
        id="rate-limited",
    ),
    pytest.param(
        lambda request: httpx.Response(HTTPStatus.TOO_MANY_REQUESTS, text="slow down"),
        ExternalServiceError,
        id="rate-limited-without-a-json-body",
    ),
    pytest.param(
        lambda request: httpx.Response(HTTPStatus.FORBIDDEN, json=SESSION_GONE_BODY),
        AuthenticationError,
        id="session-signed-out",
    ),
    pytest.param(
        lambda request: httpx.Response(HTTPStatus.NOT_FOUND, json=USER_GONE_BODY),
        AuthenticationError,
        id="user-deleted",
    ),
    pytest.param(
        lambda request: httpx.Response(HTTPStatus.OK, json={"unexpected": True}),
        ExternalServiceError,
        id="200-with-another-document",
    ),
    pytest.param(
        lambda request: httpx.Response(HTTPStatus.OK, text="<html>"),
        ExternalServiceError,
        id="200-that-is-not-json",
    ),
    pytest.param(
        refuse_connection,
        ExternalServiceError,
        id="connection-refused",
    ),
]


def verifier_for(client: FakeSupabaseClient) -> SupabaseTokenVerifier:
    """Build the verifier around a fake client."""
    return SupabaseTokenVerifier(client)


def test_when_supabase_knows_the_token_then_the_principal_is_returned():
    """when Supabase Auth returns a user, the principal carries id, email and role.

    Validates app.infrastructure.auth.supabase.SupabaseTokenVerifier.verify().
    """
    client = FakeSupabaseClient(response=make_user_response())

    principal = verifier_for(client).verify(ACCESS_TOKEN)

    assert principal.id == SUPABASE_USER_ID
    assert principal.email == SUPABASE_USER_EMAIL
    assert principal.auth_method == "supabase"
    assert principal.roles == ("authenticated",)
    assert client.auth.tokens == [ACCESS_TOKEN]


@pytest.mark.parametrize("missing_email", [None, ""])
def test_when_the_user_has_no_email_then_the_principal_has_none(missing_email):
    """when the user is phone-only, the principal is built with email None.

    Validates app.infrastructure.auth.supabase.SupabaseTokenVerifier.verify().
    """
    response = make_user_response(email=missing_email, phone="+393331234567")

    principal = verifier_for(FakeSupabaseClient(response=response)).verify(ACCESS_TOKEN)

    assert principal.email is None
    assert principal.id == SUPABASE_USER_ID


def test_when_the_user_is_anonymous_then_the_role_is_anonymous_not_authenticated():
    """when Supabase reports an anonymous sign-in, the role never reads authenticated.

    Validates app.infrastructure.auth.supabase.SupabaseTokenVerifier.verify().
    """
    response = make_user_response(is_anonymous=True, email=None)

    principal = verifier_for(FakeSupabaseClient(response=response)).verify(ACCESS_TOKEN)

    assert principal.roles == (ANONYMOUS_ROLE,)
    assert not principal.has_any_role(["authenticated"])


def test_when_the_user_has_no_role_then_the_principal_has_no_roles():
    """when Supabase reports no role, the principal holds an empty role tuple.

    Validates app.infrastructure.auth.supabase.SupabaseTokenVerifier.verify().
    """
    response = make_user_response(role=None)

    principal = verifier_for(FakeSupabaseClient(response=response)).verify(ACCESS_TOKEN)

    assert principal.roles == ()


def test_when_supabase_rejects_the_token_then_authentication_fails_with_a_reason():
    """when Supabase answers 401, AuthenticationError carries status and code for logs.

    Validates app.infrastructure.auth.supabase.SupabaseTokenVerifier.verify().
    """
    error = AuthApiError("invalid JWT", HTTPStatus.UNAUTHORIZED, REJECTED_CODE)

    with pytest.raises(AuthenticationError) as raised:
        verifier_for(FakeSupabaseClient(error=error)).verify(ACCESS_TOKEN)

    assert raised.value.log_context == {
        "reason": RejectionReason.REJECTED_BY_SUPABASE,
        "status": HTTPStatus.UNAUTHORIZED,
        "code": REJECTED_CODE,
    }
    assert "invalid JWT" not in raised.value.public_message


def test_when_supabase_returns_no_user_then_authentication_fails():
    """when the auth API answers with nothing, the token is treated as invalid.

    Validates app.infrastructure.auth.supabase.SupabaseTokenVerifier.verify().
    """
    with pytest.raises(AuthenticationError) as raised:
        verifier_for(FakeSupabaseClient(response=None)).verify(ACCESS_TOKEN)

    assert raised.value.log_context == {"reason": RejectionReason.NO_USER}


@pytest.mark.parametrize("error", UNAVAILABLE_ERRORS)
def test_when_supabase_cannot_answer_then_the_service_is_reported_unavailable(error):
    """when Supabase fails, throttles or is unreachable, ExternalServiceError is raised.

    Validates app.infrastructure.auth.supabase.SupabaseTokenVerifier.verify().
    """
    with pytest.raises(ExternalServiceError) as raised:
        verifier_for(FakeSupabaseClient(error=error)).verify(ACCESS_TOKEN)

    assert raised.value.log_context == {
        "service": "supabase_auth",
        "error": type(error).__name__,
    }
    assert "supabase" not in raised.value.public_message.lower()
    assert SUPABASE_USER_EMAIL not in repr(raised.value.log_context)


@pytest.mark.parametrize(("handler", "expected_error"), REAL_CLIENT_OUTCOMES)
def test_when_the_real_client_meets_each_answer_then_the_verifier_classifies_it(
    handler: Callable[[httpx.Request], httpx.Response],
    expected_error: type[Exception] | None,
):
    """when the pinned supabase client gets each kind of answer, the mapping holds.

    Validates app.infrastructure.auth.supabase.SupabaseTokenVerifier.verify().
    """
    options = ClientOptions(
        auto_refresh_token=False,
        persist_session=False,
        httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    verifier = SupabaseTokenVerifier(
        create_client(PROJECT_URL, PROJECT_API_KEY, options)
    )

    if expected_error is None:
        assert verifier.verify(ACCESS_TOKEN).id == SUPABASE_USER_ID
        return
    with pytest.raises(expected_error):
        verifier.verify(ACCESS_TOKEN)


def test_when_built_from_settings_then_the_client_is_stateless_and_has_a_timeout(
    monkeypatch,
):
    """when from_settings runs, sessions are not refreshed or kept and calls time out.

    Validates app.infrastructure.auth.supabase.SupabaseTokenVerifier.from_settings().
    """
    captured: dict[str, object] = {}

    def capture_create_client(url, key, options):
        """Record the arguments instead of building a real client."""
        captured.update(url=url, key=key, options=options)
        return FakeSupabaseClient()

    monkeypatch.setattr(supabase_module, "create_client", capture_create_client)
    auth_settings = AuthSettings(
        supabase_url=PROJECT_URL,
        supabase_publishable_key=PROJECT_API_KEY,
        supabase_auth_timeout=AUTH_TIMEOUT_SECONDS,
    )

    verifier = SupabaseTokenVerifier.from_settings(auth_settings)

    options = captured["options"]
    assert isinstance(verifier, SupabaseTokenVerifier)
    assert (captured["url"], captured["key"]) == (PROJECT_URL, PROJECT_API_KEY)
    assert options.auto_refresh_token is False
    assert options.persist_session is False
    assert options.httpx_client.timeout == httpx.Timeout(AUTH_TIMEOUT_SECONDS)
