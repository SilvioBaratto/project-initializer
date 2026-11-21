"""SQLAlchemy implementation of the async unit of work port.

Async twin of ``app.infrastructure.unit_of_work``: an integrity violation
becomes ``ConflictError`` whether the database rejects it at flush or at commit.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.errors import conflict_from


async def flush_or_conflict_async(session: AsyncSession) -> None:
    """Send the staged writes to the database, translating an integrity error.

    Async repositories call it after every ``add``, ``update`` and ``delete``
    instead of ``session.flush()``, so a uniqueness race is a ``ConflictError``
    and not a raw driver error that would log the SQL text and the values.

    Args:
        session: The session that holds the staged writes.

    Raises:
        ConflictError: A uniqueness or integrity constraint rejected the writes.
            The session has been rolled back and stays usable. The driver
            message is dropped and the error is chained as ``__cause__``.
    """
    try:
        await session.flush()
    except IntegrityError as error:
        await session.rollback()
        raise conflict_from(error) from error


class SqlAlchemyAsyncUnitOfWork:
    """Commits or discards the writes a repository staged on one async session."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the unit of work to a session.

        Args:
            session: Session shared with the repositories of the same request.
        """
        self._session = session

    async def commit(self) -> None:
        """Make the staged writes permanent.

        Raises:
            ConflictError: A uniqueness or integrity constraint rejected the
                writes. The session has been rolled back and stays usable. The
                database message is dropped because it can quote stored values.
        """
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise conflict_from(error) from error

    async def rollback(self) -> None:
        """Discard the staged writes."""
        await self._session.rollback()
