"""Liveness and readiness routes, mounted at the application root.

They sit outside ``/api/v1`` on purpose: load balancers and container health
checks address fixed paths and must not depend on the API version. They are
also exempt from rate limiting (see ``HEALTH_PATHS``).
"""

from typing import Literal

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.infrastructure.circuit_breaker import CircuitState
from app.infrastructure.database import database_manager, registered_readiness_probes
from app.infrastructure.health import DatabaseHealth, DatabaseStatus, probe_database

ROOT_PATH = "/"
LIVENESS_PATH = "/health"
READINESS_PATH = "/health/ready"
HEALTH_PATHS = frozenset({ROOT_PATH, LIVENESS_PATH, READINESS_PATH})

API_VERSION_LABEL = "v1"

router = APIRouter(tags=["Health"])


class RootResponse(BaseModel):
    """Body of ``GET /``.

    Attributes:
        status: Always ``operational`` while the process answers.
        api_version: Label of the current API version.
    """

    status: Literal["operational"] = "operational"
    api_version: str = API_VERSION_LABEL


class LivenessResponse(BaseModel):
    """Body of ``GET /health``.

    Attributes:
        status: Always ``ok`` while the process answers.
    """

    status: Literal["ok"] = "ok"


class DatabaseCheck(BaseModel):
    """Outcome of the probe of one database.

    Attributes:
        status: Whether the database answered.
        circuit: State of the circuit breaker guarding it.
    """

    status: DatabaseStatus
    circuit: CircuitState

    @classmethod
    def from_health(cls, health: DatabaseHealth) -> "DatabaseCheck":
        """Build the check from a probe outcome.

        Args:
            health: Outcome reported by a database probe.

        Returns:
            The same status and circuit state, as a response model.
        """
        return cls(status=health.status, circuit=health.circuit)


class ReadinessResponse(BaseModel):
    """Body of ``GET /health/ready``.

    Attributes:
        status: ``ok`` when every database answers, otherwise ``degraded``.
        database: Outcome of the primary database probe.
        circuit: State of the primary database's circuit breaker.
        additional_databases: Outcome per optional database that a component,
            such as the async overlay, registered a probe for; empty when none.
    """

    status: Literal["ok", "degraded"]
    database: DatabaseStatus
    circuit: CircuitState
    additional_databases: dict[str, DatabaseCheck] = Field(default_factory=dict)


@router.get(ROOT_PATH, summary="API root", response_model=RootResponse)
async def read_root() -> RootResponse:
    """Confirm the service is up without revealing its version or environment."""
    return RootResponse()


@router.get(LIVENESS_PATH, summary="Liveness probe", response_model=LivenessResponse)
async def read_liveness() -> LivenessResponse:
    """Report that the process is running; it checks no dependency."""
    return LivenessResponse()


@router.get(
    READINESS_PATH,
    summary="Readiness probe",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def read_readiness() -> ReadinessResponse | JSONResponse:
    """Report whether the service can reach every database it uses.

    An open circuit breaker reports ``down`` without touching the database.

    Returns:
        200 with ``status`` ``ok`` when every database answers, otherwise 503
        with ``status`` ``degraded``, so an orchestrator stops routing traffic
        here.
    """
    primary = await run_in_threadpool(probe_database, database_manager)
    additional = await registered_readiness_probes()
    all_up = primary.is_up and all(health.is_up for health in additional.values())
    body = ReadinessResponse(
        status="ok" if all_up else "degraded",
        database=primary.status,
        circuit=primary.circuit,
        additional_databases={
            name: DatabaseCheck.from_health(health)
            for name, health in additional.items()
        },
    )
    if all_up:
        return body
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=body.model_dump(mode="json"),
    )
