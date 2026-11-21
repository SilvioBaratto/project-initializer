"""Infrastructure failures and the translation of driver errors into them.

``CircuitOpenError`` and ``DatabaseUnavailableError`` inherit the public code and
message of ``ExternalServiceError``, so no internal component name (database,
breaker) appears in a response. ``DatabaseOperationError`` covers the remaining
case: the database answered but could not do the work.

Driver exceptions never leave the infrastructure layer. Their text carries the
SQL statement and, on PostgreSQL, the offending key values (``DETAIL: Key
(email)=(...)``), so ``translate_database_error`` replaces them with these
errors and keeps only the class name and the SQLSTATE in ``log_context``. The
driver error stays chained as ``__cause__``.
"""

from typing import ClassVar

from sqlalchemy.exc import (
    DBAPIError,
    DisconnectionError,
    IntegrityError,
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from app.domain.exceptions import ConflictError, DomainError, ExternalServiceError

# SQLAlchemy raises OperationalError for far more than outages, so the type is
# only a pre-filter: ``is_connectivity_failure`` decides.
CONNECTIVITY_ERRORS = (
    OperationalError,
    InterfaceError,
    DisconnectionError,
    PoolTimeoutError,
)

# PostgreSQL SQLSTATE classes that mean the server cannot be reached or is
# going away: 08 connection exception, 53 insufficient resources, 57P operator
# intervention (shutdown, crash recovery), 58 system error. 57014 (statement
# timeout) is deliberately not included: one slow query is not an outage.
CONNECTIVITY_SQLSTATE_PREFIXES = ("08", "53", "57P", "58")

# 40xxx are serialization failures and deadlocks, 55P03 is a lock timeout. The
# statement lost a race with another transaction while the server was healthy,
# so retrying is the right answer and the breaker must not count it.
CONTENTION_SQLSTATE_PREFIXES = ("40", "55P03")


class CircuitOpenError(ExternalServiceError):
    """A circuit breaker refused the call without contacting the dependency."""


class DatabaseUnavailableError(ExternalServiceError):
    """The database could not be reached or timed out."""


class DatabaseOperationError(DomainError):
    """The database answered but could not complete the operation.

    Raised for a driver error that is neither an integrity conflict nor an
    outage, such as a syntax error, a missing column or a rejected login. It is a
    server-side fault, so it carries a generic message and no dependency name.
    """

    error_code: ClassVar[str] = "DATABASE_ERROR"
    default_message: ClassVar[str] = (
        "The request could not be completed because of an internal error"
    )


def sqlstate_of(error: BaseException) -> str | None:
    """Read the SQLSTATE of a wrapped driver error.

    Args:
        error: Any exception; only SQLAlchemy driver errors carry the code.

    Returns:
        The five-character SQLSTATE, or None when the error has none, as with
        SQLite errors and socket failures.
    """
    driver_error = getattr(error, "orig", None)
    return getattr(driver_error, "pgcode", None) or getattr(
        driver_error, "sqlstate", None
    )


def is_connectivity_failure(error: BaseException) -> bool:
    """Decide whether a driver error means the database is down.

    Args:
        error: The exception raised while the database was in use.

    Returns:
        True for a pool timeout, an interface or disconnection error, and for an
        ``OperationalError`` that has no SQLSTATE, invalidated its connection or
        carries a connectivity SQLSTATE. False for contention (deadlock,
        serialization failure, lock timeout) and for every other error: the
        server answered, so it must not trip the breaker.
    """
    if isinstance(error, InterfaceError | DisconnectionError | PoolTimeoutError):
        return True
    if not isinstance(error, OperationalError):
        return False
    sqlstate = sqlstate_of(error)
    return (
        sqlstate is None
        or error.connection_invalidated
        or sqlstate.startswith(CONNECTIVITY_SQLSTATE_PREFIXES)
    )


def conflict_from(error: SQLAlchemyError) -> ConflictError:
    """Build the conflict that replaces an integrity or contention error.

    Args:
        error: The driver error. Its message is dropped because it quotes the
            SQL statement and can quote stored values.

    Returns:
        A ``ConflictError`` whose ``log_context`` holds only the error class.
    """
    return ConflictError(log_context={"error_type": type(error).__name__})


def translate_database_error(error: SQLAlchemyError) -> DomainError:
    """Replace a driver error with the domain error the API answers with.

    Args:
        error: The error raised inside a database session block.

    Returns:
        ``ConflictError`` for an integrity violation or contention,
        ``DatabaseUnavailableError`` for an outage, and
        ``DatabaseOperationError`` for any other database error. The caller
        raises it ``from`` the driver error.
    """
    if isinstance(error, IntegrityError) or _is_contention(error):
        return conflict_from(error)
    error_type = type(error).__name__
    if is_connectivity_failure(error):
        return DatabaseUnavailableError(log_context={"error_type": error_type})
    return DatabaseOperationError(
        log_context={"error_type": error_type, "sqlstate": sqlstate_of(error)}
    )


def _is_contention(error: SQLAlchemyError) -> bool:
    if not isinstance(error, DBAPIError):
        return False
    sqlstate = sqlstate_of(error)
    return sqlstate is not None and sqlstate.startswith(CONTENTION_SQLSTATE_PREFIXES)
