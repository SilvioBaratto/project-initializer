"""Unit tests for the item commands, DTOs and ItemService, run against fakes."""

from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest

from app.application.commands.item import CreateItemCommand, UpdateItemCommand
from app.application.dto.item import ItemDTO, ItemPageDTO
from app.application.services.item_service import ItemService
from app.domain.constants import DEFAULT_PAGE_SIZE
from app.domain.entities.item import UNSET, Item, ItemChanges, NewItem
from app.domain.exceptions import (
    ConflictError,
    DomainValidationError,
    EntityNotFoundError,
)
from tests.fakes import FIXED_NOW, FakeItemRepository, FakeUnitOfWork, make_item


class _ConflictingUnitOfWork(FakeUnitOfWork):
    """Unit of work whose commit hits an integrity constraint."""

    def commit(self) -> None:
        """Raise like a real adapter that detected a constraint violation."""
        raise ConflictError()


def _stored_item(item_id: str, *, minutes_old: int = 0, name: str = "Widget") -> Item:
    return make_item(
        item_id,
        name=name,
        description="A widget",
        price=9.99,
        created_at=FIXED_NOW - timedelta(minutes=minutes_old),
    )


@pytest.fixture
def unit_of_work() -> FakeUnitOfWork:
    """Provide a fresh unit of work whose commits the test can count."""
    return FakeUnitOfWork()


@pytest.fixture
def repository() -> FakeItemRepository:
    """Provide an empty in-memory item repository."""
    return FakeItemRepository()


@pytest.fixture
def service(repository, unit_of_work) -> ItemService:
    """Provide an ItemService wired to the empty repository and the unit of work."""
    return ItemService(repository, unit_of_work)


@pytest.mark.unit
def test_when_create_command_converted_then_new_item_carries_the_values():
    """when a create command is converted, the new item carries every value.

    Validates app.application.commands.item.CreateItemCommand.to_new_item().
    """
    command = CreateItemCommand(
        name="Widget", description="A widget", price=9.99, is_active=False
    )

    assert command.to_new_item() == NewItem(
        name="Widget", description="A widget", price=9.99, is_active=False
    )


@pytest.mark.unit
def test_when_create_command_invalid_then_conversion_raises_validation_error():
    """when a create command holds a blank name, conversion fails validation.

    Validates app.application.commands.item.CreateItemCommand.to_new_item().
    """
    with pytest.raises(DomainValidationError):
        CreateItemCommand(name=" ").to_new_item()


@pytest.mark.unit
def test_when_update_command_sets_nothing_then_changes_are_empty():
    """when an update command sets no field, its changes provide nothing.

    Validates app.application.commands.item.UpdateItemCommand.to_changes().
    """
    changes = UpdateItemCommand(item_id="item-1").to_changes()

    assert changes == ItemChanges()
    assert changes.provided_fields() == {}


@pytest.mark.unit
def test_when_update_command_sets_none_then_changes_clear_the_field():
    """when an update command sets a field to None, the changes provide None.

    Validates app.application.commands.item.UpdateItemCommand.to_changes().
    """
    command = UpdateItemCommand(item_id="item-1", description=None, name="Renamed")

    assert command.to_changes().provided_fields() == {
        "name": "Renamed",
        "description": None,
    }
    assert command.price is UNSET


@pytest.mark.unit
def test_when_update_command_invalid_then_conversion_raises_validation_error():
    """when an update command sets name to None, conversion fails validation.

    Validates app.application.commands.item.UpdateItemCommand.to_changes().
    """
    with pytest.raises(DomainValidationError):
        UpdateItemCommand(item_id="item-1", name=None).to_changes()  # type: ignore[arg-type]


@pytest.mark.unit
def test_when_entity_copied_then_dto_holds_every_field():
    """when an entity is copied into a DTO, every field carries over.

    Validates app.application.dto.item.ItemDTO.from_entity().
    """
    item = _stored_item("item-1")

    dto = ItemDTO.from_entity(item)

    assert (dto.id, dto.name, dto.description, dto.price, dto.is_active) == (
        item.id,
        item.name,
        item.description,
        item.price,
        item.is_active,
    )
    assert (dto.created_at, dto.updated_at) == (item.created_at, item.updated_at)


@pytest.mark.unit
def test_when_dto_modified_then_frozen_error_is_raised():
    """when a DTO field is assigned, the dataclass refuses it.

    Validates app.application.dto.item.ItemDTO.
    """
    dto = ItemDTO.from_entity(_stored_item("item-1"))

    with pytest.raises(FrozenInstanceError):
        dto.name = "Other"  # type: ignore[misc]


@pytest.mark.unit
def test_when_no_items_exist_then_empty_page_is_listed(service):
    """when there are no items, the page is empty and the total is zero.

    Validates app.application.services.item_service.ItemService.list_items().
    """
    assert service.list_items() == ItemPageDTO(items=(), total=0)


@pytest.mark.unit
def test_when_items_listed_then_newest_first_with_total(unit_of_work):
    """when items are listed, they come newest first together with the total.

    Validates app.application.services.item_service.ItemService.list_items().
    """
    stored = [
        _stored_item("old", minutes_old=20),
        _stored_item("new", minutes_old=0),
        _stored_item("mid", minutes_old=10),
    ]

    page = ItemService(FakeItemRepository(stored), unit_of_work).list_items()

    assert [item.id for item in page.items] == ["new", "mid", "old"]
    assert page.total == len(stored)
    assert all(isinstance(item, ItemDTO) for item in page.items)


@pytest.mark.unit
def test_when_offset_and_limit_given_then_they_reach_the_repository(unit_of_work):
    """when offset and limit are given, the page is that slice and total stays full.

    Validates app.application.services.item_service.ItemService.list_items().
    """
    stored = [_stored_item(f"item-{age}", minutes_old=age) for age in range(5)]

    page = ItemService(FakeItemRepository(stored), unit_of_work).list_items(
        offset=1, limit=2
    )

    assert [item.id for item in page.items] == ["item-1", "item-2"]
    assert page.total == len(stored)


@pytest.mark.unit
def test_when_offset_is_past_the_end_then_page_is_empty_but_total_is_kept(
    unit_of_work,
):
    """when the offset is past the last item, the page is empty and the total remains.

    Validates app.application.services.item_service.ItemService.list_items().
    """
    repository = FakeItemRepository([_stored_item("item-1")])

    page = ItemService(repository, unit_of_work).list_items(offset=10, limit=5)

    assert page == ItemPageDTO(items=(), total=1)


@pytest.mark.unit
def test_when_limit_omitted_then_default_page_size_applies(unit_of_work):
    """when no limit is given, at most DEFAULT_PAGE_SIZE items are returned.

    Validates app.application.services.item_service.ItemService.list_items().
    """
    stored = [
        _stored_item(f"item-{age:04d}", minutes_old=age)
        for age in range(DEFAULT_PAGE_SIZE + 1)
    ]

    page = ItemService(FakeItemRepository(stored), unit_of_work).list_items()

    assert len(page.items) == DEFAULT_PAGE_SIZE
    assert page.total == DEFAULT_PAGE_SIZE + 1


@pytest.mark.unit
def test_when_items_listed_then_nothing_is_committed(service, unit_of_work):
    """when items are listed, the unit of work is not committed.

    Validates app.application.services.item_service.ItemService.list_items().
    """
    service.list_items()

    assert unit_of_work.commits == 0


@pytest.mark.unit
def test_when_existing_id_fetched_then_item_dto_is_returned(unit_of_work):
    """when an existing id is fetched, the matching item DTO is returned.

    Validates app.application.services.item_service.ItemService.get_item().
    """
    stored = _stored_item("item-1")
    service = ItemService(FakeItemRepository([stored]), unit_of_work)

    assert service.get_item("item-1") == ItemDTO.from_entity(stored)
    assert unit_of_work.commits == 0


@pytest.mark.unit
def test_when_missing_id_fetched_then_not_found_is_raised(service):
    """when a missing id is fetched, EntityNotFoundError names the item and the id.

    Validates app.application.services.item_service.ItemService.get_item().
    """
    with pytest.raises(EntityNotFoundError) as raised:
        service.get_item("does-not-exist")

    assert raised.value.public_message == "Item not found"
    assert raised.value.log_context == {"item_id": "does-not-exist"}
    assert "does-not-exist" not in str(raised.value)


@pytest.mark.unit
def test_when_item_created_then_dto_is_returned_and_one_commit_made(
    service, unit_of_work
):
    """when an item is created, its DTO is returned and the work is committed once.

    Validates app.application.services.item_service.ItemService.create_item().
    """
    created = service.create_item(
        CreateItemCommand(name="Widget", description="A widget", price=9.99)
    )

    assert isinstance(created, ItemDTO)
    assert created.id
    assert (created.name, created.description, created.price) == (
        "Widget",
        "A widget",
        9.99,
    )
    assert created.is_active is True
    assert unit_of_work.commits == 1
    assert service.get_item(created.id) == created


@pytest.mark.unit
def test_when_invalid_item_created_then_nothing_is_stored_or_committed(
    service, repository, unit_of_work
):
    """when the command breaks a business rule, nothing is stored or committed.

    Validates app.application.services.item_service.ItemService.create_item().
    """
    with pytest.raises(DomainValidationError):
        service.create_item(CreateItemCommand(name="Widget", price=-1.0))

    assert repository.count() == 0
    assert unit_of_work.commits == 0


@pytest.mark.unit
def test_when_commit_conflicts_then_create_propagates_the_conflict(repository):
    """when the commit hits a constraint, the conflict reaches the caller.

    Validates app.application.services.item_service.ItemService.create_item().
    """
    service = ItemService(repository, _ConflictingUnitOfWork())

    with pytest.raises(ConflictError):
        service.create_item(CreateItemCommand(name="Widget"))


@pytest.mark.unit
def test_when_existing_item_updated_then_only_given_fields_change(unit_of_work):
    """when an item is updated, provided fields change, others stay, one commit is made.

    Validates app.application.services.item_service.ItemService.update_item().
    """
    stored = _stored_item("item-1")
    service = ItemService(FakeItemRepository([stored]), unit_of_work)

    updated = service.update_item(
        UpdateItemCommand(item_id="item-1", name="Renamed", price=1.0)
    )

    assert updated.name == "Renamed"
    assert updated.price == 1.0
    assert updated.description == stored.description
    assert updated.is_active is stored.is_active
    assert unit_of_work.commits == 1
    assert service.get_item("item-1") == updated


@pytest.mark.unit
def test_when_description_set_to_none_then_update_clears_it(unit_of_work):
    """when the description is set to None, the stored description is cleared.

    Validates app.application.services.item_service.ItemService.update_item().
    """
    service = ItemService(FakeItemRepository([_stored_item("item-1")]), unit_of_work)

    updated = service.update_item(UpdateItemCommand(item_id="item-1", description=None))

    assert updated.description is None
    assert updated.name == "Widget"


@pytest.mark.unit
def test_when_update_sets_no_field_then_item_is_returned_unchanged(unit_of_work):
    """when an update sets no field, the item is returned as it is.

    Validates app.application.services.item_service.ItemService.update_item().
    """
    stored = _stored_item("item-1")
    service = ItemService(FakeItemRepository([stored]), unit_of_work)

    assert service.update_item(UpdateItemCommand(item_id="item-1")) == (
        ItemDTO.from_entity(stored)
    )


@pytest.mark.unit
def test_when_missing_item_updated_then_not_found_is_raised_without_commit(
    service, unit_of_work
):
    """when a missing item is updated, EntityNotFoundError is raised, no commit.

    Validates app.application.services.item_service.ItemService.update_item().
    """
    with pytest.raises(EntityNotFoundError) as raised:
        service.update_item(UpdateItemCommand(item_id="nope", name="x"))

    assert raised.value.public_message == "Item not found"
    assert raised.value.log_context == {"item_id": "nope"}
    assert unit_of_work.commits == 0


@pytest.mark.unit
def test_when_update_breaks_a_rule_then_item_is_untouched_and_not_committed(
    unit_of_work,
):
    """when an update breaks a rule, the item is untouched and nothing is committed.

    Validates app.application.services.item_service.ItemService.update_item().
    """
    stored = _stored_item("item-1")
    service = ItemService(FakeItemRepository([stored]), unit_of_work)

    with pytest.raises(DomainValidationError):
        service.update_item(UpdateItemCommand(item_id="item-1", price=float("nan")))

    assert service.get_item("item-1") == ItemDTO.from_entity(stored)
    assert unit_of_work.commits == 0


@pytest.mark.unit
def test_when_commit_conflicts_then_update_propagates_the_conflict():
    """when an update's commit hits a constraint, the conflict reaches the caller.

    Validates app.application.services.item_service.ItemService.update_item().
    """
    service = ItemService(
        FakeItemRepository([_stored_item("item-1")]), _ConflictingUnitOfWork()
    )

    with pytest.raises(ConflictError):
        service.update_item(UpdateItemCommand(item_id="item-1", name="Renamed"))


@pytest.mark.unit
def test_when_existing_item_deleted_then_it_is_gone_and_one_commit_made(
    unit_of_work,
):
    """when an item is deleted, it disappears and the work is committed once.

    Validates app.application.services.item_service.ItemService.delete_item().
    """
    service = ItemService(FakeItemRepository([_stored_item("item-1")]), unit_of_work)

    assert service.delete_item("item-1") is None

    assert unit_of_work.commits == 1
    with pytest.raises(EntityNotFoundError):
        service.get_item("item-1")


@pytest.mark.unit
def test_when_missing_item_deleted_then_not_found_is_raised_without_commit(
    service, unit_of_work
):
    """when a missing item is deleted, EntityNotFoundError is raised, no commit.

    Validates app.application.services.item_service.ItemService.delete_item().
    """
    with pytest.raises(EntityNotFoundError) as raised:
        service.delete_item("nope")

    assert raised.value.log_context == {"item_id": "nope"}
    assert unit_of_work.commits == 0


@pytest.mark.unit
def test_when_item_deleted_twice_then_second_delete_is_not_found(
    unit_of_work,
):
    """when an item is deleted twice, the second attempt commits nothing.

    Validates app.application.services.item_service.ItemService.delete_item().
    """
    service = ItemService(FakeItemRepository([_stored_item("item-1")]), unit_of_work)
    service.delete_item("item-1")

    with pytest.raises(EntityNotFoundError):
        service.delete_item("item-1")

    assert unit_of_work.commits == 1


@pytest.mark.unit
def test_when_commit_conflicts_then_delete_propagates_the_conflict():
    """when a delete's commit hits a constraint, the conflict reaches the caller.

    Validates app.application.services.item_service.ItemService.delete_item().
    """
    service = ItemService(
        FakeItemRepository([_stored_item("item-1")]), _ConflictingUnitOfWork()
    )

    with pytest.raises(ConflictError):
        service.delete_item("item-1")
