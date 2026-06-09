"""Unit tests for the opt-in async DB path (#20).

Exercises the asyncpg URL derivation, the async session factory, and the
``AsyncBaseRepository`` CRUD against an in-memory async SQLite (aiosqlite) —
no live PostgreSQL needed. ``asyncio_mode = auto`` (pytest.ini) collects the
``async def`` tests; the module-level async engine is built lazily, so importing
it does not open a connection.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database_async import async_session_factory, get_async_db, to_asyncpg_url
from app.models.base import Base
from app.models.item import Item
from app.repositories.base_async import AsyncBaseRepository
from app.schemas.item import ItemCreate, ItemUpdate


class ItemAsyncRepository(AsyncBaseRepository[Item, ItemCreate, ItemUpdate]):
    """Async Item repository used to exercise the generic CRUD twin."""

    def __init__(self, session: AsyncSession):
        super().__init__(Item, session)


@pytest.fixture
async def session():
    """Yield an AsyncSession bound to a fresh in-memory aiosqlite engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        yield db
    await engine.dispose()


def test_when_url_has_sslmode_then_asyncpg_url_strips_it_and_sets_ssl():
    """when the URL carries sslmode=require, the asyncpg URL drops it and ssl is set."""
    url, connect_args = to_asyncpg_url(
        "postgresql://u:p@host:5432/db?sslmode=require"
    )
    assert url == "postgresql+asyncpg://u:p@host:5432/db"
    assert "sslmode" not in url
    assert "ssl" in connect_args


def test_when_url_has_no_sslmode_then_driver_is_asyncpg_and_no_ssl():
    """when the URL has no sslmode, the driver becomes asyncpg with no ssl arg."""
    url, connect_args = to_asyncpg_url("postgresql://u:p@localhost:5433/app_db")
    assert url == "postgresql+asyncpg://u:p@localhost:5433/app_db"
    assert connect_args == {}


def test_when_session_factory_built_then_it_makes_async_sessions():
    """when the async session factory is built, it produces an AsyncSession."""
    assert isinstance(async_session_factory, async_sessionmaker)
    assert callable(get_async_db)
    assert isinstance(async_session_factory(), AsyncSession)


async def test_when_item_created_then_it_is_returned_with_an_id(session):
    """when an item is created, the persisted item with an id is returned."""
    repo = ItemAsyncRepository(session)
    created = await repo.create(ItemCreate(name="Widget", price=9.99))
    assert created.id
    assert created.name == "Widget"


async def test_when_item_fetched_then_it_is_read_back(session):
    """when a created item is fetched by id, it is read back from the DB."""
    repo = ItemAsyncRepository(session)
    created = await repo.create(ItemCreate(name="Readback"))
    fetched = await repo.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id


async def test_when_items_listed_then_created_item_is_in_the_page(session):
    """when items are listed, a created item appears in the paginated result."""
    repo = ItemAsyncRepository(session)
    created = await repo.create(ItemCreate(name="Listed"))
    items = await repo.get_multi(skip=0, limit=10)
    assert any(it.id == created.id for it in items)


async def test_when_item_updated_then_changes_are_returned(session):
    """when an item is updated, the updated fields are returned."""
    repo = ItemAsyncRepository(session)
    created = await repo.create(ItemCreate(name="Old"))
    updated = await repo.update(created.id, ItemUpdate(name="New"))
    assert updated is not None
    assert updated.name == "New"


async def test_when_missing_item_updated_then_none_is_returned(session):
    """when a missing id is updated, None is returned."""
    repo = ItemAsyncRepository(session)
    assert await repo.update("does-not-exist", ItemUpdate(name="x")) is None


async def test_when_item_deleted_then_subsequent_get_is_none(session):
    """when an item is deleted, a follow-up get returns None."""
    repo = ItemAsyncRepository(session)
    created = await repo.create(ItemCreate(name="Doomed"))
    assert await repo.delete(created.id) is True
    assert await repo.get(created.id) is None


async def test_when_missing_item_deleted_then_false_is_returned(session):
    """when a missing id is deleted, False is returned."""
    repo = ItemAsyncRepository(session)
    assert await repo.delete("nope") is False
