"""Unit tests for the opt-in async database path.

They need no PostgreSQL server: URL translation is pure, the engine is built
without connecting, and the session scope, breaker and probe run on in-memory
``aiosqlite``, which the unit level allows because no external service is
involved. A server that rejects the login is played by a stand-in for
``asyncpg.connect``, so the real SQLAlchemy asyncpg dialect translates its error.
Repositories and real connection failures are in
``tests/integration/test_async_database.py``. ``asyncio_mode = auto``
(pytest.ini) collects the ``async def`` tests.
"""

import ssl
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NoReturn
from unittest import mock
from urllib.parse import urlencode

import asyncpg
import pytest
from asyncpg.exceptions import CannotConnectNowError, TooManyConnectionsError
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.domain.exceptions import ConflictError
from app.infrastructure import database, database_async
from app.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from app.infrastructure.database import CONNECTIVITY_ERRORS
from app.infrastructure.database_async import (
    ASYNC_BREAKER_NAME,
    async_session_scope,
    build_async_engine,
    dispose_async_engine,
    get_async_db,
    probe_async_database,
    to_asyncpg_url,
)
from app.infrastructure.errors import (
    CircuitOpenError,
    DatabaseOperationError,
    DatabaseUnavailableError,
    is_connectivity_failure,
    sqlstate_of,
)
from app.infrastructure.health import DatabaseStatus
from app.infrastructure.orm.base import Base
from app.infrastructure.settings import ENCRYPTED_SSL_MODES, Settings
from tests.fakes import FakeClock

POSTGRES_URL = "postgresql://u:p@host:5432/db"
FAILURE_THRESHOLD = 2
RESET_TIMEOUT_SECONDS = 30.0
CUSTOM_POOL_SIZE = 3
CUSTOM_MAX_OVERFLOW = 4
CUSTOM_POOL_TIMEOUT = 7
CUSTOM_POOL_RECYCLE = 1800
CUSTOM_CONNECT_TIMEOUT = 9
SECRET_VALUE = "hunter2"
DEADLOCK_SQLSTATE = "40P01"
UNREACHABLE_SQLITE_URL = "sqlite+aiosqlite:////nonexistent-directory/app.db"
CERTIFICATE_VALIDITY = timedelta(days=1)


class _SecretsAcceptingSettings(Settings):
    def validate_auth_secrets(self, *, production_like: bool) -> None:
        """Accept every secret, whatever the installed auth variant demands."""


class DriverError(Exception):
    """Stand-in for a driver error that carries a SQLSTATE."""

    def __init__(self, pgcode: str) -> None:
        super().__init__("driver message that quotes the statement")
        self.pgcode = pgcode


def write_certificate_pair(directory: Path, name: str) -> tuple[Path, Path]:
    """Write a throwaway self-signed certificate and its matching private key.

    Args:
        directory: Folder that receives ``<name>.crt`` and ``<name>.key``.
        name: File stem, also used as the certificate's common name.

    Returns:
        The certificate path and the key path.
    """
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - CERTIFICATE_VALIDITY)
        .not_valid_after(now + CERTIFICATE_VALIDITY)
        .sign(key, hashes.SHA256())
    )
    certificate_path = directory / f"{name}.crt"
    key_path = directory / f"{name}.key"
    certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return certificate_path, key_path


def url_with(**parameters: str) -> str:
    """Build a database URL whose query holds ``parameters``."""
    return f"{POSTGRES_URL}?{urlencode(parameters)}"


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Session factory over a fresh in-memory aiosqlite database."""
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def clock() -> FakeClock:
    """Clock that drives the replacement breaker."""
    return FakeClock()


@pytest.fixture
def breaker(monkeypatch, clock) -> CircuitBreaker:
    """Replace the module breaker with one that opens after two failures."""
    replacement = CircuitBreaker(
        ASYNC_BREAKER_NAME,
        CircuitBreakerConfig(FAILURE_THRESHOLD, RESET_TIMEOUT_SECONDS),
        failure_types=CONNECTIVITY_ERRORS,
        is_failure=is_connectivity_failure,
        clock=clock,
    )
    monkeypatch.setattr(database_async, "async_database_breaker", replacement)
    return replacement


@pytest.fixture
def route_to_sqlite(monkeypatch, session_factory) -> None:
    """Make the session scope open sessions on the in-memory database."""
    monkeypatch.setattr(database_async, "async_session_factory", session_factory)


async def throw_into_dependency(error: BaseException) -> None:
    """Start ``get_async_db`` and raise ``error`` inside the request block."""
    dependency = get_async_db()
    await anext(dependency)
    await dependency.athrow(error)


async def query_then_throw(error: BaseException) -> None:
    """Use the database once inside the request block, then raise ``error``."""
    dependency = get_async_db()
    session = await anext(dependency)
    await session.execute(select(1))
    await dependency.athrow(error)


def refuse_logins_with(
    rejection: type[asyncpg.PostgresError],
) -> Callable[..., Awaitable[NoReturn]]:
    """Build an ``asyncpg.connect`` stand-in for a server that rejects every login.

    Args:
        rejection: The asyncpg error class the server's startup answer maps to.

    Returns:
        A coroutine function that raises a fresh ``rejection`` on each call.
    """

    async def refuse(*_args: object, **_kwargs: object) -> NoReturn:
        """Fail the way ``asyncpg.connect`` does when the server answers with an error."""
        raise rejection("rejected during connection startup")

    return refuse


@pytest.fixture
async def asyncpg_engine(monkeypatch) -> AsyncIterator[AsyncEngine]:
    """An engine from ``build_async_engine``, with its connect hook, behind the session scope."""
    engine = build_async_engine(Settings(database_url=POSTGRES_URL))
    monkeypatch.setattr(
        database_async,
        "async_session_factory",
        async_sessionmaker(bind=engine, autoflush=False),
    )
    yield engine
    await engine.dispose()


async def trip_circuit(breaker: CircuitBreaker) -> None:
    """Open the breaker with the configured number of connectivity failures."""
    for _ in range(FAILURE_THRESHOLD):
        with pytest.raises(DatabaseUnavailableError):
            await throw_into_dependency(OperationalError("SELECT 1", None, OSError()))
    assert breaker.state is CircuitState.OPEN


@pytest.mark.unit
def test_when_url_has_sslmode_then_it_is_removed_and_passed_as_ssl():
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    url, connect_args = to_asyncpg_url("postgresql://u:p@host:5432/db?sslmode=require")

    assert url == "postgresql+asyncpg://u:p@host:5432/db"
    assert connect_args == {"ssl": "require"}


@pytest.mark.unit
def test_when_url_has_no_parameters_then_connect_args_are_empty():
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    url, connect_args = to_asyncpg_url("postgresql://u:p@localhost:5433/app_db")

    assert url == "postgresql+asyncpg://u:p@localhost:5433/app_db"
    assert connect_args == {}


@pytest.mark.unit
def test_when_ssl_mode_is_given_then_it_overrides_the_url_and_disable_is_kept():
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    _, overridden = to_asyncpg_url(
        "postgresql://h/db?sslmode=require", ssl_mode="verify-full"
    )
    _, disabled = to_asyncpg_url("postgresql://h/db", ssl_mode="disable")

    assert overridden == {"ssl": "verify-full"}
    assert disabled == {"ssl": "disable"}


def _production_policy_accepts(url: str, ssl_mode: str | None) -> bool:
    """Whether a production ``Settings`` takes the database URL and TLS mode."""
    try:
        _SecretsAcceptingSettings(
            environment="production", database_url=url, database_ssl_mode=ssl_mode
        )
    except ValidationError:
        return False
    return True


@pytest.mark.unit
@pytest.mark.parametrize(
    ("url_mode", "configured_mode"),
    [
        pytest.param("require", None, id="url-require"),
        pytest.param(None, "verify-full", id="configured-verify-full"),
        pytest.param("require", "disable", id="configured-disable-beats-url"),
        pytest.param("disable", "require", id="configured-require-beats-url"),
        pytest.param("prefer", None, id="url-prefer"),
        pytest.param(None, None, id="unspecified"),
    ],
)
def test_when_settings_judge_the_tls_mode_then_asyncpg_connects_with_that_mode(
    url_mode, configured_mode
):
    """Validates app.infrastructure.settings.Settings._enforce_environment_policy().

    The production policy must approve exactly the connections that the async
    path opens with an encrypting mode, so the two precedence rules cannot drift.
    """
    url = POSTGRES_URL if url_mode is None else f"{POSTGRES_URL}?sslmode={url_mode}"

    _, connect_args = to_asyncpg_url(url, ssl_mode=configured_mode)

    assert _production_policy_accepts(url, configured_mode) is (
        connect_args.get("ssl") in ENCRYPTED_SSL_MODES
    )


@pytest.mark.unit
def test_when_driver_is_named_then_it_is_replaced_by_asyncpg():
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    url, _ = to_asyncpg_url("postgresql+psycopg2://u:p%40ss@h/db")

    assert url == "postgresql+asyncpg://u:p%40ss@h/db"


@pytest.mark.unit
def test_when_url_has_connect_timeout_then_it_becomes_the_asyncpg_timeout():
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    url, connect_args = to_asyncpg_url(url_with(connect_timeout="15"))

    assert url == "postgresql+asyncpg://u:p@host:5432/db"
    assert connect_args == {"timeout": 15.0}


@pytest.mark.unit
def test_when_a_timeout_argument_is_given_then_it_overrides_the_url():
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    _, connect_args = to_asyncpg_url(
        url_with(connect_timeout="15"), connect_timeout=CUSTOM_CONNECT_TIMEOUT
    )

    assert connect_args == {"timeout": float(CUSTOM_CONNECT_TIMEOUT)}


@pytest.mark.unit
def test_when_url_has_application_name_then_it_becomes_a_server_setting():
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    _, from_url = to_asyncpg_url(url_with(application_name="reports"))
    _, overridden = to_asyncpg_url(
        url_with(application_name="reports"), application_name="app-api-test"
    )

    assert from_url == {"server_settings": {"application_name": "reports"}}
    assert overridden == {"server_settings": {"application_name": "app-api-test"}}


@pytest.mark.unit
@pytest.mark.parametrize(
    "options",
    [
        "-c search_path=app -c statement_timeout=5000",
        "-csearch_path=app --statement_timeout=5000",
    ],
)
def test_when_url_has_options_then_each_assignment_becomes_a_server_setting(options):
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    _, connect_args = to_asyncpg_url(url_with(options=options))

    assert connect_args == {
        "server_settings": {"search_path": "app", "statement_timeout": "5000"}
    }


@pytest.mark.unit
def test_when_url_keeps_a_dialect_parameter_then_it_stays_in_the_url():
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    url, connect_args = to_asyncpg_url(
        url_with(prepared_statement_cache_size="0", sslmode="require")
    )

    assert (
        url == "postgresql+asyncpg://u:p@host:5432/db?prepared_statement_cache_size=0"
    )
    assert connect_args == {"ssl": "require"}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("mode", "check_hostname", "verify_mode"),
    [
        ("verify-full", True, ssl.CERT_REQUIRED),
        ("verify-ca", False, ssl.CERT_REQUIRED),
        ("require", False, ssl.CERT_REQUIRED),
    ],
)
def test_when_url_has_a_root_certificate_then_ssl_is_a_context_that_verifies_it(
    tmp_path, mode, check_hostname, verify_mode
):
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    root_certificate, _ = write_certificate_pair(tmp_path, "root")

    url, connect_args = to_asyncpg_url(
        url_with(sslmode=mode, sslrootcert=str(root_certificate))
    )

    context = connect_args["ssl"]
    assert url == "postgresql+asyncpg://u:p@host:5432/db"
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname is check_hostname
    assert context.verify_mode == verify_mode


@pytest.mark.unit
def test_when_url_has_only_a_client_certificate_with_require_then_the_server_is_not_verified(
    tmp_path,
):
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    certificate, key = write_certificate_pair(tmp_path, "client")

    _, connect_args = to_asyncpg_url(
        url_with(sslmode="require", sslcert=str(certificate), sslkey=str(key))
    )

    context = connect_args["ssl"]
    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_NONE


@pytest.mark.unit
def test_when_the_client_key_does_not_match_the_certificate_then_it_is_refused(
    tmp_path,
):
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    certificate, _ = write_certificate_pair(tmp_path, "client")
    _, other_key = write_certificate_pair(tmp_path, "other")

    with pytest.raises(ssl.SSLError):
        to_asyncpg_url(
            url_with(sslmode="require", sslcert=str(certificate), sslkey=str(other_key))
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "parameters",
    [
        {"pgbouncer": "true"},
        {"gssencmode": "disable", "password": SECRET_VALUE},
        {"target_session_attrs": "read-write"},
    ],
)
def test_when_url_has_an_unsupported_parameter_then_it_is_refused_by_name_only(
    parameters,
):
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    with pytest.raises(ValueError, match="not supported with asyncpg") as refused:
        to_asyncpg_url(url_with(**parameters))

    for name in parameters:
        assert name in str(refused.value)
    assert SECRET_VALUE not in str(refused.value)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("application_name=a&application_name=b", "repeats"),
        ("connect_timeout=soon", "number of seconds"),
        ("options=--", "malformed"),
        ("options=-c%20novalue", "malformed"),
        ("options=positional", "unsupported token"),
        ("sslrootcert=/ca.crt", "need sslmode"),
        ("sslmode=prefer&sslcert=/c.crt", "need sslmode"),
    ],
)
def test_when_a_parameter_is_malformed_then_it_is_refused_at_startup(query, message):
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    with pytest.raises(ValueError, match=message):
        to_asyncpg_url(f"{POSTGRES_URL}?{query}")


@pytest.mark.unit
def test_when_a_client_key_has_no_certificate_then_it_is_refused(tmp_path):
    """Validates app.infrastructure.database_async.to_asyncpg_url()."""
    root_certificate, key = write_certificate_pair(tmp_path, "client")

    with pytest.raises(ValueError, match="sslkey needs sslcert"):
        to_asyncpg_url(
            url_with(
                sslmode="verify-ca",
                sslrootcert=str(root_certificate),
                sslkey=str(key),
            )
        )


EXPECTED_ENGINE_ARGUMENTS = {
    "url": "postgresql+asyncpg://u:p@host:5432/db",
    "connect_args": {
        "ssl": "verify-ca",
        "timeout": float(CUSTOM_CONNECT_TIMEOUT),
        "server_settings": {"application_name": "app-api-development"},
    },
    "echo": True,
    "pool_size": CUSTOM_POOL_SIZE,
    "max_overflow": CUSTOM_MAX_OVERFLOW,
    "pool_timeout": CUSTOM_POOL_TIMEOUT,
    "pool_recycle": CUSTOM_POOL_RECYCLE,
    "pool_pre_ping": False,
    "hide_parameters": True,
}


def record_engine_arguments(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Capture what ``build_async_engine`` passes to ``create_async_engine``.

    Returns:
        The dict filled with the URL and keyword arguments once the engine is built.
    """
    captured: dict[str, object] = {}

    def recording_create_async_engine(url: str, **engine_kwargs: object):
        """Remember the arguments, then build the real engine."""
        captured["url"] = url
        captured.update(engine_kwargs)
        return create_async_engine(url, **engine_kwargs)

    monkeypatch.setattr(
        database_async, "create_async_engine", recording_create_async_engine
    )
    return captured


@pytest.mark.unit
def test_when_engine_is_built_then_every_setting_reaches_the_engine_and_nothing_connects(
    monkeypatch,
):
    """Validates app.infrastructure.database_async.build_async_engine()."""
    captured = record_engine_arguments(monkeypatch)
    app_settings = Settings(
        database_url=url_with(sslmode="require"),
        database_ssl_mode="verify-ca",
        environment="development",
        database_echo=True,
        database_pool_size=CUSTOM_POOL_SIZE,
        database_max_overflow=CUSTOM_MAX_OVERFLOW,
        database_pool_timeout=CUSTOM_POOL_TIMEOUT,
        database_pool_recycle=CUSTOM_POOL_RECYCLE,
        database_pool_pre_ping=False,
        database_connect_timeout=CUSTOM_CONNECT_TIMEOUT,
    )

    engine = build_async_engine(app_settings)

    assert captured == EXPECTED_ENGINE_ARGUMENTS
    assert engine.url.drivername == "postgresql+asyncpg"
    assert engine.sync_engine.pool.size() == CUSTOM_POOL_SIZE


@pytest.mark.unit
def test_when_the_url_has_an_unsupported_parameter_then_the_engine_is_not_built():
    """Validates app.infrastructure.database_async.build_async_engine()."""
    app_settings = Settings(database_url=url_with(pgbouncer="true"))

    with pytest.raises(ValueError, match="pgbouncer"):
        build_async_engine(app_settings)


@pytest.mark.unit
def test_when_the_module_is_imported_then_it_registers_its_shutdown_hook_and_probe():
    """Validates app.infrastructure.database_async.probe_async_database()."""
    assert dispose_async_engine in database._shutdown_hooks
    assert database._readiness_probes[ASYNC_BREAKER_NAME] is probe_async_database


@pytest.mark.unit
async def test_when_get_async_db_runs_then_it_yields_a_session_and_finishes(
    route_to_sqlite, breaker
):
    """Validates app.infrastructure.database_async.get_async_db()."""
    dependency = get_async_db()

    yielded = await anext(dependency)
    await yielded.execute(select(1))

    assert isinstance(yielded, AsyncSession)
    with pytest.raises(StopAsyncIteration):
        await anext(dependency)
    assert breaker.state is CircuitState.CLOSED


@pytest.mark.unit
async def test_when_the_database_is_unreachable_then_unavailable_error_is_raised_from_it(
    route_to_sqlite, breaker, caplog
):
    """Validates app.infrastructure.database_async.get_async_db()."""
    outage = OperationalError("SELECT 1", None, OSError("refused"))

    with pytest.raises(DatabaseUnavailableError) as raised:
        await throw_into_dependency(outage)

    assert raised.value.__cause__ is outage
    assert raised.value.log_context == {"error_type": "OperationalError"}
    assert [r for r in caplog.records if r.levelname == "ERROR"] == []
    assert "SELECT" not in caplog.text


@pytest.mark.unit
async def test_when_outages_reach_the_threshold_then_the_next_request_is_refused(
    route_to_sqlite, breaker
):
    """Validates app.infrastructure.database_async.get_async_db()."""
    await trip_circuit(breaker)

    with pytest.raises(CircuitOpenError):
        await anext(get_async_db())


@pytest.mark.unit
@pytest.mark.parametrize(
    "rejection",
    [TooManyConnectionsError, CannotConnectNowError],
    ids=["53300-too-many-connections", "57P03-starting-up"],
)
async def test_when_the_server_rejects_the_login_then_unavailable_is_raised_and_the_circuit_opens(
    monkeypatch, asyncpg_engine, breaker, rejection
):
    """Validates app.infrastructure.database_async.build_async_engine()."""
    monkeypatch.setattr(asyncpg, "connect", refuse_logins_with(rejection))

    for _ in range(FAILURE_THRESHOLD):
        with pytest.raises(DatabaseUnavailableError) as raised:
            async with async_session_scope() as session:
                await session.execute(select(1))
        assert isinstance(raised.value.__cause__, OperationalError)
        assert sqlstate_of(raised.value.__cause__) == rejection.sqlstate

    assert breaker.state is CircuitState.OPEN


@pytest.mark.unit
@pytest.mark.parametrize(
    "unrelated_failure",
    [ConnectionRefusedError("refused"), TimeoutError(), OSError("disk")],
)
async def test_when_the_request_raises_an_os_error_then_it_propagates_and_the_circuit_stays_closed(
    route_to_sqlite, breaker, unrelated_failure
):
    """Validates app.infrastructure.database_async.async_session_scope()."""
    for _ in range(FAILURE_THRESHOLD + 1):
        with pytest.raises(type(unrelated_failure)):
            await query_then_throw(unrelated_failure)

    assert breaker.state is CircuitState.CLOSED


@pytest.mark.unit
async def test_when_a_constraint_fails_then_a_conflict_is_raised_and_the_circuit_stays_closed(
    route_to_sqlite, breaker, caplog
):
    """Validates app.infrastructure.database_async.async_session_scope()."""
    violation = IntegrityError("INSERT secret", None, DriverError("23505"))

    for _ in range(FAILURE_THRESHOLD + 1):
        with pytest.raises(ConflictError) as raised:
            await query_then_throw(violation)

    assert raised.value.__cause__ is violation
    assert raised.value.log_context == {"error_type": "IntegrityError"}
    assert breaker.state is CircuitState.CLOSED
    assert "secret" not in caplog.text


@pytest.mark.unit
async def test_when_a_deadlock_occurs_then_a_conflict_is_raised_and_the_circuit_stays_closed(
    route_to_sqlite, breaker
):
    """Validates app.infrastructure.database_async.async_session_scope()."""
    deadlock = OperationalError("UPDATE items", None, DriverError(DEADLOCK_SQLSTATE))

    for _ in range(FAILURE_THRESHOLD + 1):
        with pytest.raises(ConflictError):
            await query_then_throw(deadlock)

    assert breaker.state is CircuitState.CLOSED


@pytest.mark.unit
async def test_when_another_database_error_occurs_then_an_operation_error_is_raised(
    route_to_sqlite, breaker, caplog
):
    """Validates app.infrastructure.database_async.async_session_scope()."""
    failure = ProgrammingError("INSERT secret", None, DriverError("42P01"))

    for _ in range(FAILURE_THRESHOLD + 1):
        with pytest.raises(DatabaseOperationError) as raised:
            await query_then_throw(failure)

    assert raised.value.log_context == {
        "error_type": "ProgrammingError",
        "sqlstate": "42P01",
    }
    assert breaker.state is CircuitState.CLOSED
    assert "secret" not in caplog.text


@pytest.mark.unit
async def test_when_a_request_never_uses_the_database_then_a_half_open_circuit_stays_half_open(
    route_to_sqlite, breaker, clock
):
    """Validates app.infrastructure.database_async.async_session_scope()."""
    await trip_circuit(breaker)
    clock.advance(RESET_TIMEOUT_SECONDS)

    with pytest.raises(ValueError, match="invalid body"):
        await throw_into_dependency(ValueError("invalid body"))
    async with async_session_scope():
        pass

    assert breaker.state is CircuitState.HALF_OPEN


@pytest.mark.unit
async def test_when_requests_never_use_the_database_then_they_do_not_reset_the_failure_streak(
    route_to_sqlite, breaker
):
    """Validates app.infrastructure.database_async.async_session_scope()."""
    with pytest.raises(DatabaseUnavailableError):
        await throw_into_dependency(OperationalError("SELECT 1", None, OSError()))

    with pytest.raises(ValueError, match="invalid body"):
        await throw_into_dependency(ValueError("invalid body"))
    with pytest.raises(DatabaseUnavailableError):
        await throw_into_dependency(OperationalError("SELECT 1", None, OSError()))

    assert breaker.state is CircuitState.OPEN


@pytest.mark.unit
async def test_when_a_half_open_request_uses_the_database_then_the_circuit_closes(
    route_to_sqlite, breaker, clock
):
    """Validates app.infrastructure.database_async.async_session_scope()."""
    await trip_circuit(breaker)
    clock.advance(RESET_TIMEOUT_SECONDS)

    async with async_session_scope() as session:
        await session.execute(select(1))

    assert breaker.state is CircuitState.CLOSED


@pytest.mark.unit
async def test_when_the_database_answers_then_the_async_probe_reports_up(
    route_to_sqlite, breaker
):
    """Validates app.infrastructure.database_async.probe_async_database()."""
    health = await probe_async_database()

    assert health.status is DatabaseStatus.UP
    assert health.circuit is CircuitState.CLOSED


@pytest.mark.unit
async def test_when_the_database_cannot_be_opened_then_the_async_probe_reports_down(
    monkeypatch, breaker, caplog
):
    """Validates app.infrastructure.database_async.probe_async_database()."""
    engine = create_async_engine(UNREACHABLE_SQLITE_URL)
    monkeypatch.setattr(
        database_async, "async_session_factory", async_sessionmaker(bind=engine)
    )
    caplog.set_level("WARNING", logger="app.infrastructure.database_async")

    health = await probe_async_database()

    assert health.status is DatabaseStatus.DOWN
    assert [(r.getMessage(), r.breaker) for r in caplog.records] == [
        ("database.probe_failed", ASYNC_BREAKER_NAME)
    ]
    await engine.dispose()


@pytest.mark.unit
async def test_when_the_circuit_is_open_then_the_async_probe_reports_down_without_a_session(
    monkeypatch, breaker
):
    """Validates app.infrastructure.database_async.probe_async_database()."""
    await trip_circuit(breaker)
    refusing_factory = mock.Mock(side_effect=AssertionError("no session expected"))
    monkeypatch.setattr(database_async, "async_session_factory", refusing_factory)

    health = await probe_async_database()

    assert (health.status, health.circuit) == (DatabaseStatus.DOWN, CircuitState.OPEN)
    refusing_factory.assert_not_called()


@pytest.mark.unit
async def test_when_the_engine_is_disposed_then_the_pool_is_closed(monkeypatch):
    """Validates app.infrastructure.database_async.dispose_async_engine()."""
    engine = mock.Mock(dispose=mock.AsyncMock())
    monkeypatch.setattr(database_async, "async_engine", engine)

    await dispose_async_engine()

    engine.dispose.assert_awaited_once_with()
