"""Audit trail for state-changing actions.

The helper is a plain ``def`` on purpose: FastAPI runs a sync callable scheduled
through ``BackgroundTasks`` in its worker threadpool, so the log write never
blocks the event loop or the response.
"""

import logging

AUDIT_LOGGER_NAME = "app.audit"
# A constant message keeps every audit record findable with one search term; the
# variable parts travel as fields, so the JSON output keeps them queryable.
AUDIT_EVENT = "audit.action"

logger = logging.getLogger(AUDIT_LOGGER_NAME)


def write_audit_log(action: str, resource_id: str, actor_id: str) -> None:
    """Record who did what to which resource.

    The record goes out at INFO on the ``app.audit`` logger with the fields
    ``action``, ``resource_id`` and ``actor_id``. ``configure_logging`` pins that
    logger to INFO, so a high ``LOG_LEVEL`` does not switch the trail off.

    Args:
        action: Dotted action name, for example ``"item.create"``.
        resource_id: Identifier of the affected resource.
        actor_id: Opaque identifier of the authenticated caller. Never pass an
            email or a username: logs must not identify a person directly.
    """
    logger.info(
        AUDIT_EVENT,
        extra={"action": action, "resource_id": resource_id, "actor_id": actor_id},
    )
