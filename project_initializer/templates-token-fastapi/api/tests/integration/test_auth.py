"""Integration tests of the static-token authentication of the token variant.

They use the real ``get_current_user`` and the real static-token verifier, with
the secret pinned in ``tests/auth_test_env.py``. The shared item and chat tests
replace ``get_current_user`` instead, so this file is where the credential
checks themselves are covered.
"""

import logging
from http import HTTPStatus

import pytest
from pydantic import SecretStr

from app.api.auth_deps import get_token_verifier
from app.api.bearer import MAX_BEARER_TOKEN_LENGTH
from app.api.deps import get_chat_model
from app.infrastructure.auth.static_token import (
    STATIC_TOKEN_AUTH_METHOD,
    STATIC_TOKEN_USER_ID,
    StaticTokenVerifier,
)
from app.main import app
from tests.auth_assertions import assert_authentication_failure
from tests.auth_test_env import TEST_AUTH_TOKEN
from tests.fakes import FakeChatModel

pytestmark = pytest.mark.integration

AUDIT_LOGGER = "app.audit"
VALID_AUTHORIZATION = {"Authorization": f"Bearer {TEST_AUTH_TOKEN}"}
ITEM_BODY = {"name": "Widget", "price": 1.0}
UNKNOWN_ITEM_ID = "00000000-0000-4000-8000-000000000000"
CHAT_BODY = {"user_question": "What can this API do?"}
CHAT_ROUTES = ["/chat/", "/chat/stream"]

NON_MATCHING_PROBE_TOKENS = [
    pytest.param("wrong-token-value", id="wrong"),
    pytest.param("", id="empty"),
    pytest.param("é" * 16, id="non-ascii"),
    pytest.param(TEST_AUTH_TOKEN.upper(), id="different-case"),
    pytest.param(f" {TEST_AUTH_TOKEN}", id="leading-space"),
    pytest.param("t" * MAX_BEARER_TOKEN_LENGTH, id="maximum-length"),
]
REJECTED_AUTHORIZATION_HEADERS = [
    pytest.param(None, id="header-missing"),
    pytest.param("Basic dXNlcjpwYXNz", id="other-scheme"),
    pytest.param(f"Token {TEST_AUTH_TOKEN}", id="token-scheme"),
    pytest.param(TEST_AUTH_TOKEN, id="no-scheme"),
    pytest.param("Bearer", id="scheme-only"),
    pytest.param("Bearer ", id="empty-token"),
    pytest.param("Bearer wrong-token-value", id="wrong-token"),
    pytest.param(f"Bearer {TEST_AUTH_TOKEN.upper()}", id="token-in-other-case"),
    pytest.param(f"Bearer {TEST_AUTH_TOKEN}x", id="token-with-a-suffix"),
    pytest.param("Bearer " + "t" * (MAX_BEARER_TOKEN_LENGTH + 1), id="token-too-long"),
    pytest.param("Bearer é-token".encode(), id="non-ascii-token"),
]


@pytest.fixture
def me_url(api_prefix: str) -> str:
    """URL of the static-token current-user route."""
    return f"{api_prefix}/auth/me"


@pytest.fixture
def validate_url(api_prefix: str) -> str:
    """URL of the token validity probe."""
    return f"{api_prefix}/auth/validate"


@pytest.fixture
def items_url(api_prefix: str) -> str:
    """Collection URL of the item routes."""
    return f"{api_prefix}/items"


def test_when_validate_gets_the_configured_token_then_authenticated_is_true(
    client, validate_url
):
    """when /auth/validate gets the configured token, authenticated is true.

    Validates app.api.v1.endpoints.auth.validate_token().
    """
    response = client.post(validate_url, json={"token": TEST_AUTH_TOKEN})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["authenticated"] is True


@pytest.mark.parametrize("token", NON_MATCHING_PROBE_TOKENS)
def test_when_validate_gets_another_token_then_200_with_authenticated_false(
    client, validate_url, token
):
    """when /auth/validate gets any other token, the answer is 200 with false.

    LOCKED CONTRACT: the route is a validity probe, not a guard. An invalid token
    is a successful answer to "is this token valid?"; 401 is reserved for the
    routes that refuse access. Non-ASCII input must not raise inside the
    constant-time comparison.

    Validates app.api.v1.endpoints.auth.validate_token().
    """
    response = client.post(validate_url, json={"token": token})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["authenticated"] is False


def test_when_validate_rejects_a_token_then_one_warning_logs_only_the_reason(
    client, validate_url, caplog
):
    """when /auth/validate rejects a token, one warning holds its reason, not the token.

    The route answers 200 for a wrong token, so the log is the only place a
    burst of guesses shows up.

    Validates app.api.v1.endpoints.auth.validate_token().
    """
    presented = "presented-guess-token-value"

    with caplog.at_level(logging.WARNING):
        client.post(validate_url, json={"token": presented})

    rejections = [
        record
        for record in caplog.records
        if record.getMessage() == "auth.validate_rejected"
    ]
    assert [record.context for record in rejections] == [
        {"reason": "static_token_mismatch"}
    ]
    assert presented not in caplog.text


def test_when_validate_gets_an_oversized_token_then_422_without_echoing_it(
    client, validate_url
):
    """when the probed token is over the bearer limit, validation answers 422.

    Validates app.api.schemas.auth.AuthValidationRequest.
    """
    oversized = "t" * (MAX_BEARER_TOKEN_LENGTH + 1)

    response = client.post(validate_url, json={"token": oversized})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert oversized not in response.text


def test_when_validate_has_no_token_field_then_422(client, validate_url):
    """when the body lacks the token field, validation answers 422.

    Validates app.api.schemas.auth.AuthValidationRequest.
    """
    assert client.post(validate_url, json={}).status_code == (
        HTTPStatus.UNPROCESSABLE_ENTITY
    )


def test_when_no_static_token_is_configured_then_validate_accepts_nothing(
    client, validate_url
):
    """when AUTH_TOKEN is empty, even an empty probed token is not authenticated.

    Validates app.infrastructure.auth.static_token.tokens_match().
    """
    app.dependency_overrides[get_token_verifier] = lambda: StaticTokenVerifier(
        SecretStr("")
    )

    response = client.post(validate_url, json={"token": ""})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["authenticated"] is False


def test_when_me_gets_the_configured_token_then_the_static_principal_is_returned(
    client, me_url
):
    """when /auth/me gets the configured token, it describes the static-token principal.

    Validates app.api.v1.endpoints.auth.read_current_user().
    """
    response = client.get(me_url, headers=VALID_AUTHORIZATION)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "id": STATIC_TOKEN_USER_ID,
        "email": None,
        "username": STATIC_TOKEN_USER_ID,
        "roles": [],
        "auth_method": STATIC_TOKEN_AUTH_METHOD,
    }


@pytest.mark.parametrize("authorization", REJECTED_AUTHORIZATION_HEADERS)
def test_when_the_authorization_header_is_unusable_then_me_answers_401(
    client, me_url, authorization
):
    """when the header is unusable, /auth/me answers 401.

    Validates app.api.auth_deps.get_current_user().
    """
    headers = {} if authorization is None else {"Authorization": authorization}

    assert_authentication_failure(client.get(me_url, headers=headers))


@pytest.mark.parametrize("authorization", REJECTED_AUTHORIZATION_HEADERS)
def test_when_the_authorization_header_is_unusable_then_item_writes_answer_401(
    client, items_url, authorization
):
    """when the header is unusable, create, update and delete all answer 401.

    Validates app.api.auth_deps.get_current_user().
    """
    headers = {} if authorization is None else {"Authorization": authorization}

    responses = [
        client.post(items_url, json=ITEM_BODY, headers=headers),
        client.put(
            f"{items_url}/{UNKNOWN_ITEM_ID}", json={"name": "x"}, headers=headers
        ),
        client.delete(f"{items_url}/{UNKNOWN_ITEM_ID}", headers=headers),
    ]

    for response in responses:
        assert_authentication_failure(response)


def test_when_a_write_is_rejected_then_nothing_is_stored_or_audited(
    client, items_url, caplog
):
    """when an unauthenticated create is refused, nothing is stored or audited.

    Validates app.api.v1.endpoints.items.create_item().
    """
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        rejected = client.post(
            items_url, json=ITEM_BODY, headers={"Authorization": "Bearer x"}
        )

    assert_authentication_failure(rejected)
    assert client.get(items_url).json()["total"] == 0
    assert [r for r in caplog.records if r.name == AUDIT_LOGGER] == []


def test_when_the_caller_is_unknown_then_authentication_comes_before_body_validation(
    client, items_url
):
    """when an unauthenticated caller sends an invalid body, the answer is 401, not 422.

    Validates app.api.v1.endpoints.items.create_item().
    """
    response = client.post(items_url, json={"name": ""})

    assert_authentication_failure(response)
    assert "details" not in response.json()["error"]


def test_when_the_configured_token_is_sent_then_item_writes_succeed_and_are_audited(
    client, items_url, caplog
):
    """when the configured token is sent, a create succeeds and is audited.

    Validates app.api.v1.endpoints.items.create_item().
    """
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        created = client.post(items_url, json=ITEM_BODY, headers=VALID_AUTHORIZATION)

    assert created.status_code == HTTPStatus.CREATED
    audit_records = [r for r in caplog.records if r.name == AUDIT_LOGGER]
    assert [(r.action, r.actor_id) for r in audit_records] == [
        ("item.create", STATIC_TOKEN_USER_ID)
    ]


def test_when_no_credentials_are_sent_then_item_reads_stay_public(client, items_url):
    """when a request carries no credentials, listing and fetching items still work.

    Validates app.api.v1.endpoints.items.list_items().
    """
    assert client.get(items_url).status_code == HTTPStatus.OK
    assert client.get(f"{items_url}/{UNKNOWN_ITEM_ID}").status_code == (
        HTTPStatus.NOT_FOUND
    )


@pytest.mark.parametrize("route", CHAT_ROUTES)
def test_when_a_chat_route_has_no_credentials_then_it_answers_401(
    client, api_prefix, route
):
    """when no token is sent, the chat routes refuse the request before any LLM call.

    Validates app.api.v1.endpoints.chatbot.chat().
    """
    app.dependency_overrides[get_chat_model] = lambda: FakeChatModel()

    response = client.post(f"{api_prefix}{route}", json=CHAT_BODY)

    assert_authentication_failure(response)


def test_when_a_chat_route_gets_the_configured_token_then_it_answers(
    client, api_prefix
):
    """when the configured token is sent, the chat route answers from the model.

    Validates app.api.v1.endpoints.chatbot.chat().
    """
    app.dependency_overrides[get_chat_model] = lambda: FakeChatModel(answer="hello")

    response = client.post(
        f"{api_prefix}/chat/", json=CHAT_BODY, headers=VALID_AUTHORIZATION
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"answer": "hello"}


def test_when_authentication_fails_then_the_token_is_not_logged(client, me_url, caplog):
    """when a wrong token is rejected, no log record contains it.

    Validates app.api.auth_deps.get_current_user().
    """
    presented = "presented-wrong-token-value"

    with caplog.at_level(logging.DEBUG):
        client.get(me_url, headers={"Authorization": f"Bearer {presented}"})

    assert presented not in caplog.text


def test_when_the_schema_is_read_then_static_routes_document_a_bearer_scheme_and_401(
    openapi_schema, api_prefix
):
    """when OpenAPI is generated, /auth/me and /auth/validate carry their contracts.

    Validates app.api.v1.endpoints.auth.read_current_user().
    """
    paths = openapi_schema["paths"]
    me = paths[f"{api_prefix}/auth/me"]["get"]
    validate = paths[f"{api_prefix}/auth/validate"]["post"]

    assert me["security"] == [{"HTTPBearer": []}]
    assert me["responses"]["401"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/ErrorEnvelope")
    assert "security" not in validate
    assert "200" in validate["responses"]
