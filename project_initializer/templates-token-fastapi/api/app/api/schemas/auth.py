"""Request and response models of the token authentication routes."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.api.bearer import MAX_BEARER_TOKEN_LENGTH
from app.api.schemas.common import NulFreeStr
from app.api.schemas.user import UserCreate
from app.application.dto.user import BEARER_TOKEN_TYPE
from app.domain.constants import EMAIL_MAX_LENGTH, PASSWORD_MAX_BYTES


def normalize_email(value: str) -> str:
    """Bring an email address to the one form that accounts are stored and found by.

    Registration and login both apply it. The unique key on the email column is
    case-sensitive and the address validator keeps the case of the local part,
    so without a common form ``Jane@example.com`` could not log in with what was
    typed and ``jane@example.com`` could register a second account.

    Args:
        value: Address as typed by the client.

    Returns:
        The address without surrounding whitespace, in lower case.
    """
    return value.strip().lower()


class RegistrationRequest(UserCreate):
    """Registration body: the shared user model with the account rules of this variant.

    The base model validates every text field, but it keeps the email as typed
    and an empty username as an empty string.
    """

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("username")
    @classmethod
    def _blank_username_is_absent(cls, value: str | None) -> str | None:
        # A form that submits an empty optional field must not claim the one
        # empty handle for the first account that registers.
        if value is None or not value.strip():
            return None
        return value


class AuthValidationRequest(BaseModel):
    """A token whose validity the caller wants to know.

    Attributes:
        token: The token to check. It is capped at the bearer-token limit so the
            probe cannot be made to hash an arbitrarily large body.
    """

    token: str = Field(
        max_length=MAX_BEARER_TOKEN_LENGTH,
        description="The static token to check",
    )


class AuthValidationResponse(BaseModel):
    """Answer of the validity probe.

    Attributes:
        authenticated: Whether the token is the configured one.
        message: Short human-readable outcome.
    """

    authenticated: bool
    message: str


class TokenResponse(BaseModel):
    """A freshly issued access token.

    Attributes:
        access_token: Signed JWT to send as ``Authorization: Bearer <token>``.
        token_type: Always ``bearer``.
    """

    model_config = ConfigDict(from_attributes=True)

    access_token: str
    token_type: str = BEARER_TOKEN_TYPE


class LoginForm(BaseModel):
    """Form body of the OAuth2 password flow, with every field bounded.

    The password is capped at the length of the longest password registration
    accepts. A longer one cannot be correct, so rejecting it early also keeps an
    oversized body away from the password hasher.

    Attributes:
        username: Email address of the account; the OAuth2 flow calls it username.
        password: Plain-text password.
    """

    username: Annotated[NulFreeStr, AfterValidator(normalize_email)] = Field(
        min_length=1, max_length=EMAIL_MAX_LENGTH
    )
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_BYTES)
