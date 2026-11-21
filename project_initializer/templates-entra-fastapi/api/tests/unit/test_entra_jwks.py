"""Unit tests of the signing-key resolver: cooldown, rotation and failure mapping."""

import http.client
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import jwt
import pytest
from jwt.exceptions import (
    PyJWKClientConnectionError,
    PyJWKClientError,
    PyJWKSetError,
)

from app.domain.exceptions import ExternalServiceError
from app.infrastructure.auth.entra_jwks import (
    SERVICE_NAME,
    CooldownSigningKeyResolver,
)
from tests.entra_tokens import (
    SIGNING_KID,
    StubKeySource,
    forge_token_with_header,
    make_token,
    sign_token,
    tenant_signing_key,
    valid_claims,
)

pytestmark = pytest.mark.unit

COOLDOWN_SECONDS = 30.0
ROTATED_KID = "rotated-in"
RANDOM_KIDS = [f"random-kid-{number}" for number in range(6)]
CONCURRENT_CALLERS = 8
CLOCK_STEP_SECONDS = 0.02
KEY_ENDPOINT_FAILURES = [
    pytest.param(PyJWKClientConnectionError("unreachable"), id="connection-error"),
    pytest.param(PyJWKClientError("not a JSON object"), id="client-error"),
    pytest.param(PyJWKSetError("no keys"), id="empty-key-set"),
    pytest.param(ConnectionResetError("reset"), id="connection-reset"),
    pytest.param(TimeoutError("slow"), id="timeout"),
    pytest.param(json.JSONDecodeError("not json", "<html>", 0), id="not-json"),
    pytest.param(UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"), id="undecodable"),
    pytest.param(http.client.IncompleteRead(b""), id="broken-http-exchange"),
]


class ManualClock:
    """Monotonic clock that only moves when a test says so."""

    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        """Move time forward."""
        self.now += seconds


def token_for(kid: str) -> str:
    """Valid claims signed under an arbitrary key id."""
    return sign_token(valid_claims(), tenant_signing_key(), kid=kid)


def resolver_over(
    source: StubKeySource, clock: ManualClock | None = None
) -> CooldownSigningKeyResolver:
    """Build the resolver with a controllable clock."""
    return CooldownSigningKeyResolver(
        source,
        refresh_cooldown_seconds=COOLDOWN_SECONDS,
        clock=clock if clock is not None else ManualClock(),
    )


def tenant_source() -> StubKeySource:
    """Key source that publishes the tenant's public key."""
    return StubKeySource({SIGNING_KID: tenant_signing_key().public_key()})


def test_when_the_kid_is_published_then_its_key_is_returned_without_a_reload():
    """when the cached key set holds the kid, the key comes back and nothing reloads.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    source = tenant_source()

    key = resolver_over(source).get_signing_key_from_jwt(make_token())

    assert key.key == tenant_signing_key().public_key()
    assert source.loads == [False]


def test_when_the_kid_is_unknown_then_one_reload_runs_and_the_answer_is_none():
    """when no published key has the kid, the key set is reloaded once, then None.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    source = tenant_source()

    key = resolver_over(source).get_signing_key_from_jwt(token_for("unknown"))

    assert key is None
    assert source.loads == [False, True]


def test_when_a_key_was_just_rotated_in_then_the_reload_finds_it():
    """when Entra publishes a new kid, the first token naming it triggers a reload.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    source = tenant_source()
    resolver = resolver_over(source)
    source.get_signing_keys()
    source.publish(ROTATED_KID, tenant_signing_key().public_key())

    key = resolver.get_signing_key_from_jwt(token_for(ROTATED_KID))

    assert key is not None
    assert source.refreshes == 1


def test_when_many_unknown_kids_arrive_within_the_cooldown_then_only_one_reload_runs():
    """when strangers send tokens with random kids, Entra is called once, not per token.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    source = tenant_source()
    resolver = resolver_over(source)

    answers = [resolver.get_signing_key_from_jwt(token_for(kid)) for kid in RANDOM_KIDS]

    assert answers == [None] * len(RANDOM_KIDS)
    assert source.refreshes == 1


def test_when_the_cooldown_has_elapsed_then_an_unknown_kid_reloads_again():
    """when the cooldown is over, a rotated-in key is picked up by a new reload.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    clock = ManualClock()
    source = tenant_source()
    resolver = resolver_over(source, clock)
    resolver.get_signing_key_from_jwt(token_for("unknown"))
    source.publish(ROTATED_KID, tenant_signing_key().public_key())

    assert resolver.get_signing_key_from_jwt(token_for(ROTATED_KID)) is None
    clock.advance(COOLDOWN_SECONDS)

    assert resolver.get_signing_key_from_jwt(token_for(ROTATED_KID)) is not None
    assert source.loads == [False, True, True]


def test_when_the_cooldown_has_not_quite_elapsed_then_no_reload_runs():
    """when one second of the cooldown remains, an unknown kid still does not reload.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    clock = ManualClock()
    source = tenant_source()
    resolver = resolver_over(source, clock)
    resolver.get_signing_key_from_jwt(token_for("unknown"))
    clock.advance(COOLDOWN_SECONDS - 1)

    resolver.get_signing_key_from_jwt(token_for("unknown"))

    assert source.refreshes == 1


def test_when_a_reload_fails_then_the_next_unknown_kid_does_not_hammer_the_endpoint():
    """when a forced reload fails, the cooldown still holds, so Entra is not retried.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """

    source = tenant_source()
    source.get_signing_keys()
    source.error = PyJWKClientConnectionError("down")
    resolver = resolver_over(source)

    with pytest.raises(ExternalServiceError):
        resolver.get_signing_key_from_jwt(token_for("unknown"))

    assert resolver.get_signing_key_from_jwt(token_for("unknown-again")) is None
    assert source.refreshes == 1


def test_when_callers_race_for_a_reload_then_exactly_one_of_them_wins():
    """when threads miss at once, only one forced reload is claimed.

    The clock sleeps between reading and comparing, which widens the race window
    enough that an unguarded check-then-set would let several threads through.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    source = tenant_source()

    def slow_clock() -> float:
        """Read the clock slowly, so concurrent callers interleave."""
        threading.Event().wait(CLOCK_STEP_SECONDS)
        return time.monotonic()

    resolver = CooldownSigningKeyResolver(
        source, refresh_cooldown_seconds=COOLDOWN_SECONDS, clock=slow_clock
    )
    token = token_for("unknown")

    with ThreadPoolExecutor(max_workers=CONCURRENT_CALLERS) as pool:
        list(
            pool.map(
                lambda _: resolver.get_signing_key_from_jwt(token),
                range(CONCURRENT_CALLERS),
            )
        )

    assert source.refreshes == 1


@pytest.mark.parametrize(
    "header",
    [
        pytest.param({"alg": "RS256"}, id="no-kid"),
        pytest.param({"alg": "RS256", "kid": ""}, id="kid-is-empty"),
    ],
)
def test_when_the_token_has_no_usable_kid_then_none_is_returned_without_any_load(
    header,
):
    """when the header has no text kid, no key can match and Entra is not asked.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    source = tenant_source()
    token = forge_token_with_header(header, valid_claims())

    assert resolver_over(source).get_signing_key_from_jwt(token) is None
    assert source.loads == []


def test_when_the_token_is_malformed_then_the_decode_error_propagates():
    """when the header cannot be read, the token error reaches the verifier.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    with pytest.raises(jwt.InvalidTokenError):
        resolver_over(tenant_source()).get_signing_key_from_jwt("not-a-jwt")


@pytest.mark.parametrize("failure", KEY_ENDPOINT_FAILURES)
def test_when_the_key_endpoint_fails_then_the_service_is_reported_unavailable(failure):
    """when the key set cannot be loaded, ExternalServiceError names only the class.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    source = StubKeySource({}, error=failure)

    with pytest.raises(ExternalServiceError) as raised:
        resolver_over(source).get_signing_key_from_jwt(make_token())

    assert raised.value.log_context == {
        "service": SERVICE_NAME,
        "error": type(failure).__name__,
    }
    assert str(failure) not in repr(raised.value.log_context)


def test_when_an_unrelated_error_is_raised_then_it_is_not_taken_for_an_outage():
    """when the source raises a programming error, it is not disguised as a 503.

    Validates app.infrastructure.auth.entra_jwks.CooldownSigningKeyResolver.
    """
    source = StubKeySource({}, error=AttributeError("bug"))

    with pytest.raises(AttributeError):
        resolver_over(source).get_signing_key_from_jwt(make_token())
