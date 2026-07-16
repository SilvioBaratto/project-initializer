"""Audit-log helper for FastAPI ``BackgroundTasks`` demos.

``write_audit_log`` is a side-effect-only logging helper: it records that a
domain action happened, with no database write and no extra dependency. It is
scheduled via ``BackgroundTasks.add_task`` so it runs *after* the response is
sent and never blocks the request.

Kept as a plain ``def`` (not ``async def``) on purpose: when a sync callable is
scheduled, FastAPI/Starlette runs it in a worker threadpool, so this logging
side-effect never touches the event loop — matching the template's sync rule.
"""

import logging

logger = logging.getLogger("app.audit")


def write_audit_log(action: str, resource_id: str) -> None:
    """Log a single audit line for ``action`` on ``resource_id``.

    Args:
        action: Dotted action name, e.g. ``"item.create"``.
        resource_id: Identifier of the affected resource.
    """
    logger.info("audit action=%s resource_id=%s", action, resource_id)
