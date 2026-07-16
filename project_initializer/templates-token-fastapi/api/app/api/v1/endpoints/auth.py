"""Authentication endpoints.

Auth modes (opt-in)
-------------------
Two authentication modes co-exist in this variant. Each mode is independent
— neither overwrites the other's guard logic.

(a) Static shared-secret mode
    Set ``AUTH_TOKEN`` in the environment.  Clients send
    ``Authorization: Bearer <AUTH_TOKEN>`` on every request.  The token is
    validated by ``/auth/validate`` (returns a JSON boolean) and by the static
    ``CurrentUser`` guard that protects item writes.  This mode is ideal for
    internal service-to-service auth where a single shared secret is enough.

(b) JWT opt-in mode
    Set ``JWT_SECRET_KEY``, ``JWT_ALGORITHM`` (default ``HS256``), and
    ``ACCESS_TOKEN_EXPIRE_MINUTES`` (default 30) in the environment.
    1. POST ``/auth/register`` with ``{"email": ..., "password": ...}`` to
       create a per-user account and receive a ``UserPublic`` response.
    2. POST ``/auth/token`` (OAuth2 form body: ``username=<email>&password=...``)
       to receive a signed ``access_token``.
    3. Send ``Authorization: Bearer <access_token>`` to JWT-guarded routes
       such as ``GET /auth/me/jwt``.  The token is decoded, the user is loaded
       from the database, and active status is enforced.

Choosing a mode
    - Static (a): simple shared secret — good for internal / machine clients.
    - JWT (b): per-user login with time-limited tokens — good for user-facing
      APIs that need individual identity and session expiry.
Both modes can be active simultaneously; they guard different endpoints.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.settings import settings
from app.infrastructure.security import create_access_token, hash_password, verify_password
from app.infrastructure.database import get_db
from app.api.deps import ActiveJWTUser, CurrentUser
from app.infrastructure.orm import User
from app.infrastructure.repositories.base import BaseRepository
from app.api.schemas import UserCreate, UserPublic

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------------------------
# Shared request / response models
# ---------------------------------------------------------------------------


class AuthRequest(BaseModel):
    token: str


class AuthResponse(BaseModel):
    authenticated: bool
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Shared OpenAPI error-response docs for the JWT routes. Spread with ``{**...}``
# at each call site so every decorator receives its own dict instance.
EMAIL_TAKEN_RESPONSE = {400: {"description": "Email already registered"}}
BAD_CREDENTIALS_RESPONSE = {401: {"description": "Incorrect email or password"}}
INVALID_TOKEN_RESPONSE = {401: {"description": "Missing or invalid bearer token"}}


# ---------------------------------------------------------------------------
# Static shared-secret mode  (keep byte-identical — DO NOT modify)
# ---------------------------------------------------------------------------


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


@router.get("/me")
async def get_me(current_user: CurrentUser):
    """
    Get the current authenticated user's information.

    Requires a valid Bearer token in the Authorization header.
    """
    return current_user


# ---------------------------------------------------------------------------
# JWT opt-in mode — register, token, and JWT-protected route
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    response_description="The newly created user (no credentials in the body).",
    responses={**EMAIL_TAKEN_RESPONSE},
)
def register(user_in: UserCreate, db: Session = Depends(get_db)) -> User:
    """Create a new user account and return the public user representation."""
    repo = BaseRepository(User, db)
    if repo.get_by_field("email", user_in.email):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )
    data = user_in.model_dump(exclude={"password"})
    data["password_hash"] = hash_password(user_in.password)
    user = repo.create_from_dict(data)
    db.commit()
    return user


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Log in for an access token",
    response_description="A signed JWT access token and its bearer type.",
    responses={**BAD_CREDENTIALS_RESPONSE},
)
def login(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> TokenResponse:
    """Mint a signed JWT for a registered user (OAuth2 password flow)."""
    user = BaseRepository(User, db).get_by_field("email", form.username)
    if user is None or not verify_password(form.password, user.password_hash or ""):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        user.id,
        settings.jwt_secret_key,
        settings.jwt_algorithm,
        settings.access_token_expire_minutes,
    )
    return TokenResponse(access_token=token)


@router.get(
    "/me/jwt",
    response_model=UserPublic,
    summary="Get the current JWT user",
    response_description="The active user resolved from the bearer JWT.",
    responses={**INVALID_TOKEN_RESPONSE},
)
def get_me_jwt(current_user: ActiveJWTUser) -> User:
    """JWT-protected: returns the active user resolved from the bearer JWT (401 without)."""
    return current_user
