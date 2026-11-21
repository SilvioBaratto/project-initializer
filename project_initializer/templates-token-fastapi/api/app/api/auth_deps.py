"""Authentication dependencies of the token variant.

This module is the auth seam: it replaces the base module and exports the same
``get_current_user`` and ``CurrentUser``, so routes and the role guard never
learn which variant is running. Two independent modes live side by side:

- Static token: ``get_current_user`` accepts the shared ``AUTH_TOKEN`` as the
  bearer token. It guards item writes, chat and ``/auth/me``.
- JWT: ``get_current_jwt_user`` accepts the access token that ``/auth/token``
  issues after a login. It guards ``/auth/me/jwt``.

The two never accept each other's tokens.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.api.bearer import MAX_BEARER_TOKEN_LENGTH, BearerToken
from app.application.services.auth_service import AuthService
from app.application.services.registration import RegistrationService
from app.domain.entities.authenticated_user import AuthenticatedUser
from app.domain.exceptions import AuthenticationError, ExternalServiceError
from app.domain.ports.credentials import AccessTokenIssuerPort, PasswordHasherPort
from app.domain.ports.token_verifier import TokenVerifierPort
from app.infrastructure.auth.static_token import StaticTokenVerifier
from app.infrastructure.database import get_db
from app.infrastructure.repositories.user import SqlAlchemyUserRepository
from app.infrastructure.security import BcryptPasswordHasher, JwtAccessTokenIssuer
from app.infrastructure.settings import settings
from app.infrastructure.unit_of_work import SqlAlchemyUnitOfWork

LOGIN_UNAVAILABLE_MESSAGE = "Login is not available"

# Relative on purpose: Swagger UI resolves it against the docs page, so it
# lands on the versioned prefix wherever the API is mounted.
TOKEN_URL = f"{settings.api_v1_str.lstrip('/')}/auth/token"

# ``auto_error=False`` so a missing header becomes our AuthenticationError and
# therefore the standard error envelope instead of FastAPI's own 401 body.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=TOKEN_URL, auto_error=False)


@lru_cache(maxsize=1)
def get_token_verifier() -> TokenVerifierPort:
    """Return the process-wide verifier of the static token.

    Cached because the configured secret never changes while the process runs,
    and so tests can replace the whole dependency.

    Returns:
        A verifier bound to ``AUTH_TOKEN``.
    """
    return StaticTokenVerifier(settings.auth_token)


def get_current_user(
    token: BearerToken,
    verifier: Annotated[TokenVerifierPort, Depends(get_token_verifier)],
) -> AuthenticatedUser:
    """Resolve the caller from the static bearer token.

    It is a plain ``def`` because the check is CPU-only and touches no I/O.

    Args:
        token: Bearer token of the request.
        verifier: Verifier of the static token.

    Returns:
        The static-token principal.

    Raises:
        AuthenticationError: The header is missing or unusable, or the token is
            not the configured one.
    """
    return verifier.verify(token)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


@lru_cache(maxsize=1)
def get_password_hasher() -> PasswordHasherPort:
    """Return the process-wide password hasher.

    Returns:
        A bcrypt hasher at the default cost factor.
    """
    return BcryptPasswordHasher()


@lru_cache(maxsize=1)
def get_access_token_issuer() -> AccessTokenIssuerPort:
    """Return the process-wide JWT issuer.

    Returns:
        An issuer configured from the settings.

    Raises:
        ExternalServiceError: ``JWT_SECRET_KEY`` is empty, so signing tokens is
            switched off and the request is answered 503 before any credential
            is checked. Nothing is cached in that case, so fixing the setting
            takes effect on the next request.
    """
    try:
        return JwtAccessTokenIssuer.from_settings(settings)
    except ValueError as error:
        raise ExternalServiceError(
            LOGIN_UNAVAILABLE_MESSAGE,
            log_context={"reason": "jwt_secret_key_not_configured"},
        ) from error


def get_registration_service(
    session: Annotated[Session, Depends(get_db)],
    hasher: Annotated[PasswordHasherPort, Depends(get_password_hasher)],
) -> RegistrationService:
    """Build the registration service for one request.

    The repository and the unit of work share the request's session, so the
    service's commit covers exactly the writes the repository staged. It takes
    no token issuer, so registration works while JWT signing is not configured.

    Args:
        session: Database session of the request.
        hasher: Password hasher.

    Returns:
        A registration service bound to that session.
    """
    return RegistrationService(
        SqlAlchemyUserRepository(session), SqlAlchemyUnitOfWork(session), hasher
    )


RegistrationServiceDep = Annotated[
    RegistrationService, Depends(get_registration_service)
]


def get_auth_service(
    session: Annotated[Session, Depends(get_db)],
    hasher: Annotated[PasswordHasherPort, Depends(get_password_hasher)],
    tokens: Annotated[AccessTokenIssuerPort, Depends(get_access_token_issuer)],
) -> AuthService:
    """Build the login and token service for one request.

    Args:
        session: Database session of the request; used for reads only.
        hasher: Password hasher.
        tokens: JWT issuer.

    Returns:
        An account service bound to that session.
    """
    return AuthService(SqlAlchemyUserRepository(session), hasher, tokens)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def require_oauth2_token(token: Annotated[str | None, Depends(oauth2_scheme)]) -> str:
    """Return the bearer token of a request to a JWT-guarded route.

    Args:
        token: Token read by the OAuth2 scheme, or None when the header is
            missing or does not use the ``Bearer`` scheme.

    Returns:
        The raw token.

    Raises:
        AuthenticationError: The token is missing, empty or longer than
            ``MAX_BEARER_TOKEN_LENGTH``.
    """
    if not token or len(token) > MAX_BEARER_TOKEN_LENGTH:
        raise AuthenticationError(log_context={"reason": "unusable_bearer_header"})
    return token


def get_current_jwt_user(
    token: Annotated[str, Depends(require_oauth2_token)],
    service: AuthServiceDep,
) -> AuthenticatedUser:
    """Resolve the caller from a JWT access token.

    Args:
        token: Bearer token of the request.
        service: Account service that verifies the token and reads the account.

    Returns:
        The principal of the account the token was issued to.

    Raises:
        AuthenticationError: The token is invalid or expired, or its account is
            gone or inactive.
    """
    return service.resolve_access_token(token)


JwtUser = Annotated[AuthenticatedUser, Depends(get_current_jwt_user)]
