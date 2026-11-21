"""Authentication routes of the token variant.

Two modes live side by side and guard different routes.

Static shared secret
    Set ``AUTH_TOKEN``. Clients send ``Authorization: Bearer <AUTH_TOKEN>``.
    ``POST /auth/validate`` tells whether a token is the configured one, and the
    static guard protects ``GET /auth/me``, item writes and chat. It suits
    service-to-service calls, where one shared secret is enough.

JWT login
    Set ``JWT_SECRET_KEY`` (plus ``JWT_ALGORITHM`` and
    ``ACCESS_TOKEN_EXPIRE_MINUTES`` if the defaults do not fit).

    1. ``POST /auth/register`` creates an account.
    2. ``POST /auth/token`` (OAuth2 form: ``username=<email>&password=...``)
       returns a signed access token.
    3. ``GET /auth/me/jwt`` with ``Authorization: Bearer <access_token>``
       returns the account. The token is verified and the account is read from
       the database on every call, so a deactivated account loses access at once.

    It suits user-facing APIs that need individual identity and expiring sessions.
    While ``JWT_SECRET_KEY`` is empty, registration still works and the two
    routes that sign or verify a token answer 503.

``/auth/validate`` is a probe, not a guard: an invalid token is a successful
answer to "is this token valid?", so it returns HTTP 200 with
``authenticated=false``. 401 is reserved for guarded routes that refuse access.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Response, status

from app.api.auth_deps import (
    AuthServiceDep,
    CurrentUser,
    JwtUser,
    RegistrationServiceDep,
    get_token_verifier,
)
from app.api.errors import AUTHENTICATED_ROUTE_ERRORS, error_responses
from app.api.schemas.auth import (
    AuthValidationRequest,
    AuthValidationResponse,
    LoginForm,
    RegistrationRequest,
    TokenResponse,
)
from app.api.schemas.user import CurrentUserResponse, UserPublic
from app.application.commands.user import RegisterUserCommand
from app.application.services.auth_service import INVALID_LOGIN_MESSAGE
from app.application.services.registration import (
    REGISTRATION_CONFLICT_MESSAGE,
)
from app.domain.exceptions import AuthenticationError
from app.domain.ports.token_verifier import TokenVerifierPort
from app.infrastructure.audit import write_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

AUDIT_USER_REGISTER = "user.register"
AUDIT_USER_LOGIN = "user.login"

VALIDATION_ACCEPTED_MESSAGE = "Authentication successful"
VALIDATION_REJECTED_MESSAGE = "Invalid token"
# RFC 6749 section 5.1: a token response must never be stored by a cache.
TOKEN_RESPONSE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache"}

VALIDATE_ERRORS = error_responses(status.HTTP_422_UNPROCESSABLE_CONTENT)
# Every route that needs a caller documents the same statuses in every auth
# variant, although a static token never meets 403 or 503.
ME_ERRORS = AUTHENTICATED_ROUTE_ERRORS
REGISTER_ERRORS = error_responses(
    status.HTTP_409_CONFLICT,
    status.HTTP_422_UNPROCESSABLE_CONTENT,
    status.HTTP_503_SERVICE_UNAVAILABLE,
    descriptions={status.HTTP_409_CONFLICT: REGISTRATION_CONFLICT_MESSAGE},
)
LOGIN_ERRORS = error_responses(
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_422_UNPROCESSABLE_CONTENT,
    status.HTTP_503_SERVICE_UNAVAILABLE,
    descriptions={status.HTTP_401_UNAUTHORIZED: INVALID_LOGIN_MESSAGE},
)
JWT_ME_ERRORS = error_responses(
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_503_SERVICE_UNAVAILABLE,
    descriptions={status.HTTP_401_UNAUTHORIZED: "Missing or invalid bearer token"},
)


@router.post(
    "/validate",
    response_model=AuthValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Check a static token",
    response_description="Whether the token is the configured one; always 200.",
    responses=VALIDATE_ERRORS,
)
def validate_token(
    payload: AuthValidationRequest,
    verifier: Annotated[TokenVerifierPort, Depends(get_token_verifier)],
) -> AuthValidationResponse:
    """Tell whether a token is the configured static token.

    The route is public and answers 200 for a wrong token too: it reports
    validity instead of guarding anything. Each rejection is logged with its
    reason and without the token, so a burst of guesses is visible.
    """
    try:
        verifier.verify(payload.token)
    except AuthenticationError as error:
        logger.warning("auth.validate_rejected", extra={"context": error.log_context})
        return AuthValidationResponse(
            authenticated=False, message=VALIDATION_REJECTED_MESSAGE
        )
    return AuthValidationResponse(
        authenticated=True, message=VALIDATION_ACCEPTED_MESSAGE
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get the current user",
    response_description="The authenticated caller.",
    responses=ME_ERRORS,
)
def read_current_user(current_user: CurrentUser) -> CurrentUserResponse:
    """Return the identity of the caller authenticated with the static token."""
    return CurrentUserResponse.from_user(current_user)


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    response_description="The newly created user (no credentials in the body).",
    responses=REGISTER_ERRORS,
)
def register(
    user_in: RegistrationRequest,
    background_tasks: BackgroundTasks,
    service: RegistrationServiceDep,
) -> UserPublic:
    """Create an account and return its public representation.

    The email is stored in lower case. A duplicate email or username answers 409
    without saying which one matched. Registration works while ``JWT_SECRET_KEY``
    is empty; only login and the JWT guard need it. A successful registration
    writes a ``user.register`` audit record that names the new account by id.
    """
    command = RegisterUserCommand(
        email=user_in.email,
        password=user_in.password,
        username=user_in.username,
        first_name=user_in.first_name,
        last_name=user_in.last_name,
    )
    user = service.register(command)
    # The new account acts on itself, and its opaque id is the only identifier
    # that may reach a log: an email or a username would identify the person.
    background_tasks.add_task(write_audit_log, AUDIT_USER_REGISTER, user.id, user.id)
    return UserPublic.model_validate(user)


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Log in for an access token",
    response_description="A signed JWT access token and its bearer type.",
    responses=LOGIN_ERRORS,
)
def login(
    form: Annotated[LoginForm, Form()],
    background_tasks: BackgroundTasks,
    service: AuthServiceDep,
    response: Response,
) -> TokenResponse:
    """Exchange an email and password for a signed JWT (OAuth2 password flow).

    The email is matched in lower case. A wrong password, an unknown email and
    an inactive account all answer the same 401. While ``JWT_SECRET_KEY`` is
    empty every request answers 503 before the credentials are looked at, so
    the status never tells whether they were right. A successful login writes a
    ``user.login`` audit record that names the account by id; a failed one is
    only warn-logged by the exception handler.
    """
    response.headers.update(TOKEN_RESPONSE_HEADERS)
    issued = service.authenticate(form.username, form.password)
    background_tasks.add_task(
        write_audit_log, AUDIT_USER_LOGIN, issued.user_id, issued.user_id
    )
    return TokenResponse.model_validate(issued)


@router.get(
    "/me/jwt",
    response_model=CurrentUserResponse,
    summary="Get the current JWT user",
    response_description="The active user resolved from the bearer JWT.",
    responses=JWT_ME_ERRORS,
)
def read_current_jwt_user(current_user: JwtUser) -> CurrentUserResponse:
    """Return the active account resolved from the bearer JWT; 401 without one.

    Answers 503 while ``JWT_SECRET_KEY`` is empty, because no token can be
    verified then.
    """
    return CurrentUserResponse.from_user(current_user)
