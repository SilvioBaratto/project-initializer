"""SQLAlchemy implementation of the user repository port."""

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.domain.entities.user import NewUser, User
from app.infrastructure.orm.user import UserRecord
from app.infrastructure.unit_of_work import flush_or_conflict


def _to_entity(record: UserRecord) -> User:
    return User(
        id=record.id,
        email=record.email,
        username=record.username,
        first_name=record.first_name,
        last_name=record.last_name,
        is_active=record.is_active,
        password_hash=record.password_hash,
    )


class SqlAlchemyUserRepository:
    """Stores accounts through a session and returns domain entities.

    Writes are flushed, never committed: the unit of work owns the transaction.
    """

    def __init__(self, session: Session) -> None:
        """Bind the repository to a session.

        Args:
            session: Session shared with the unit of work of the same request.
        """
        self._session = session

    def get_by_id(self, user_id: str) -> User | None:
        """Fetch an account by identifier, or None when the id is unknown."""
        record = self._session.get(UserRecord, user_id)
        return _to_entity(record) if record else None

    def get_by_email(self, email: str) -> User | None:
        """Fetch an account by its exact email address, or None when unused."""
        record = self._session.scalar(
            select(UserRecord).where(UserRecord.email == email)
        )
        return _to_entity(record) if record else None

    def is_email_or_username_taken(self, email: str, username: str | None) -> bool:
        """Report whether an existing account uses the email or the username.

        A missing username is ignored, because accounts without one do not
        conflict with each other.
        """
        clashes = [UserRecord.email == email]
        if username is not None:
            clashes.append(UserRecord.username == username)
        return bool(self._session.scalar(select(exists().where(or_(*clashes)))))

    def add(self, new_user: NewUser) -> User:
        """Stage a new account and return it with its generated id.

        Raises:
            ConflictError: The email or the username is already stored. The
                session has been rolled back.
        """
        record = UserRecord(
            email=new_user.email,
            password_hash=new_user.password_hash,
            username=new_user.username,
            first_name=new_user.first_name,
            last_name=new_user.last_name,
        )
        self._session.add(record)
        flush_or_conflict(self._session)
        return _to_entity(record)
