"""Integration tests for ``/auth/me`` and the guards built on the current user.

They replace ``get_current_user``, so they hold in every auth variant. How a
variant resolves real credentials is tested in its own ``test_auth.py``.
"""

from http import HTTPStatus
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.auth_deps import get_current_user
from app.api.authorization import require_roles
from app.api.bearer import MAX_BEARER_TOKEN_LENGTH, BearerToken
from app.api.handlers import setup_exception_handlers
from app.domain.entities.authenticated_user import AuthenticatedUser
from app.main import app
from tests.fakes import TEST_USER

pytestmark = pytest.mark.integration

ME_FIELDS = {"id", "email", "username", "roles", "auth_method"}
ACCESS_TOKEN = "token-value-123"
REJECTED_AUTHORIZATION_HEADERS = [
    pytest.param(None, id="header-missing"),
    pytest.param("Basic dXNlcjpwYXNz", id="other-scheme"),
    pytest.param("Bearer", id="no-token"),
    pytest.param(
        f"Bearer {'t' * (MAX_BEARER_TOKEN_LENGTH + 1)}", id="token-over-the-cap"
    ),
]


def build_probe_client(user: AuthenticatedUser, *roles: str) -> TestClient:
    """Client for a tiny app whose ``/guarded`` route needs one of ``roles``.

    The same app also serves ``/token``, which echoes the bearer token, so the
    two shared guards are exercised through real routing and real handlers.
    """
    application = FastAPI()
    setup_exception_handlers(application)
    application.dependency_overrides[get_current_user] = lambda: user

    @application.get("/guarded")
    def guarded(
        principal: Annotated[AuthenticatedUser, Depends(require_roles(*roles))],
    ) -> dict[str, str]:
        """Return the id of the principal the guard admitted."""
        return {"id": principal.id}

    @application.get("/token")
    def echo_token(token: BearerToken) -> dict[str, str]:
        """Return the bearer token the dependency extracted."""
        return {"token": token}

    return TestClient(application)


def user_with_roles(*roles: str) -> AuthenticatedUser:
    """A principal that holds exactly ``roles``."""
    return AuthenticatedUser(id="role-holder", auth_method="test", roles=roles)


@pytest.fixture
def me_url(api_prefix: str) -> str:
    """URL of the current-user route."""
    return f"{api_prefix}/auth/me"


def test_when_a_principal_is_resolved_then_me_lists_its_identity(
    authenticated_client, me_url
):
    """when the caller is authenticated, /auth/me returns the principal's claims.

    Validates app.api.v1.endpoints.auth.read_current_user().
    """
    response = authenticated_client.get(me_url)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "id": TEST_USER.id,
        "email": TEST_USER.email,
        "username": TEST_USER.username,
        "roles": list(TEST_USER.roles),
        "auth_method": TEST_USER.auth_method,
    }


def test_when_the_principal_has_no_profile_then_me_leaves_it_empty(
    authenticated_client, me_url
):
    """when the principal has no email, username or roles, /auth/me shows nulls and [].

    Validates app.api.v1.endpoints.auth.read_current_user().
    """
    service_account = AuthenticatedUser(
        id="service-account", auth_method="static_token"
    )
    app.dependency_overrides[get_current_user] = lambda: service_account

    body = authenticated_client.get(me_url).json()

    assert (body["email"], body["username"], body["roles"]) == (None, None, [])


def test_when_me_is_answered_then_only_identity_fields_are_exposed(
    authenticated_client, me_url
):
    """when /auth/me answers, the body holds the five identity fields and nothing else.

    The principal is converted field by field, so no credential can leak
    through an extra attribute.

    Validates app.api.schemas.user.CurrentUserResponse.
    """
    assert set(authenticated_client.get(me_url).json()) == ME_FIELDS


def test_when_no_principal_is_resolved_then_me_answers_401_with_a_challenge(
    unauthenticated_client, me_url
):
    """when credentials are missing, /auth/me answers 401 with the bearer challenge.

    Validates app.api.v1.endpoints.auth.read_current_user().
    """
    response = unauthenticated_client.get(me_url)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"]["code"] == "AUTHENTICATION_ERROR"
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert set(response.json()) == {"error"}


def test_when_the_schema_is_read_then_me_documents_its_response_and_the_401(
    openapi_schema, me_url
):
    """when OpenAPI is generated, /auth/me carries a summary and a 401 envelope.

    Validates app.api.v1.endpoints.auth.read_current_user().
    """
    operation = openapi_schema["paths"][me_url]["get"]
    unauthorized = operation["responses"]["401"]["content"]["application/json"]

    assert operation["summary"] == "Get the current user"
    assert unauthorized["schema"]["$ref"].endswith("/ErrorEnvelope")


def test_when_the_caller_holds_the_required_role_then_the_guard_admits_it():
    """when the principal has the role, the guarded route answers 200.

    Validates app.api.authorization.require_roles().
    """
    client = build_probe_client(user_with_roles("admin"), "admin")

    response = client.get("/guarded")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"id": "role-holder"}


def test_when_the_caller_holds_any_one_of_the_roles_then_the_guard_admits_it():
    """when the principal has one of several accepted roles, it is admitted.

    Validates app.api.authorization.require_roles().
    """
    client = build_probe_client(user_with_roles("editor"), "admin", "editor")

    assert client.get("/guarded").status_code == HTTPStatus.OK


@pytest.mark.parametrize(
    "roles",
    [
        pytest.param(("viewer",), id="other-role"),
        pytest.param((), id="no-roles"),
        pytest.param(("Admin",), id="role-name-differs-in-case"),
    ],
)
def test_when_the_caller_lacks_the_role_then_403_without_naming_the_required_role(
    roles,
):
    """when the principal lacks the role, the answer is 403 and the policy stays hidden.

    Validates app.api.authorization.require_roles().
    """
    client = build_probe_client(user_with_roles(*roles), "admin")

    response = client.get("/guarded")

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["error"]["code"] == "AUTHORIZATION_ERROR"
    assert "admin" not in response.text.lower()


def test_when_no_role_is_given_then_the_guard_cannot_be_built():
    """when require_roles gets no roles, it fails at definition time, not per request.

    Validates app.api.authorization.require_roles().
    """
    with pytest.raises(ValueError, match="at least one role"):
        require_roles()


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
def test_when_a_bearer_token_is_sent_then_it_is_extracted_whatever_the_scheme_case(
    scheme,
):
    """when the Authorization header uses the Bearer scheme, the token is extracted.

    Validates app.api.bearer.require_bearer_token().
    """
    client = build_probe_client(user_with_roles("admin"), "admin")

    response = client.get(
        "/token", headers={"Authorization": f"{scheme} {ACCESS_TOKEN}"}
    )

    assert response.json() == {"token": ACCESS_TOKEN}


def test_when_token_has_the_maximum_length_then_it_is_accepted():
    """when the token is exactly the length cap, it is extracted.

    Validates app.api.bearer.require_bearer_token().
    """
    client = build_probe_client(user_with_roles("admin"), "admin")
    token = "t" * MAX_BEARER_TOKEN_LENGTH

    response = client.get("/token", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize("authorization", REJECTED_AUTHORIZATION_HEADERS)
def test_when_the_authorization_header_is_unusable_then_401_with_the_envelope(
    authorization,
):
    """when the header is missing, not Bearer, empty or oversized, the answer is 401.

    Validates app.api.bearer.require_bearer_token().
    """
    client = build_probe_client(user_with_roles("admin"), "admin")
    headers: dict[str, Any] = (
        {} if authorization is None else {"Authorization": authorization}
    )

    response = client.get("/token", headers=headers)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["error"]["code"] == "AUTHENTICATION_ERROR"
    assert response.headers["WWW-Authenticate"] == "Bearer"
