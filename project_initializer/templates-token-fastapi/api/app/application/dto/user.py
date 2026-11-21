"""User DTOs: what ``AuthService`` returns, so entities and hashes stay inside."""

from dataclasses import dataclass, field

from app.domain.entities.user import User

BEARER_TOKEN_TYPE = "bearer"


@dataclass(frozen=True, slots=True)
class UserDTO:
    """Read model of an account; it never carries credentials.

    Attributes:
        id: Identifier of the account.
        email: Email address.
        username: Optional unique handle.
        first_name: Optional given name.
        last_name: Optional family name.
        is_active: Whether the account may sign in.
    """

    id: str
    email: str
    username: str | None
    first_name: str | None
    last_name: str | None
    is_active: bool

    @classmethod
    def from_entity(cls, user: User) -> "UserDTO":
        """Copy an entity into its read model, leaving the password hash behind.

        Args:
            user: The entity to copy.

        Returns:
            A DTO with the public fields of the entity.
        """
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
        )


@dataclass(frozen=True, slots=True)
class AccessTokenDTO:
    """A freshly issued access token.

    Attributes:
        access_token: The signed token. Left out of ``repr`` so a logged DTO
            never carries it.
        user_id: Identifier of the account the token was issued to; the caller
            uses it to audit the login without an email or a username.
        token_type: Authorization scheme the client sends it with.
    """

    access_token: str = field(repr=False)
    user_id: str
    token_type: str = BEARER_TOKEN_TYPE
