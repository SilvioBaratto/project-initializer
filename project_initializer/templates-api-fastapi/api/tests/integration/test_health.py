"""Integration tests for the root, liveness and readiness routes."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool

from app.api import health
from app.api.health import LIVENESS_PATH, READINESS_PATH, ROOT_PATH
from app.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from app.infrastructure.database import DatabaseManager
from app.infrastructure.health import DatabaseHealth, DatabaseStatus
from app.infrastructure.settings import settings

pytestmark = pytest.mark.integration

ROOT_BODY = {"status": "operational", "api_version": "v1"}
LIVENESS_BODY = {"status": "ok"}
BREAKER_RESET_SECONDS = 60.0


def fake_probe(
    status: DatabaseStatus, circuit: CircuitState
) -> Callable[..., DatabaseHealth]:
    """A stand-in for ``probe_database`` that reports a fixed outcome."""

    def probe(_manager: DatabaseManager) -> DatabaseHealth:
        """Ignore the manager and return the configured outcome."""
        return DatabaseHealth(status, circuit)

    return probe


def fake_registered_probes(
    outcomes: dict[str, DatabaseHealth],
) -> Callable[[], Awaitable[dict[str, DatabaseHealth]]]:
    """A stand-in for ``registered_readiness_probes`` with fixed outcomes."""

    async def registered() -> dict[str, DatabaseHealth]:
        """Report the configured outcome of every registered database."""
        return outcomes

    return registered


def refuse_to_build_engine(_settings: object) -> Engine:
    """Engine factory that fails the test when the database would be touched."""
    raise AssertionError("an open circuit must not reach the database")


@pytest.fixture(autouse=True)
def no_additional_databases(monkeypatch) -> None:
    """Report no optional database, whatever the installed overlays registered.

    The async overlay registers a probe when it is imported. Without this, a
    readiness test would also probe that overlay's real database.
    """
    monkeypatch.setattr(
        health, "registered_readiness_probes", fake_registered_probes({})
    )


def test_when_root_is_requested_then_it_reports_operational_without_internals(client):
    """when GET / is requested, only the status and the API version label are returned.

    Validates app.api.health.read_root().
    """
    response = client.get(ROOT_PATH)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == ROOT_BODY


def test_when_liveness_is_requested_then_it_answers_ok(client):
    """when GET /health is requested, 200 and a bare ok status are returned.

    Validates app.api.health.read_liveness().
    """
    response = client.get(LIVENESS_PATH)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == LIVENESS_BODY


def test_when_database_answers_then_readiness_is_ok(client, monkeypatch):
    """when the probe reports the database up, readiness is 200 with the circuit state.

    Validates app.api.health.read_readiness().
    """
    monkeypatch.setattr(
        health, "probe_database", fake_probe(DatabaseStatus.UP, CircuitState.CLOSED)
    )

    response = client.get(READINESS_PATH)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "status": "ok",
        "database": "up",
        "circuit": "closed",
        "additional_databases": {},
    }


@pytest.mark.parametrize(
    "circuit", [CircuitState.CLOSED, CircuitState.OPEN, CircuitState.HALF_OPEN]
)
def test_when_database_is_down_then_readiness_is_503_in_every_circuit_state(
    client, monkeypatch, circuit
):
    """when the probe reports the database down, readiness is 503 and degraded.

    Validates app.api.health.read_readiness().
    """
    monkeypatch.setattr(
        health, "probe_database", fake_probe(DatabaseStatus.DOWN, circuit)
    )

    response = client.get(READINESS_PATH)

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {
        "status": "degraded",
        "database": "down",
        "circuit": circuit.value,
        "additional_databases": {},
    }


def test_when_real_manager_reaches_the_database_then_readiness_is_ok(
    client, monkeypatch
):
    """when the real probe runs against a reachable database, readiness is 200.

    The manager gets its own engine: sharing the test session's connection would
    nest a second transaction on it.

    Validates app.api.health.read_readiness().
    """
    private_engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    manager = DatabaseManager(settings, engine_factory=lambda _settings: private_engine)
    monkeypatch.setattr(health, "database_manager", manager)

    try:
        response = client.get(READINESS_PATH)
    finally:
        manager.close()

    assert response.status_code == HTTPStatus.OK
    assert response.json()["database"] == "up"
    assert response.json()["circuit"] == "closed"


def test_when_circuit_is_open_then_readiness_is_503_without_touching_the_database(
    client, monkeypatch
):
    """when the database breaker is open, readiness reports down with no I/O.

    Validates app.api.health.read_readiness().
    """
    breaker = CircuitBreaker(
        "database",
        CircuitBreakerConfig(
            failure_threshold=1, reset_timeout_seconds=BREAKER_RESET_SECONDS
        ),
        failure_types=(OperationalError,),
    )
    breaker.record_failure(breaker.before_call())
    manager = DatabaseManager(settings, breaker, engine_factory=refuse_to_build_engine)
    monkeypatch.setattr(health, "database_manager", manager)

    response = client.get(READINESS_PATH)

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "down"
    assert response.json()["circuit"] == "open"


def test_when_caller_has_no_credentials_then_probes_are_still_public(
    unauthenticated_client, monkeypatch
):
    """when no principal is available, root, liveness and readiness stay reachable.

    Orchestrators probe these routes without credentials.

    Validates app.api.health.router.
    """
    monkeypatch.setattr(
        health, "probe_database", fake_probe(DatabaseStatus.UP, CircuitState.CLOSED)
    )

    statuses = [
        unauthenticated_client.get(path).status_code
        for path in (ROOT_PATH, LIVENESS_PATH, READINESS_PATH)
    ]

    assert statuses == [200, 200, 200]


@pytest.mark.parametrize(
    ("additional_status", "expected_status", "expected_body_status"),
    [
        pytest.param(DatabaseStatus.UP, HTTPStatus.OK, "ok", id="all-up"),
        pytest.param(
            DatabaseStatus.DOWN,
            HTTPStatus.SERVICE_UNAVAILABLE,
            "degraded",
            id="additional-down",
        ),
    ],
)
def test_when_an_additional_database_is_registered_then_readiness_reports_it_by_name(
    client, monkeypatch, additional_status, expected_status, expected_body_status
):
    """when an optional component registers a probe, readiness includes and obeys it.

    The primary database is up in both cases, so the 503 comes from the
    additional one alone.

    Validates app.api.health.read_readiness().
    """
    monkeypatch.setattr(
        health, "probe_database", fake_probe(DatabaseStatus.UP, CircuitState.CLOSED)
    )
    monkeypatch.setattr(
        health,
        "registered_readiness_probes",
        fake_registered_probes(
            {"analytics": DatabaseHealth(additional_status, CircuitState.HALF_OPEN)}
        ),
    )

    response = client.get(READINESS_PATH)

    assert response.status_code == expected_status
    body = response.json()
    assert body["status"] == expected_body_status
    assert body["database"] == "up"
    assert body["additional_databases"] == {
        "analytics": {"status": additional_status.value, "circuit": "half_open"}
    }
