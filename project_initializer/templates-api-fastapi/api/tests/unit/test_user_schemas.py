"""Unit tests for User Pydantic schemas (issue #14).

Covers the full UserBase/UserCreate/UserPublic/UserInDB contract:
- email validation via EmailStr
- password length enforcement on UserCreate
- secret-stripping: password / password_hash absent from UserPublic dumps
- UserInDB preserves password_hash
"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas import UserBase, UserCreate, UserInDB, UserPublic


# ---------------------------------------------------------------------------
# UserBase — email validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_when_email_is_invalid_then_validation_error_is_raised():
    """when email is invalid, a ValidationError is raised."""
    with pytest.raises(ValidationError):
        UserBase(email="not-an-email")


@pytest.mark.unit
def test_when_email_is_valid_then_userbase_is_accepted():
    """when email is valid, UserBase is accepted and optional fields default."""
    user = UserBase(email="alice@example.com")

    assert user.email == "alice@example.com"
    assert user.username is None
    assert user.first_name is None
    assert user.last_name is None
    assert user.is_active is True


# ---------------------------------------------------------------------------
# UserCreate — password rules
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_when_usercreate_has_no_password_then_validation_error_is_raised():
    """when UserCreate payload omits password, a ValidationError is raised."""
    with pytest.raises(ValidationError):
        UserCreate(email="bob@example.com")


@pytest.mark.unit
def test_when_usercreate_password_is_too_short_then_validation_error_is_raised():
    """when UserCreate password is shorter than 8 chars, a ValidationError is raised."""
    with pytest.raises(ValidationError):
        UserCreate(email="bob@example.com", password="short")


@pytest.mark.unit
def test_when_usercreate_has_valid_password_then_it_is_accepted_and_exposed():
    """when UserCreate has a valid 8+ char password, it is accepted and password is exposed."""
    user = UserCreate(email="bob@example.com", password="securepassword")

    assert user.password == "securepassword"
    assert user.email == "bob@example.com"


# ---------------------------------------------------------------------------
# UserPublic — secret-stripping
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_when_userpublic_validates_object_with_password_hash_then_dump_excludes_it():
    """when an object carrying password_hash is validated by UserPublic, the dump has no password_hash."""
    stub = SimpleNamespace(
        id="uuid-1",
        email="carol@example.com",
        username=None,
        first_name=None,
        last_name=None,
        is_active=True,
        password_hash="$2b$12$hashed",
    )
    user_public = UserPublic.model_validate(stub)

    assert "password_hash" not in user_public.model_dump()
    assert "password_hash" not in user_public.model_dump(mode="json")
    assert user_public.email == "carol@example.com"
    assert user_public.id == "uuid-1"


@pytest.mark.unit
def test_when_userpublic_validates_object_with_password_attr_then_dump_excludes_password():
    """when an object with a password attribute is validated by UserPublic, password is absent from dump."""
    stub = SimpleNamespace(
        id="uuid-2",
        email="dave@example.com",
        username=None,
        first_name=None,
        last_name=None,
        is_active=True,
        password="plaintextpassword",
    )
    user_public = UserPublic.model_validate(stub)

    assert "password" not in user_public.model_dump()
    assert user_public.email == "dave@example.com"


# ---------------------------------------------------------------------------
# UserInDB — preserves password_hash
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_when_userindb_is_built_then_it_keeps_password_hash():
    """when UserInDB is built, it keeps password_hash."""
    user_in_db = UserInDB(
        id="uuid-3",
        email="eve@example.com",
        password_hash="$2b$12$realhash",
    )

    assert user_in_db.password_hash == "$2b$12$realhash"
    assert user_in_db.email == "eve@example.com"
    assert user_in_db.id == "uuid-3"
