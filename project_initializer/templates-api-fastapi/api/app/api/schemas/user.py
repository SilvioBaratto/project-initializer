"""User models: the registration payload and the identity views."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.api.schemas.common import NulFreeStr
from app.domain.constants import (
    EMAIL_MAX_LENGTH,
    PASSWORD_MAX_BYTES,
    PASSWORD_MIN_LENGTH,
    PERSON_NAME_MAX_LENGTH,
    USERNAME_MAX_LENGTH,
)
from app.domain.entities.authenticated_user import AuthenticatedUser


class UserBase(BaseModel):
    """Profile fields shared by the user models.

    Attributes:
        email: Email address.
        username: Optional public handle.
        first_name: Optional given name.
        last_name: Optional family name.
    """

    email: EmailStr = Field(
        max_length=EMAIL_MAX_LENGTH,
        description="User email address",
        examples=["jane.doe@example.com"],
    )
    username: NulFreeStr | None = Field(
        default=None,
        max_length=USERNAME_MAX_LENGTH,
        description="Optional username",
        examples=["jane"],
    )
    first_name: NulFreeStr | None = Field(
        default=None,
        max_length=PERSON_NAME_MAX_LENGTH,
        description="First name",
        examples=["Jane"],
    )
    last_name: NulFreeStr | None = Field(
        default=None,
        max_length=PERSON_NAME_MAX_LENGTH,
        description="Last name",
        examples=["Doe"],
    )


class UserCreate(UserBase):
    """Registration payload; the password is never part of a response.

    Attributes:
        password: Plain-text password, at most ``PASSWORD_MAX_BYTES`` bytes
            because bcrypt silently ignores anything beyond that. A NUL
            character is refused for the same reason: bcrypt stops reading at it.
    """

    password: NulFreeStr = Field(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_BYTES,
        description=(
            f"Plain-text password, {PASSWORD_MIN_LENGTH} to {PASSWORD_MAX_BYTES} bytes"
        ),
    )

    @field_validator("password")
    @classmethod
    def _fits_bcrypt_limit(cls, value: str) -> str:
        # The character limit alone passes multi-byte text beyond the byte limit.
        if len(value.encode()) > PASSWORD_MAX_BYTES:
            raise ValueError(f"must be at most {PASSWORD_MAX_BYTES} bytes")
        return value


class UserPublic(UserBase):
    """A stored user as returned to clients; never exposes credentials.

    Attributes:
        id: User identifier.
        is_active: Whether the account may sign in.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="User ID")
    is_active: bool = Field(description="Whether the account is active")


class CurrentUserResponse(BaseModel):
    """The caller's identity as seen by this API, whatever the auth variant.

    Attributes:
        id: Stable identifier of the caller.
        email: Email address when the identity provider supplies one.
        username: Username when the identity provider supplies one.
        roles: Roles granted to the caller.
        auth_method: How the caller authenticated.
    """

    id: str
    email: str | None = None
    username: str | None = None
    roles: list[str]
    auth_method: str

    @classmethod
    def from_user(cls, user: AuthenticatedUser) -> "CurrentUserResponse":
        """Build the response from an authenticated principal.

        Args:
            user: The principal resolved by ``get_current_user``.

        Returns:
            The response with the principal's roles as a list.
        """
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            roles=list(user.roles),
            auth_method=user.auth_method,
        )
