"""Auth endpoints - returns current user info from JWT"""

from fastapi import APIRouter

from app.api.deps import CurrentUser

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get(
    "/me",
    summary="Get the current user",
    response_description="The authenticated user's info from the verified JWT.",
    responses={401: {"description": "Missing or invalid bearer token"}},
)
async def get_me(current_user: CurrentUser) -> dict:
    """Return the authenticated user's info from the verified JWT."""
    return current_user
