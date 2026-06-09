"""Users router — exposes the current user via a secret-stripping response model."""

from fastapi import APIRouter

from app.dependencies import CurrentUser
from app.schemas import UserPublic

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get the current user",
    response_description="The authenticated user, with secret fields stripped.",
)
def read_current_user(current_user: CurrentUser) -> dict:
    """Return the authenticated user; response_model=UserPublic strips any secret."""
    return current_user
