"""Unit tests for the request models of the token authentication routes."""

import pytest
from pydantic import ValidationError

from app.api.schemas.auth import LoginForm, RegistrationRequest, normalize_email
from app.domain.constants import EMAIL_MAX_LENGTH

pytestmark = pytest.mark.unit

PASSWORD = "strongpassword"
MIXED_CASE_EMAIL = "Jane.Doe@Example.COM"
NORMALIZED_EMAIL = "jane.doe@example.com"


def registration(**overrides: object) -> RegistrationRequest:
    """Build a valid registration body with ``overrides`` applied."""
    body = {"email": NORMALIZED_EMAIL, "password": PASSWORD, **overrides}
    return RegistrationRequest.model_validate(body)


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        pytest.param(MIXED_CASE_EMAIL, NORMALIZED_EMAIL, id="mixed-case"),
        pytest.param(f"  {NORMALIZED_EMAIL}\n", NORMALIZED_EMAIL, id="whitespace"),
        pytest.param(NORMALIZED_EMAIL, NORMALIZED_EMAIL, id="already-normalized"),
    ],
)
def test_when_an_email_is_normalized_then_it_is_trimmed_and_lower_case(typed, expected):
    """when an address is normalized, whitespace and case are removed.

    Validates app.api.schemas.auth.normalize_email().
    """
    assert normalize_email(typed) == expected


def test_when_the_registration_email_has_capitals_then_it_is_stored_in_lower_case():
    """when a registration email has capitals, the local part and domain are lowered.

    Validates app.api.schemas.auth.RegistrationRequest.
    """
    assert registration(email=MIXED_CASE_EMAIL).email == NORMALIZED_EMAIL


def test_when_the_login_username_has_capitals_then_it_is_looked_up_in_lower_case():
    """when the login username has capitals, the lookup key is lower case.

    Validates app.api.schemas.auth.LoginForm.
    """
    form = LoginForm(username=MIXED_CASE_EMAIL, password=PASSWORD)

    assert form.username == NORMALIZED_EMAIL


def test_when_the_registration_and_login_forms_get_one_address_then_they_agree():
    """when one address reaches both models, both produce the same key.

    Validates app.api.schemas.auth.normalize_email().
    """
    typed = f" {MIXED_CASE_EMAIL} "

    assert (
        registration(email=typed).email
        == LoginForm(username=typed, password=PASSWORD).username
    )


@pytest.mark.parametrize("blank", ["", " ", "\t \n"])
def test_when_the_username_is_blank_then_the_account_has_no_username(blank):
    """when the username is empty or whitespace, it is treated as not provided.

    Validates app.api.schemas.auth.RegistrationRequest.
    """
    assert registration(username=blank).username is None


def test_when_the_username_is_given_then_it_is_kept_unchanged():
    """when the username has content, it is stored as sent.

    Validates app.api.schemas.auth.RegistrationRequest.
    """
    assert registration(username=" jane ").username == " jane "


@pytest.mark.parametrize("field", ["username", "first_name", "last_name"])
def test_when_a_registration_text_field_holds_nul_then_validation_fails(field):
    """when username, first_name or last_name holds a NUL character, validation fails.

    Validates app.api.schemas.auth.RegistrationRequest.
    """
    with pytest.raises(ValidationError):
        registration(**{field: "a\x00b"})


def test_when_the_login_username_holds_nul_then_validation_fails():
    """when the login username holds a NUL character, validation fails.

    Validates app.api.schemas.auth.LoginForm.
    """
    with pytest.raises(ValidationError):
        LoginForm(username="a\x00b@example.com", password=PASSWORD)


@pytest.mark.parametrize("username", ["", "u" * (EMAIL_MAX_LENGTH + 1)])
def test_when_the_login_username_is_empty_or_too_long_then_validation_fails(username):
    """when the login username is empty or over the length limit, validation fails.

    Validates app.api.schemas.auth.LoginForm.
    """
    with pytest.raises(ValidationError):
        LoginForm(username=username, password=PASSWORD)
