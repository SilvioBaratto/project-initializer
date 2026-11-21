"""Authentication routes of the base variant: who the caller is."""

from fastapi import APIRouter, status

from app.api.auth_deps import CurrentUser
from app.api.errors import AUTHENTICATED_ROUTE_ERRORS, error_responses
from app.api.schemas.user import CurrentUserResponse

ME_ERRORS = {
    **AUTHENTICATED_ROUTE_ERRORS,
    **error_responses(status.HTTP_422_UNPROCESSABLE_CONTENT),
}

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get the current user",
    response_description="The authenticated caller.",
    responses=ME_ERRORS,
)
def read_current_user(current_user: CurrentUser) -> CurrentUserResponse:
    """Return the identity of the caller, whichever auth variant is running."""
    return CurrentUserResponse.from_user(current_user)
