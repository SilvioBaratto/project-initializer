"""Login and access-token use cases of the token variant.

The service depends on ports only, so unit tests run it against in-memory fakes.
A wrong password, an unknown email and an inactive account carry one generic
public message, so the answer does not say which check failed; the specific
cause goes into the error's ``log_context``, which holds no email address.
"""

from app.application.dto.user import AccessTokenDTO
from app.domain.entities.authenticated_user import AuthenticatedUser
from app.domain.entities.user import User
from app.domain.exceptions import AuthenticationError
from app.domain.ports.credentials import AccessTokenIssuerPort, PasswordHasherPort
from app.domain.ports.user_repository import UserRepositoryPort

JWT_AUTH_METHOD = "jwt"
INVALID_LOGIN_MESSAGE = "Incorrect email or password"


class AuthService:
    """Logs accounts in and resolves their access tokens."""

    def __init__(
        self,
        users: UserRepositoryPort,
        hasher: PasswordHasherPort,
        tokens: AccessTokenIssuerPort,
    ) -> None:
        """Wire the service.

        Args:
            users: Account storage; only read here.
            hasher: Password verification.
            tokens: Access token signing and verification.
        """
        self._users = users
        self._hasher = hasher
        self._tokens = tokens

    def authenticate(self, email: str, password: str) -> AccessTokenDTO:
        """Check a login and issue an access token.

        The password is verified even when the account is missing or inactive,
        so every failure takes about as long as a wrong password does.

        Args:
            email: Login name of the account, in the form accounts are stored by.
            password: Plain-text candidate password.

        Returns:
            A signed access token for the account and the account's id.

        Raises:
            AuthenticationError: The account is unknown, has no matching
                password or is inactive. All three look the same to the caller.
        """
        user = self._users.get_by_email(email)
        password_matches = self._hasher.verify(
            password, user.password_hash if user else None
        )
        if user is None or not password_matches:
            raise _invalid_login("invalid_credentials")
        if not user.is_active:
            raise _invalid_login("inactive_account")
        return AccessTokenDTO(access_token=self._tokens.issue(user.id), user_id=user.id)

    def resolve_access_token(self, token: str) -> AuthenticatedUser:
        """Turn an access token into the principal it was issued to.

        Args:
            token: Encoded access token received from a client.

        Returns:
            The principal. The account is read on every call, so deactivating
            an account takes effect before its tokens expire.

        Raises:
            AuthenticationError: The token is invalid or expired, or its account
                no longer exists or is inactive.
        """
        user = self._active_user(self._tokens.subject_of(token))
        return AuthenticatedUser(
            id=user.id,
            auth_method=JWT_AUTH_METHOD,
            email=user.email,
            username=user.username,
        )

    def _active_user(self, user_id: str) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise AuthenticationError(log_context={"reason": "unknown_subject"})
        if not user.is_active:
            raise AuthenticationError(log_context={"reason": "inactive_account"})
        return user


def _invalid_login(reason: str) -> AuthenticationError:
    return AuthenticationError(INVALID_LOGIN_MESSAGE, log_context={"reason": reason})
