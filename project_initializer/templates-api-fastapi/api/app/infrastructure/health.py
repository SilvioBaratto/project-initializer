"""Database readiness probe for the ``/health/ready`` endpoint."""

import logging
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.domain.exceptions import DomainError
from app.infrastructure.circuit_breaker import CircuitState
from app.infrastructure.database import DatabaseManager

logger = logging.getLogger(__name__)


class DatabaseStatus(StrEnum):
    """Whether a database answered a probe."""

    UP = "up"
    DOWN = "down"


@dataclass(frozen=True)
class DatabaseHealth:
    """Outcome of one database probe.

    Attributes:
        status: ``UP`` when a trivial query succeeded, otherwise ``DOWN``.
        circuit: State of the database breaker when the probe finished.
    """

    status: DatabaseStatus
    circuit: CircuitState

    @property
    def is_up(self) -> bool:
        """True when the probe found the database answering."""
        return self.status == DatabaseStatus.UP


def probe_database(manager: DatabaseManager) -> DatabaseHealth:
    """Check that the database answers a trivial query.

    The probe goes through the breaker, so it also serves as the trial call that
    closes a half-open circuit once the database is back.

    Args:
        manager: Manager whose database is checked.

    Returns:
        ``DOWN`` when the circuit is open (no connection is attempted) or the
        query fails; otherwise ``UP``. The probe never raises. A failed query is
        logged once at WARNING with the error class only, because readiness
        polling is the only place a swallowed outage would otherwise go unseen.
    """
    if manager.breaker.state is CircuitState.OPEN:
        return DatabaseHealth(DatabaseStatus.DOWN, CircuitState.OPEN)
    try:
        with manager.session_scope() as session:
            session.execute(select(1))
    except (DomainError, SQLAlchemyError) as error:
        logger.warning(
            "database.probe_failed", extra={"error_type": type(error).__name__}
        )
        return DatabaseHealth(DatabaseStatus.DOWN, manager.breaker.state)
    return DatabaseHealth(DatabaseStatus.UP, manager.breaker.state)
