"""Unit tests for JWT dependency functions (issue #17).

These tests exercise get_current_user_jwt and get_current_active_user directly
(no HTTP) using a real SQLite db_session from the base conftest. All five
behaviours under test are named "when X, Y is returned/raised".

Markers: @pytest.mark.unit
"""

import pytest
from fastapi import HTTPException

from app.config import settings
from app.core.security import create_access_token
from app.dependencies import get_current_active_user, get_current_user_jwt
from app.models import User


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_when_valid_token_names_active_user_get_current_active_user_returns_that_user(
    db_session,
):
    """when a valid token names an active user, get_current_active_user returns that user."""
    user = User(id="u-active-jwt", email="active-jwt@example.com", is_active=True)
    db_session.add(user)
    db_session.commit()

    token = create_access_token(
        "u-active-jwt", settings.jwt_secret_key, settings.jwt_algorithm
    )
    resolved = get_current_user_jwt(token=token, db=db_session)
    active = get_current_active_user(current_user=resolved)

    assert active.id == "u-active-jwt"


# ---------------------------------------------------------------------------
# Inactive user
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_when_valid_token_names_inactive_user_get_current_active_user_raises_400(
    db_session,
):
    """when a valid token names an inactive user, get_current_active_user raises
    HTTPException with status 400."""
    user = User(id="u-inactive-jwt", email="inactive-jwt@example.com", is_active=False)
    db_session.add(user)
    db_session.commit()

    token = create_access_token(
        "u-inactive-jwt", settings.jwt_secret_key, settings.jwt_algorithm
    )
    resolved = get_current_user_jwt(token=token, db=db_session)

    with pytest.raises(HTTPException) as exc:
        get_current_active_user(current_user=resolved)

    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Non-existent user
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_when_token_sub_names_nonexistent_user_get_current_user_jwt_raises_401(
    db_session,
):
    """when the token sub references a user not in the DB, get_current_user_jwt
    raises HTTPException with status 401."""
    token = create_access_token(
        "does-not-exist", settings.jwt_secret_key, settings.jwt_algorithm
    )

    with pytest.raises(HTTPException) as exc:
        get_current_user_jwt(token=token, db=db_session)

    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Wrong key / tampered token
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_when_token_is_signed_with_wrong_key_get_current_user_jwt_raises_401(
    db_session,
):
    """when the token is signed with a different key, get_current_user_jwt
    raises HTTPException with status 401 (JWTError caught internally)."""
    token = create_access_token("u-active-jwt", "completely-wrong-secret-key")

    with pytest.raises(HTTPException) as exc:
        get_current_user_jwt(token=token, db=db_session)

    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Missing token (None)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_when_token_is_none_get_current_user_jwt_raises_401(db_session):
    """when no bearer token is provided (token=None), get_current_user_jwt
    raises HTTPException with status 401."""
    with pytest.raises(HTTPException) as exc:
        get_current_user_jwt(token=None, db=db_session)

    assert exc.value.status_code == 401
