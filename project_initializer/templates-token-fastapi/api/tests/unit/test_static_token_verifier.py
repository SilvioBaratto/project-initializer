"""Unit tests for the static bearer token verifier."""

import pytest
from pydantic import SecretStr

from app.domain.exceptions import AuthenticationError
from app.domain.ports.token_verifier import TokenVerifierPort
from app.infrastructure.auth.static_token import (
    STATIC_TOKEN_AUTH_METHOD,
    STATIC_TOKEN_USER_ID,
    StaticTokenVerifier,
    tokens_match,
)

pytestmark = pytest.mark.unit

EXPECTED = "expected-static-token-0123456789"

UNMATCHING_CANDIDATES = [
    pytest.param("", id="empty"),
    pytest.param("expected-static-token-012345678", id="one-character-short"),
    pytest.param(EXPECTED + "x", id="one-character-long"),
    pytest.param(EXPECTED.upper(), id="different-case"),
    pytest.param("é" * len(EXPECTED), id="non-ascii"),
    pytest.param("\ud800", id="lone-surrogate"),
    pytest.param("x" * 100_000, id="very-long"),
]


@pytest.fixture
def verifier() -> StaticTokenVerifier:
    """Verifier of ``EXPECTED``."""
    return StaticTokenVerifier(SecretStr(EXPECTED))


def test_when_the_verifier_is_built_then_it_satisfies_the_token_verifier_port(
    verifier,
):
    """when the verifier is built, it matches the TokenVerifierPort protocol.

    Validates app.infrastructure.auth.static_token.StaticTokenVerifier.
    """
    assert isinstance(verifier, TokenVerifierPort)


def test_when_the_candidate_is_identical_then_tokens_match():
    """when the presented token equals the configured one, they match.

    Validates app.infrastructure.auth.static_token.tokens_match().
    """
    assert tokens_match(EXPECTED, EXPECTED) is True


@pytest.mark.parametrize("candidate", UNMATCHING_CANDIDATES)
def test_when_the_candidate_differs_then_tokens_do_not_match(candidate):
    """when the presented token differs in any way, the comparison is False.

    Non-ASCII text must not make the constant-time comparison raise.

    Validates app.infrastructure.auth.static_token.tokens_match().
    """
    assert tokens_match(candidate, EXPECTED) is False


def test_when_the_expected_token_is_non_ascii_then_the_comparison_still_works():
    """when the configured token holds non-ASCII text, it matches itself.

    Validates app.infrastructure.auth.static_token.tokens_match().
    """
    assert tokens_match("pässwörd-token", "pässwörd-token") is True


@pytest.mark.parametrize("candidate", ["", "anything", "\ud800"])
def test_when_the_expected_token_is_empty_then_nothing_matches(candidate):
    """when the configured token is empty, even an empty candidate is refused.

    An unset secret must switch the feature off, not open it to everyone.

    Validates app.infrastructure.auth.static_token.tokens_match().
    """
    assert tokens_match(candidate, "") is False


def test_when_the_token_matches_then_verify_returns_the_static_principal(verifier):
    """when the configured token is presented, verify returns the static principal.

    Validates app.infrastructure.auth.static_token.StaticTokenVerifier.verify().
    """
    user = verifier.verify(EXPECTED)

    assert user.id == STATIC_TOKEN_USER_ID
    assert user.auth_method == STATIC_TOKEN_AUTH_METHOD
    assert user.email is None
    assert user.roles == ()


@pytest.mark.parametrize("candidate", UNMATCHING_CANDIDATES)
def test_when_the_token_differs_then_verify_raises_authentication_error(
    verifier, candidate
):
    """when a wrong token is presented, verify raises AuthenticationError.

    Validates app.infrastructure.auth.static_token.StaticTokenVerifier.verify().
    """
    with pytest.raises(AuthenticationError):
        verifier.verify(candidate)


def test_when_verify_fails_twice_then_each_error_is_a_new_instance(verifier):
    """when two wrong tokens are presented, the two errors are distinct objects.

    A shared instance would accumulate traceback frames across requests.

    Validates app.infrastructure.auth.static_token.StaticTokenVerifier.verify().
    """
    errors = []
    for _ in range(2):
        with pytest.raises(AuthenticationError) as raised:
            verifier.verify("wrong")
        errors.append(raised.value)

    assert errors[0] is not errors[1]


def test_when_verify_fails_then_the_error_reveals_neither_token(verifier):
    """when verification fails, the public message and the log context hold no token.

    Validates app.infrastructure.auth.static_token.StaticTokenVerifier.verify().
    """
    with pytest.raises(AuthenticationError) as raised:
        verifier.verify("presented-secret-value")

    leaked_text = f"{raised.value.public_message} {raised.value.log_context}"
    assert "presented-secret-value" not in leaked_text
    assert EXPECTED not in leaked_text


def test_when_the_configured_token_is_empty_then_verify_rejects_every_token():
    """when the verifier holds an empty secret, every token is refused.

    Validates app.infrastructure.auth.static_token.StaticTokenVerifier.verify().
    """
    unconfigured = StaticTokenVerifier(SecretStr(""))

    with pytest.raises(AuthenticationError):
        unconfigured.verify("")


def test_when_the_verifier_is_printed_then_the_secret_is_masked(verifier):
    """when the verifier or its secret is rendered as text, the value does not appear.

    Validates app.infrastructure.auth.static_token.StaticTokenVerifier.
    """
    assert EXPECTED not in repr(verifier.__dict__)
