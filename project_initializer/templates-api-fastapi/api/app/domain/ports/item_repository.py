"""Item repository port — the data-access interface the application depends on.

The application layer is typed against this ``Protocol``, never against a
concrete SQLAlchemy repository, so the business logic has no infrastructure
import. The infrastructure repository provides the adapter that implements it;
the API dependency layer wires the two together.

Create/update inputs are declared as ``Any`` on purpose: the concrete adapter
accepts the Pydantic ``ItemCreate``/``ItemUpdate`` DTOs, but naming those here
would pull an API-schema import into the domain and break the boundary. The port
cares about the operations, not the DTO types.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, Sequence, runtime_checkable


@runtime_checkable
class ItemRepositoryPort(Protocol):
    """Data-access operations the item use cases require."""

    def get(self, id: Any) -> Optional[Any]:
        """Return a single item by id, or None if absent."""
        ...

    def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        desc: bool = True,
    ) -> Sequence[Any]:
        """Return a page of items."""
        ...

    def create(self, obj_in: Any) -> Any:
        """Persist a new item (flush only; caller owns the commit)."""
        ...

    def update(self, id: Any, obj_in: Any) -> Optional[Any]:
        """Update an existing item, or None if it does not exist."""
        ...

    def delete(self, id: Any) -> bool:
        """Delete an item, returning whether a row was removed."""
        ...

    def count(self) -> int:
        """Return the total item count."""
        ...

    def commit(self) -> None:
        """Commit the current unit of work.

        The repository owns the session; the application service decides *when*
        to commit (after a successful write) without importing the session type.
        """
        ...
