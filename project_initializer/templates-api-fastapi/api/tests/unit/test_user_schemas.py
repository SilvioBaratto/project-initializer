"""Unit tests for the user request and response schemas."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.schemas.user import CurrentUserResponse, UserBase, UserCreate, UserPublic
from app.domain.constants import (
    EMAIL_MAX_LENGTH,
    PASSWORD_MAX_BYTES,
    PASSWORD_MIN_LENGTH,
    PERSON_NAME_MAX_LENGTH,
    USERNAME_MAX_LENGTH,
)
from app.domain.entities.authenticated_user import AuthenticatedUser
from tests.fakes import TEST_USER
from tests.schema_helpers import error_fields

pytestmark = pytest.mark.unit

EMAIL = "alice@example.com"
VALID_PASSWORD = "p" * PASSWORD_MIN_LENGTH
# Two bytes per character in UTF-8, so the byte limit is hit before the character limit.
TWO_BYTE_CHARACTER = "é"
# Address-syntax limits (RFC 5321) that make a 256-character address otherwise valid.
MAX_LOCAL_PART_LENGTH = 64
MAX_DOMAIN_LABEL_LENGTH = 63
TEXT_FIELD_LIMITS = [
    pytest.param("username", USERNAME_MAX_LENGTH, id="username"),
    pytest.param("first_name", PERSON_NAME_MAX_LENGTH, id="first-name"),
    pytest.param("last_name", PERSON_NAME_MAX_LENGTH, id="last-name"),
]


def _oversized_email() -> str:
    """An address one character wider than the column that is otherwise valid."""
    local_part = "a" * MAX_LOCAL_PART_LENGTH
    fixed_length = len(local_part) + len("@") + len(".com")
    last_label = EMAIL_MAX_LENGTH + 1 - fixed_length - 2 * (MAX_DOMAIN_LABEL_LENGTH + 1)
    labels = ["b" * MAX_DOMAIN_LABEL_LENGTH, "c" * MAX_DOMAIN_LABEL_LENGTH]
    return f"{local_part}@{'.'.join([*labels, 'd' * last_label])}.com"


def test_when_email_is_not_an_address_then_user_base_rejects_it():
    """when the email is malformed, UserBase rejects it.

    Validates app.api.schemas.user.UserBase.
    """
    with pytest.raises(ValidationError) as error:
        UserBase(email="not-an-email")

    assert error_fields(error) == {"email"}


def test_when_email_exceeds_the_column_width_then_user_base_rejects_it():
    """when the email is wider than the stored column, UserBase rejects it.

    Validates app.api.schemas.user.UserBase.
    """
    oversized = _oversized_email()
    assert len(oversized) == EMAIL_MAX_LENGTH + 1

    with pytest.raises(ValidationError) as error:
        UserBase(email=oversized)

    assert error_fields(error) == {"email"}


def test_when_only_an_email_is_given_then_optional_fields_are_empty():
    """when only the email is given, the optional profile fields default to None.

    Validates app.api.schemas.user.UserBase.
    """
    user = UserBase(email=EMAIL)

    assert user.email == EMAIL
    assert (user.username, user.first_name, user.last_name) == (None, None, None)


@pytest.mark.parametrize(("field", "limit"), TEXT_FIELD_LIMITS)
def test_when_text_field_is_at_its_limit_then_it_is_accepted(field, limit):
    """when a text field has exactly the maximum length, UserBase accepts it.

    Validates app.api.schemas.user.UserBase.
    """
    user = UserBase(email=EMAIL, **{field: "x" * limit})

    assert len(getattr(user, field)) == limit


@pytest.mark.parametrize(("field", "limit"), TEXT_FIELD_LIMITS)
def test_when_text_field_is_one_over_its_limit_then_it_is_rejected(field, limit):
    """when a text field is one character too long, UserBase rejects only that field.

    Validates app.api.schemas.user.UserBase.
    """
    with pytest.raises(ValidationError) as error:
        UserBase(email=EMAIL, **{field: "x" * (limit + 1)})

    assert error_fields(error) == {field}


def test_when_password_is_missing_then_user_create_rejects_it():
    """when the password is omitted, UserCreate rejects the payload.

    Validates app.api.schemas.user.UserCreate.
    """
    with pytest.raises(ValidationError) as error:
        UserCreate(email=EMAIL)

    assert error_fields(error) == {"password"}


def test_when_password_is_one_short_of_the_minimum_then_it_is_rejected():
    """when the password has seven characters, UserCreate rejects it.

    Validates app.api.schemas.user.UserCreate.
    """
    with pytest.raises(ValidationError) as error:
        UserCreate(email=EMAIL, password="p" * (PASSWORD_MIN_LENGTH - 1))

    assert error_fields(error) == {"password"}


def test_when_password_has_the_minimum_length_then_it_is_accepted():
    """when the password has eight characters, UserCreate accepts it.

    Validates app.api.schemas.user.UserCreate.
    """
    user = UserCreate(email=EMAIL, password=VALID_PASSWORD)

    assert user.password == VALID_PASSWORD


def test_when_password_fills_the_byte_limit_then_it_is_accepted():
    """when the password is exactly 72 bytes, UserCreate accepts it.

    Validates app.api.schemas.user.UserCreate.
    """
    password = "p" * PASSWORD_MAX_BYTES

    assert UserCreate(email=EMAIL, password=password).password == password


def test_when_password_is_one_byte_over_the_limit_then_it_is_rejected():
    """when the password is 73 bytes, UserCreate rejects it.

    bcrypt ignores everything past 72 bytes, so a longer password would be
    silently truncated.

    Validates app.api.schemas.user.UserCreate.
    """
    with pytest.raises(ValidationError) as error:
        UserCreate(email=EMAIL, password="p" * (PASSWORD_MAX_BYTES + 1))

    assert error_fields(error) == {"password"}


def test_when_password_is_short_in_characters_but_long_in_bytes_then_it_is_rejected():
    """when multi-byte characters push a password past 72 bytes, it is rejected.

    The limit counts UTF-8 bytes, not characters.

    Validates app.api.schemas.user.UserCreate.
    """
    password = TWO_BYTE_CHARACTER * (PASSWORD_MAX_BYTES // 2 + 1)
    assert len(password) < PASSWORD_MAX_BYTES

    with pytest.raises(ValidationError) as error:
        UserCreate(email=EMAIL, password=password)

    assert error_fields(error) == {"password"}


def test_when_multi_byte_password_fits_the_byte_limit_then_it_is_accepted():
    """when multi-byte characters total exactly 72 bytes, UserCreate accepts it.

    Validates app.api.schemas.user.UserCreate.
    """
    password = TWO_BYTE_CHARACTER * (PASSWORD_MAX_BYTES // 2)

    assert UserCreate(email=EMAIL, password=password).password == password


def test_when_client_sends_is_active_then_user_create_ignores_it():
    """when a registration payload carries is_active, it never reaches the model.

    A caller must not choose whether its own new account is active.

    Validates app.api.schemas.user.UserCreate.
    """
    user = UserCreate.model_validate(
        {"email": EMAIL, "password": VALID_PASSWORD, "is_active": False}
    )

    assert "is_active" not in UserCreate.model_fields
    assert "is_active" not in user.model_dump()


def test_when_a_stored_user_is_validated_then_public_schema_drops_credentials():
    """when an object with credential attributes is validated, none are exposed.

    Validates app.api.schemas.user.UserPublic.
    """
    stored_user = SimpleNamespace(
        id="user-1",
        email=EMAIL,
        username=None,
        first_name=None,
        last_name=None,
        is_active=True,
        password_hash="$2b$12$hash",
        password="plaintext",
    )

    public = UserPublic.model_validate(stored_user, from_attributes=True)

    assert set(public.model_dump()) == {
        "id",
        "email",
        "username",
        "first_name",
        "last_name",
        "is_active",
    }


def test_when_a_principal_is_converted_then_the_response_lists_its_claims():
    """when TEST_USER is converted, the response carries id, contact, roles and method.

    Validates app.api.schemas.user.CurrentUserResponse.from_user().
    """
    response = CurrentUserResponse.from_user(TEST_USER)

    assert response.model_dump() == {
        "id": TEST_USER.id,
        "email": TEST_USER.email,
        "username": TEST_USER.username,
        "roles": list(TEST_USER.roles),
        "auth_method": TEST_USER.auth_method,
    }


def test_when_a_principal_has_no_profile_then_the_response_leaves_it_empty():
    """when the principal has no email, username or roles, the response is empty there.

    Validates app.api.schemas.user.CurrentUserResponse.from_user().
    """
    service_account = AuthenticatedUser(
        id="service-account", auth_method="static_token"
    )

    response = CurrentUserResponse.from_user(service_account)

    assert response.email is None
    assert response.username is None
    assert response.roles == []
