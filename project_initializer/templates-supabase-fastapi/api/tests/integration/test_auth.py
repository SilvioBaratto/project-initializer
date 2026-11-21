"""Integration tests of the Supabase variant's authentication.

Each test swaps the process-wide verifier for one that wraps a fake Supabase
client, so the real dependency chain (bearer extraction, verifier, error
handlers) runs without a network or a Supabase project.
"""

import logging
from collections.abc import Callable, Iterator
from http import HTTPStatus

import httpx
import pytest
from fastapi.testclient import TestClient
from supabase import AuthApiError, AuthRetryableError

from app.api.auth_deps import get_token_verifier
from app.domain.exceptions import AuthenticationError
from app.infrastructure.auth.supabase import SupabaseTokenVerifier
from app.main import app
from tests import http_helpers
from tests.http_helpers import HANDLER_LOGGER, bearer
from tests.supabase_fakes import (
    ACCESS_TOKEN,
    SUPABASE_USER_EMAIL,
    SUPABASE_USER_ID,
    FakeSupabaseClient,
    make_malformed_user_error,
    make_user_response,
)

pytestmark = pytest.mark.integration

# Binding the shared fixture to a name of this module is what makes pytest see it;
# a plain import would turn every test parameter into a redefined unused import.
me_url = http_helpers.me_url

AUTHENTICATION_CODE = "AUTHENTICATION_ERROR"
UNAVAILABLE_CODE = "SERVICE_UNAVAILABLE"
REJECTION = AuthApiError("invalid JWT", HTTPStatus.UNAUTHORIZED, "bad_jwt")
BAD_GATEWAY_STATUS = 502
OUTAGES = [
    pytest.param(
        AuthRetryableError("bad gateway", BAD_GATEWAY_STATUS),
        id="retryable-gateway-error",
    ),
    pytest.param(httpx.ConnectError("refused"), id="connection-refused"),
    pytest.param(httpx.ReadTimeout("slow"), id="timeout"),
]
PROTECTED_REQUESTS = [
    pytest.param("post", "/items", {"json": {"name": "Widget"}}, id="item-write"),
    pytest.param("get", "/auth/me", {}, id="current-user"),
]
ITEM_BODY = {"name": "Widget", "price": 1.0}


@pytest.fixture
def use_supabase_client(client: TestClient) -> Callable[..., TestClient]:
    """Factory of a client whose token checks go to a fake Supabase client."""

    def use(fake: FakeSupabaseClient) -> TestClient:
        """Route the application's token checks to ``fake``."""
        verifier = SupabaseTokenVerifier(fake)
        app.dependency_overrides[get_token_verifier] = lambda: verifier
        return client

    return use


def test_when_a_known_token_is_sent_then_me_returns_the_supabase_identity(
    use_supabase_client, me_url
):
    """when Supabase accepts the bearer token, /auth/me answers with the principal.

    Validates app.api.auth_deps.get_current_user().
    """
    fake = FakeSupabaseClient(response=make_user_response())

    response = use_supabase_client(fake).get(me_url, headers=bearer(ACCESS_TOKEN))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "id": SUPABASE_USER_ID,
        "email": SUPABASE_USER_EMAIL,
        "username": None,
        "roles": ["authenticated"],
        "auth_method": "supabase",
    }
    assert fake.auth.tokens == [ACCESS_TOKEN]


def test_when_the_user_has_only_a_phone_then_me_answers_200_without_an_email(
    use_supabase_client, me_url
):
    """when the Supabase user has no email, /auth/me answers 200 with a null email.

    Validates app.api.auth_deps.get_current_user().
    """
    fake = FakeSupabaseClient(response=make_user_response(email=None, phone="+39333"))

    response = use_supabase_client(fake).get(me_url, headers=bearer(ACCESS_TOKEN))

    assert response.status_code == HTTPStatus.OK
    assert response.json()["email"] is None


def test_when_supabase_rejects_the_token_then_401_with_the_generic_envelope(
    use_supabase_client, me_url
):
    """when Supabase answers 401, the caller gets the generic envelope and a challenge.

    Validates app.api.auth_deps.get_current_user().
    """
    client = use_supabase_client(FakeSupabaseClient(error=REJECTION))

    response = client.get(me_url, headers=bearer(ACCESS_TOKEN))

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.headers["WWW-Authenticate"] == "Bearer"
    error = response.json()["error"]
    assert error["code"] == AUTHENTICATION_CODE
    assert error["message"] == AuthenticationError.default_message
    assert "invalid JWT" not in response.text


def test_when_supabase_rejects_the_token_then_the_log_has_the_reason_but_no_token(
    use_supabase_client, me_url, caplog
):
    """when a token is rejected, the log carries the reason code and never the token.

    Validates app.api.auth_deps.get_current_user().
    """
    client = use_supabase_client(FakeSupabaseClient(error=REJECTION))

    with caplog.at_level(logging.WARNING, logger=HANDLER_LOGGER):
        client.get(me_url, headers=bearer(ACCESS_TOKEN))

    (record,) = [r for r in caplog.records if r.name == HANDLER_LOGGER]
    assert record.context["reason"] == "rejected_by_supabase"
    assert ACCESS_TOKEN not in caplog.text


@pytest.mark.parametrize("outage", OUTAGES)
def test_when_supabase_is_unavailable_then_503_with_retry_after(
    use_supabase_client, me_url, outage
):
    """when Supabase cannot be reached, the answer is 503 with Retry-After, not 401.

    Validates app.api.auth_deps.get_current_user().
    """
    client = use_supabase_client(FakeSupabaseClient(error=outage))

    response = client.get(me_url, headers=bearer(ACCESS_TOKEN))

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["error"]["code"] == UNAVAILABLE_CODE
    assert "Retry-After" in response.headers
    assert "supabase" not in response.text.lower()


@pytest.mark.parametrize("outage", OUTAGES)
def test_when_supabase_is_unavailable_then_the_log_names_the_service_and_error_class(
    use_supabase_client, me_url, caplog, outage
):
    """when the lookup fails, the log carries the service and class, not the message.

    Validates app.api.auth_deps.get_current_user().
    """
    client = use_supabase_client(FakeSupabaseClient(error=outage))

    with caplog.at_level(logging.ERROR, logger=HANDLER_LOGGER):
        client.get(me_url, headers=bearer(ACCESS_TOKEN))

    (record,) = [r for r in caplog.records if r.name == HANDLER_LOGGER]
    assert record.context == {
        "service": "supabase_auth",
        "error": type(outage).__name__,
    }
    assert ACCESS_TOKEN not in caplog.text


def test_when_supabase_answers_200_with_something_else_then_503_and_no_email_is_logged(
    use_supabase_client, me_url, caplog
):
    """when the 200 body is not a user, the caller sees 503 and the log holds no input.

    Validates app.api.auth_deps.get_current_user().
    """
    client = use_supabase_client(FakeSupabaseClient(error=make_malformed_user_error()))

    with caplog.at_level(logging.ERROR, logger=HANDLER_LOGGER):
        response = client.get(me_url, headers=bearer(ACCESS_TOKEN))

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["error"]["code"] == UNAVAILABLE_CODE
    (record,) = [r for r in caplog.records if r.name == HANDLER_LOGGER]
    assert record.context == {"service": "supabase_auth", "error": "ValidationError"}
    assert SUPABASE_USER_EMAIL not in caplog.text


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
    assert response.json()["error"]["code"] == AUTHENTICATION_CODE


def test_when_a_known_token_creates_an_item_then_201(use_supabase_client, api_prefix):
    """when Supabase accepts the token, a protected item write succeeds.

    Validates app.api.auth_deps.CurrentUser.
    """
    client = use_supabase_client(FakeSupabaseClient(response=make_user_response()))

    response = client.post(
        f"{api_prefix}/items", json=ITEM_BODY, headers=bearer(ACCESS_TOKEN)
    )

    assert response.status_code == HTTPStatus.CREATED


def test_when_the_token_is_rejected_then_an_item_write_is_401(
    use_supabase_client, api_prefix
):
    """when Supabase rejects the token, a protected item write answers 401.

    Validates app.api.auth_deps.CurrentUser.
    """
    client = use_supabase_client(FakeSupabaseClient(error=REJECTION))

    response = client.post(
        f"{api_prefix}/items", json=ITEM_BODY, headers=bearer(ACCESS_TOKEN)
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

    assert isinstance(first, SupabaseTokenVerifier)
    assert get_token_verifier() is first
