"""Opt-in async SQLAlchemy path over asyncpg, added by the ``--async-db`` flag.

The sync path (``app.infrastructure.database``) stays the default. This module
adds an async engine, a session factory and the ``get_async_db`` dependency,
guarded by their own circuit breaker (``database_async``) and configured from the
same settings.

Importing it plugs the path into the application lifecycle: the engine is
disposed by a shutdown hook and its health is reported by a readiness probe (see
the hook registry in ``app.infrastructure.database``).

asyncpg does not take libpq's query parameters, so ``to_asyncpg_url`` translates
the ones it knows and refuses the rest at startup. asyncpg also lets socket
errors escape unwrapped; ``_open_connection`` wraps them where the connection is
made, so a timeout from unrelated code in a request can never open the breaker.

Required packages (added by the flag): ``asyncpg`` and ``sqlalchemy[asyncio]``.
"""

import logging
import shlex
import ssl
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from urllib.parse import ParseResult, parse_qsl, urlencode, urlparse, urlunparse

import asyncpg
from sqlalchemy import event, select
from sqlalchemy.engine import Dialect
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import ConnectionPoolEntry

from app.domain.exceptions import DomainError
from app.infrastructure.circuit_breaker import CircuitState
from app.infrastructure.database import (
    application_name,
    build_database_breaker,
    mark_exercised_on_first_connection,
    register_readiness_probe,
    register_shutdown_hook,
)
from app.infrastructure.errors import translate_database_error
from app.infrastructure.health import DatabaseHealth, DatabaseStatus
from app.infrastructure.settings import Settings, settings

logger = logging.getLogger(__name__)

ASYNC_BREAKER_NAME = "database_async"

ASYNCPG_SCHEME = "postgresql+asyncpg"

# libpq query parameters that ``to_asyncpg_url`` translates into asyncpg
# arguments.
SSL_MODE_PARAMETER = "sslmode"
CONNECT_TIMEOUT_PARAMETER = "connect_timeout"
APPLICATION_NAME_PARAMETER = "application_name"
OPTIONS_PARAMETER = "options"
SSL_ROOT_CERT_PARAMETER = "sslrootcert"
SSL_CERT_PARAMETER = "sslcert"
SSL_KEY_PARAMETER = "sslkey"
SSL_FILE_PARAMETERS = (SSL_ROOT_CERT_PARAMETER, SSL_CERT_PARAMETER, SSL_KEY_PARAMETER)
# Read by SQLAlchemy's own asyncpg dialect from the URL, so it stays in it.
DIALECT_PARAMETERS = ("prepared_statement_cache_size",)
TRANSLATED_PARAMETERS = frozenset(
    {
        SSL_MODE_PARAMETER,
        CONNECT_TIMEOUT_PARAMETER,
        APPLICATION_NAME_PARAMETER,
        OPTIONS_PARAMETER,
        *SSL_FILE_PARAMETERS,
        *DIALECT_PARAMETERS,
    }
)

# Only TLS modes that insist on an encrypted channel can carry certificate files.
CERTIFICATE_SSL_MODES = frozenset({"require", "verify-ca", "verify-full"})
VERIFY_FULL_SSL_MODE = "verify-full"
REQUIRE_SSL_MODE = "require"
OPTION_ASSIGNMENT_FLAG = "-c"
OPTION_LONG_PREFIX = "--"


def to_asyncpg_url(
    url: str,
    *,
    ssl_mode: str | None = None,
    connect_timeout: float | None = None,
    application_name: str | None = None,
) -> tuple[str, dict[str, object]]:
    """Derive an asyncpg URL and its connect arguments from a libpq-style URL.

    SQLAlchemy hands every URL query parameter to ``asyncpg.connect`` as a
    keyword, so an unknown one fails at the first connection with a ``TypeError``.
    This function translates the libpq parameters it knows and refuses the rest.

    Args:
        url: A ``postgresql://`` or ``postgresql+psycopg2://`` URL.
        ssl_mode: libpq TLS mode that wins over a ``sslmode`` in the URL, usually
            ``database_ssl_mode``.
        connect_timeout: Seconds allowed to open a connection; wins over the
            URL's ``connect_timeout``.
        application_name: Name announced to the server; wins over the URL's.

    Returns:
        The ``postgresql+asyncpg`` URL, keeping only the parameters the SQLAlchemy
        dialect reads itself, and the ``connect_args``: ``timeout`` from
        ``connect_timeout``, ``server_settings`` from ``application_name`` and
        ``options``, and ``ssl``. ``ssl`` is the libpq mode string, or an
        ``ssl.SSLContext`` when ``sslrootcert``, ``sslcert`` or ``sslkey`` is
        given. Arguments that are not set are absent and the driver default
        applies.

    Raises:
        ValueError: A query parameter is repeated, unsupported or malformed, or
            certificate files are given without a TLS mode that uses them. The
            message names parameters, never their values, which may be secrets.
        OSError: A certificate file cannot be read.
    """
    parsed = urlparse(url)
    parameters = _query_parameters(parsed.query)
    unsupported = sorted(parameters.keys() - TRANSLATED_PARAMETERS)
    if unsupported:
        raise ValueError(
            "Database URL parameters not supported with asyncpg: "
            + ", ".join(unsupported)
        )
    overrides = {
        SSL_MODE_PARAMETER: ssl_mode,
        CONNECT_TIMEOUT_PARAMETER: connect_timeout,
        APPLICATION_NAME_PARAMETER: application_name,
    }
    effective = parameters | {
        name: str(value) for name, value in overrides.items() if value is not None
    }
    return _asyncpg_url(parsed, parameters), _connect_args(effective)


def _asyncpg_url(parsed: ParseResult, parameters: Mapping[str, str]) -> str:
    kept = [
        (name, parameters[name]) for name in DIALECT_PARAMETERS if name in parameters
    ]
    return urlunparse(
        (
            ASYNCPG_SCHEME,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(kept),
            parsed.fragment,
        )
    )


def _query_parameters(query: str) -> dict[str, str]:
    pairs = parse_qsl(query, keep_blank_values=True)
    parameters = dict(pairs)
    if len(parameters) != len(pairs):
        raise ValueError("Database URL repeats a query parameter")
    return parameters


def _connect_args(parameters: Mapping[str, str]) -> dict[str, object]:
    connect_args: dict[str, object] = {}
    if CONNECT_TIMEOUT_PARAMETER in parameters:
        connect_args["timeout"] = _seconds(parameters[CONNECT_TIMEOUT_PARAMETER])
    server_settings = _server_settings(parameters)
    if server_settings:
        connect_args["server_settings"] = server_settings
    ssl_argument = _ssl_argument(parameters)
    if ssl_argument is not None:
        connect_args["ssl"] = ssl_argument
    return connect_args


def _seconds(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        raise ValueError(
            f"{CONNECT_TIMEOUT_PARAMETER} must be a number of seconds"
        ) from None


def _server_settings(parameters: Mapping[str, str]) -> dict[str, str]:
    server_settings: dict[str, str] = {}
    if OPTIONS_PARAMETER in parameters:
        server_settings.update(_parse_options(parameters[OPTIONS_PARAMETER]))
    if APPLICATION_NAME_PARAMETER in parameters:
        server_settings[APPLICATION_NAME_PARAMETER] = parameters[
            APPLICATION_NAME_PARAMETER
        ]
    return server_settings


def _parse_options(options: str) -> dict[str, str]:
    # libpq's ``options`` is a command-line style string: ``-c name=value`` or
    # ``--name=value``, with backslash-escaped spaces.
    assignments: dict[str, str] = {}
    tokens = iter(shlex.split(options))
    for token in tokens:
        if token == OPTION_ASSIGNMENT_FLAG:
            assignment = next(tokens, "")
        elif token.startswith(OPTION_ASSIGNMENT_FLAG):
            assignment = token.removeprefix(OPTION_ASSIGNMENT_FLAG)
        elif token.startswith(OPTION_LONG_PREFIX):
            assignment = token.removeprefix(OPTION_LONG_PREFIX)
        else:
            raise ValueError(f"{OPTIONS_PARAMETER} holds an unsupported token")
        name, separator, value = assignment.partition("=")
        if not name or not separator:
            raise ValueError(f"{OPTIONS_PARAMETER} holds a malformed assignment")
        assignments[name] = value
    return assignments


def _ssl_argument(parameters: Mapping[str, str]) -> str | ssl.SSLContext | None:
    mode = parameters.get(SSL_MODE_PARAMETER)
    files = {
        name: parameters[name] for name in SSL_FILE_PARAMETERS if name in parameters
    }
    if not files:
        return mode
    if mode not in CERTIFICATE_SSL_MODES:
        raise ValueError(
            "sslrootcert, sslcert and sslkey need sslmode "
            + ", ".join(sorted(CERTIFICATE_SSL_MODES))
        )
    return _ssl_context(mode, files)


def _ssl_context(mode: str, files: Mapping[str, str]) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=files.get(SSL_ROOT_CERT_PARAMETER))
    context.check_hostname = mode == VERIFY_FULL_SSL_MODE
    if mode == REQUIRE_SSL_MODE and SSL_ROOT_CERT_PARAMETER not in files:
        # libpq's ``require`` encrypts without checking the server certificate.
        context.verify_mode = ssl.CERT_NONE
    if SSL_CERT_PARAMETER in files:
        context.load_cert_chain(
            files[SSL_CERT_PARAMETER], keyfile=files.get(SSL_KEY_PARAMETER)
        )
    elif SSL_KEY_PARAMETER in files:
        raise ValueError("sslkey needs sslcert")
    return context


def build_async_engine(app_settings: Settings) -> AsyncEngine:
    """Create the pooled async engine without opening a connection.

    Args:
        app_settings: Source of the URL, the TLS mode, the connect timeout, the
            application name and every pool setting.

    Returns:
        An engine that hides bound parameters from error messages and reports a
        failed connect as an ``OperationalError``.

    Raises:
        ValueError: The URL carries a parameter asyncpg cannot take.
    """
    url, connect_args = to_asyncpg_url(
        app_settings.database_url,
        ssl_mode=app_settings.database_ssl_mode,
        connect_timeout=app_settings.database_connect_timeout,
        application_name=application_name(app_settings),
    )
    engine = create_async_engine(
        url,
        connect_args=connect_args,
        echo=app_settings.database_echo,
        pool_size=app_settings.database_pool_size,
        max_overflow=app_settings.database_max_overflow,
        pool_timeout=app_settings.database_pool_timeout,
        pool_recycle=app_settings.database_pool_recycle,
        pool_pre_ping=app_settings.database_pool_pre_ping,
        hide_parameters=True,
    )
    event.listen(engine.sync_engine, "do_connect", _open_connection)
    return engine


def _open_connection(
    dialect: Dialect,
    _connection_record: ConnectionPoolEntry,
    connect_args: tuple[object, ...],
    connect_kwargs: dict[str, object],
) -> DBAPIConnection:
    # asyncpg raises socket and server errors from ``connect`` unwrapped, so the
    # breaker could not tell them from an unrelated OSError raised elsewhere in
    # a request. Wrapping them here, where the connection is made, is what lets
    # the breaker ignore every other OSError.
    try:
        return dialect.connect(*connect_args, **connect_kwargs)
    except (OSError, asyncpg.PostgresError) as error:
        raise OperationalError(None, None, error) from error


async_engine = build_async_engine(settings)
async_session_factory = async_sessionmaker(
    bind=async_engine, autoflush=False, expire_on_commit=False
)
async_database_breaker = build_database_breaker(settings, name=ASYNC_BREAKER_NAME)


@asynccontextmanager
async def async_session_scope() -> AsyncIterator[AsyncSession]:
    """Provide an async session for one unit of work.

    Leaving the block without committing discards the changes, because closing
    the session rolls back. The breaker hears a verdict only if the block really
    used the database.

    Yields:
        An ``AsyncSession`` bound to the pooled async engine.

    Raises:
        CircuitOpenError: The async database breaker is open.
        DatabaseUnavailableError: The database could not be reached.
        ConflictError: An integrity constraint rejected a write, or the
            transaction lost a deadlock or serialization race.
        DatabaseOperationError: Any other database error. The driver error is
            chained and never logged here: the exception handler logs once.
    """
    async with async_session_factory() as session:
        try:
            with async_database_breaker.guard() as call:
                mark_exercised_on_first_connection(session.sync_session, call)
                yield session
        except SQLAlchemyError as error:
            raise translate_database_error(error) from error


async def get_async_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields one async session per request.

    The caller commits through the async unit of work. Leaving without
    committing discards the changes, because closing the session rolls back.

    Yields:
        An ``AsyncSession`` bound to the pooled async engine.

    Raises:
        CircuitOpenError: The async database breaker is open.
        DatabaseUnavailableError: The database could not be reached.
        ConflictError: An integrity constraint rejected a write.
        DatabaseOperationError: Any other database error.
    """
    async with async_session_scope() as session:
        yield session


async def probe_async_database() -> DatabaseHealth:
    """Check that the async path answers a trivial query.

    Registered as a readiness probe on import. It goes through the async
    breaker, so it is also the trial call that closes a half-open circuit.

    Returns:
        ``DOWN`` when the circuit is open (no connection is attempted) or the
        query fails; otherwise ``UP``. It never raises.
    """
    if async_database_breaker.state is CircuitState.OPEN:
        return DatabaseHealth(DatabaseStatus.DOWN, CircuitState.OPEN)
    try:
        async with async_session_scope() as session:
            await session.execute(select(1))
    except (DomainError, SQLAlchemyError) as error:
        logger.warning(
            "database.probe_failed",
            extra={"error_type": type(error).__name__, "breaker": ASYNC_BREAKER_NAME},
        )
        return DatabaseHealth(DatabaseStatus.DOWN, async_database_breaker.state)
    return DatabaseHealth(DatabaseStatus.UP, async_database_breaker.state)


async def dispose_async_engine() -> None:
    """Close the pooled connections.

    Registered as a shutdown hook on import, so the application's shutdown path
    runs it through ``run_shutdown_hooks``.
    """
    await async_engine.dispose()


register_shutdown_hook(dispose_async_engine)
register_readiness_probe(ASYNC_BREAKER_NAME, probe_async_database)
