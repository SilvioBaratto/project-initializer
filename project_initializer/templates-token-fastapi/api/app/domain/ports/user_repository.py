"""User repository port: how the application reads and stores accounts."""

from typing import Protocol, runtime_checkable

from app.domain.entities.user import NewUser, User


@runtime_checkable
class UserRepositoryPort(Protocol):
    """Stores user accounts. Writes are staged only; the unit of work commits."""

    def get_by_id(self, user_id: str) -> User | None:
        """Fetch an account by identifier.

        Args:
            user_id: Identifier of the account.

        Returns:
            The account, or None when the id is unknown.
        """
        ...

    def get_by_email(self, email: str) -> User | None:
        """Fetch an account by its exact email address.

        Args:
            email: Email address to look up.

        Returns:
            The account, or None when no account uses that address.
        """
        ...

    def is_email_or_username_taken(self, email: str, username: str | None) -> bool:
        """Report whether registering these values would break a unique key.

        Args:
            email: Email address of the account to register.
            username: Handle of the account to register; None skips the handle
                check because several accounts may have no handle.

        Returns:
            True when an existing account uses the email or the handle. The
            caller must not tell the client which of the two matched.
        """
        ...

    def add(self, new_user: NewUser) -> User:
        """Stage a new account.

        Args:
            new_user: Values of the account.

        Returns:
            The account with its generated id. It is not permanent until the
            unit of work commits.

        Raises:
            ConflictError: A concurrent registration took the email or the
                username after ``is_email_or_username_taken`` answered False.
                The staged writes of the request are discarded.
        """
        ...
