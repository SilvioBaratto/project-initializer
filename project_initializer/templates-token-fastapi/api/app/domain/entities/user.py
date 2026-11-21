"""User account entities of the token authentication variant."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class User:
    """A stored user account.

    Attributes:
        id: Opaque identifier assigned on creation.
        email: Unique email address, used as the login name.
        username: Optional unique handle.
        first_name: Optional given name.
        last_name: Optional family name.
        is_active: Whether the account may sign in.
        password_hash: Salted hash of the password, or None for an account that
            has no password and therefore cannot sign in. Left out of ``repr``
            so a logged entity never carries it.
    """

    id: str
    email: str
    username: str | None
    first_name: str | None
    last_name: str | None
    is_active: bool
    password_hash: str | None = field(repr=False)


@dataclass(frozen=True, slots=True)
class NewUser:
    """Values of an account that does not exist yet.

    Attributes:
        email: Unique email address, used as the login name.
        password_hash: Salted hash of the password; the plain text never
            reaches the repository. Left out of ``repr``.
        username: Optional unique handle.
        first_name: Optional given name.
        last_name: Optional family name.
    """

    email: str
    password_hash: str = field(repr=False)
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
