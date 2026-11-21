"""Unit tests for the audit trail helper."""

import logging

import pytest

from app.infrastructure.audit import AUDIT_EVENT, AUDIT_LOGGER_NAME, write_audit_log

pytestmark = pytest.mark.unit

ACTION = "item.create"
RESOURCE_ID = "3f2c9d1e-0000-4000-8000-000000000001"
ACTOR_ID = "actor-42"


def _audit_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == AUDIT_LOGGER_NAME]


def test_when_an_action_is_audited_then_one_info_record_carries_the_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Validates app.infrastructure.audit.write_audit_log()."""
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        write_audit_log(ACTION, RESOURCE_ID, ACTOR_ID)

    (record,) = _audit_records(caplog)
    assert record.levelno == logging.INFO
    assert (record.action, record.resource_id, record.actor_id) == (
        ACTION,
        RESOURCE_ID,
        ACTOR_ID,
    )


def test_when_different_actions_are_audited_then_the_message_stays_constant(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Validates app.infrastructure.audit.write_audit_log()."""
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        write_audit_log("item.create", "item-1", "actor-1")
        write_audit_log("item.delete", "item-2", "actor-2")

    messages = [record.getMessage() for record in _audit_records(caplog)]
    assert messages == [AUDIT_EVENT, AUDIT_EVENT]
