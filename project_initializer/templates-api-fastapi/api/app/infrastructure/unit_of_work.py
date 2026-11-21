"""SQLAlchemy implementation of the unit of work port.

An integrity violation surfaces at flush time, when a repository stages a write,
or at commit time, when a deferred constraint is checked. Both paths translate
it into ``ConflictError`` here, so the HTTP layer sees one error whichever
moment the database rejected the write.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.errors import conflict_from


def flush_or_conflict(session: Session) -> None:
    """Send the staged writes to the database, translating an integrity error.

    Repositories call it after every ``add``, ``update`` and ``delete`` instead
    of ``session.flush()``, so a uniqueness race is a ``ConflictError`` and not a
    raw driver error that would log the SQL text and the offending values.

    Args:
        session: The session that holds the staged writes.

    Raises:
        ConflictError: A uniqueness or integrity constraint rejected the writes.
            The session has been rolled back and stays usable. The driver
            message is dropped and the error is chained as ``__cause__``.
    """
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise conflict_from(error) from error


class SqlAlchemyUnitOfWork:
    """Commits or discards the writes a repository staged on one session."""

    def __init__(self, session: Session) -> None:
        """Bind the unit of work to a session.

        Args:
            session: Session shared with the repositories of the same request.
        """
        self._session = session

    def commit(self) -> None:
        """Make the staged writes permanent.

        Raises:
            ConflictError: A uniqueness or integrity constraint rejected the
                writes. The session has been rolled back and stays usable. The
                database message is dropped because it can quote stored values.
        """
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise conflict_from(error) from error

    def rollback(self) -> None:
        """Discard the staged writes."""
        self._session.rollback()
