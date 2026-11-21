"""In-memory stand-ins for the user and credential ports, shared by the unit tests."""

from collections.abc import Iterable

from app.domain.constants import PASSWORD_MAX_BYTES
from app.domain.entities.user import NewUser, User

EMAIL = "jane.doe@example.com"
PASSWORD = "correct-horse-battery"
HASH_PREFIX = "hashed::"


class FakeUserRepository:
    """Dict-backed ``UserRepositoryPort``."""

    def __init__(self, users: Iterable[User] = ()) -> None:
        self._users = {user.id: user for user in users}
        self.added: list[NewUser] = []

    def get_by_id(self, user_id: str) -> User | None:
        """Return the stored account, or None when the id is unknown."""
        return self._users.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        """Return the account that uses the email, or None."""
        return next((u for u in self._users.values() if u.email == email), None)

    def is_email_or_username_taken(self, email: str, username: str | None) -> bool:
        """Report whether an account uses the email or, when given, the username."""
        return any(
            user.email == email or (username is not None and user.username == username)
            for user in self._users.values()
        )

    def add(self, new_user: NewUser) -> User:
        """Store the account under a sequential id."""
        created = User(
            id=f"user-{len(self._users) + 1}",
            email=new_user.email,
            username=new_user.username,
            first_name=new_user.first_name,
            last_name=new_user.last_name,
            is_active=True,
            password_hash=new_user.password_hash,
        )
        self._users[created.id] = created
        self.added.append(new_user)
        return created


class FakePasswordHasher:
    """``PasswordHasherPort`` whose hash is readable and which records its calls."""

    def __init__(self) -> None:
        self.verify_calls: list[tuple[str, str | None]] = []

    def hash(self, password: str) -> str:
        """Return a readable stand-in for a hash, refusing over-long passwords."""
        if len(password.encode()) > PASSWORD_MAX_BYTES:
            raise ValueError("password too long")
        return f"{HASH_PREFIX}{password}"

    def verify(self, password: str, password_hash: str | None) -> bool:
        """Record the call and compare against the stand-in hash."""
        self.verify_calls.append((password, password_hash))
        return password_hash == f"{HASH_PREFIX}{password}"


def make_user(**overrides: object) -> User:
    """Build a stored active account whose password is ``PASSWORD``."""
    defaults: dict[str, object] = {
        "id": "user-existing",
        "email": EMAIL,
        "username": "jane",
        "first_name": "Jane",
        "last_name": "Doe",
        "is_active": True,
        "password_hash": f"{HASH_PREFIX}{PASSWORD}",
    }
    return User(**{**defaults, **overrides})
