"""Auth endpoints - returns current user info from JWT"""

from fastapi import APIRouter

from app.dependencies import CurrentUser

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/me")
async def get_me(current_user: CurrentUser) -> dict:
    """Return the authenticated user's info from the verified JWT."""
    return current_user
