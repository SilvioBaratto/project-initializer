"""Unit tests for the translation of driver errors into infrastructure errors.

The driver is replaced by a stub that carries only a SQLSTATE, which is all the
classification reads, so every PostgreSQL error class is reachable without a
PostgreSQL server.
"""

import pytest
from sqlalchemy.exc import (
    DisconnectionError,
    IntegrityError,
    InterfaceError,
    OperationalError,
    ProgrammingError,
)
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from app.domain.exceptions import ConflictError, DomainError, ExternalServiceError
from app.infrastructure.errors import (
    DatabaseOperationError,
    DatabaseUnavailableError,
    conflict_from,
    is_connectivity_failure,
    sqlstate_of,
    translate_database_error,
)

SECRET_VALUE = "secret@example.com"
SECRET_STATEMENT = "INSERT INTO users (email) VALUES (:email)"
DEADLOCK_SQLSTATE = "40P01"
SERIALIZATION_SQLSTATE = "40001"
LOCK_TIMEOUT_SQLSTATE = "55P03"
STATEMENT_TIMEOUT_SQLSTATE = "57014"
INVALID_PASSWORD_SQLSTATE = "28P01"
UNDEFINED_TABLE_SQLSTATE = "42P01"
CONNECTIVITY_SQLSTATES = ["08006", "08001", "53300", "57P01", "57P03", "58030"]


class Psycopg2Error(Exception):
    """Stand-in for a psycopg2 error, which exposes ``pgcode``."""

    def __init__(self, pgcode: str | None) -> None:
        super().__init__("driver message that quotes the statement")
        self.pgcode = pgcode


class AsyncpgError(Exception):
    """Stand-in for an asyncpg error, which exposes ``sqlstate``."""

    def __init__(self, sqlstate: str) -> None:
        super().__init__("driver message that quotes the statement")
        self.sqlstate = sqlstate


def operational_error(sqlstate: str | None) -> OperationalError:
    """An ``OperationalError`` whose statement and parameters hold a secret."""
    return OperationalError(
        SECRET_STATEMENT, {"email": SECRET_VALUE}, Psycopg2Error(sqlstate)
    )


@pytest.mark.unit
def test_when_the_driver_exposes_pgcode_then_sqlstate_is_read_from_it():
    """Validates app.infrastructure.errors.sqlstate_of()."""
    assert sqlstate_of(operational_error(DEADLOCK_SQLSTATE)) == DEADLOCK_SQLSTATE


@pytest.mark.unit
def test_when_the_driver_exposes_sqlstate_then_sqlstate_is_read_from_it():
    """Validates app.infrastructure.errors.sqlstate_of()."""
    error = OperationalError(
        SECRET_STATEMENT, None, AsyncpgError(SERIALIZATION_SQLSTATE)
    )

    assert sqlstate_of(error) == SERIALIZATION_SQLSTATE


@pytest.mark.unit
@pytest.mark.parametrize(
    "error", [ValueError("no driver"), OperationalError("SELECT 1", None, OSError())]
)
def test_when_the_error_carries_no_sqlstate_then_none_is_returned(error):
    """Validates app.infrastructure.errors.sqlstate_of()."""
    assert sqlstate_of(error) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "error",
    [
        InterfaceError("SELECT 1", None, Psycopg2Error(None)),
        DisconnectionError("connection invalidated"),
        PoolTimeoutError("pool exhausted"),
        operational_error(None),
        *[operational_error(sqlstate) for sqlstate in CONNECTIVITY_SQLSTATES],
    ],
)
def test_when_the_database_cannot_be_reached_then_the_error_counts_as_connectivity(
    error,
):
    """Validates app.infrastructure.errors.is_connectivity_failure()."""
    assert is_connectivity_failure(error) is True


@pytest.mark.unit
def test_when_an_operational_error_invalidated_the_connection_then_it_counts_as_connectivity():
    """Validates app.infrastructure.errors.is_connectivity_failure()."""
    error = OperationalError(
        SECRET_STATEMENT,
        None,
        Psycopg2Error(INVALID_PASSWORD_SQLSTATE),
        connection_invalidated=True,
    )

    assert is_connectivity_failure(error) is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "error",
    [
        operational_error(DEADLOCK_SQLSTATE),
        operational_error(SERIALIZATION_SQLSTATE),
        operational_error(LOCK_TIMEOUT_SQLSTATE),
        operational_error(STATEMENT_TIMEOUT_SQLSTATE),
        operational_error(INVALID_PASSWORD_SQLSTATE),
        ProgrammingError(
            SECRET_STATEMENT, None, Psycopg2Error(UNDEFINED_TABLE_SQLSTATE)
        ),
        IntegrityError(SECRET_STATEMENT, None, Psycopg2Error("23505")),
        ValueError("not a driver error"),
    ],
)
def test_when_the_server_answered_then_the_error_does_not_count_as_connectivity(error):
    """Validates app.infrastructure.errors.is_connectivity_failure()."""
    assert is_connectivity_failure(error) is False


@pytest.mark.unit
def test_when_an_integrity_error_is_translated_then_a_conflict_with_only_the_class_is_returned():
    """Validates app.infrastructure.errors.translate_database_error()."""
    error = IntegrityError(
        SECRET_STATEMENT, {"email": SECRET_VALUE}, Psycopg2Error("23505")
    )

    translated = translate_database_error(error)

    assert type(translated) is ConflictError
    assert translated.log_context == {"error_type": "IntegrityError"}


@pytest.mark.unit
@pytest.mark.parametrize(
    "sqlstate", [DEADLOCK_SQLSTATE, SERIALIZATION_SQLSTATE, LOCK_TIMEOUT_SQLSTATE]
)
def test_when_a_transaction_loses_a_race_then_it_is_translated_to_a_conflict(sqlstate):
    """Validates app.infrastructure.errors.translate_database_error()."""
    translated = translate_database_error(operational_error(sqlstate))

    assert type(translated) is ConflictError
    assert translated.log_context == {"error_type": "OperationalError"}


@pytest.mark.unit
def test_when_the_database_is_unreachable_then_it_is_translated_to_unavailable():
    """Validates app.infrastructure.errors.translate_database_error()."""
    translated = translate_database_error(operational_error(None))

    assert type(translated) is DatabaseUnavailableError
    assert translated.log_context == {"error_type": "OperationalError"}


@pytest.mark.unit
@pytest.mark.parametrize(
    "error", [DisconnectionError("invalidated"), PoolTimeoutError("pool exhausted")]
)
def test_when_the_pool_fails_then_it_is_translated_to_unavailable(error):
    """Validates app.infrastructure.errors.translate_database_error()."""
    translated = translate_database_error(error)

    assert type(translated) is DatabaseUnavailableError
    assert translated.log_context == {"error_type": type(error).__name__}


@pytest.mark.unit
def test_when_the_database_answers_with_another_error_then_it_is_translated_to_an_operation_error():
    """Validates app.infrastructure.errors.translate_database_error()."""
    error = ProgrammingError(
        SECRET_STATEMENT,
        {"email": SECRET_VALUE},
        Psycopg2Error(UNDEFINED_TABLE_SQLSTATE),
    )

    translated = translate_database_error(error)

    assert type(translated) is DatabaseOperationError
    assert translated.log_context == {
        "error_type": "ProgrammingError",
        "sqlstate": UNDEFINED_TABLE_SQLSTATE,
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "error",
    [
        IntegrityError(
            SECRET_STATEMENT, {"email": SECRET_VALUE}, Psycopg2Error("23505")
        ),
        operational_error(None),
        ProgrammingError(
            SECRET_STATEMENT, {"email": SECRET_VALUE}, Psycopg2Error("42P01")
        ),
    ],
)
def test_when_an_error_is_translated_then_neither_sql_nor_values_survive(error):
    """Validates app.infrastructure.errors.translate_database_error()."""
    translated = translate_database_error(error)

    exposed = f"{translated!s} {translated.public_message} {translated.log_context!r}"
    assert SECRET_VALUE not in exposed
    assert "INSERT" not in exposed


@pytest.mark.unit
def test_when_a_conflict_is_built_from_an_error_then_only_its_class_is_kept():
    """Validates app.infrastructure.errors.conflict_from()."""
    conflict = conflict_from(operational_error(DEADLOCK_SQLSTATE))

    assert conflict.log_context == {"error_type": "OperationalError"}
    assert conflict.public_message == ConflictError.default_message


@pytest.mark.unit
def test_when_a_database_operation_fails_then_the_public_error_is_generic_and_not_a_503():
    """Validates app.infrastructure.errors.DatabaseOperationError."""
    error = DatabaseOperationError()

    assert error.error_code == "DATABASE_ERROR"
    assert isinstance(error, DomainError)
    assert not isinstance(error, ExternalServiceError)
    assert "database" not in error.public_message.lower()
