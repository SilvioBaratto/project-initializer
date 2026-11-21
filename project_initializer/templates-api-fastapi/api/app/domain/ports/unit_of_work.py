"""Unit of work port: the transaction boundary owned by the application layer.

A commit can fail in two ways the use cases need to tell apart: the database
rejected the writes (``ConflictError``) or it could not be reached
(``ExternalServiceError``). Adapters never let a driver exception escape the
session scope they run in; it is translated into one of those two.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class UnitOfWorkPort(Protocol):
    """Makes the writes staged by repositories permanent, or discards them."""

    def commit(self) -> None:
        """Make all staged writes permanent.

        Raises:
            ConflictError: A uniqueness or integrity constraint rejected the
                writes. The adapter has already rolled back when this is raised.
            ExternalServiceError: The store is unavailable. Raised once the
                error leaves the adapter's session scope.
        """
        ...

    def rollback(self) -> None:
        """Discard all staged writes."""
        ...
