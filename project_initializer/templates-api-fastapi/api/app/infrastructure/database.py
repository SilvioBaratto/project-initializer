"""Synchronous SQLAlchemy engine and session management.

``DatabaseManager`` owns the engine, hands out sessions through a circuit
breaker, and translates every driver failure into a domain error (see
``app.infrastructure.errors``). Driver errors never reach the logs with their
text: it carries the SQL statement and sometimes bound values such as emails.
The single error record per failure is the one the API's exception handler
writes from the translated error's ``log_context``.

Optional components, such as the async overlay, plug into the application's
lifecycle through the hook registry at the end of this module: a shutdown hook
releases their resources and a readiness probe reports their health.

The schema is owned by Alembic. Nothing here creates tables.
"""

import inspect
import logging
import threading
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, NamedTuple

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    GuardedCall,
)
from app.infrastructure.errors import (
    CONNECTIVITY_ERRORS,
    is_connectivity_failure,
    translate_database_error,
)
from app.infrastructure.settings import Settings, settings

if TYPE_CHECKING:
    from app.infrastructure.health import DatabaseHealth

logger = logging.getLogger(__name__)

BREAKER_NAME = "database"
APPLICATION_NAME_PREFIX = "app-api"
POSTGRES_BACKEND = "postgresql"
# SQLAlchemy 2.1 runs a driverless ``postgresql://`` URL on psycopg 3, which the
# project does not install; psycopg2 is the driver it ships.
PSYCOPG2_DRIVERNAME = "postgresql+psycopg2"

# Without TCP keepalives a firewall or NAT can drop an idle pooled connection
# silently, and the next request then hangs until the OS gives up.
KEEPALIVES_ENABLED = 1
KEEPALIVES_IDLE_SECONDS = 30
KEEPALIVES_INTERVAL_SECONDS = 10
KEEPALIVES_PROBE_COUNT = 3

ShutdownHook = Callable[[], Awaitable[None] | None]
# The health module imports this one, so the result type is a forward reference.
ReadinessProbe = Callable[[], Awaitable["DatabaseHealth"]]


class _Runtime(NamedTuple):
    engine: Engine
    sessions: sessionmaker[Session]


def application_name(app_settings: Settings) -> str:
    """Name the application announces to the database server.

    Args:
        app_settings: Application settings; the environment is part of the name.

    Returns:
        A label that identifies this service in ``pg_stat_activity``.
    """
    return f"{APPLICATION_NAME_PREFIX}-{app_settings.environment}"


def with_psycopg2_driver(url: str | URL) -> URL:
    """Parse a database URL and name the psycopg2 driver when it names none.

    The settings default, the compose file, the generated ``.env`` and the URLs
    the Supabase dashboard hands out are all driverless ``postgresql://`` URLs.

    Args:
        url: Database URL from the settings.

    Returns:
        The parsed URL; a driverless PostgreSQL one with ``postgresql+psycopg2``
        as its driver name. Every other part, the password included, is kept, so
        pass the returned object on rather than its string form, which masks the
        password. A URL that names its driver, or another backend, is unchanged.
    """
    parsed = make_url(url)
    if parsed.drivername != POSTGRES_BACKEND:
        return parsed
    return parsed.set(drivername=PSYCOPG2_DRIVERNAME)


def build_connect_args(url: str | URL, app_settings: Settings) -> dict[str, object]:
    """Build the libpq connection arguments for a PostgreSQL URL.

    Args:
        url: Database URL the engine will connect to.
        app_settings: Source of the connect timeout and the TLS mode.

    Returns:
        Arguments for ``create_engine(connect_args=...)``. Empty for any backend
        other than PostgreSQL, since the keys are libpq options. ``sslmode`` is
        present only when ``database_ssl_mode`` is set, which then overrides a
        ``sslmode`` given in the URL.
    """
    if make_url(url).get_backend_name() != POSTGRES_BACKEND:
        return {}
    connect_args: dict[str, object] = {
        "application_name": application_name(app_settings),
        "connect_timeout": app_settings.database_connect_timeout,
        "keepalives": KEEPALIVES_ENABLED,
        "keepalives_idle": KEEPALIVES_IDLE_SECONDS,
        "keepalives_interval": KEEPALIVES_INTERVAL_SECONDS,
        "keepalives_count": KEEPALIVES_PROBE_COUNT,
    }
    if app_settings.database_ssl_mode:
        connect_args["sslmode"] = app_settings.database_ssl_mode
    return connect_args


def build_engine(app_settings: Settings) -> Engine:
    """Create the pooled engine without opening a connection.

    Args:
        app_settings: Source of the URL and every pool setting.

    Returns:
        An engine that hides bound parameters from error messages and from the
        SQL echo, so values such as emails stay out of logs. A driverless
        PostgreSQL URL runs on psycopg2 (see ``with_psycopg2_driver``).
    """
    url = with_psycopg2_driver(app_settings.database_url)
    return create_engine(
        url,
        connect_args=build_connect_args(url, app_settings),
        echo=app_settings.database_echo,
        pool_size=app_settings.database_pool_size,
        max_overflow=app_settings.database_max_overflow,
        pool_timeout=app_settings.database_pool_timeout,
        pool_recycle=app_settings.database_pool_recycle,
        pool_pre_ping=app_settings.database_pool_pre_ping,
        hide_parameters=True,
    )


def build_database_breaker(
    app_settings: Settings, *, name: str = BREAKER_NAME
) -> CircuitBreaker:
    """Create a database circuit breaker from the settings.

    Args:
        app_settings: Source of the failure threshold and the reset timeout.
        name: Label in logs and in the refusal's ``log_context``; give each
            engine its own so their transitions can be told apart.

    Returns:
        A closed breaker that counts only the errors
        ``is_connectivity_failure`` accepts. A deadlock or serialization failure
        is a conflict, not an outage, and never trips it.
    """
    config = CircuitBreakerConfig(
        failure_threshold=app_settings.database_breaker_failure_threshold,
        reset_timeout_seconds=app_settings.database_breaker_reset_timeout,
    )
    return CircuitBreaker(
        name,
        config,
        failure_types=CONNECTIVITY_ERRORS,
        is_failure=is_connectivity_failure,
    )


def mark_exercised_on_first_connection(session: Session, call: GuardedCall) -> None:
    """Make a guarded call vote only if its session really takes a connection.

    SQLAlchemy checks a connection out lazily, so a request that fails
    validation, or answers from the identity map, never touches the database.
    Letting it vote would count a request that proved nothing as a success.

    Args:
        session: The session the guarded block uses. For an ``AsyncSession``
            pass its ``sync_session``.
        call: The handle ``CircuitBreaker.guard`` yielded for the block.
    """

    def _mark_exercised(*_: object) -> None:
        call.mark_exercised()

    event.listen(session, "after_begin", _mark_exercised, once=True)


class DatabaseManager:
    """Owns the engine and issues sessions guarded by a circuit breaker."""

    def __init__(
        self,
        app_settings: Settings,
        breaker: CircuitBreaker | None = None,
        *,
        engine_factory: Callable[[Settings], Engine] = build_engine,
    ) -> None:
        """Create a manager that has not built its engine yet.

        Args:
            app_settings: Database and breaker configuration.
            breaker: Breaker to use; one is built from the settings when omitted.
            engine_factory: Builds the engine on first use. Tests replace it to
                run against SQLite.
        """
        self._settings = app_settings
        self._breaker = breaker or build_database_breaker(app_settings)
        self._engine_factory = engine_factory
        self._lock = threading.Lock()
        self._runtime: _Runtime | None = None

    @property
    def breaker(self) -> CircuitBreaker:
        """The circuit breaker that guards every session."""
        return self._breaker

    @property
    def engine(self) -> Engine:
        """The engine, built on first access."""
        return self._ensure_runtime().engine

    def initialize(self) -> None:
        """Build the engine and session factory if they do not exist yet.

        Safe to call repeatedly and from several threads. It opens no
        connection, so a database outage cannot make it fail.
        """
        self._ensure_runtime()

    def close(self) -> None:
        """Dispose the engine and its pooled connections.

        Safe to call when nothing was initialized. A later ``initialize`` builds
        a fresh engine.
        """
        with self._lock:
            runtime, self._runtime = self._runtime, None
        if runtime is not None:
            runtime.engine.dispose()
            logger.info("Database engine disposed")

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """Provide a session for one unit of work.

        The caller commits through the unit of work; leaving the block without
        committing discards the changes. The session is always closed. The
        breaker hears a verdict only if the block really used the database, so a
        request that fails validation first cannot close a half-open circuit.

        Yields:
            A session bound to the pooled engine.

        Raises:
            CircuitOpenError: The breaker is open, so no connection is attempted.
            DatabaseUnavailableError: The database could not be reached. The
                breaker records a failure and the driver error is chained.
            ConflictError: An integrity constraint rejected a write, or the
                transaction lost a deadlock or serialization race.
            DatabaseOperationError: Any other database error.
        """
        session = self._ensure_runtime().sessions()
        try:
            with self._breaker.guard() as call:
                mark_exercised_on_first_connection(session, call)
                yield session
        except SQLAlchemyError as error:
            _rollback_quietly(session)
            raise translate_database_error(error) from error
        except BaseException:
            _rollback_quietly(session)
            raise
        finally:
            session.close()

    def _ensure_runtime(self) -> _Runtime:
        with self._lock:
            if self._runtime is None:
                engine = self._engine_factory(self._settings)
                sessions = sessionmaker(
                    bind=engine, autoflush=False, expire_on_commit=False
                )
                self._runtime = _Runtime(engine, sessions)
                logger.info(
                    "Database engine created: pool_size=%d max_overflow=%d",
                    self._settings.database_pool_size,
                    self._settings.database_max_overflow,
                )
            return self._runtime


def _rollback_quietly(session: Session) -> None:
    # A failed rollback must not hide the error that made us roll back.
    try:
        session.rollback()
    except SQLAlchemyError as error:
        logger.warning("Database rollback failed: %s", type(error).__name__)


database_manager = DatabaseManager(settings)

_shutdown_hooks: list[ShutdownHook] = []
_readiness_probes: dict[str, ReadinessProbe] = {}


def register_shutdown_hook(hook: ShutdownHook) -> None:
    """Add a callable that ``run_shutdown_hooks`` runs when the application stops.

    Registering the same callable twice keeps one entry, so importing a module
    again cannot run its hook twice.

    Args:
        hook: Callable taking no arguments. It may be a coroutine function.
    """
    if hook not in _shutdown_hooks:
        _shutdown_hooks.append(hook)


async def run_shutdown_hooks() -> None:
    """Run every registered shutdown hook, last registered first.

    Await it from the application's shutdown path, on the event loop that owns
    the resources the hooks release. A hook that raises is logged and does not
    stop the others, because the process is going down regardless.
    """
    for hook in reversed(_shutdown_hooks):
        try:
            outcome = hook()
            if inspect.isawaitable(outcome):
                await outcome
        except Exception as error:
            # One failing hook must not keep the others from releasing theirs.
            logger.warning(
                "database.shutdown_hook_failed",
                extra={
                    "hook": getattr(hook, "__qualname__", repr(hook)),
                    "error_type": type(error).__name__,
                },
            )


def register_readiness_probe(name: str, probe: ReadinessProbe) -> None:
    """Add a database health check that the readiness endpoint reports.

    Registering a name again replaces its probe, so importing a module again is
    harmless.

    Args:
        name: Key under which ``registered_readiness_probes`` reports the result.
        probe: Coroutine function taking no arguments and returning the
            ``DatabaseHealth`` of its database. It must not raise: a failure is
            reported as ``DatabaseStatus.DOWN``.
    """
    _readiness_probes[name] = probe


async def registered_readiness_probes() -> "dict[str, DatabaseHealth]":
    """Run every registered readiness probe.

    Returns:
        The health of each registered database by name; empty when no optional
        component registered one. The primary database is probed separately by
        ``app.infrastructure.health.probe_database``.
    """
    return {name: await probe() for name, probe in list(_readiness_probes.items())}


def init_db() -> None:
    """Build the engine at application startup.

    Opens no connection and creates no schema; Alembic owns the schema.
    """
    database_manager.initialize()


def close_db() -> None:
    """Dispose the engine at application shutdown."""
    database_manager.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields one session per request.

    Yields:
        A session that the request's unit of work commits or discards.

    Raises:
        CircuitOpenError: The database breaker is open.
        DatabaseUnavailableError: The database could not be reached.
        ConflictError: An integrity constraint rejected a write.
        DatabaseOperationError: Any other database error.
    """
    with database_manager.session_scope() as session:
        yield session
