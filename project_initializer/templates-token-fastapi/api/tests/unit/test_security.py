"""Unit tests for app.core.security — pure crypto primitives.

Each test names the exact behaviour under test:
  "when X, Y is returned/raised"

No settings or config imports: all secrets are literals scoped to this module.
"""

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)

_SECRET = "test-secret-key-not-for-prod"


# ---------------------------------------------------------------------------
# hash_password
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_when_password_is_hashed_hash_differs_from_plaintext():
    """when a password is hashed, the hash differs from the plaintext."""
    plain = "my-plain-password"

    result = hash_password(plain)

    assert result != plain
    assert result.startswith("$2b$")


# ---------------------------------------------------------------------------
# verify_password
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_when_verify_password_receives_correct_password_true_is_returned():
    """when verify_password is given the correct password, True is returned."""
    plain = "correct-password"
    hashed = hash_password(plain)

    assert verify_password(plain, hashed) is True


@pytest.mark.unit
def test_when_verify_password_receives_wrong_password_false_is_returned():
    """when verify_password is given a wrong password, False is returned."""
    hashed = hash_password("original-password")

    assert verify_password("wrong-password", hashed) is False


# ---------------------------------------------------------------------------
# create_access_token + decode_token round-trip
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_when_token_is_created_and_decoded_sub_claim_round_trips():
    """when a token is created then decoded with the same key, sub round-trips
    and an exp claim is present."""
    subject = "user-42"

    token = create_access_token(subject, _SECRET)
    payload = decode_token(token, _SECRET)

    assert payload["sub"] == subject
    assert "exp" in payload


@pytest.mark.unit
def test_when_create_access_token_is_called_jwt_carries_correct_sub():
    """when create_access_token is called, the returned JWT decodes to carry
    sub equal to the subject."""
    subject = "user-99"

    token = create_access_token(subject, _SECRET)
    payload = decode_token(token, _SECRET)

    assert payload["sub"] == subject


@pytest.mark.unit
def test_when_create_access_token_uses_defaults_token_is_decodable():
    """when create_access_token is called with defaults (HS256, 30 min),
    the token is decodable and carries the expected subject."""
    subject = "default-user"

    token = create_access_token(subject, _SECRET)
    payload = decode_token(token, _SECRET)

    assert payload["sub"] == subject
    assert "exp" in payload


# ---------------------------------------------------------------------------
# decode_token error paths
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_when_token_is_decoded_with_wrong_key_jose_error_is_raised():
    """when a token is decoded with the wrong key, a jose JWTError is raised."""
    token = create_access_token("user-1", _SECRET)

    with pytest.raises(JWTError):
        decode_token(token, "completely-different-wrong-secret-key")


@pytest.mark.unit
def test_when_token_payload_is_tampered_jose_error_is_raised():
    """when a token is tampered (mutated payload segment) then decoded with
    the right key, a JWTError is raised."""
    token = create_access_token("user-1", _SECRET)

    # A JWT is header.payload.signature — mutate a character in the payload
    header, payload_segment, signature = token.split(".")
    # Flip the first character of the payload segment
    first_char = payload_segment[0]
    mutated_char = "A" if first_char != "A" else "B"
    tampered_token = ".".join([header, mutated_char + payload_segment[1:], signature])

    with pytest.raises(JWTError):
        decode_token(tampered_token, _SECRET)
