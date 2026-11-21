"""Unit tests for structured logging and the request-id context."""

import json
import logging
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from io import StringIO

import pytest

from app.infrastructure.audit import AUDIT_EVENT, AUDIT_LOGGER_NAME, write_audit_log
from app.infrastructure.request_context import (
    bind_request_id,
    current_request_id,
    reset_request_id,
)
from app.infrastructure.structured_logging import (
    NO_REQUEST_ID,
    UVICORN_ACCESS_LOGGER_NAME,
    JsonLogFormatter,
    ManagedStreamHandler,
    TextLogFormatter,
    configure_logging,
    set_log_level,
)

pytestmark = pytest.mark.unit

CapturedLogger = tuple[logging.Logger, StringIO]
LoggerState = tuple[list[logging.Handler], bool, int, bool]

REQUEST_ID = "req-1234"
RECORD_REQUEST_ID = "req-from-record"
DURATION_MS = 12.5
SERVER_LOGGER_NAMES = ("uvicorn", "uvicorn.error", UVICORN_ACCESS_LOGGER_NAME)
FORGED_LINE = "2026-01-01 INFO app.audit [-] admin granted"


@pytest.fixture
def captured() -> Iterator[CapturedLogger]:
    """A detached logger writing through ``JsonLogFormatter`` into a buffer."""
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger("tests.structured_logging")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)
    yield logger, stream
    logger.removeHandler(handler)


def _logger_state(logger: logging.Logger) -> LoggerState:
    return list(logger.handlers), logger.propagate, logger.level, logger.disabled


def _restore_logger(logger: logging.Logger, state: LoggerState) -> None:
    handlers, propagate, level, disabled = state
    logger.handlers[:] = handlers
    logger.propagate = propagate
    logger.setLevel(level)
    logger.disabled = disabled


@pytest.fixture
def restored_root_logger() -> Iterator[logging.Logger]:
    """The root logger, with every logger ``configure_logging`` touches restored.

    Covers the root handlers and level, the audit logger's level and the uvicorn
    loggers, so no test leaks its configuration into the next one.
    """
    root = logging.getLogger()
    touched = [root, logging.getLogger(AUDIT_LOGGER_NAME)] + [
        logging.getLogger(name) for name in SERVER_LOGGER_NAMES
    ]
    saved = [(logger, _logger_state(logger)) for logger in touched]
    # Importing app.main (conftest does) already installed the managed handler; tests
    # of configure_logging must start from a root logger that does not have one.
    root.handlers[:] = [
        handler
        for handler in root.handlers
        if not isinstance(handler, ManagedStreamHandler)
    ]
    yield root
    for logger, state in saved:
        _restore_logger(logger, state)


def _only_record(stream: StringIO) -> dict[str, object]:
    lines = stream.getvalue().splitlines()
    assert len(lines) == 1, "one log call must produce exactly one line"
    return json.loads(lines[0])


def _json_lines(output: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]


def _text_record(**fields: object) -> logging.LogRecord:
    return logging.makeLogRecord({"levelno": logging.INFO, **fields})


def test_when_a_message_holds_quotes_and_newlines_then_the_json_stays_valid(
    captured: CapturedLogger,
) -> None:
    """Validates app.infrastructure.structured_logging.JsonLogFormatter.format()."""
    logger, stream = captured
    message = 'user said "hello"\nsecond line\twith a tab and \\ backslash'

    logger.info("%s", message)

    assert _only_record(stream)["message"] == message


def test_when_a_record_is_logged_then_it_carries_timestamp_level_logger_and_message(
    captured: CapturedLogger,
) -> None:
    """Validates app.infrastructure.structured_logging.JsonLogFormatter.format()."""
    logger, stream = captured

    logger.warning("disk almost full")

    payload = _only_record(stream)
    assert payload["level"] == "WARNING"
    assert payload["logger"] == "tests.structured_logging"
    assert payload["message"] == "disk almost full"
    moment = datetime.fromisoformat(str(payload["timestamp"]))
    assert moment.utcoffset() == timedelta(0)
    assert abs(datetime.now(UTC) - moment) < timedelta(minutes=1)


def test_when_a_request_id_is_bound_then_the_json_record_carries_it(
    captured: CapturedLogger,
) -> None:
    """Validates app.infrastructure.structured_logging.JsonLogFormatter.format()."""
    logger, stream = captured
    token = bind_request_id(REQUEST_ID)
    try:
        logger.info("inside a request")
    finally:
        reset_request_id(token)

    assert _only_record(stream)["request_id"] == REQUEST_ID


def test_when_no_request_is_active_then_the_json_request_id_is_null(
    captured: CapturedLogger,
) -> None:
    """Validates app.infrastructure.structured_logging.JsonLogFormatter.format()."""
    logger, stream = captured

    logger.info("startup")

    assert _only_record(stream)["request_id"] is None


def test_when_the_record_names_a_request_id_then_it_wins_over_the_bound_one(
    captured: CapturedLogger,
) -> None:
    """Validates app.infrastructure.structured_logging.JsonLogFormatter.format()."""
    logger, stream = captured
    token = bind_request_id(REQUEST_ID)
    try:
        logger.info("from a worker", extra={"request_id": RECORD_REQUEST_ID})
    finally:
        reset_request_id(token)

    assert _only_record(stream)["request_id"] == RECORD_REQUEST_ID


def test_when_extra_fields_are_passed_then_the_json_record_includes_them(
    captured: CapturedLogger,
) -> None:
    """Validates app.infrastructure.structured_logging.JsonLogFormatter.format()."""
    logger, stream = captured

    logger.info("http.request", extra={"path": "/items", "duration_ms": DURATION_MS})

    payload = _only_record(stream)
    assert payload["path"] == "/items"
    assert payload["duration_ms"] == DURATION_MS


def test_when_extra_fields_clash_with_core_fields_then_the_core_fields_win(
    captured: CapturedLogger,
) -> None:
    """Validates app.infrastructure.structured_logging.JsonLogFormatter.format()."""
    logger, stream = captured

    logger.info("real message", extra={"level": "SPOOFED", "logger": "spoofed"})

    payload = _only_record(stream)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "tests.structured_logging"


def test_when_an_extra_is_not_serialisable_then_logging_still_works(
    captured: CapturedLogger,
) -> None:
    """Validates app.infrastructure.structured_logging.JsonLogFormatter.format()."""
    logger, stream = captured
    marker = object()

    logger.info("odd extra", extra={"marker": marker})

    assert _only_record(stream)["marker"] == str(marker)


def test_when_an_exception_is_logged_then_the_traceback_is_one_json_field(
    captured: CapturedLogger,
) -> None:
    """Validates app.infrastructure.structured_logging.JsonLogFormatter.format()."""
    logger, stream = captured

    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("operation failed")

    exception = str(_only_record(stream)["exception"])
    assert "Traceback" in exception
    assert "ValueError: boom" in exception


def test_when_a_request_id_is_bound_then_the_text_line_shows_it() -> None:
    """Validates app.infrastructure.structured_logging.TextLogFormatter.format()."""
    record = _text_record(msg="hello")
    token = bind_request_id(REQUEST_ID)
    try:
        line = TextLogFormatter().format(record)
    finally:
        reset_request_id(token)

    assert f"[{REQUEST_ID}]" in line
    assert "hello" in line


def test_when_no_request_is_active_then_the_text_line_shows_a_dash() -> None:
    """Validates app.infrastructure.structured_logging.TextLogFormatter.format()."""
    assert f"[{NO_REQUEST_ID}]" in TextLogFormatter().format(_text_record(msg="hello"))


def test_when_the_record_names_a_request_id_then_the_text_line_prefers_it() -> None:
    """Validates app.infrastructure.structured_logging.TextLogFormatter.format()."""
    record = _text_record(msg="hello", request_id=RECORD_REQUEST_ID)
    token = bind_request_id(REQUEST_ID)
    try:
        line = TextLogFormatter().format(record)
    finally:
        reset_request_id(token)

    assert f"[{RECORD_REQUEST_ID}]" in line
    assert REQUEST_ID not in line


def test_when_extra_fields_are_passed_then_the_text_line_appends_them() -> None:
    """Validates app.infrastructure.structured_logging.TextLogFormatter.format()."""
    record = _text_record(
        msg="http.request", status=HTTPStatus.OK.value, duration_ms=DURATION_MS
    )

    line = TextLogFormatter().format(record)

    assert line.endswith(f"http.request status=200 duration_ms={DURATION_MS}")


def test_when_a_text_record_has_a_traceback_then_the_fields_precede_it() -> None:
    """Validates app.infrastructure.structured_logging.TextLogFormatter.format()."""
    try:
        raise ValueError("boom")
    except ValueError:
        record = _text_record(
            msg="failed", status=HTTPStatus.INTERNAL_SERVER_ERROR.value
        )
        record.exc_info = sys.exc_info()

    lines = TextLogFormatter().format(record).splitlines()

    assert lines[0].endswith("failed status=500")
    assert "Traceback" in lines[1]
    assert lines[-1] == "ValueError: boom"


@pytest.mark.parametrize(
    "separator", ["\n", "\r", "\r\n", "\x1b", "\x00", "\x85", " ", " "]
)
def test_when_a_message_holds_a_line_separator_then_the_text_line_cannot_be_forged(
    separator: str,
) -> None:
    """Validates app.infrastructure.structured_logging.TextLogFormatter.format()."""
    record = _text_record(msg="%s", args=(f"/x{separator}{FORGED_LINE}",))

    line = TextLogFormatter().format(record)

    assert len(line.splitlines()) == 1
    assert separator not in line
    assert FORGED_LINE in line


@pytest.mark.parametrize("separator", ["\n", "\r", "\x1b", " "])
def test_when_an_extra_holds_a_line_separator_then_the_text_line_cannot_be_forged(
    separator: str,
) -> None:
    """Validates app.infrastructure.structured_logging.TextLogFormatter.format()."""
    record = _text_record(msg="http.request", path=f"/x{separator}{FORGED_LINE}")

    line = TextLogFormatter().format(record)

    assert len(line.splitlines()) == 1
    assert separator not in line
    assert FORGED_LINE in line


def test_when_a_text_record_is_formatted_then_the_original_is_unchanged() -> None:
    """Validates app.infrastructure.structured_logging.TextLogFormatter.format()."""
    record = _text_record(msg="%s", args=("a\nb",), path="/x\ny")

    TextLogFormatter().format(record)

    assert record.msg == "%s"
    assert record.args == ("a\nb",)
    assert not hasattr(record, "request_id")


def test_when_a_request_id_is_reset_then_the_previous_one_is_restored() -> None:
    """Validates app.infrastructure.request_context.reset_request_id()."""
    outer = bind_request_id("outer")
    inner = bind_request_id("inner")
    assert current_request_id() == "inner"

    reset_request_id(inner)
    assert current_request_id() == "outer"

    reset_request_id(outer)
    assert current_request_id() is None


def test_when_configure_logging_runs_twice_then_one_handler_is_added(
    restored_root_logger: logging.Logger,
) -> None:
    """Validates app.infrastructure.structured_logging.configure_logging()."""
    before = list(restored_root_logger.handlers)

    configure_logging("info", "json")
    configure_logging("debug", "text")

    added = [h for h in restored_root_logger.handlers if h not in before]
    assert len(added) == 1
    assert isinstance(added[0], ManagedStreamHandler)
    assert isinstance(added[0].formatter, TextLogFormatter)
    assert restored_root_logger.level == logging.DEBUG


def test_when_configure_logging_runs_then_json_lines_go_to_stdout(
    restored_root_logger: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    """Validates app.infrastructure.structured_logging.configure_logging()."""
    configure_logging("info", "json")

    logging.getLogger("tests.end_to_end").info("hello")

    emitted = _json_lines(capsys.readouterr().out)
    assert [entry["message"] for entry in emitted] == ["hello"]


@pytest.mark.parametrize(
    ("level", "log_format"), [("verbose", "json"), ("info", "xml")]
)
def test_when_configure_logging_gets_an_unknown_value_then_nothing_changes(
    restored_root_logger: logging.Logger, level: str, log_format: str
) -> None:
    """Validates app.infrastructure.structured_logging.configure_logging()."""
    handlers_before = list(restored_root_logger.handlers)
    level_before = restored_root_logger.level

    with pytest.raises(ValueError, match="Unknown log"):
        configure_logging(level, log_format)

    assert restored_root_logger.handlers == handlers_before
    assert restored_root_logger.level == level_before


def test_when_the_log_level_is_high_then_audit_records_are_still_written(
    restored_root_logger: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    """Validates app.infrastructure.structured_logging.configure_logging()."""
    configure_logging("critical", "json")

    logging.getLogger("tests.other").warning("below the configured level")
    write_audit_log("item.create", "item-1", "actor-1")

    (entry,) = _json_lines(capsys.readouterr().out)
    assert entry["message"] == AUDIT_EVENT
    assert entry["logger"] == AUDIT_LOGGER_NAME
    assert entry["action"] == "item.create"
    assert entry["resource_id"] == "item-1"
    assert entry["actor_id"] == "actor-1"


def test_when_the_server_set_up_its_own_handler_then_its_errors_come_out_as_json(
    restored_root_logger: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    """Validates app.infrastructure.structured_logging.configure_logging()."""
    server_logger = logging.getLogger("uvicorn.error")
    server_parent = logging.getLogger("uvicorn")
    for logger in (server_logger, server_parent):
        logger.addHandler(logging.StreamHandler(sys.stderr))
        logger.propagate = False
        logger.setLevel(logging.INFO)

    configure_logging("info", "json")
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        server_logger.exception("Exception in ASGI application")

    captured = capsys.readouterr()
    (entry,) = _json_lines(captured.out)
    assert entry["logger"] == "uvicorn.error"
    assert "RuntimeError: boom" in str(entry["exception"])
    assert captured.err == ""


def test_when_the_log_level_is_raised_then_the_server_loggers_follow_it(
    restored_root_logger: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    """Validates app.infrastructure.structured_logging.configure_logging()."""
    logging.getLogger("uvicorn").setLevel(logging.INFO)

    configure_logging("error", "json")
    logging.getLogger("uvicorn.error").info("Application startup complete.")

    assert _json_lines(capsys.readouterr().out) == []


def test_when_the_server_logs_an_access_line_then_nothing_is_written(
    restored_root_logger: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    """Validates app.infrastructure.structured_logging.configure_logging()."""
    configure_logging("info", "json")

    logging.getLogger(UVICORN_ACCESS_LOGGER_NAME).info("10.0.0.1 GET /x?token=abc")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_when_set_log_level_is_called_then_the_root_level_changes(
    restored_root_logger: logging.Logger,
) -> None:
    """Validates app.infrastructure.structured_logging.set_log_level()."""
    set_log_level("WARNING")
    assert restored_root_logger.level == logging.WARNING

    set_log_level("debug")
    assert restored_root_logger.level == logging.DEBUG


def test_when_set_log_level_gets_an_unknown_name_then_the_level_is_kept(
    restored_root_logger: logging.Logger,
) -> None:
    """Validates app.infrastructure.structured_logging.set_log_level()."""
    set_log_level("info")

    with pytest.raises(ValueError, match="Unknown log level"):
        set_log_level("verbose")

    assert restored_root_logger.level == logging.INFO
