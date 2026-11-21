"""Item use cases: list, read, create, update and delete.

The service depends on ports only, so it runs against in-memory fakes in unit
tests. It owns the transaction boundary: repositories flush, and the service
commits once a write has succeeded. A write that finds nothing to act on commits
nothing and raises, so the HTTP layer can answer 404 without knowing about it.

A constraint violation is a ``ConflictError`` whether the repository hits it
while staging the write or the unit of work hits it at commit; the use cases
let it propagate. An unreachable store surfaces as ``ExternalServiceError``
once the error leaves the request's database session.
"""

from app.application.commands.item import CreateItemCommand, UpdateItemCommand
from app.application.dto.item import ItemDTO, ItemPageDTO
from app.domain.constants import DEFAULT_PAGE_SIZE
from app.domain.exceptions import EntityNotFoundError
from app.domain.ports.item_repository import ItemRepositoryPort
from app.domain.ports.unit_of_work import UnitOfWorkPort

ITEM_ENTITY_NAME = "Item"


class ItemService:
    """Orchestrates item use cases over an ``ItemRepositoryPort``."""

    def __init__(
        self, repository: ItemRepositoryPort, unit_of_work: UnitOfWorkPort
    ) -> None:
        """Wire the service.

        Args:
            repository: Item storage. Must flush only and never commit.
            unit_of_work: Transaction that the repository's writes belong to.
        """
        self._repository = repository
        self._unit_of_work = unit_of_work

    def list_items(
        self, *, offset: int = 0, limit: int = DEFAULT_PAGE_SIZE
    ) -> ItemPageDTO:
        """List one page of items.

        Args:
            offset: Number of items to skip.
            limit: Maximum number of items on the page. Callers bound it; the
                service passes it through unchanged.

        Returns:
            The page and the total item count across all pages.
        """
        page = self._repository.list_page(offset=offset, limit=limit)
        return ItemPageDTO(
            items=tuple(ItemDTO.from_entity(item) for item in page),
            total=self._repository.count(),
        )

    def get_item(self, item_id: str) -> ItemDTO:
        """Fetch one item.

        Args:
            item_id: Identifier of the item.

        Returns:
            The item.

        Raises:
            EntityNotFoundError: No item has that id.
        """
        item = self._repository.get(item_id)
        if item is None:
            raise _item_not_found(item_id)
        return ItemDTO.from_entity(item)

    def create_item(self, command: CreateItemCommand) -> ItemDTO:
        """Create an item and commit.

        Args:
            command: Values of the new item.

        Returns:
            The created item with its generated id.

        Raises:
            DomainValidationError: A value breaks a business rule. Nothing is
                written.
            ConflictError: The write or the commit hit an integrity constraint.
        """
        created = self._repository.add(command.to_new_item())
        self._unit_of_work.commit()
        return ItemDTO.from_entity(created)

    def update_item(self, command: UpdateItemCommand) -> ItemDTO:
        """Change an item and commit.

        Args:
            command: Target id and the fields to change.

        Returns:
            The item after the change.

        Raises:
            DomainValidationError: A provided value breaks a business rule.
                Nothing is written.
            EntityNotFoundError: No item has that id. Nothing is committed.
            ConflictError: The write or the commit hit an integrity constraint.
        """
        updated = self._repository.update(command.item_id, command.to_changes())
        if updated is None:
            raise _item_not_found(command.item_id)
        self._unit_of_work.commit()
        return ItemDTO.from_entity(updated)

    def delete_item(self, item_id: str) -> None:
        """Delete an item and commit.

        Args:
            item_id: Identifier of the item to delete.

        Raises:
            EntityNotFoundError: No item has that id. Nothing is committed.
            ConflictError: The write or the commit hit an integrity constraint.
        """
        if not self._repository.delete(item_id):
            raise _item_not_found(item_id)
        self._unit_of_work.commit()


def _item_not_found(item_id: str) -> EntityNotFoundError:
    return EntityNotFoundError(ITEM_ENTITY_NAME, log_context={"item_id": item_id})
