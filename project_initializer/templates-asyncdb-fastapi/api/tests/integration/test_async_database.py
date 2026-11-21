"""Integration tests for the async repository, unit of work and connect failures.

The repository tests run on a file-backed ``aiosqlite`` database under
``tmp_path`` with ``NullPool``, so every session has its own connection and a
second session only sees what the first one really committed. The connect test
points the real asyncpg driver at a closed local port, which needs no server.
``asyncio_mode = auto`` (pytest.ini) collects the ``async def`` tests.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.domain.entities.item import Item, ItemChanges, NewItem
from app.domain.exceptions import ConflictError
from app.domain.ports.async_item_repository import (
    AsyncItemRepositoryPort,
    AsyncUnitOfWorkPort,
)
from app.infrastructure import database_async
from app.infrastructure.circuit_breaker import CircuitBreaker, CircuitState
from app.infrastructure.database_async import async_session_scope, build_async_engine
from app.infrastructure.errors import DatabaseUnavailableError
from app.infrastructure.orm.base import Base
from app.infrastructure.orm.item import ItemRecord
from app.infrastructure.repositories.item_async import SqlAlchemyAsyncItemRepository
from app.infrastructure.settings import Settings
from app.infrastructure.unit_of_work_async import (
    SqlAlchemyAsyncUnitOfWork,
    flush_or_conflict_async,
)

pytestmark = pytest.mark.integration

BASE_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
UNIQUE_NAME_INDEX = "CREATE UNIQUE INDEX uq_items_name ON items (name)"
CLOSED_PORT_URL = "postgresql://user:password@127.0.0.1:1/app_db"
CONNECT_TIMEOUT_SECONDS = 2
FAILURE_THRESHOLD = 2
SEEDED_ITEM_COUNT = 3


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """File-backed async engine where every session gets its own connection."""
    file_engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'items.db'}", poolclass=NullPool
    )
    async with file_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield file_engine
    await file_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory over the file-backed database."""
    return async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
async def session(session_factory) -> AsyncIterator[AsyncSession]:
    """One session on the file-backed database."""
    async with session_factory() as db:
        yield db


@pytest.fixture
async def unique_name_session(engine, session_factory) -> AsyncIterator[AsyncSession]:
    """Session on a database that rejects two items with the same name."""
    async with engine.begin() as connection:
        await connection.execute(text(UNIQUE_NAME_INDEX))
    async with session_factory() as db:
        yield db


async def add_record(session: AsyncSession, *, item_id: str, name: str) -> None:
    """Insert an old row with an explicit id, bypassing the repository."""
    session.add(
        ItemRecord(id=item_id, name=name, created_at=BASE_TIME, updated_at=BASE_TIME)
    )
    await session.flush()


async def test_when_the_repository_is_built_then_it_satisfies_the_async_ports(session):
    """Validates app.infrastructure.repositories.item_async.SqlAlchemyAsyncItemRepository."""
    assert isinstance(SqlAlchemyAsyncItemRepository(session), AsyncItemRepositoryPort)
    assert isinstance(SqlAlchemyAsyncUnitOfWork(session), AsyncUnitOfWorkPort)


async def test_when_an_item_is_added_then_it_is_returned_as_an_entity_and_readable(
    session,
):
    """Validates app.infrastructure.repositories.item_async.SqlAlchemyAsyncItemRepository.add()."""
    repository = SqlAlchemyAsyncItemRepository(session)

    created = await repository.add(NewItem(name="Widget", price=9.99))

    assert type(created) is Item
    assert created.id
    assert await repository.get(created.id) == created


async def test_when_the_id_is_unknown_then_get_update_and_delete_find_nothing(session):
    """Validates app.infrastructure.repositories.item_async.SqlAlchemyAsyncItemRepository.get()."""
    repository = SqlAlchemyAsyncItemRepository(session)

    assert await repository.get("nope") is None
    assert await repository.update("nope", ItemChanges(name="x")) is None
    assert await repository.delete("nope") is False


async def test_when_items_are_listed_then_newest_comes_first_and_count_ignores_paging(
    session,
):
    """Validates app.infrastructure.repositories.item_async.SqlAlchemyAsyncItemRepository.list_page()."""
    repository = SqlAlchemyAsyncItemRepository(session)
    for index, name in enumerate(["oldest", "middle", "newest"]):
        session.add(
            ItemRecord(
                id=f"id-{index}",
                name=name,
                created_at=BASE_TIME + timedelta(minutes=index),
            )
        )
    await session.flush()

    page = await repository.list_page(offset=1, limit=1)

    assert [item.name for item in page] == ["middle"]
    assert await repository.count() == SEEDED_ITEM_COUNT


async def test_when_an_item_is_updated_then_only_provided_fields_change(session):
    """Validates app.infrastructure.repositories.item_async.SqlAlchemyAsyncItemRepository.update()."""
    repository = SqlAlchemyAsyncItemRepository(session)
    created = await repository.add(NewItem(name="Old", description="keep"))

    updated = await repository.update(created.id, ItemChanges(name="New"))

    assert updated is not None
    assert (updated.name, updated.description) == ("New", "keep")


async def test_when_an_item_is_updated_then_updated_at_advances_and_created_at_does_not(
    session,
):
    """Validates app.infrastructure.repositories.item_async.SqlAlchemyAsyncItemRepository.update()."""
    await add_record(session, item_id="aged", name="Aged")

    updated = await SqlAlchemyAsyncItemRepository(session).update(
        "aged", ItemChanges(name="Renamed")
    )

    assert updated is not None
    assert updated.created_at.replace(tzinfo=None) == BASE_TIME.replace(tzinfo=None)
    assert updated.updated_at.replace(tzinfo=None) > BASE_TIME.replace(tzinfo=None)


async def test_when_an_item_is_deleted_then_a_follow_up_get_finds_nothing(session):
    """Validates app.infrastructure.repositories.item_async.SqlAlchemyAsyncItemRepository.delete()."""
    repository = SqlAlchemyAsyncItemRepository(session)
    created = await repository.add(NewItem(name="Doomed"))

    assert await repository.delete(created.id) is True
    assert await repository.get(created.id) is None


async def test_when_the_unit_of_work_commits_then_another_connection_sees_the_item(
    session_factory,
):
    """Validates app.infrastructure.unit_of_work_async.SqlAlchemyAsyncUnitOfWork.commit()."""
    async with session_factory() as writer:
        created = await SqlAlchemyAsyncItemRepository(writer).add(NewItem(name="Kept"))
        await SqlAlchemyAsyncUnitOfWork(writer).commit()

        async with session_factory() as reader:
            assert (
                await SqlAlchemyAsyncItemRepository(reader).get(created.id) is not None
            )


async def test_when_the_unit_of_work_has_not_committed_then_another_connection_sees_nothing(
    session_factory,
):
    """Validates app.infrastructure.repositories.item_async.SqlAlchemyAsyncItemRepository.add()."""
    async with session_factory() as writer:
        created = await SqlAlchemyAsyncItemRepository(writer).add(
            NewItem(name="Staged")
        )

        async with session_factory() as reader:
            assert await SqlAlchemyAsyncItemRepository(reader).get(created.id) is None


async def test_when_the_unit_of_work_rolls_back_then_the_staged_item_is_discarded(
    session,
):
    """Validates app.infrastructure.unit_of_work_async.SqlAlchemyAsyncUnitOfWork.rollback()."""
    repository = SqlAlchemyAsyncItemRepository(session)
    await repository.add(NewItem(name="Discarded"))

    await SqlAlchemyAsyncUnitOfWork(session).rollback()

    assert await repository.count() == 0


async def test_when_a_constraint_rejects_the_commit_then_conflict_error_is_raised(
    session,
):
    """Validates app.infrastructure.unit_of_work_async.SqlAlchemyAsyncUnitOfWork.commit()."""
    for _ in range(2):
        session.add(ItemRecord(id="duplicate", name="Clash"))

    with pytest.raises(ConflictError) as raised:
        await SqlAlchemyAsyncUnitOfWork(session).commit()

    assert isinstance(raised.value.__cause__, IntegrityError)
    assert await SqlAlchemyAsyncItemRepository(session).count() == 0


async def test_when_a_flush_violates_a_constraint_then_flush_or_conflict_async_raises_a_conflict(
    session,
):
    """Validates app.infrastructure.unit_of_work_async.flush_or_conflict_async()."""
    for _ in range(2):
        session.add(ItemRecord(id="duplicate", name="Clash"))

    with pytest.raises(ConflictError) as raised:
        await flush_or_conflict_async(session)

    assert isinstance(raised.value.__cause__, IntegrityError)
    assert raised.value.log_context == {"error_type": "IntegrityError"}
    assert await SqlAlchemyAsyncItemRepository(session).count() == 0


async def test_when_the_flush_succeeds_then_flush_or_conflict_async_stages_the_write(
    session,
):
    """Validates app.infrastructure.unit_of_work_async.flush_or_conflict_async()."""
    session.add(ItemRecord(id="fine", name="Fine"))

    await flush_or_conflict_async(session)

    assert await SqlAlchemyAsyncItemRepository(session).count() == 1


async def test_when_an_insert_violates_a_constraint_then_add_raises_a_conflict_and_leaves_the_session_usable(
    unique_name_session,
):
    """Validates app.infrastructure.repositories.item_async.SqlAlchemyAsyncItemRepository.add()."""
    repository = SqlAlchemyAsyncItemRepository(unique_name_session)
    await repository.add(NewItem(name="Widget"))

    with pytest.raises(ConflictError) as raised:
        await repository.add(NewItem(name="Widget"))

    assert isinstance(raised.value.__cause__, IntegrityError)
    assert raised.value.log_context == {"error_type": "IntegrityError"}
    assert "Widget" not in f"{raised.value} {raised.value.log_context}"
    assert await repository.count() == 0
    assert (await repository.add(NewItem(name="Gadget"))).name == "Gadget"


async def test_when_an_update_violates_a_constraint_then_it_raises_a_conflict(
    unique_name_session,
):
    """Validates app.infrastructure.repositories.item_async.SqlAlchemyAsyncItemRepository.update()."""
    repository = SqlAlchemyAsyncItemRepository(unique_name_session)
    await repository.add(NewItem(name="Taken"))
    other = await repository.add(NewItem(name="Free"))
    await SqlAlchemyAsyncUnitOfWork(unique_name_session).commit()

    with pytest.raises(ConflictError) as raised:
        await repository.update(other.id, ItemChanges(name="Taken"))

    assert isinstance(raised.value.__cause__, IntegrityError)
    assert await repository.get(other.id) == other


async def test_when_the_item_was_deleted_by_another_transaction_then_update_returns_none(
    session, engine
):
    """Validates app.infrastructure.repositories.item_async.SqlAlchemyAsyncItemRepository.update()."""
    repository = SqlAlchemyAsyncItemRepository(session)
    created = await repository.add(NewItem(name="Vanishing"))
    await SqlAlchemyAsyncUnitOfWork(session).commit()
    # The identity map holds rows weakly: without this reference the update would
    # re-read the row, find it gone and never reach the stale write.
    loaded = await session.get(ItemRecord, created.id)
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM items"))

    updated = await repository.update(created.id, ItemChanges(name="Too late"))

    assert loaded is not None
    assert updated is None
    assert await repository.count() == 0


async def test_when_the_server_refuses_the_connection_then_an_operation_error_with_the_socket_error_is_raised():
    """Validates app.infrastructure.database_async.build_async_engine()."""
    engine = build_async_engine(
        Settings(
            database_url=CLOSED_PORT_URL,
            database_connect_timeout=CONNECT_TIMEOUT_SECONDS,
        )
    )

    try:
        with pytest.raises(OperationalError) as raised:
            async with engine.connect():
                pass
    finally:
        await engine.dispose()

    assert isinstance(raised.value.__cause__, OSError)


def point_sessions_at_closed_port(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[AsyncEngine, CircuitBreaker]:
    """Route ``async_session_scope`` to a closed port behind a fresh breaker.

    Returns:
        The engine, which the caller must dispose, and the breaker guarding it.
    """
    engine = build_async_engine(
        Settings(
            database_url=CLOSED_PORT_URL,
            database_connect_timeout=CONNECT_TIMEOUT_SECONDS,
            database_breaker_failure_threshold=FAILURE_THRESHOLD,
        )
    )
    breaker = database_async.build_database_breaker(
        Settings(database_breaker_failure_threshold=FAILURE_THRESHOLD),
        name=database_async.ASYNC_BREAKER_NAME,
    )
    monkeypatch.setattr(database_async, "async_database_breaker", breaker)
    monkeypatch.setattr(
        database_async,
        "async_session_factory",
        async_sessionmaker(bind=engine, autoflush=False),
    )
    return engine, breaker


async def test_when_the_server_refuses_connections_then_the_breaker_opens_and_the_requests_see_unavailable(
    monkeypatch,
):
    """Validates app.infrastructure.database_async.async_session_scope()."""
    engine, breaker = point_sessions_at_closed_port(monkeypatch)

    try:
        for _ in range(FAILURE_THRESHOLD):
            with pytest.raises(DatabaseUnavailableError) as raised:
                async with async_session_scope() as scoped:
                    await scoped.execute(select(1))
            assert isinstance(raised.value.__cause__, OperationalError)
    finally:
        await engine.dispose()

    assert breaker.state is CircuitState.OPEN
