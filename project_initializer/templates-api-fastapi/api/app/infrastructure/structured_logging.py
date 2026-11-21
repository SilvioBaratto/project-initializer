"""Structured logging: JSON or text records that carry the request id.

Building the JSON with ``json.dumps`` (rather than a ``%`` format string) keeps
every line valid JSON even when a message holds quotes or newlines, and it lets
fields passed through ``extra=`` reach the log aggregator.
"""

import copy
import json
import logging
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime

from app.infrastructure.audit import AUDIT_LOGGER_NAME
from app.infrastructure.request_context import current_request_id

NO_REQUEST_ID = "-"
TEXT_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"
UVICORN_ACCESS_LOGGER_NAME = "uvicorn.access"
_UVICORN_LOGGER_NAMES = ("uvicorn", "uvicorn.error", UVICORN_ACCESS_LOGGER_NAME)

# C0 and C1 control characters plus the Unicode line separators: a terminal or a
# log viewer starts a new line at any of them, which would let a request path
# forge a record.
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")

# Attributes every LogRecord has; anything else on a record came from ``extra=``.
_STANDARD_RECORD_FIELDS = frozenset(
    vars(logging.LogRecord("", logging.NOTSET, "", 0, "", (), None))
) | {"message", "asctime", "taskName"}


def _request_id_of(record: logging.LogRecord) -> str | None:
    return getattr(record, "request_id", None) or current_request_id()


def _escape_control_characters(text: str) -> str:
    return _CONTROL_CHARACTERS.sub(
        lambda match: match.group().encode("unicode_escape").decode("ascii"), text
    )


def _extra_fields(record: logging.LogRecord) -> dict[str, object]:
    """Return the fields the caller attached through ``extra=``, in insertion order."""
    return {
        key: value
        for key, value in vars(record).items()
        if key not in _STANDARD_RECORD_FIELDS
    }


class JsonLogFormatter(logging.Formatter):
    """Renders each record as one JSON object on one line.

    The object holds ``timestamp`` (ISO 8601, UTC), ``level``, ``logger``,
    ``message``, ``request_id`` (null outside a request), any fields passed via
    ``extra=``, and ``exception`` when the record carries exception info.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Serialise ``record`` to a JSON string.

        Args:
            record: The record to render.

        Returns:
            A single-line JSON document. Extras that are not JSON-serialisable
            are rendered with ``str``; they never make logging raise.
        """
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _request_id_of(record),
        }
        for key, value in _extra_fields(record).items():
            payload.setdefault(key, value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str)


class TextLogFormatter(logging.Formatter):
    """Human-readable format for a terminal, still tagged with the request id."""

    def __init__(self) -> None:
        super().__init__(TEXT_LOG_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        """Render ``record`` as one text line, plus the traceback when present.

        Control characters in the message and in the extra fields are written as
        escape sequences, so a value taken from a request cannot start a second,
        forged line. The traceback keeps its own line breaks.

        Args:
            record: The record to render. It is not modified.

        Returns:
            The formatted line, with ``key=value`` pairs for every field passed
            through ``extra=`` after the message; the request id shows ``-``
            outside a request.
        """
        extras = (
            f"{key}={_escape_control_characters(str(value))}"
            for key, value in _extra_fields(record).items()
            if key != "request_id"
        )
        # A copy keeps the escaped text and the request id away from the other
        # handlers that receive the same record.
        printable = copy.copy(record)
        printable.msg = " ".join(
            (_escape_control_characters(record.getMessage()), *extras)
        )
        printable.args = None
        printable.request_id = _request_id_of(record) or NO_REQUEST_ID
        return super().format(printable)


class ManagedStreamHandler(logging.StreamHandler):
    """Marks the root handler owned by ``configure_logging``."""


_FORMATTERS: dict[str, Callable[[], logging.Formatter]] = {
    "json": JsonLogFormatter,
    "text": TextLogFormatter,
}


def _formatter_for(log_format: str) -> logging.Formatter:
    try:
        return _FORMATTERS[log_format]()
    except KeyError:
        raise ValueError(f"Unknown log format: {log_format!r}") from None


def _numeric_level(level: str) -> int:
    numeric_level = logging.getLevelNamesMapping().get(level.upper())
    if numeric_level is None:
        raise ValueError(f"Unknown log level: {level!r}")
    return numeric_level


def _managed_root_handler() -> ManagedStreamHandler:
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, ManagedStreamHandler):
            return handler
    handler = ManagedStreamHandler(sys.stdout)
    root.addHandler(handler)
    return handler


def _route_server_logs_through_root() -> None:
    # uvicorn installs its own plain-text handlers and stops propagation, so its
    # tracebacks would bypass the JSON formatter; its access line is replaced by
    # the structured ``http.request`` record and would only repeat the client
    # address and query string unstructured.
    for name in _UVICORN_LOGGER_NAMES:
        server_logger = logging.getLogger(name)
        server_logger.handlers.clear()
        server_logger.propagate = True
        server_logger.setLevel(logging.NOTSET)
    logging.getLogger(UVICORN_ACCESS_LOGGER_NAME).disabled = True


def configure_logging(level: str, log_format: str) -> None:
    """Configure the root logger to write structured records to stdout.

    Safe to call more than once: the second call reconfigures the existing
    handler instead of adding another, so records are never duplicated. It also
    pins the ``app.audit`` logger to INFO so the audit trail survives a high
    ``level``, and hands the uvicorn loggers over to the root handler so server
    errors come out in the same format; uvicorn's access log is switched off.

    Args:
        level: Minimum severity name, case-insensitive (for example ``"info"``).
        log_format: ``"json"`` or ``"text"``.

    Raises:
        ValueError: ``level`` is not a standard logging level or ``log_format``
            is not a known format. The logging configuration is left unchanged.
    """
    formatter = _formatter_for(log_format)
    numeric_level = _numeric_level(level)

    _managed_root_handler().setFormatter(formatter)
    logging.getLogger().setLevel(numeric_level)
    logging.getLogger(AUDIT_LOGGER_NAME).setLevel(logging.INFO)
    _route_server_logs_through_root()


def set_log_level(level: str) -> None:
    """Change the minimum severity of the running process.

    Lets an operator raise or lower the verbosity without a restart, for example
    from a shell attached to the process; the SIGHUP handler of
    ``app.infrastructure.log_level`` calls it. The ``app.audit`` logger keeps its
    own INFO level.

    Args:
        level: Minimum severity name, case-insensitive (for example ``"debug"``).

    Raises:
        ValueError: ``level`` is not a standard logging level; the current level
            is kept.
    """
    logging.getLogger().setLevel(_numeric_level(level))
