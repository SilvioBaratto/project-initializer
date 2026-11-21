"""Unit tests for the database circuit breaker, driven by a fake clock."""

import asyncio
import logging
import threading

import pytest

from app.infrastructure.circuit_breaker import (
    CallTicket,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from app.infrastructure.errors import CircuitOpenError
from tests.fakes import FakeClock

FAILURE_THRESHOLD = 3
RESET_TIMEOUT_SECONDS = 30.0
BREAKER_NAME = "orders-database"
LOCK_WAIT_SECONDS = 1.0
CONCURRENT_THREADS = 50


class DependencyDownError(Exception):
    """Failure type the breaker under test counts."""


class DeadlockError(DependencyDownError):
    """A failure type that the predicate under test refuses to count."""


def is_not_deadlock(error: BaseException) -> bool:
    """Count every dependency failure except a deadlock."""
    return not isinstance(error, DeadlockError)


def make_breaker(
    *, half_open_max_calls: int = 1, is_failure=None
) -> tuple[CircuitBreaker, FakeClock]:
    """Build a closed breaker on a fake clock.

    Args:
        half_open_max_calls: Probe slots while half-open.
        is_failure: Optional predicate narrowing the counted failure types.

    Returns:
        The breaker and the clock that drives it.
    """
    clock = FakeClock()
    config = CircuitBreakerConfig(
        failure_threshold=FAILURE_THRESHOLD,
        reset_timeout_seconds=RESET_TIMEOUT_SECONDS,
        half_open_max_calls=half_open_max_calls,
    )
    breaker = CircuitBreaker(
        BREAKER_NAME,
        config,
        failure_types=(DependencyDownError,),
        is_failure=is_failure,
        clock=clock,
    )
    return breaker, clock


def fail_once(breaker: CircuitBreaker) -> None:
    """Admit one call and report it as a failure."""
    breaker.record_failure(breaker.before_call())


def trip(breaker: CircuitBreaker) -> None:
    """Open the circuit with the configured number of consecutive failures."""
    for _ in range(FAILURE_THRESHOLD):
        fail_once(breaker)


def half_open(breaker: CircuitBreaker, clock: FakeClock) -> None:
    """Trip the circuit and let the reset timeout elapse."""
    trip(breaker)
    clock.advance(RESET_TIMEOUT_SECONDS)


class StateReadingHandler(logging.Handler):
    """Handler that calls back into the breaker, as a metrics exporter might."""

    def __init__(self, breaker: CircuitBreaker) -> None:
        super().__init__()
        self._breaker = breaker
        self.states_read: list[CircuitState] = []
        self.records_blocked_on_lock: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Read the breaker state from a helper thread that cannot deadlock the test.

        A helper that is still waiting after ``LOCK_WAIT_SECONDS`` means the
        record was logged while the breaker's lock was held.
        """
        reader = threading.Thread(
            target=lambda: self.states_read.append(self._breaker.state),
            daemon=True,
        )
        reader.start()
        reader.join(timeout=LOCK_WAIT_SECONDS)
        if reader.is_alive():
            self.records_blocked_on_lock.append(record.getMessage())


def exercise(breaker: CircuitBreaker, *, outcome: BaseException | None = None) -> None:
    """Run one guarded block that uses the dependency, then raise ``outcome``."""
    with breaker.guard() as call:
        call.mark_exercised()
        if outcome is not None:
            raise outcome


@pytest.mark.unit
def test_when_breaker_is_new_then_it_is_closed_and_admits_calls():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.before_call()."""
    breaker, _ = make_breaker()

    ticket = breaker.before_call()

    assert isinstance(ticket, CallTicket)
    assert breaker.state is CircuitState.CLOSED


@pytest.mark.unit
def test_when_failures_stay_below_threshold_then_circuit_stays_closed():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.record_failure()."""
    breaker, _ = make_breaker()

    for _ in range(FAILURE_THRESHOLD - 1):
        fail_once(breaker)

    assert breaker.state is CircuitState.CLOSED


@pytest.mark.unit
def test_when_failures_reach_threshold_then_circuit_opens_and_refuses_calls():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.before_call()."""
    breaker, _ = make_breaker()

    trip(breaker)

    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        breaker.before_call()


@pytest.mark.unit
def test_when_circuit_refuses_a_call_then_public_message_hides_the_breaker_name():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.before_call()."""
    breaker, _ = make_breaker()
    trip(breaker)

    with pytest.raises(CircuitOpenError) as refused:
        breaker.before_call()

    assert BREAKER_NAME not in refused.value.public_message
    assert refused.value.log_context == {"breaker": BREAKER_NAME}


@pytest.mark.unit
def test_when_a_success_interrupts_the_streak_then_failures_count_from_zero():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.record_success()."""
    breaker, _ = make_breaker()

    for _ in range(FAILURE_THRESHOLD - 1):
        fail_once(breaker)
    breaker.record_success(breaker.before_call())
    for _ in range(FAILURE_THRESHOLD - 1):
        fail_once(breaker)

    assert breaker.state is CircuitState.CLOSED


@pytest.mark.unit
def test_when_reset_timeout_has_not_elapsed_then_circuit_stays_open():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.state."""
    breaker, clock = make_breaker()
    trip(breaker)

    clock.advance(RESET_TIMEOUT_SECONDS - 1)

    assert breaker.state is CircuitState.OPEN


@pytest.mark.unit
def test_when_reset_timeout_elapsed_then_state_reports_half_open():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.state."""
    breaker, clock = make_breaker()
    half_open(breaker, clock)

    assert breaker.state is CircuitState.HALF_OPEN


@pytest.mark.unit
def test_when_half_open_then_only_the_configured_number_of_probes_are_admitted():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.before_call()."""
    breaker, clock = make_breaker(half_open_max_calls=2)
    half_open(breaker, clock)

    breaker.before_call()
    breaker.before_call()

    with pytest.raises(CircuitOpenError):
        breaker.before_call()


@pytest.mark.unit
def test_when_the_probe_succeeds_then_circuit_closes():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.record_success()."""
    breaker, clock = make_breaker()
    half_open(breaker, clock)
    probe = breaker.before_call()

    breaker.record_success(probe)

    assert breaker.state is CircuitState.CLOSED
    breaker.before_call()


@pytest.mark.unit
def test_when_the_probe_fails_then_circuit_reopens_for_a_full_timeout():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.record_failure()."""
    breaker, clock = make_breaker()
    half_open(breaker, clock)
    probe = breaker.before_call()

    breaker.record_failure(probe)
    clock.advance(RESET_TIMEOUT_SECONDS - 1)

    assert breaker.state is CircuitState.OPEN
    clock.advance(1)
    assert breaker.state is CircuitState.HALF_OPEN


@pytest.mark.unit
def test_when_a_late_success_arrives_while_open_then_circuit_stays_open():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.record_success()."""
    breaker, _ = make_breaker()
    slow_call = breaker.before_call()
    trip(breaker)

    breaker.record_success(slow_call)

    assert breaker.state is CircuitState.OPEN


@pytest.mark.unit
def test_when_a_call_admitted_while_closed_succeeds_late_then_it_cannot_close_a_half_open_circuit():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.record_success()."""
    breaker, clock = make_breaker()
    slow_call = breaker.before_call()
    half_open(breaker, clock)
    probe = breaker.before_call()

    breaker.record_success(slow_call)

    assert breaker.state is CircuitState.HALF_OPEN
    breaker.record_success(probe)
    assert breaker.state is CircuitState.CLOSED


@pytest.mark.unit
def test_when_a_stale_failure_arrives_then_it_does_not_count_toward_the_new_streak():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.record_failure()."""
    breaker, clock = make_breaker()
    slow_calls = [breaker.before_call() for _ in range(FAILURE_THRESHOLD)]
    half_open(breaker, clock)
    breaker.record_success(breaker.before_call())

    for slow_call in slow_calls:
        breaker.record_failure(slow_call)

    assert breaker.state is CircuitState.CLOSED


@pytest.mark.unit
def test_when_a_probe_is_released_then_the_next_call_may_probe():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.release()."""
    breaker, clock = make_breaker()
    half_open(breaker, clock)
    probe = breaker.before_call()
    with pytest.raises(CircuitOpenError):
        breaker.before_call()

    breaker.release(probe)

    assert breaker.state is CircuitState.HALF_OPEN
    breaker.before_call()


@pytest.mark.unit
def test_when_a_stale_ticket_is_released_then_the_current_probe_slot_stays_taken():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.release()."""
    breaker, clock = make_breaker()
    slow_call = breaker.before_call()
    half_open(breaker, clock)
    breaker.before_call()

    breaker.release(slow_call)

    with pytest.raises(CircuitOpenError):
        breaker.before_call()


@pytest.mark.unit
def test_when_a_call_is_released_while_closed_then_the_failure_streak_is_kept():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.release()."""
    breaker, _ = make_breaker()
    for _ in range(FAILURE_THRESHOLD - 1):
        fail_once(breaker)

    breaker.release(breaker.before_call())
    fail_once(breaker)

    assert breaker.state is CircuitState.OPEN


@pytest.mark.unit
def test_when_state_changes_then_each_transition_is_logged_at_warning(caplog):
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.record_failure()."""
    breaker, clock = make_breaker()
    caplog.set_level(logging.DEBUG, logger="app.infrastructure.circuit_breaker")

    half_open(breaker, clock)
    breaker.record_success(breaker.before_call())

    transitions = [
        record for record in caplog.records if record.name.endswith("circuit_breaker")
    ]
    assert [record.levelno for record in transitions] == [logging.WARNING] * 3
    assert [record.getMessage().rsplit(": ", 1)[1] for record in transitions] == [
        "closed -> open",
        "open -> half_open",
        "half_open -> closed",
    ]
    assert [
        (record.breaker, record.from_state, record.to_state) for record in transitions
    ] == [
        (BREAKER_NAME, "closed", "open"),
        (BREAKER_NAME, "open", "half_open"),
        (BREAKER_NAME, "half_open", "closed"),
    ]


@pytest.mark.unit
def test_when_a_log_handler_reads_the_breaker_then_the_transition_is_logged_outside_the_lock():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.record_failure()."""
    breaker, _ = make_breaker()
    handler = StateReadingHandler(breaker)
    breaker_logger = logging.getLogger("app.infrastructure.circuit_breaker")
    breaker_logger.addHandler(handler)
    try:
        trip(breaker)
    finally:
        breaker_logger.removeHandler(handler)

    assert handler.records_blocked_on_lock == []
    assert handler.states_read == [CircuitState.OPEN]


@pytest.mark.unit
def test_when_the_block_raises_a_failure_type_then_guard_records_a_failure():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.guard()."""
    breaker, _ = make_breaker()

    for _ in range(FAILURE_THRESHOLD):
        with pytest.raises(DependencyDownError), breaker.guard():
            raise DependencyDownError

    assert breaker.state is CircuitState.OPEN


@pytest.mark.unit
def test_when_the_block_raises_another_error_after_using_the_dependency_then_guard_records_a_success():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.guard()."""
    breaker, _ = make_breaker()

    for _ in range(FAILURE_THRESHOLD - 1):
        fail_once(breaker)
    with pytest.raises(ValueError, match="bad input"):
        exercise(breaker, outcome=ValueError("bad input"))
    for _ in range(FAILURE_THRESHOLD - 1):
        fail_once(breaker)

    assert breaker.state is CircuitState.CLOSED


@pytest.mark.unit
def test_when_the_block_never_uses_the_dependency_then_guard_does_not_reset_the_streak():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.guard()."""
    breaker, _ = make_breaker()

    for _ in range(FAILURE_THRESHOLD - 1):
        fail_once(breaker)
    with pytest.raises(ValueError, match="rejected before any query"), breaker.guard():
        raise ValueError("rejected before any query")
    with breaker.guard():
        pass
    fail_once(breaker)

    assert breaker.state is CircuitState.OPEN


@pytest.mark.unit
def test_when_a_half_open_block_never_uses_the_dependency_then_the_circuit_stays_half_open():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.guard()."""
    breaker, clock = make_breaker()
    half_open(breaker, clock)

    with pytest.raises(ValueError, match="rejected"), breaker.guard():
        raise ValueError("rejected")
    with breaker.guard():
        pass

    assert breaker.state is CircuitState.HALF_OPEN
    breaker.before_call()


@pytest.mark.unit
@pytest.mark.parametrize("cancellation", [asyncio.CancelledError(), GeneratorExit()])
def test_when_a_half_open_block_is_cancelled_then_guard_releases_the_probe_without_a_verdict(
    cancellation,
):
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.guard()."""
    breaker, clock = make_breaker()
    half_open(breaker, clock)

    with pytest.raises(type(cancellation)):
        exercise(breaker, outcome=cancellation)

    assert breaker.state is CircuitState.HALF_OPEN
    breaker.before_call()


@pytest.mark.unit
def test_when_the_circuit_is_open_then_guard_refuses_before_running_the_block():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.guard()."""
    breaker, _ = make_breaker()
    trip(breaker)
    ran = []

    with pytest.raises(CircuitOpenError), breaker.guard():
        ran.append(True)

    assert ran == []


@pytest.mark.unit
def test_when_a_half_open_block_uses_the_dependency_and_returns_then_guard_closes_the_circuit():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.guard()."""
    breaker, clock = make_breaker()
    half_open(breaker, clock)

    exercise(breaker)

    assert breaker.state is CircuitState.CLOSED


@pytest.mark.unit
def test_when_the_predicate_rejects_a_failure_type_then_guard_does_not_count_it():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.guard()."""
    breaker, _ = make_breaker(is_failure=is_not_deadlock)

    for _ in range(FAILURE_THRESHOLD + 1):
        with pytest.raises(DeadlockError):
            exercise(breaker, outcome=DeadlockError())

    assert breaker.state is CircuitState.CLOSED


@pytest.mark.unit
def test_when_the_predicate_accepts_a_failure_type_then_guard_counts_it():
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.guard()."""
    breaker, _ = make_breaker(is_failure=is_not_deadlock)

    for _ in range(FAILURE_THRESHOLD):
        with pytest.raises(DependencyDownError):
            exercise(breaker, outcome=DependencyDownError())

    assert breaker.state is CircuitState.OPEN


@pytest.mark.unit
@pytest.mark.parametrize(
    ("failure_threshold", "reset_timeout_seconds", "half_open_max_calls"),
    [(0, 1.0, 1), (1, 0.0, 1), (1, -1.0, 1), (1, 1.0, 0)],
)
def test_when_config_has_a_non_positive_value_then_it_is_rejected(
    failure_threshold, reset_timeout_seconds, half_open_max_calls
):
    """Validates app.infrastructure.circuit_breaker.CircuitBreakerConfig.__post_init__()."""
    with pytest.raises(ValueError, match="Breaker"):
        CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            reset_timeout_seconds=reset_timeout_seconds,
            half_open_max_calls=half_open_max_calls,
        )


@pytest.mark.unit
def test_when_many_threads_fail_at_once_then_the_circuit_opens_exactly_once(caplog):
    """Validates app.infrastructure.circuit_breaker.CircuitBreaker.record_failure()."""
    breaker, _ = make_breaker()
    caplog.set_level(logging.WARNING, logger="app.infrastructure.circuit_breaker")
    tickets = [breaker.before_call() for _ in range(CONCURRENT_THREADS)]
    start = threading.Barrier(CONCURRENT_THREADS)

    def fail(ticket: CallTicket) -> None:
        """Wait for every thread, then report the failure together."""
        start.wait()
        breaker.record_failure(ticket)

    threads = [threading.Thread(target=fail, args=(ticket,)) for ticket in tickets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert breaker.state is CircuitState.OPEN
    assert len(caplog.records) == 1
