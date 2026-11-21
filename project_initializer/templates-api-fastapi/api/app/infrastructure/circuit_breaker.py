"""Circuit breaker that fails fast while a dependency is down.

After ``failure_threshold`` consecutive failures the breaker opens and rejects
calls immediately, instead of letting every request wait for a pool or connect
timeout. Once ``reset_timeout_seconds`` has passed it half-opens and admits a
limited number of probe calls: a successful probe closes it, a failed one
re-opens it for another full timeout.

Only a call that really exercised the dependency may vote. A request that was
refused by validation, never reached the database or was cancelled says nothing
about the dependency, so it frees its slot without a verdict (``release``).
Every state change starts a new generation, and a verdict from a call admitted
in an older generation is ignored: a slow call that began while the circuit was
closed must not close it while a probe is still in flight.

The fallback while open is fail-fast: callers get ``CircuitOpenError`` and the
API answers 503 with ``Retry-After``. There is no cache or read-only mode.
"""

import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum

from app.infrastructure.errors import CircuitOpenError

logger = logging.getLogger(__name__)


class CircuitState(StrEnum):
    """Position of a circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Thresholds of a circuit breaker.

    Attributes:
        failure_threshold: Consecutive failures that open the circuit.
        reset_timeout_seconds: Time the circuit stays open before it admits a probe.
        half_open_max_calls: Probe calls admitted at once while half-open.

    Raises:
        ValueError: On construction, when a value is not positive.
    """

    failure_threshold: int
    reset_timeout_seconds: float
    half_open_max_calls: int = 1

    def __post_init__(self) -> None:
        if self.failure_threshold < 1 or self.half_open_max_calls < 1:
            raise ValueError("Breaker call counts must be at least 1")
        if self.reset_timeout_seconds <= 0:
            raise ValueError("Breaker reset timeout must be positive")


@dataclass(frozen=True)
class CallTicket:
    """Receipt for an admitted call, handed back when the call reports.

    Attributes:
        generation: Breaker generation at admission. A verdict carried by a
            ticket of an older generation is ignored.
    """

    generation: int


class GuardedCall:
    """Handle that a guarded block uses to say it contacted the dependency."""

    def __init__(self) -> None:
        self._exercised = False

    @property
    def exercised(self) -> bool:
        """True once the block has used the dependency."""
        return self._exercised

    def mark_exercised(self) -> None:
        """Record that the dependency was contacted, so the call may vote."""
        self._exercised = True


class CircuitBreaker:
    """Thread-safe circuit breaker for one dependency.

    Every state transition is logged at WARNING, after the internal lock is
    released, so an operator can see when the dependency was declared down and
    when it recovered.
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig,
        *,
        failure_types: tuple[type[BaseException], ...],
        is_failure: Callable[[BaseException], bool] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create a closed breaker.

        Args:
            name: Label used in logs and in the error context.
            config: Failure threshold and timings.
            failure_types: Exception types that may count as a dependency failure
                in ``guard``. Any other exception means the dependency answered.
            is_failure: Narrows ``failure_types``: an instance of one of them
                counts only when this returns True. Use it when the type alone is
                ambiguous, such as a driver error that is also raised for a
                deadlock. Omitted, every instance of ``failure_types`` counts.
            clock: Monotonic time source in seconds; tests inject a fake one.
        """
        self._name = name
        self._config = config
        self._failure_types = failure_types
        self._is_failure = is_failure
        self._clock = clock
        self._lock = threading.Lock()
        self._announcements: list[tuple[CircuitState, CircuitState]] = []
        self._state = CircuitState.CLOSED
        self._generation = 0
        self._consecutive_failures = 0
        self._opened_at = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """The current state, with an elapsed reset timeout already applied.

        Reading it after the timeout reports ``HALF_OPEN`` even when no call has
        arrived yet, so a readiness probe can see the circuit is ready to retry.
        """
        with self._exclusive():
            self._half_open_if_reset_elapsed()
            return self._state

    def before_call(self) -> CallTicket:
        """Admit a call or refuse it.

        Returns:
            A ticket the caller passes to exactly one of ``record_success``,
            ``record_failure`` or ``release`` when the call ends.

        Raises:
            CircuitOpenError: The circuit is open, or half-open with all probe
                slots taken. The caller must not contact the dependency.
        """
        with self._exclusive():
            self._half_open_if_reset_elapsed()
            if self._state is CircuitState.CLOSED:
                return CallTicket(self._generation)
            if (
                self._state is CircuitState.HALF_OPEN
                and self._half_open_calls < self._config.half_open_max_calls
            ):
                self._half_open_calls += 1
                return CallTicket(self._generation)
            raise CircuitOpenError(log_context={"breaker": self._name})

    def record_success(self, ticket: CallTicket) -> None:
        """Report that an admitted call used the dependency and it answered.

        A success while half-open closes the circuit. While closed it clears the
        failure streak. A ticket from an older generation is ignored.

        Args:
            ticket: The ticket ``before_call`` returned for this call.
        """
        with self._exclusive():
            if ticket.generation != self._generation:
                return
            # Opening starts a new generation, so a current ticket can only
            # belong to a closed or a half-open period.
            if self._state is CircuitState.HALF_OPEN:
                self._transition(CircuitState.CLOSED)
            else:
                self._consecutive_failures = 0

    def record_failure(self, ticket: CallTicket) -> None:
        """Report that an admitted call found the dependency failing.

        A failure while half-open re-opens the circuit. While closed it extends
        the failure streak and opens the circuit at the threshold. A ticket from
        an older generation is ignored.

        Args:
            ticket: The ticket ``before_call`` returned for this call.
        """
        with self._exclusive():
            if ticket.generation != self._generation:
                return
            if self._state is CircuitState.HALF_OPEN:
                self._transition(CircuitState.OPEN)
                return
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._config.failure_threshold:
                self._transition(CircuitState.OPEN)

    def release(self, ticket: CallTicket) -> None:
        """End an admitted call without a verdict.

        Use it when the call never contacted the dependency or was cancelled. A
        half-open probe gives its slot back, so the next call can probe; the
        failure streak is left untouched. A ticket from an older generation is
        ignored, because a transition already reset the slots it once held.

        Args:
            ticket: The ticket ``before_call`` returned for this call.
        """
        with self._exclusive():
            if ticket.generation != self._generation:
                return
            if self._state is CircuitState.HALF_OPEN and self._half_open_calls > 0:
                self._half_open_calls -= 1

    @contextmanager
    def guard(self) -> Iterator[GuardedCall]:
        """Run a block as one call through the breaker.

        The verdict depends on how the block ends:

        * An exception that counts as a failure (see ``failure_types`` and
          ``is_failure``) is recorded as a failure.
        * Any other ``Exception``, or a normal return, is recorded as a success
          only if the block called ``GuardedCall.mark_exercised``; otherwise the
          dependency was never contacted and the call is released.
        * A ``BaseException`` that is not an ``Exception``, such as a cancellation,
          is released: it says nothing about the dependency.

        Every exception is re-raised unchanged.

        Yields:
            The handle the block marks once it has contacted the dependency.

        Raises:
            CircuitOpenError: Before the block runs, when the call is refused.
        """
        ticket = self.before_call()
        call = GuardedCall()
        try:
            yield call
        except Exception as error:
            self._settle_after_error(ticket, call, error)
            raise
        except BaseException:
            self.release(ticket)
            raise
        else:
            self._settle(ticket, call)

    def _settle(self, ticket: CallTicket, call: GuardedCall) -> None:
        if call.exercised:
            self.record_success(ticket)
        else:
            self.release(ticket)

    def _settle_after_error(
        self, ticket: CallTicket, call: GuardedCall, error: Exception
    ) -> None:
        if self._counts_as_failure(error):
            self.record_failure(ticket)
        else:
            self._settle(ticket, call)

    def _counts_as_failure(self, error: Exception) -> bool:
        if not isinstance(error, self._failure_types):
            return False
        return self._is_failure is None or self._is_failure(error)

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        # Logging under the lock would let a slow or re-entrant log handler
        # stall every caller, so transitions are announced after it is freed.
        announced: list[tuple[CircuitState, CircuitState]] = []
        try:
            with self._lock:
                try:
                    yield
                finally:
                    announced, self._announcements = self._announcements, []
        finally:
            for previous, current in announced:
                self._announce(previous, current)

    def _half_open_if_reset_elapsed(self) -> None:
        if self._state is not CircuitState.OPEN:
            return
        if self._clock() - self._opened_at >= self._config.reset_timeout_seconds:
            self._transition(CircuitState.HALF_OPEN)

    def _transition(self, new_state: CircuitState) -> None:
        self._announcements.append((self._state, new_state))
        self._state = new_state
        self._generation += 1
        self._consecutive_failures = 0
        self._half_open_calls = 0
        if new_state is CircuitState.OPEN:
            self._opened_at = self._clock()

    def _announce(self, previous: CircuitState, current: CircuitState) -> None:
        logger.warning(
            "Circuit breaker %s changed state: %s -> %s",
            self._name,
            previous,
            current,
            extra={
                "breaker": self._name,
                "from_state": previous.value,
                "to_state": current.value,
            },
        )
