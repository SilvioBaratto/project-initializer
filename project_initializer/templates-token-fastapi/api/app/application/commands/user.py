"""User commands: the write intents the API layer hands to ``AuthService``."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    """Intent to create an account.

    Attributes:
        email: Email address, used as the login name.
        password: Plain-text password. Left out of ``repr`` so a logged command
            never carries it.
        username: Optional unique handle.
        first_name: Optional given name.
        last_name: Optional family name.
    """

    email: str
    password: str = field(repr=False)
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
