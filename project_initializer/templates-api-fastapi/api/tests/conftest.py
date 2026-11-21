"""Shared fixtures: a pinned test environment, an in-memory database and clients.

The suite must not depend on the developer's ``.env``. Importing ``app.main``
calls ``load_configuration()``, which copies that file into ``os.environ``, and
pinning a few variables first would protect only those: every other value in
the file (``API_V1_STR``, ``CORS_ORIGINS``, ...) would reach the ``Settings()``
that tests build afterwards. ``app.main`` is therefore imported with
``load_configuration`` replaced by a no-op, so a run sees only the exported
environment plus the values pinned below.
"""

# ruff: noqa: E402 - the environment must be pinned before app.main is imported.

import logging
import os
import signal
from collections.abc import Callable, Iterator
from http import HTTPStatus
from typing import Any, NoReturn
from unittest import mock

from tests.auth_test_env import AUTH_TEST_ENV

PINNED_TEST_ENVIRONMENT = {
    "ENVIRONMENT": "test",
    "DEBUG": "false",
    "LOG_LEVEL": "warning",
}
os.environ.update(PINNED_TEST_ENVIRONMENT)
os.environ.update(AUTH_TEST_ENV)

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.infrastructure.orm  # noqa: F401 - registers every table on Base.metadata
from app.api.auth_deps import get_current_user
from app.domain.entities.authenticated_user import AuthenticatedUser
from app.domain.exceptions import AuthenticationError
from app.infrastructure.database import get_db
from app.infrastructure.orm.base import Base
from app.infrastructure.settings import Settings, settings
from tests.fakes import TEST_USER

with mock.patch("app.infrastructure.config.load_configuration"):
    from app.main import app, create_application

IN_MEMORY_SQLITE_URL = "sqlite://"


@pytest.fixture(scope="session")
def test_engine() -> Iterator[Engine]:
    """In-memory SQLite engine with the schema created once per session.

    A ``StaticPool`` shares one connection across threads, which the
    ``TestClient`` needs because it runs sync endpoints in a worker thread.
    The two listeners are the recipe in the SQLAlchemy pysqlite documentation
    ("Serializable isolation / Savepoints / Transactional DDL"): the driver
    would otherwise start its transactions lazily and make SAVEPOINT
    unreliable, so the ``db_session`` fixture could not roll a test back.
    """
    engine = create_engine(
        IN_MEMORY_SQLITE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _disable_driver_autobegin(dbapi_connection, _connection_record) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin_explicitly(connection: Connection) -> None:
        connection.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Iterator[Session]:
    """Session whose writes, including commits, are undone after the test.

    The session joins an outer transaction through a SAVEPOINT, so a
    ``commit()`` issued by the code under test releases the savepoint only. The
    session options mirror the ones ``DatabaseManager`` uses at runtime.
    """
    connection = test_engine.connect()
    outer_transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        expire_on_commit=False,
    )
    yield session
    session.close()
    outer_transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """Client for the real application, with the database bound to ``db_session``.

    The client is not used as a context manager on purpose: that would run the
    real lifespan, which would reach the database named in the developer's
    ``.env`` instead of the test database.

    No credentials are supplied. Use ``authenticated_client`` or
    ``unauthenticated_client`` for routes that need a principal.
    """

    def override_get_db() -> Iterator[Session]:
        """Hand every request the shared test session."""
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client(client: TestClient) -> TestClient:
    """Client whose requests are made by ``TEST_USER``, in every auth variant.

    Replacing ``get_current_user`` keeps the shared tests independent of how a
    variant verifies credentials; each variant tests that in its own
    ``test_auth.py``.

    It shares one client with ``unauthenticated_client``; requesting both fails.
    """
    _override_current_user(lambda: TEST_USER)
    return client


def _override_current_user(provider: Callable[[], AuthenticatedUser]) -> None:
    """Install ``provider`` in place of ``get_current_user``.

    Raises:
        AssertionError: Another fixture already replaced it, which means a test
            requested both client fixtures and would silently get only one.
    """
    assert get_current_user not in app.dependency_overrides, (
        "authenticated_client and unauthenticated_client are mutually exclusive"
    )
    app.dependency_overrides[get_current_user] = provider


def _reject_missing_credentials() -> NoReturn:
    raise AuthenticationError()


@pytest.fixture
def unauthenticated_client(client: TestClient) -> TestClient:
    """Client whose requests are rejected as carrying no valid credentials.

    Use it instead of ``authenticated_client``; requesting both fails.
    """
    _override_current_user(_reject_missing_credentials)
    return client


@pytest.fixture
def build_app() -> Callable[..., FastAPI]:
    """Factory for a fresh application under the given settings overrides.

    The overrides are applied with ``model_copy``, which skips validation. That
    lets a test build a production-like application in every auth variant
    without supplying the production-grade secrets a variant demands of a real
    production configuration.
    """

    def factory(**overrides: Any) -> FastAPI:
        """Build an application from the shared settings plus ``overrides``."""
        app_settings: Settings = settings.model_copy(update=overrides)
        return create_application(app_settings)

    return factory


@pytest.fixture
def restored_root_level() -> Iterator[int]:
    """The root logger's level, put back after a test that changes it."""
    root = logging.getLogger()
    original_level = root.level
    yield original_level
    root.setLevel(original_level)


@pytest.fixture
def ignored_sighup() -> Iterator[None]:
    """Run the test with SIGHUP ignored, and restore the real disposition after.

    A test that raises SIGHUP must not be able to terminate the test run if the
    handler it expects is missing: the default action of SIGHUP is to exit.
    Skips the test on a platform that has no SIGHUP.
    """
    if not hasattr(signal, "SIGHUP"):
        pytest.skip("this platform has no SIGHUP")
    original = signal.signal(signal.SIGHUP, signal.SIG_IGN)
    yield
    signal.signal(signal.SIGHUP, signal.SIG_DFL if original is None else original)


@pytest.fixture(scope="session")
def api_prefix() -> str:
    """URL prefix every versioned route lives under, such as ``/api/v1``."""
    return settings.api_v1_str


@pytest.fixture
def item_payload() -> dict[str, Any]:
    """A valid body for creating an item; each test gets its own copy."""
    return {"name": "Widget", "description": "A widget", "price": 9.99}


@pytest.fixture
def create_item(
    authenticated_client: TestClient, api_prefix: str, item_payload: dict[str, Any]
) -> Callable[..., dict[str, Any]]:
    """Create an item through the API and return the response body.

    Keyword arguments override fields of ``item_payload``. The call fails the
    test unless the API answers 201, so a test that needs an existing item does
    not repeat that assertion.
    """

    def create(**overrides: Any) -> dict[str, Any]:
        """POST the payload with ``overrides`` and return the created item."""
        response = authenticated_client.post(
            f"{api_prefix}/items", json={**item_payload, **overrides}
        )
        assert response.status_code == HTTPStatus.CREATED, response.text
        return response.json()

    return create


@pytest.fixture(scope="session")
def openapi_schema() -> dict[str, Any]:
    """The OpenAPI document, generated in-process once per session.

    It is read from the application object rather than over HTTP, so a test of
    the contract does not depend on whether the docs routes are served.
    """
    return app.openapi()
