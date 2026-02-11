"""Authentication endpoints"""

import secrets

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])


class AuthRequest(BaseModel):
    token: str


class AuthResponse(BaseModel):
    authenticated: bool
    message: str


@router.post("/validate", response_model=AuthResponse, status_code=status.HTTP_200_OK)
async def validate_token(request: AuthRequest):
    """
    Validate an authentication token.

    Compares the provided token against the configured AUTH_TOKEN
    using constant-time comparison to prevent timing attacks.
    """
    if secrets.compare_digest(request.token, settings.auth_token):
        return AuthResponse(authenticated=True, message="Authentication successful")

    return AuthResponse(authenticated=False, message="Invalid token")
