"""Authentication dependency of the base (no-auth) variant.

This module is the auth seam: every auth overlay replaces it with a module that
exports the same two names, ``get_current_user`` and ``CurrentUser``, so routes
and the role guard never learn which variant is running.

Without authentication every caller is the development principal. In a local or
test environment the ``X-User-Id`` header can pick another id, which lets one
developer exercise ownership rules; anywhere else the header is ignored so
nobody can impersonate a user by sending it.
"""

from typing import Annotated

from fastapi import Depends, Header

from app.domain.entities.authenticated_user import AuthenticatedUser
from app.infrastructure.settings import settings

DEV_USER_ID = "dev-user"
DEV_USER_HEADER = "X-User-Id"
DEV_USER_ID_MAX_LENGTH = 64
DEV_USER_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
DEVELOPMENT_AUTH_METHOD = "development"


def get_current_user(
    x_user_id: Annotated[
        str | None,
        Header(
            alias=DEV_USER_HEADER,
            max_length=DEV_USER_ID_MAX_LENGTH,
            pattern=DEV_USER_ID_PATTERN,
            description="Development only: act as this user id",
        ),
    ] = None,
) -> AuthenticatedUser:
    """Resolve the caller to the development principal.

    It is a plain ``def`` like the overlay versions, whose token checks block on
    I/O, so the seam has one shape in every variant. FastAPI runs it in its worker
    pool; this version does no I/O.

    Args:
        x_user_id: Optional id from the ``X-User-Id`` header. A value that is
            too long or has characters outside the pattern is rejected with 422
            whatever the environment.

    Returns:
        A principal with the header's id when the environment is local or test
        and the header is present, otherwise the constant development principal.
    """
    user_id = x_user_id if x_user_id and settings.is_local else DEV_USER_ID
    return AuthenticatedUser(
        id=user_id, auth_method=DEVELOPMENT_AUTH_METHOD, username=user_id
    )


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
