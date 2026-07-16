"""Opt-in async SQLAlchemy path for FastAPI (additive, isolated overlay).

Provides an async engine + session factory + ``get_async_db`` dependency that
mirror the sync ``app/database.py``, using the asyncpg driver. The sync path
stays the default; this module is only wired in when the generator's
``--async-db`` flag is set (follow-up issue). Pair with ``AsyncBaseRepository``
in ``app/repositories/base_async.py``.

Required deps (added by the flag-wiring issue, not here): ``asyncpg`` and
``sqlalchemy[asyncio]``.
"""

import ssl
from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.settings import settings


def to_asyncpg_url(url: str) -> tuple[str, dict]:
    """Derive an asyncpg URL + connect_args from a sync PostgreSQL URL.

    asyncpg rejects libpq's ``sslmode`` query param (it raises on the unknown
    parameter), so it is stripped from the query and mapped to an ``ssl``
    connect_arg — any mode except ``disable`` enables SSL. Handles
    ``postgresql://`` and ``postgresql+psycopg2://`` inputs alike.
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    sslmode = params.pop("sslmode", [None])[0]
    query = urlencode({key: value[0] for key, value in params.items()})
    asyncpg_url = urlunparse(
        (
            "postgresql+asyncpg",
            parsed.netloc,
            parsed.path,
            parsed.params,
            query,
            parsed.fragment,
        )
    )
    connect_args: dict = {}
    if sslmode and sslmode != "disable":
        connect_args["ssl"] = ssl.create_default_context()
    return asyncpg_url, connect_args


_async_url, _connect_args = to_asyncpg_url(settings.database_url)

async_engine = create_async_engine(
    _async_url,
    connect_args=_connect_args,
    pool_pre_ping=settings.database_pool_pre_ping,
    echo=settings.database_echo,
)

# async_sessionmaker(expire_on_commit=False) — objects stay usable after commit.
async_session_factory = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an ``AsyncSession`` (closed/rolled back on exit)."""
    async with async_session_factory() as session:
        yield session
