"""Integration tests for the SQLAlchemy item repository and unit of work.

Repository tests use the shared ``db_session`` fixture, a session joined to an
outer transaction that is rolled back after each test. The unit-of-work and
conflict tests need real commits and real constraints, so they build a
file-backed SQLite database under ``tmp_path``. A file with ``NullPool`` gives
every session its own connection, so a second session only sees what the first
one really committed; a shared in-memory connection would show uncommitted rows
too and could not tell a commit from a flush.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.domain.constants import ENTITY_ID_LENGTH
from app.domain.entities.item import UNSET, Item, ItemChanges, NewItem
from app.domain.exceptions import ConflictError
from app.domain.ports.item_repository import ItemRepositoryPort
from app.domain.ports.unit_of_work import UnitOfWorkPort
from app.infrastructure.orm.base import Base
from app.infrastructure.orm.item import ItemRecord
from app.infrastructure.repositories.item import SqlAlchemyItemRepository
from app.infrastructure.unit_of_work import SqlAlchemyUnitOfWork, flush_or_conflict

BASE_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
SEEDED_ITEM_COUNT = 2
SEEDED_PRICE = 5.0
UNIQUE_NAME_INDEX = "CREATE UNIQUE INDEX uq_items_name ON items (name)"


@pytest.fixture
def repository(db_session: Session) -> SqlAlchemyItemRepository:
    """Repository bound to the rolled-back test session."""
    return SqlAlchemyItemRepository(db_session)


@pytest.fixture
def committing_engine(tmp_path) -> Iterator[Engine]:
    """File-backed engine where every session gets its own connection."""
    engine = create_engine(f"sqlite:///{tmp_path / 'items.db'}", poolclass=NullPool)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def committing_session(committing_engine: Engine) -> Iterator[Session]:
    """Session on the file-backed database where commits are real."""
    with Session(committing_engine, autoflush=False, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def unique_name_session(committing_engine: Engine) -> Iterator[Session]:
    """Session on a database that rejects two items with the same name."""
    with committing_engine.begin() as connection:
        connection.execute(text(UNIQUE_NAME_INDEX))
    with Session(committing_engine, autoflush=False, expire_on_commit=False) as session:
        yield session


def add_record(
    session: Session, *, item_id: str, name: str, created_at: datetime
) -> None:
    """Insert a row with an explicit id and creation time, bypassing the repository.

    ``updated_at`` starts equal to ``created_at`` so a later update can be seen
    to move it.
    """
    session.add(
        ItemRecord(id=item_id, name=name, created_at=created_at, updated_at=created_at)
    )
    session.flush()


@pytest.mark.integration
def test_when_repository_is_built_then_it_satisfies_the_port(repository, db_session):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository."""
    assert isinstance(repository, ItemRepositoryPort)
    assert isinstance(SqlAlchemyUnitOfWork(db_session), UnitOfWorkPort)


@pytest.mark.integration
def test_when_item_is_added_then_a_domain_entity_with_generated_fields_is_returned(
    repository,
):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.add()."""
    created = repository.add(NewItem(name="Widget", description="A widget", price=9.99))

    assert type(created) is Item
    assert len(created.id) == ENTITY_ID_LENGTH
    assert (created.name, created.description, created.price) == (
        "Widget",
        "A widget",
        9.99,
    )
    assert created.is_active is True
    assert isinstance(created.created_at, datetime)
    assert isinstance(created.updated_at, datetime)


@pytest.mark.integration
def test_when_an_item_is_added_then_it_is_only_flushed_and_a_rollback_discards_it(
    repository, db_session
):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.add()."""
    repository.add(NewItem(name="Draft"))

    db_session.rollback()

    assert repository.count() == 0


@pytest.mark.integration
def test_when_an_item_is_added_then_get_returns_the_same_entity(repository):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.get()."""
    created = repository.add(NewItem(name="Readback", is_active=False))

    assert repository.get(created.id) == created


@pytest.mark.integration
def test_when_the_id_is_unknown_then_get_returns_none(repository):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.get()."""
    assert repository.get("does-not-exist") is None


@pytest.mark.integration
def test_when_items_are_listed_then_newest_comes_first_and_ties_break_by_id(
    repository, db_session
):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.list_page()."""
    add_record(db_session, item_id="b", name="tie-b", created_at=BASE_TIME)
    add_record(db_session, item_id="a", name="tie-a", created_at=BASE_TIME)
    add_record(
        db_session,
        item_id="z",
        name="newest",
        created_at=BASE_TIME + timedelta(hours=1),
    )
    add_record(
        db_session,
        item_id="y",
        name="oldest",
        created_at=BASE_TIME - timedelta(hours=1),
    )

    names = [item.name for item in repository.list_page(offset=0, limit=10)]

    assert names == ["newest", "tie-a", "tie-b", "oldest"]


@pytest.mark.integration
@pytest.mark.parametrize(
    ("offset", "limit", "expected_names"),
    [
        (0, 2, ["item-0", "item-1"]),
        (2, 2, ["item-2", "item-3"]),
        (4, 2, ["item-4"]),
        (5, 2, []),
        (0, 1, ["item-0"]),
    ],
)
def test_when_a_page_is_requested_then_offset_and_limit_are_honoured(
    repository, db_session, offset, limit, expected_names
):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.list_page()."""
    for index in range(5):
        add_record(
            db_session,
            item_id=f"id-{index}",
            name=f"item-{index}",
            created_at=BASE_TIME - timedelta(minutes=index),
        )

    page = repository.list_page(offset=offset, limit=limit)

    assert [item.name for item in page] == expected_names


@pytest.mark.integration
def test_when_items_exist_then_count_ignores_paging(repository):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.count()."""
    assert repository.count() == 0

    repository.add(NewItem(name="first"))
    repository.add(NewItem(name="second"))

    assert repository.count() == SEEDED_ITEM_COUNT


@pytest.mark.integration
def test_when_fields_are_provided_then_update_changes_only_those(repository):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.update()."""
    created = repository.add(
        NewItem(name="Old", description="keep", price=SEEDED_PRICE)
    )

    updated = repository.update(created.id, ItemChanges(name="New", is_active=False))

    assert updated is not None
    assert (updated.name, updated.is_active) == ("New", False)
    assert (updated.description, updated.price) == ("keep", SEEDED_PRICE)
    assert updated.id == created.id


@pytest.mark.integration
def test_when_an_item_is_updated_then_updated_at_advances_and_created_at_does_not(
    repository, db_session
):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.update()."""
    add_record(db_session, item_id="aged", name="Aged", created_at=BASE_TIME)

    updated = repository.update("aged", ItemChanges(name="Renamed"))

    assert updated is not None
    assert updated.created_at.replace(tzinfo=None) == BASE_TIME.replace(tzinfo=None)
    assert updated.updated_at.replace(tzinfo=None) > BASE_TIME.replace(tzinfo=None)


@pytest.mark.integration
def test_when_a_field_is_set_to_none_then_update_clears_it(repository):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.update()."""
    created = repository.add(
        NewItem(name="Item", description="text", price=SEEDED_PRICE)
    )

    updated = repository.update(created.id, ItemChanges(description=None))

    assert updated is not None
    assert updated.description is None
    assert updated.price == SEEDED_PRICE


@pytest.mark.integration
def test_when_nothing_is_provided_then_update_returns_the_item_unchanged(repository):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.update()."""
    created = repository.add(NewItem(name="Stable"))

    updated = repository.update(created.id, ItemChanges(name=UNSET))

    assert updated == created


@pytest.mark.integration
def test_when_the_id_is_unknown_then_update_returns_none(repository):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.update()."""
    assert repository.update("does-not-exist", ItemChanges(name="x")) is None


@pytest.mark.integration
def test_when_an_item_is_deleted_then_it_is_gone_and_true_is_returned(repository):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.delete()."""
    created = repository.add(NewItem(name="Doomed"))

    assert repository.delete(created.id) is True
    assert repository.get(created.id) is None


@pytest.mark.integration
def test_when_the_id_is_unknown_then_delete_returns_false(repository):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.delete()."""
    assert repository.delete("does-not-exist") is False


@pytest.mark.unit
def test_when_a_record_is_printed_then_only_its_id_is_shown():
    """Validates app.infrastructure.orm.item.ItemRecord.__repr__()."""
    record = ItemRecord(id="abc", name="Confidential name")

    assert repr(record) == "<ItemRecord id=abc>"


@pytest.mark.integration
def test_when_the_unit_of_work_commits_then_another_connection_sees_the_item(
    committing_session, committing_engine
):
    """Validates app.infrastructure.unit_of_work.SqlAlchemyUnitOfWork.commit()."""
    created = SqlAlchemyItemRepository(committing_session).add(NewItem(name="Durable"))

    SqlAlchemyUnitOfWork(committing_session).commit()

    with Session(committing_engine) as other:
        assert SqlAlchemyItemRepository(other).get(created.id) is not None


@pytest.mark.integration
def test_when_the_unit_of_work_has_not_committed_then_another_connection_sees_nothing(
    committing_session, committing_engine
):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.add()."""
    created = SqlAlchemyItemRepository(committing_session).add(NewItem(name="Staged"))

    with Session(committing_engine) as other:
        assert SqlAlchemyItemRepository(other).get(created.id) is None


@pytest.mark.integration
def test_when_the_unit_of_work_rolls_back_then_the_staged_item_is_discarded(
    committing_session,
):
    """Validates app.infrastructure.unit_of_work.SqlAlchemyUnitOfWork.rollback()."""
    repository = SqlAlchemyItemRepository(committing_session)
    repository.add(NewItem(name="Discarded"))

    SqlAlchemyUnitOfWork(committing_session).rollback()

    assert repository.count() == 0


@pytest.mark.integration
def test_when_a_constraint_rejects_the_commit_then_conflict_error_is_raised(
    committing_session,
):
    """Validates app.infrastructure.unit_of_work.SqlAlchemyUnitOfWork.commit()."""
    for _ in range(2):
        committing_session.add(ItemRecord(id="duplicate", name="Clash"))
    unit_of_work = SqlAlchemyUnitOfWork(committing_session)

    with pytest.raises(ConflictError) as raised:
        unit_of_work.commit()

    assert isinstance(raised.value.__cause__, IntegrityError)
    assert "duplicate" not in raised.value.public_message
    assert SqlAlchemyItemRepository(committing_session).count() == 0


@pytest.mark.integration
def test_when_a_flush_violates_a_constraint_then_flush_or_conflict_raises_a_conflict(
    committing_session,
):
    """Validates app.infrastructure.unit_of_work.flush_or_conflict()."""
    for _ in range(2):
        committing_session.add(ItemRecord(id="duplicate", name="Clash"))

    with pytest.raises(ConflictError) as raised:
        flush_or_conflict(committing_session)

    assert isinstance(raised.value.__cause__, IntegrityError)
    assert raised.value.log_context == {"error_type": "IntegrityError"}
    assert SqlAlchemyItemRepository(committing_session).count() == 0


@pytest.mark.integration
def test_when_the_flush_succeeds_then_flush_or_conflict_stages_the_write(
    committing_session,
):
    """Validates app.infrastructure.unit_of_work.flush_or_conflict()."""
    committing_session.add(ItemRecord(id="fine", name="Fine"))

    flush_or_conflict(committing_session)

    assert SqlAlchemyItemRepository(committing_session).count() == 1


@pytest.mark.integration
def test_when_an_insert_violates_a_constraint_then_add_raises_a_conflict_and_leaves_the_session_usable(
    unique_name_session,
):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.add()."""
    repository = SqlAlchemyItemRepository(unique_name_session)
    repository.add(NewItem(name="Widget"))

    with pytest.raises(ConflictError) as raised:
        repository.add(NewItem(name="Widget"))

    assert isinstance(raised.value.__cause__, IntegrityError)
    assert raised.value.log_context == {"error_type": "IntegrityError"}
    assert "Widget" not in f"{raised.value} {raised.value.log_context}"
    assert repository.count() == 0
    assert repository.add(NewItem(name="Gadget")).name == "Gadget"


@pytest.mark.integration
def test_when_an_update_violates_a_constraint_then_it_raises_a_conflict(
    unique_name_session,
):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.update()."""
    repository = SqlAlchemyItemRepository(unique_name_session)
    repository.add(NewItem(name="Taken"))
    other = repository.add(NewItem(name="Free"))
    SqlAlchemyUnitOfWork(unique_name_session).commit()

    with pytest.raises(ConflictError) as raised:
        repository.update(other.id, ItemChanges(name="Taken"))

    assert isinstance(raised.value.__cause__, IntegrityError)
    assert repository.get(other.id) == other


@pytest.mark.integration
def test_when_the_item_was_deleted_by_another_transaction_then_update_returns_none(
    committing_session, committing_engine
):
    """Validates app.infrastructure.repositories.item.SqlAlchemyItemRepository.update()."""
    repository = SqlAlchemyItemRepository(committing_session)
    created = repository.add(NewItem(name="Vanishing"))
    SqlAlchemyUnitOfWork(committing_session).commit()
    # The identity map holds rows weakly: without this reference the update would
    # re-read the row, find it gone and never reach the stale write.
    loaded = committing_session.get(ItemRecord, created.id)
    with committing_engine.begin() as connection:
        connection.execute(text("DELETE FROM items"))

    updated = repository.update(created.id, ItemChanges(name="Too late"))

    assert loaded is not None
    assert updated is None
    assert repository.count() == 0
