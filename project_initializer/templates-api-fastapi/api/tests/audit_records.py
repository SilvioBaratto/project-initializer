"""Reading the audit trail from captured log records."""

import logging

import pytest

from app.infrastructure.audit import AUDIT_EVENT, AUDIT_LOGGER_NAME


def audit_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return the audit records captured so far, oldest first.

    Args:
        caplog: The ``caplog`` fixture of the test, with the audit logger enabled
            at INFO (``caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME)``).

    Returns:
        The records of the audit logger; each carries ``action``,
        ``resource_id`` and ``actor_id`` as attributes.
    """
    return [
        record
        for record in caplog.records
        if record.name == AUDIT_LOGGER_NAME and record.getMessage() == AUDIT_EVENT
    ]
