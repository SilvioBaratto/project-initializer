"""Unit tests for the database manager, its health probe, its engine setup and its hooks.

The manager runs on in-memory SQLite through the injectable engine factory, which
the unit level allows because no external service is involved (see
``tests/__init__.py``). SQLite reports a missing table as ``OperationalError``
without a SQLSTATE, which the manager classifies as a connectivity failure, so
these tests exercise the real error translation without a PostgreSQL server.
"""

import asyncio
import logging
from unittest import mock

import pytest
from sqlalchemy import Engine, create_engine, event, select, text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.domain.exceptions import ConflictError
from app.infrastructure import database
from app.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    GuardedCall,
)
from app.infrastructure.database import (
    DatabaseManager,
    ReadinessProbe,
    build_connect_args,
    build_database_breaker,
    build_engine,
    mark_exercised_on_first_connection,
    register_readiness_probe,
    register_shutdown_hook,
    registered_readiness_probes,
    run_shutdown_hooks,
)
from app.infrastructure.errors import (
    CONNECTIVITY_ERRORS,
    CircuitOpenError,
    DatabaseOperationError,
    DatabaseUnavailableError,
    is_connectivity_failure,
)
from app.infrastructure.health import DatabaseHealth, DatabaseStatus, probe_database
from app.infrastructure.settings import Settings
from tests.fakes import FakeClock

SQLITE_URL = "sqlite://"
POSTGRES_URL = "postgresql://localhost:5433/app_db"
UNREACHABLE_SQLITE_URL = "sqlite:////nonexistent-directory/app.db"
FAILURE_THRESHOLD = 3
RESET_TIMEOUT_SECONDS = 30.0
CUSTOM_POOL_SIZE = 3
CUSTOM_POOL_TIMEOUT = 7
CUSTOM_CONNECT_TIMEOUT = 9
DUPLICATE_INSERT_COUNT = 2
ENGINES_AFTER_REOPEN = 2
SECRET_VALUE = "secret@example.com"
MISSING_TABLE_QUERY = "SELECT email FROM missing_table WHERE email = :email"
DEADLOCK_SQLSTATE = "40P01"
UNDEFINED_TABLE_SQLSTATE = "42P01"
UP_HEALTH = DatabaseHealth(DatabaseStatus.UP, CircuitState.CLOSED)
DOWN_HEALTH = DatabaseHealth(DatabaseStatus.DOWN, CircuitState.OPEN)


class DriverError(Exception):
    """Stand-in for a driver error that carries a SQLSTATE."""

    def __init__(self, pgcode: str) -> None:
        super().__init__("driver message that quotes the statement")
        self.pgcode = pgcode


class RecordingEngineFactory:
    """Engine factory that remembers each engine built and each connection opened."""

    def __init__(self, url: str = SQLITE_URL) -> None:
        self._url = url
        self.engines: list[Engine] = []
        self.connects: list[bool] = []

    def __call__(self, app_settings: Settings) -> Engine:
        """Build a shared in-memory SQLite engine that records new connections."""
        engine = create_engine(
            self._url,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            hide_parameters=True,
        )
        event.listen(engine, "connect", lambda *_: self.connects.append(True))
        self.engines.append(engine)
        return engine


def make_settings(**overrides: object) -> Settings:
    """Build settings with a small breaker threshold and a known reset timeout.

    Args:
        overrides: Fields to override, by field name.

    Returns:
        Settings that point at in-memory SQLite.
    """
    # Pinned so a developer's or a generated .env (DATABASE_SSL_MODE=require in the supabase
    # scaffold) cannot change the connect args these tests assert on.
    values: dict[str, object] = {
        "database_url": SQLITE_URL,
        "database_ssl_mode": None,
        "database_breaker_failure_threshold": FAILURE_THRESHOLD,
        "database_breaker_reset_timeout": RESET_TIMEOUT_SECONDS,
    }
    return Settings(**(values | overrides))


def make_manager(
    clock: FakeClock | None = None,
    engine_factory: RecordingEngineFactory | None = None,
) -> DatabaseManager:
    """Create a manager whose breaker runs on ``clock`` and whose engine is SQLite."""
    breaker = CircuitBreaker(
        "database",
        CircuitBreakerConfig(FAILURE_THRESHOLD, RESET_TIMEOUT_SECONDS),
        failure_types=CONNECTIVITY_ERRORS,
        is_failure=is_connectivity_failure,
        clock=clock or FakeClock(),
    )
    return DatabaseManager(
        make_settings(),
        breaker,
        engine_factory=engine_factory or RecordingEngineFactory(),
    )


def fail_once(manager: DatabaseManager) -> None:
    """Run one session block that queries a missing table and expect it to fail."""
    with pytest.raises(DatabaseUnavailableError), manager.session_scope() as session:
        session.execute(text(MISSING_TABLE_QUERY), {"email": SECRET_VALUE})


def open_half_open_circuit(manager: DatabaseManager, clock: FakeClock) -> None:
    """Trip the manager's breaker and let its reset timeout elapse."""
    for _ in range(FAILURE_THRESHOLD):
        fail_once(manager)
    clock.advance(RESET_TIMEOUT_SECONDS)


def raise_after_a_query(manager: DatabaseManager, error: Exception) -> None:
    """Use the database once inside a session block, then raise ``error``."""
    with manager.session_scope() as session:
        session.execute(select(1))
        raise error


def constant_probe(health: DatabaseHealth) -> ReadinessProbe:
    """Build a readiness probe that always reports ``health``."""

    async def probe() -> DatabaseHealth:
        """Return the fixed outcome."""
        return health

    return probe


@pytest.fixture
def isolated_hook_registry(monkeypatch) -> None:
    """Give the test an empty shutdown-hook list and readiness-probe table."""
    monkeypatch.setattr(database, "_shutdown_hooks", [])
    monkeypatch.setattr(database, "_readiness_probes", {})


@pytest.mark.unit
def test_when_url_is_postgres_then_connect_args_carry_timeout_and_keepalives():
    """Validates app.infrastructure.database.build_connect_args()."""
    app_settings = make_settings(
        database_connect_timeout=CUSTOM_CONNECT_TIMEOUT, environment="test"
    )

    connect_args = build_connect_args(POSTGRES_URL, app_settings)

    assert connect_args["connect_timeout"] == CUSTOM_CONNECT_TIMEOUT
    assert connect_args["application_name"] == "app-api-test"
    assert connect_args["keepalives"] == 1
    assert "sslmode" not in connect_args


@pytest.mark.unit
def test_when_ssl_mode_is_configured_then_connect_args_include_it():
    """Validates app.infrastructure.database.build_connect_args()."""
    app_settings = make_settings(database_ssl_mode="verify-full")

    connect_args = build_connect_args(POSTGRES_URL, app_settings)

    assert connect_args["sslmode"] == "verify-full"


@pytest.mark.unit
def test_when_url_is_not_postgres_then_connect_args_are_empty():
    """Validates app.infrastructure.database.build_connect_args()."""
    assert build_connect_args(SQLITE_URL, make_settings()) == {}


@pytest.mark.unit
def test_when_engine_is_built_then_pool_follows_settings_and_parameters_are_hidden():
    """Validates app.infrastructure.database.build_engine()."""
    app_settings = make_settings(
        database_url=POSTGRES_URL,
        database_pool_size=CUSTOM_POOL_SIZE,
        database_pool_timeout=CUSTOM_POOL_TIMEOUT,
    )

    engine = build_engine(app_settings)

    assert engine.pool.size() == CUSTOM_POOL_SIZE
    assert engine.pool.timeout() == CUSTOM_POOL_TIMEOUT
    assert engine.hide_parameters is True
    engine.dispose()


@pytest.mark.unit
def test_when_a_breaker_is_built_then_it_carries_the_given_name_and_the_settings_threshold():
    """Validates app.infrastructure.database.build_database_breaker()."""
    breaker = build_database_breaker(make_settings(), name="replica")

    for _ in range(FAILURE_THRESHOLD):
        breaker.record_failure(breaker.before_call())
    with pytest.raises(CircuitOpenError) as refused:
        breaker.before_call()

    assert refused.value.log_context == {"breaker": "replica"}


@pytest.mark.unit
def test_when_initialized_twice_then_the_engine_is_built_once_without_connecting():
    """Validates app.infrastructure.database.DatabaseManager.initialize()."""
    factory = RecordingEngineFactory()
    manager = make_manager(engine_factory=factory)

    manager.initialize()
    manager.initialize()

    assert len(factory.engines) == 1
    assert factory.connects == []


@pytest.mark.unit
def test_when_closed_then_the_engine_is_disposed_once_and_a_later_use_builds_a_new_one():
    """Validates app.infrastructure.database.DatabaseManager.close()."""
    factory = RecordingEngineFactory()
    manager = make_manager(engine_factory=factory)
    manager.initialize()

    with mock.patch.object(factory.engines[0], "dispose") as dispose:
        manager.close()
        manager.close()
    manager.initialize()

    dispose.assert_called_once_with()
    assert len(factory.engines) == ENGINES_AFTER_REOPEN


@pytest.mark.unit
def test_when_a_session_begins_a_transaction_then_the_guarded_call_is_marked_exercised():
    """Validates app.infrastructure.database.mark_exercised_on_first_connection()."""
    manager = make_manager()
    call = GuardedCall()

    with manager.session_scope() as session:
        mark_exercised_on_first_connection(session, call)
        assert call.exercised is False
        session.execute(select(1))

    assert call.exercised is True


@pytest.mark.unit
def test_when_a_session_is_never_used_then_the_guarded_call_is_not_marked_exercised():
    """Validates app.infrastructure.database.mark_exercised_on_first_connection()."""
    manager = make_manager()
    call = GuardedCall()

    with manager.session_scope() as session:
        mark_exercised_on_first_connection(session, call)

    assert call.exercised is False


@pytest.mark.unit
def test_when_a_block_succeeds_then_the_session_is_closed(monkeypatch):
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    closed = []
    original_close = Session.close
    monkeypatch.setattr(
        Session, "close", lambda self: (closed.append(self), original_close(self))
    )
    manager = make_manager()

    with manager.session_scope() as session:
        assert session.execute(select(1)).scalar_one() == 1

    assert closed == [session]
    assert manager.breaker.state is CircuitState.CLOSED


@pytest.mark.unit
def test_when_the_database_is_unreachable_then_unavailable_error_is_raised_from_it():
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    manager = make_manager()

    with (
        pytest.raises(DatabaseUnavailableError) as raised,
        manager.session_scope() as session,
    ):
        session.execute(text(MISSING_TABLE_QUERY), {"email": SECRET_VALUE})

    assert isinstance(raised.value.__cause__, OperationalError)
    assert raised.value.public_message == DatabaseUnavailableError.default_message
    assert raised.value.log_context == {"error_type": "OperationalError"}


@pytest.mark.unit
def test_when_the_database_fails_then_the_manager_writes_no_error_record_of_its_own(
    caplog,
):
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    manager = make_manager()
    caplog.set_level(logging.DEBUG, logger="app.infrastructure.database")

    fail_once(manager)

    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
    assert all(r.exc_info is None for r in caplog.records)
    assert "missing_table" not in caplog.text
    assert SECRET_VALUE not in caplog.text


@pytest.mark.unit
def test_when_failures_reach_the_threshold_then_the_next_block_is_refused_unrun():
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    manager = make_manager()
    for _ in range(FAILURE_THRESHOLD):
        fail_once(manager)
    ran = []

    with pytest.raises(CircuitOpenError), manager.session_scope():
        ran.append(True)

    assert ran == []
    assert manager.breaker.state is CircuitState.OPEN


@pytest.mark.unit
def test_when_the_circuit_recovers_then_a_successful_block_closes_it():
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    clock = FakeClock()
    manager = make_manager(clock)
    open_half_open_circuit(manager, clock)

    with manager.session_scope() as session:
        session.execute(select(1))

    assert manager.breaker.state is CircuitState.CLOSED


@pytest.mark.unit
def test_when_a_constraint_fails_then_a_conflict_is_raised_and_no_error_is_logged(
    caplog,
):
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    manager = make_manager()
    caplog.set_level(logging.DEBUG, logger="app.infrastructure.database")

    with pytest.raises(ConflictError) as raised, manager.session_scope() as session:
        session.execute(text("CREATE TABLE people (email TEXT UNIQUE)"))
        for _ in range(DUPLICATE_INSERT_COUNT):
            session.execute(
                text("INSERT INTO people VALUES (:email)"), {"email": SECRET_VALUE}
            )

    assert isinstance(raised.value.__cause__, IntegrityError)
    assert raised.value.log_context == {"error_type": "IntegrityError"}
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
    assert SECRET_VALUE not in caplog.text
    assert "INSERT" not in caplog.text


@pytest.mark.unit
def test_when_constraints_keep_failing_then_the_circuit_stays_closed():
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    manager = make_manager()
    violation = IntegrityError("INSERT", (SECRET_VALUE,), Exception("duplicate"))

    for _ in range(FAILURE_THRESHOLD + 1):
        with pytest.raises(ConflictError):
            raise_after_a_query(manager, violation)

    assert manager.breaker.state is CircuitState.CLOSED


@pytest.mark.unit
def test_when_a_deadlock_occurs_then_a_conflict_is_raised_and_the_circuit_stays_closed():
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    manager = make_manager()
    deadlock = OperationalError(
        "UPDATE items SET name = :name", None, DriverError(DEADLOCK_SQLSTATE)
    )

    for _ in range(FAILURE_THRESHOLD + 1):
        with pytest.raises(ConflictError) as raised:
            raise_after_a_query(manager, deadlock)

    assert raised.value.__cause__ is deadlock
    assert manager.breaker.state is CircuitState.CLOSED


@pytest.mark.unit
def test_when_another_database_error_occurs_then_an_operation_error_is_raised_and_the_circuit_stays_closed(
    caplog,
):
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    manager = make_manager()
    caplog.set_level(logging.DEBUG, logger="app.infrastructure.database")
    failure = ProgrammingError(
        "SELECT secret", None, DriverError(UNDEFINED_TABLE_SQLSTATE)
    )

    for _ in range(FAILURE_THRESHOLD + 1):
        with pytest.raises(DatabaseOperationError) as raised:
            raise_after_a_query(manager, failure)

    assert raised.value.__cause__ is failure
    assert raised.value.log_context == {
        "error_type": "ProgrammingError",
        "sqlstate": UNDEFINED_TABLE_SQLSTATE,
    }
    assert manager.breaker.state is CircuitState.CLOSED
    assert "secret" not in caplog.text


@pytest.mark.unit
def test_when_the_block_raises_another_error_then_it_propagates_unlogged(caplog):
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    manager = make_manager()
    caplog.set_level(logging.DEBUG, logger="app.infrastructure.database")
    caplog.clear()

    with pytest.raises(ValueError, match="bad input"), manager.session_scope():
        raise ValueError("bad input")

    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


@pytest.mark.unit
def test_when_a_request_never_uses_the_database_then_a_half_open_circuit_stays_half_open():
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    clock = FakeClock()
    manager = make_manager(clock)
    open_half_open_circuit(manager, clock)

    with pytest.raises(ValueError, match="invalid body"), manager.session_scope():
        raise ValueError("invalid body")
    with manager.session_scope():
        pass

    assert manager.breaker.state is CircuitState.HALF_OPEN


@pytest.mark.unit
def test_when_requests_never_use_the_database_then_they_do_not_reset_the_failure_streak():
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    manager = make_manager()
    for _ in range(FAILURE_THRESHOLD - 1):
        fail_once(manager)

    with pytest.raises(ValueError, match="invalid body"), manager.session_scope():
        raise ValueError("invalid body")
    fail_once(manager)

    assert manager.breaker.state is CircuitState.OPEN


@pytest.mark.unit
def test_when_a_half_open_request_is_cancelled_then_the_probe_slot_is_released():
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    clock = FakeClock()
    manager = make_manager(clock)
    open_half_open_circuit(manager, clock)

    with pytest.raises(asyncio.CancelledError):
        raise_after_a_query(manager, asyncio.CancelledError())

    assert manager.breaker.state is CircuitState.HALF_OPEN
    with manager.session_scope() as session:
        session.execute(select(1))
    assert manager.breaker.state is CircuitState.CLOSED


@pytest.mark.unit
def test_when_the_block_raises_then_uncommitted_writes_are_discarded():
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    manager = make_manager()
    with manager.session_scope() as session:
        session.execute(text("CREATE TABLE notes (body TEXT)"))
        session.commit()

    with pytest.raises(ValueError, match="stop"), manager.session_scope() as session:
        session.execute(text("INSERT INTO notes VALUES ('draft')"))
        raise ValueError("stop")

    with manager.session_scope() as session:
        assert session.execute(text("SELECT count(*) FROM notes")).scalar_one() == 0


@pytest.mark.unit
def test_when_the_rollback_itself_fails_then_the_original_error_still_propagates(
    monkeypatch, caplog
):
    """Validates app.infrastructure.database.DatabaseManager.session_scope()."""
    manager = make_manager()
    caplog.set_level(logging.WARNING, logger="app.infrastructure.database")

    def broken_rollback(self: Session) -> None:
        """Simulate a connection that died before the rollback."""
        raise OperationalError("ROLLBACK", None, Exception("connection lost"))

    monkeypatch.setattr(Session, "rollback", broken_rollback)

    with pytest.raises(ValueError, match="original"), manager.session_scope():
        raise ValueError("original")

    assert "Database rollback failed: OperationalError" in caplog.text
    assert "connection lost" not in caplog.text


@pytest.mark.unit
def test_when_the_database_answers_then_the_probe_reports_up():
    """Validates app.infrastructure.health.probe_database()."""
    health = probe_database(make_manager())

    assert health.status is DatabaseStatus.UP
    assert health.is_up is True
    assert health.circuit is CircuitState.CLOSED


@pytest.mark.unit
def test_when_the_database_cannot_be_opened_then_the_probe_reports_down_and_logs_once(
    caplog,
):
    """Validates app.infrastructure.health.probe_database()."""
    manager = make_manager(
        engine_factory=RecordingEngineFactory(UNREACHABLE_SQLITE_URL)
    )
    caplog.set_level(logging.WARNING, logger="app.infrastructure.health")

    health = probe_database(manager)

    assert health.status is DatabaseStatus.DOWN
    assert health.is_up is False
    failures = [r for r in caplog.records if r.name == "app.infrastructure.health"]
    assert [(r.getMessage(), r.error_type) for r in failures] == [
        ("database.probe_failed", "DatabaseUnavailableError")
    ]


@pytest.mark.unit
def test_when_the_circuit_is_open_then_the_probe_reports_down_without_any_query():
    """Validates app.infrastructure.health.probe_database()."""
    manager = make_manager()
    for _ in range(FAILURE_THRESHOLD):
        fail_once(manager)
    statements = []
    event.listen(
        manager.engine, "before_cursor_execute", lambda *args: statements.append(args)
    )

    health = probe_database(manager)

    assert (health.status, health.circuit) == (DatabaseStatus.DOWN, CircuitState.OPEN)
    assert statements == []


@pytest.mark.unit
def test_when_the_reset_timeout_elapsed_then_the_probe_closes_the_circuit():
    """Validates app.infrastructure.health.probe_database()."""
    clock = FakeClock()
    manager = make_manager(clock)
    open_half_open_circuit(manager, clock)

    health = probe_database(manager)

    assert (health.status, health.circuit) == (DatabaseStatus.UP, CircuitState.CLOSED)


@pytest.mark.unit
def test_when_init_db_runs_then_it_opens_no_connection_and_creates_no_tables(
    monkeypatch,
):
    """Validates app.infrastructure.database.init_db()."""
    factory = RecordingEngineFactory()
    manager = make_manager(engine_factory=factory)
    monkeypatch.setattr(database, "database_manager", manager)

    database.init_db()

    assert len(factory.engines) == 1
    assert factory.connects == []
    with manager.session_scope() as session:
        tables = session.execute(text("SELECT name FROM sqlite_master")).all()
    assert tables == []


@pytest.mark.unit
def test_when_get_db_is_consumed_then_it_yields_a_session_and_then_finishes(
    monkeypatch,
):
    """Validates app.infrastructure.database.get_db()."""
    monkeypatch.setattr(database, "database_manager", make_manager())

    dependency = database.get_db()
    session = next(dependency)

    assert session.execute(select(1)).scalar_one() == 1
    with pytest.raises(StopIteration):
        next(dependency)


@pytest.mark.unit
def test_when_close_db_runs_then_the_engine_is_disposed(monkeypatch):
    """Validates app.infrastructure.database.close_db()."""
    factory = RecordingEngineFactory()
    manager = make_manager(engine_factory=factory)
    manager.initialize()
    monkeypatch.setattr(database, "database_manager", manager)

    with mock.patch.object(factory.engines[0], "dispose") as dispose:
        database.close_db()

    dispose.assert_called_once_with()


@pytest.mark.unit
async def test_when_hooks_are_registered_then_they_run_last_registered_first(
    isolated_hook_registry,
):
    """Validates app.infrastructure.database.run_shutdown_hooks()."""
    order: list[str] = []

    async def dispose_async_pool() -> None:
        """Record that the async hook ran."""
        order.append("async pool")

    register_shutdown_hook(lambda: order.append("sync pool"))
    register_shutdown_hook(dispose_async_pool)

    await run_shutdown_hooks()

    assert order == ["async pool", "sync pool"]


@pytest.mark.unit
async def test_when_a_hook_is_registered_twice_then_it_runs_once(
    isolated_hook_registry,
):
    """Validates app.infrastructure.database.register_shutdown_hook()."""
    hook = mock.Mock()

    register_shutdown_hook(hook)
    register_shutdown_hook(hook)
    await run_shutdown_hooks()

    hook.assert_called_once_with()


@pytest.mark.unit
async def test_when_a_hook_raises_then_the_others_still_run_and_only_the_class_is_logged(
    isolated_hook_registry, caplog
):
    """Validates app.infrastructure.database.run_shutdown_hooks()."""
    survivor = mock.Mock()

    def failing_hook() -> None:
        """Fail with a message that must never be logged."""
        raise RuntimeError(SECRET_VALUE)

    register_shutdown_hook(survivor)
    register_shutdown_hook(failing_hook)
    caplog.set_level(logging.WARNING, logger="app.infrastructure.database")

    await run_shutdown_hooks()

    survivor.assert_called_once_with()
    assert [r.getMessage() for r in caplog.records] == ["database.shutdown_hook_failed"]
    assert caplog.records[0].error_type == "RuntimeError"
    assert SECRET_VALUE not in caplog.text


@pytest.mark.unit
async def test_when_no_hook_is_registered_then_running_them_does_nothing(
    isolated_hook_registry,
):
    """Validates app.infrastructure.database.run_shutdown_hooks()."""
    await run_shutdown_hooks()


@pytest.mark.unit
async def test_when_probes_are_registered_then_each_result_is_reported_by_name(
    isolated_hook_registry,
):
    """Validates app.infrastructure.database.registered_readiness_probes()."""
    register_readiness_probe("replica", constant_probe(UP_HEALTH))
    register_readiness_probe("analytics", constant_probe(DOWN_HEALTH))

    assert await registered_readiness_probes() == {
        "replica": UP_HEALTH,
        "analytics": DOWN_HEALTH,
    }


@pytest.mark.unit
async def test_when_a_probe_name_is_registered_again_then_the_latest_probe_wins(
    isolated_hook_registry,
):
    """Validates app.infrastructure.database.register_readiness_probe()."""
    register_readiness_probe("replica", constant_probe(UP_HEALTH))
    register_readiness_probe("replica", constant_probe(DOWN_HEALTH))

    assert await registered_readiness_probes() == {"replica": DOWN_HEALTH}


@pytest.mark.unit
async def test_when_no_probe_is_registered_then_the_result_is_empty(
    isolated_hook_registry,
):
    """Validates app.infrastructure.database.registered_readiness_probes()."""
    assert await registered_readiness_probes() == {}
