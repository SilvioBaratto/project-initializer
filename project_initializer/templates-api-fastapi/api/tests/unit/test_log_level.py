"""Unit tests for reloading the log level of a running process."""

import json
import logging
import os
import signal
import threading
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.infrastructure import log_level
from app.infrastructure.log_level import (
    LOG_LEVEL_VARIABLE,
    reload_log_level,
    reload_log_level_on_sighup,
)
from app.infrastructure.settings import LOG_LEVEL_NAMES
from app.infrastructure.structured_logging import JsonLogFormatter

pytestmark = pytest.mark.unit

REJECTED_LEVEL = "chatty-level"
LOGGER_NAME = "app.infrastructure.log_level"
UNRELATED_SETTING = "LOG_LEVEL_TEST_UNRELATED_SETTING"


@pytest.fixture(autouse=True)
def isolated_log_level(
    monkeypatch: pytest.MonkeyPatch, restored_root_level: int
) -> None:
    """Start without a ``LOG_LEVEL`` in the environment; the root level is restored."""
    monkeypatch.delenv(LOG_LEVEL_VARIABLE, raising=False)
    monkeypatch.delenv(UNRELATED_SETTING, raising=False)
    logging.getLogger().setLevel(logging.ERROR)


@pytest.fixture
def write_env_file(tmp_path: Path) -> Callable[[str], Path]:
    """Factory that writes a ``.env`` file with the given body."""

    def write(body: str) -> Path:
        """Write ``body`` to ``.env`` below the test's temporary directory."""
        env_file = tmp_path / ".env"
        env_file.write_text(body, encoding="utf-8")
        return env_file

    return write


def test_when_the_file_sets_a_level_then_it_is_applied_to_the_root_logger(
    write_env_file,
) -> None:
    """Validates app.infrastructure.log_level.reload_log_level()."""
    applied = reload_log_level(write_env_file("LOG_LEVEL=debug\n"))

    assert applied == "debug"
    assert logging.getLogger().level == logging.DEBUG


def test_when_the_level_has_capitals_then_it_is_lowercased_and_applied(
    write_env_file,
) -> None:
    """Validates app.infrastructure.log_level.reload_log_level()."""
    applied = reload_log_level(write_env_file("LOG_LEVEL=WARNING\n"))

    assert applied == "warning"
    assert logging.getLogger().level == logging.WARNING


def test_when_file_and_environment_disagree_then_the_file_wins(
    write_env_file, monkeypatch
) -> None:
    """Validates app.infrastructure.log_level.reload_log_level().

    The process environment cannot change while the process runs, and at startup
    it already holds the value the file had then, so the file is the one source
    an operator can edit.
    """
    monkeypatch.setenv(LOG_LEVEL_VARIABLE, "error")

    applied = reload_log_level(write_env_file("LOG_LEVEL=debug\n"))

    assert applied == "debug"


@pytest.mark.parametrize("file_body", ["OTHER=1\n", "LOG_LEVEL=\n", "LOG_LEVEL\n"])
def test_when_the_file_has_no_usable_level_then_the_environment_is_used(
    write_env_file, monkeypatch, file_body
) -> None:
    """Validates app.infrastructure.log_level.reload_log_level()."""
    monkeypatch.setenv(LOG_LEVEL_VARIABLE, "warning")

    applied = reload_log_level(write_env_file(file_body))

    assert applied == "warning"
    assert logging.getLogger().level == logging.WARNING


def test_when_there_is_no_file_then_the_environment_is_used(monkeypatch) -> None:
    """Validates app.infrastructure.log_level.reload_log_level()."""
    monkeypatch.setenv(LOG_LEVEL_VARIABLE, "info")

    assert reload_log_level(None) == "info"
    assert logging.getLogger().level == logging.INFO


def test_when_the_file_does_not_exist_then_the_environment_is_used(
    tmp_path, monkeypatch
) -> None:
    """Validates app.infrastructure.log_level.reload_log_level()."""
    monkeypatch.setenv(LOG_LEVEL_VARIABLE, "critical")

    assert reload_log_level(tmp_path / "missing.env") == "critical"


def test_when_no_level_is_configured_then_nothing_changes() -> None:
    """Validates app.infrastructure.log_level.reload_log_level()."""
    assert reload_log_level(None) is None
    assert logging.getLogger().level == logging.ERROR


def test_when_the_file_holds_other_settings_then_the_environment_is_not_changed(
    write_env_file,
) -> None:
    """Validates app.infrastructure.log_level.reload_log_level().

    Only the log level may change while the service runs; the other settings in
    the file are read once at startup.
    """
    env_file = write_env_file(f"{UNRELATED_SETTING}=x\nLOG_LEVEL=debug\n")

    reload_log_level(env_file)

    assert UNRELATED_SETTING not in os.environ
    assert LOG_LEVEL_VARIABLE not in os.environ


def test_when_the_level_is_invalid_then_the_current_level_is_kept_with_one_warning(
    write_env_file, caplog
) -> None:
    """Validates app.infrastructure.log_level.reload_log_level()."""
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        applied = reload_log_level(write_env_file(f"LOG_LEVEL={REJECTED_LEVEL}\n"))

    assert applied is None
    assert logging.getLogger().level == logging.ERROR
    warnings = [record for record in caplog.records if record.name == LOGGER_NAME]
    assert len(warnings) == 1
    assert warnings[0].rejected_length == len(REJECTED_LEVEL)
    assert warnings[0].accepted_levels == list(LOG_LEVEL_NAMES)


def test_when_the_level_is_invalid_then_the_rejected_text_is_not_logged(
    write_env_file, caplog
) -> None:
    """Validates app.infrastructure.log_level.reload_log_level().

    The records are rendered as the JSON formatter would, extra fields included,
    because ``caplog.text`` leaves those out.
    """
    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        reload_log_level(write_env_file(f"LOG_LEVEL={REJECTED_LEVEL}\n"))

    rendered = [
        JsonLogFormatter().format(record)
        for record in caplog.records
        if record.name == LOGGER_NAME
    ]
    assert rendered
    assert all(REJECTED_LEVEL not in line for line in rendered)


def test_when_the_level_is_applied_then_the_change_is_logged_once(
    write_env_file, caplog
) -> None:
    """Validates app.infrastructure.log_level.reload_log_level()."""
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        reload_log_level(write_env_file("LOG_LEVEL=info\n"))

    reloads = [r for r in caplog.records if r.getMessage() == "log_level.reloaded"]
    rendered = [json.loads(JsonLogFormatter().format(record)) for record in reloads]
    assert [line["applied_level"] for line in rendered] == ["info"]


@pytest.mark.usefixtures("ignored_sighup")
def test_when_sighup_arrives_then_the_level_is_reloaded_and_the_handler_removed(
    write_env_file, monkeypatch
) -> None:
    """Validates app.infrastructure.log_level.reload_log_level_on_sighup()."""
    env_file = write_env_file("LOG_LEVEL=debug\n")
    monkeypatch.setattr(log_level, "locate_project_dotenv", lambda: env_file)

    with reload_log_level_on_sighup() as installed:
        assert installed is True
        signal.raise_signal(signal.SIGHUP)
        assert logging.getLogger().level == logging.DEBUG

    assert signal.getsignal(signal.SIGHUP) is signal.SIG_IGN


@pytest.mark.usefixtures("ignored_sighup")
def test_when_the_block_fails_then_the_previous_handler_is_still_restored() -> None:
    """Validates app.infrastructure.log_level.reload_log_level_on_sighup()."""
    with pytest.raises(RuntimeError, match="boom"), reload_log_level_on_sighup():
        raise RuntimeError("boom")

    assert signal.getsignal(signal.SIGHUP) is signal.SIG_IGN


@pytest.mark.usefixtures("ignored_sighup")
def test_when_the_reload_fails_then_sighup_logs_a_warning_and_raises_nothing(
    monkeypatch, caplog
) -> None:
    """Validates app.infrastructure.log_level.reload_log_level_on_sighup().

    A handler runs inside arbitrary main-thread code, so an error must not leave it.
    """

    def unreadable_file(_env_file: Path | None) -> str | None:
        """Fail like a ``.env`` that the process may not read."""
        raise PermissionError("not-for-the-log")

    monkeypatch.setattr(log_level, "locate_project_dotenv", lambda: None)
    monkeypatch.setattr(log_level, "reload_log_level", unreadable_file)

    with (
        caplog.at_level(logging.WARNING, logger=LOGGER_NAME),
        reload_log_level_on_sighup(),
    ):
        signal.raise_signal(signal.SIGHUP)

    failures = [
        r for r in caplog.records if r.getMessage() == "log_level.reload_failed"
    ]
    assert [record.error_type for record in failures] == ["PermissionError"]
    assert "not-for-the-log" not in caplog.text


@pytest.mark.usefixtures("ignored_sighup")
def test_when_called_off_the_main_thread_then_no_handler_is_installed() -> None:
    """Validates app.infrastructure.log_level.reload_log_level_on_sighup()."""
    outcomes: list[tuple[bool, object]] = []

    def run() -> None:
        """Enter the context from a worker thread and note what it reports."""
        with reload_log_level_on_sighup() as installed:
            outcomes.append((installed, signal.getsignal(signal.SIGHUP)))

    worker = threading.Thread(target=run)
    worker.start()
    worker.join()

    assert outcomes == [(False, signal.SIG_IGN)]


def test_when_the_platform_has_no_sighup_then_the_block_runs_without_a_handler(
    monkeypatch,
) -> None:
    """Validates app.infrastructure.log_level.reload_log_level_on_sighup().

    The module's own ``signal`` reference is replaced, not the real module, so the
    fixtures that restore SIGHUP keep working.
    """
    monkeypatch.setattr(log_level, "signal", SimpleNamespace())

    with reload_log_level_on_sighup() as installed:
        assert installed is False


@pytest.mark.usefixtures("ignored_sighup")
def test_when_the_previous_handler_is_unknown_then_the_default_is_restored(
    monkeypatch,
) -> None:
    """Validates app.infrastructure.log_level.reload_log_level_on_sighup().

    ``signal.signal`` answers None for a handler that was installed from C.
    """
    installed_handlers: list[object] = []

    def install(_signal_number: int, handler: object) -> None:
        """Record the handler and answer None, as ``signal.signal`` can."""
        installed_handlers.append(handler)

    fake_signal_module = SimpleNamespace(
        signal=install,
        SIGHUP=signal.SIGHUP,
        SIG_DFL=signal.SIG_DFL,
    )
    monkeypatch.setattr(log_level, "signal", fake_signal_module)

    with reload_log_level_on_sighup():
        pass

    assert installed_handlers[-1] == signal.SIG_DFL
