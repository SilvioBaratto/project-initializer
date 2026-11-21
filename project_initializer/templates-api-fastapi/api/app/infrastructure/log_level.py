"""Runtime log-level changes: an operator sends SIGHUP, the process re-reads ``LOG_LEVEL``.

A running process cannot see its own environment change, so the project ``.env``
file is the source an operator can edit while the service runs. ``reload_log_level``
therefore prefers the value in that file over the one in the process environment
(the reverse of the precedence at startup, where the environment wins), and falls
back to the environment when the file has none, which also undoes a level that
was set by hand.

Signal handlers only work in the main thread of the main interpreter, and SIGHUP
does not exist on Windows; ``reload_log_level_on_sighup`` degrades to doing
nothing in both cases.
"""

import logging
import os
import signal
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType

from dotenv import dotenv_values
from pydantic import TypeAdapter, ValidationError

from app.infrastructure.config import locate_project_dotenv
from app.infrastructure.settings import LOG_LEVEL_NAMES, LogLevel
from app.infrastructure.structured_logging import set_log_level

logger = logging.getLogger(__name__)

LOG_LEVEL_VARIABLE = "LOG_LEVEL"

_LOG_LEVEL_ADAPTER: TypeAdapter[str] = TypeAdapter(LogLevel)


def _configured_log_level(env_file: Path | None) -> str | None:
    from_file = None
    if env_file is not None and env_file.is_file():
        # dotenv_values leaves os.environ untouched: only LOG_LEVEL may change
        # while the service runs, never the other settings the file holds.
        from_file = dotenv_values(env_file).get(LOG_LEVEL_VARIABLE)
    return from_file or os.environ.get(LOG_LEVEL_VARIABLE)


def reload_log_level(env_file: Path | None) -> str | None:
    """Apply the ``LOG_LEVEL`` currently configured to the running process.

    The value comes from ``env_file`` when that file defines a non-empty
    ``LOG_LEVEL``, otherwise from the process environment. It is validated like
    the setting at startup, so any letter case is accepted. Nothing but the log
    level is changed: neither ``os.environ`` nor any other setting.

    Args:
        env_file: The project ``.env`` to read, or None to use the process
            environment alone. A path that is not a file counts as None.

    Returns:
        The level that was applied, lower case; None when no ``LOG_LEVEL`` is
        configured or the configured one is invalid. An invalid value keeps the
        current level and is reported by one warning that carries the length of
        the rejected text and the accepted names, never the text itself.

    Raises:
        OSError: ``env_file`` exists but cannot be read.
    """
    configured = _configured_log_level(env_file)
    if configured is None:
        return None
    try:
        level = _LOG_LEVEL_ADAPTER.validate_python(configured)
    except ValidationError:
        logger.warning(
            "log_level.reload_rejected",
            extra={
                "rejected_length": len(configured),
                "accepted_levels": list(LOG_LEVEL_NAMES),
            },
        )
        return None
    set_log_level(level)
    # Not named "level": the JSON formatter reserves that key for the severity.
    logger.info("log_level.reloaded", extra={"applied_level": level})
    return level


def _handle_sighup(_signal_number: int, _frame: FrameType | None) -> None:
    # A handler runs inside whatever the main thread was doing, so an exception
    # raised here would surface in unrelated code: it is logged instead.
    try:
        reload_log_level(locate_project_dotenv())
    except Exception as error:
        logger.warning(
            "log_level.reload_failed", extra={"error_type": type(error).__name__}
        )


@contextmanager
def reload_log_level_on_sighup() -> Iterator[bool]:
    """Reload the log level whenever the process receives SIGHUP.

    The previous SIGHUP disposition is put back when the block ends, so the
    handler never outlives the application that installed it. Note that a
    terminal hang-up also sends SIGHUP: a server started from a terminal that
    closes keeps running instead of exiting.

    Yields:
        True when the handler is installed; False when it is not because the
        platform has no SIGHUP or the caller is not the main thread, in which
        case the block still runs.
    """
    sighup = getattr(signal, "SIGHUP", None)
    if sighup is None or threading.current_thread() is not threading.main_thread():
        yield False
        return
    previous = signal.signal(sighup, _handle_sighup)
    try:
        yield True
    finally:
        # signal.signal returns None for a handler that was not set from Python.
        signal.signal(sighup, signal.SIG_DFL if previous is None else previous)
