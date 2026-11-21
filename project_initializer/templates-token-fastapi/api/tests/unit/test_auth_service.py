"""Unit tests for the login and access-token use cases, run against in-memory fakes."""

from dataclasses import replace

import pytest

from app.application.dto.user import AccessTokenDTO
from app.application.services.auth_service import (
    INVALID_LOGIN_MESSAGE,
    JWT_AUTH_METHOD,
    AuthService,
)
from app.domain.exceptions import AuthenticationError
from tests.auth_fakes import (
    EMAIL,
    HASH_PREFIX,
    PASSWORD,
    FakePasswordHasher,
    FakeUserRepository,
    make_user,
)

pytestmark = pytest.mark.unit

TOKEN_PREFIX = "token-for-"


class FakeAccessTokenIssuer:
    """``AccessTokenIssuerPort`` with tokens that spell out their subject."""

    def __init__(self) -> None:
        self.issued_subjects: list[str] = []

    def issue(self, subject: str) -> str:
        """Record the subject and return a token naming it."""
        self.issued_subjects.append(subject)
        return f"{TOKEN_PREFIX}{subject}"

    def subject_of(self, token: str) -> str:
        """Return the subject of a token this fake issued, else refuse it."""
        if not token.startswith(TOKEN_PREFIX):
            raise AuthenticationError()
        return token.removeprefix(TOKEN_PREFIX)


@pytest.fixture
def users() -> FakeUserRepository:
    """Repository that already holds one active account."""
    return FakeUserRepository([make_user()])


@pytest.fixture
def hasher() -> FakePasswordHasher:
    """Hasher that records every verification."""
    return FakePasswordHasher()


@pytest.fixture
def tokens() -> FakeAccessTokenIssuer:
    """Issuer that records every subject it signs."""
    return FakeAccessTokenIssuer()


@pytest.fixture
def service(users, hasher, tokens) -> AuthService:
    """Service wired to the fakes."""
    return AuthService(users, hasher, tokens)


def test_when_credentials_are_right_then_authenticate_issues_a_token(service, tokens):
    """when the email and password match an active account, a token is issued.

    Validates app.application.services.auth_service.AuthService.authenticate().
    """
    issued = service.authenticate(EMAIL, PASSWORD)

    assert isinstance(issued, AccessTokenDTO)
    assert issued.access_token == f"{TOKEN_PREFIX}user-existing"
    assert issued.token_type == "bearer"
    assert tokens.issued_subjects == ["user-existing"]


def test_when_credentials_are_right_then_the_token_names_the_account_by_id(service):
    """when a login succeeds, the result carries the account id for the audit record.

    Validates app.application.services.auth_service.AuthService.authenticate().
    """
    issued = service.authenticate(EMAIL, PASSWORD)

    assert issued.user_id == "user-existing"


def test_when_the_token_dto_is_printed_then_the_token_is_hidden(service):
    """when an access token DTO is rendered as text, the token is not in it.

    Validates app.application.dto.user.AccessTokenDTO.
    """
    assert TOKEN_PREFIX not in repr(service.authenticate(EMAIL, PASSWORD))


def test_when_the_password_is_wrong_then_authenticate_raises_the_generic_error(
    service, tokens
):
    """when the password is wrong, a generic authentication error is raised.

    Validates app.application.services.auth_service.AuthService.authenticate().
    """
    with pytest.raises(AuthenticationError) as raised:
        service.authenticate(EMAIL, "not-the-password")

    assert raised.value.public_message == INVALID_LOGIN_MESSAGE
    assert tokens.issued_subjects == []


def test_when_the_email_is_unknown_then_the_password_is_still_verified(service, hasher):
    """when no account has the email, verify still runs, against a missing hash.

    That keeps the response time of an unknown email close to a wrong password.

    Validates app.application.services.auth_service.AuthService.authenticate().
    """
    with pytest.raises(AuthenticationError) as raised:
        service.authenticate("nobody@example.com", PASSWORD)

    assert raised.value.public_message == INVALID_LOGIN_MESSAGE
    assert hasher.verify_calls == [(PASSWORD, None)]


def test_when_the_account_is_inactive_then_it_is_treated_as_invalid_credentials(
    hasher, tokens
):
    """when the account is inactive, the answer is the same as for a wrong password.

    Validates app.application.services.auth_service.AuthService.authenticate().
    """
    users = FakeUserRepository([make_user(is_active=False)])
    service = AuthService(users, hasher, tokens)

    with pytest.raises(AuthenticationError) as raised:
        service.authenticate(EMAIL, PASSWORD)

    assert raised.value.public_message == INVALID_LOGIN_MESSAGE
    assert raised.value.log_context == {"reason": "inactive_account"}
    assert hasher.verify_calls == [(PASSWORD, f"{HASH_PREFIX}{PASSWORD}")]
    assert tokens.issued_subjects == []


def test_when_the_account_has_no_password_then_authenticate_refuses_it(hasher, tokens):
    """when the stored password hash is missing, login fails instead of crashing.

    Validates app.application.services.auth_service.AuthService.authenticate().
    """
    users = FakeUserRepository([make_user(password_hash=None)])
    service = AuthService(users, hasher, tokens)

    with pytest.raises(AuthenticationError):
        service.authenticate(EMAIL, PASSWORD)

    assert hasher.verify_calls == [(PASSWORD, None)]


def test_when_a_login_fails_then_the_log_context_holds_no_email(service):
    """when a login fails, the log context holds a reason and no email address.

    Validates app.application.services.auth_service.AuthService.authenticate().
    """
    with pytest.raises(AuthenticationError) as raised:
        service.authenticate(EMAIL, "not-the-password")

    assert raised.value.log_context == {"reason": "invalid_credentials"}
    assert EMAIL not in repr(raised.value.log_context)


def test_when_a_token_is_valid_then_resolve_returns_its_principal(service):
    """when a token names an active account, its principal is returned.

    Validates app.application.services.auth_service.AuthService.resolve_access_token().
    """
    principal = service.resolve_access_token(f"{TOKEN_PREFIX}user-existing")

    assert principal.id == "user-existing"
    assert principal.auth_method == JWT_AUTH_METHOD
    assert principal.email == EMAIL
    assert principal.username == "jane"
    assert principal.roles == ()


def test_when_the_token_is_invalid_then_resolve_raises_authentication_error(service):
    """when the issuer refuses the token, resolve raises AuthenticationError.

    Validates app.application.services.auth_service.AuthService.resolve_access_token().
    """
    with pytest.raises(AuthenticationError):
        service.resolve_access_token("forged-token")


def test_when_the_subject_has_no_account_then_resolve_raises_authentication_error(
    service,
):
    """when a valid token names an account that no longer exists, it is refused.

    Validates app.application.services.auth_service.AuthService.resolve_access_token().
    """
    with pytest.raises(AuthenticationError) as raised:
        service.resolve_access_token(f"{TOKEN_PREFIX}user-deleted")

    assert raised.value.log_context == {"reason": "unknown_subject"}


def test_when_the_account_was_deactivated_then_resolve_refuses_its_token(
    hasher, tokens
):
    """when a token's account is now inactive, the token stops working at once.

    Validates app.application.services.auth_service.AuthService.resolve_access_token().
    """
    inactive = make_user()
    users = FakeUserRepository([replace(inactive, is_active=False)])
    service = AuthService(users, hasher, tokens)

    with pytest.raises(AuthenticationError) as raised:
        service.resolve_access_token(f"{TOKEN_PREFIX}{inactive.id}")

    assert raised.value.log_context == {"reason": "inactive_account"}
