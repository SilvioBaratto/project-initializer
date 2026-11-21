"""Unit tests for the password hasher and the JWT issuer of the token variant."""

import base64
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import bcrypt
import pytest
from jose import jwt
from pydantic import SecretStr

from app.domain.constants import PASSWORD_MAX_BYTES
from app.domain.exceptions import AuthenticationError
from app.domain.ports.credentials import AccessTokenIssuerPort, PasswordHasherPort
from app.infrastructure.auth_settings import AuthSettings
from app.infrastructure.security import (
    BCRYPT_HASH_PATTERN,
    BcryptPasswordHasher,
    JwtAccessTokenIssuer,
)
from tests.fakes import FIXED_NOW

pytestmark = pytest.mark.unit

# bcrypt's lowest legal cost keeps the suite fast; production uses the default.
FAST_BCRYPT_ROUNDS = 4
BCRYPT_COSTS = range(FAST_BCRYPT_ROUNDS, 13)
# bcrypt encodes the 16-byte salt in 22 characters, so the last one carries only
# two meaningful bits and bcrypt accepts nothing but these four there.
CANONICAL_LAST_SALT_CHARACTERS = [".", "O", "e", "u"]
NON_CANONICAL_LAST_SALT_CHARACTERS = ["/", "A", "z", "9"]
SALT_PREFIX = f"$2b${FAST_BCRYPT_ROUNDS:02d}$"
BODY_BEFORE_LAST_SALT_CHARACTER = "a" * 21
HASH_BODY_AFTER_SALT = "b" * 31
# Well-shaped in everything but the cost, so a cost case fails for that alone.
SALT_AND_DIGEST_OF_A_VALID_HASH = (
    f"{BODY_BEFORE_LAST_SALT_CHARACTER}.{HASH_BODY_AFTER_SALT}"
)
SECRET = SecretStr("unit-test-signing-key-0123456789-abcdef")
OTHER_SECRET = SecretStr("another-signing-key-0123456789-abcdefgh")
EXPIRY_MINUTES = 15
SECONDS_PER_MINUTE = 60
SUBJECT = "user-42"
# Year 2100, so the unsigned token is refused for its algorithm, not for expiry.
FAR_FUTURE_EPOCH = 4_102_444_800

MALFORMED_HASHES = [
    pytest.param(None, id="none"),
    pytest.param("", id="empty"),
    pytest.param("not-a-hash", id="plain-text"),
    pytest.param("$2b$04$abc", id="truncated"),
    pytest.param("$2b$99$" + SALT_AND_DIGEST_OF_A_VALID_HASH, id="cost-out-of-range"),
    pytest.param("$2b$03$" + SALT_AND_DIGEST_OF_A_VALID_HASH, id="cost-below-minimum"),
    pytest.param("$2b$32$" + SALT_AND_DIGEST_OF_A_VALID_HASH, id="cost-above-maximum"),
    pytest.param("$2b$04$" + "/" * 53, id="salt-with-an-invalid-last-character"),
    pytest.param("$1$" + "a" * 57, id="other-scheme"),
]
MALFORMED_TOKENS = [
    pytest.param("", id="empty"),
    pytest.param("not-a-jwt", id="no-segments"),
    pytest.param("a.b.c", id="not-base64-json"),
    pytest.param("é.é.é", id="non-ascii"),
    pytest.param("\ud800.\ud800.\ud800", id="lone-surrogate"),
]


@pytest.fixture
def hasher() -> BcryptPasswordHasher:
    """Hasher at the lowest bcrypt cost."""
    return BcryptPasswordHasher(rounds=FAST_BCRYPT_ROUNDS)


@pytest.fixture
def issuer() -> JwtAccessTokenIssuer:
    """Issuer on the real clock that signs HS256 tokens for ``EXPIRY_MINUTES``."""
    return JwtAccessTokenIssuer(SECRET, "HS256", EXPIRY_MINUTES)


def forge_token(claims: dict[str, object], *, algorithm: str = "HS256") -> str:
    """Sign arbitrary claims with the test key, bypassing the issuer's rules."""
    return jwt.encode(claims, SECRET.get_secret_value(), algorithm=algorithm)


def valid_claims(**overrides: object) -> dict[str, object]:
    """Claims the issuer would accept, with ``overrides`` applied."""
    claims: dict[str, object] = {
        "sub": SUBJECT,
        "exp": datetime.now(UTC) + timedelta(minutes=EXPIRY_MINUTES),
    }
    return {**claims, **overrides}


def url_safe_json(document: dict[str, object]) -> str:
    """Encode a JSON document the way a JWT segment is encoded."""
    raw = json.dumps(document).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def test_when_adapters_are_built_then_they_satisfy_their_ports(hasher, issuer):
    """when the adapters are built, they match the credential ports.

    Validates app.infrastructure.security.BcryptPasswordHasher.
    """
    assert isinstance(hasher, PasswordHasherPort)
    assert isinstance(issuer, AccessTokenIssuerPort)


def test_when_a_password_is_hashed_then_the_hash_is_a_bcrypt_hash_of_the_cost(hasher):
    """when a password is hashed, the result is a $2b$ hash and not the plain text.

    Validates app.infrastructure.security.BcryptPasswordHasher.hash().
    """
    password_hash = hasher.hash("my-plain-password")

    assert password_hash.startswith(f"$2b${FAST_BCRYPT_ROUNDS:02d}$")
    assert "my-plain-password" not in password_hash


def test_when_the_same_password_is_hashed_twice_then_the_salts_differ(hasher):
    """when one password is hashed twice, the two hashes differ but both verify.

    Validates app.infrastructure.security.BcryptPasswordHasher.hash().
    """
    first = hasher.hash("same-password")
    second = hasher.hash("same-password")

    assert first != second
    assert hasher.verify("same-password", first)
    assert hasher.verify("same-password", second)


def test_when_the_password_is_correct_then_verify_returns_true(hasher):
    """when verify gets the right password, it returns True.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    assert hasher.verify("correct-password", hasher.hash("correct-password")) is True


def test_when_the_password_is_wrong_then_verify_returns_false(hasher):
    """when verify gets a wrong password, it returns False.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    assert hasher.verify("wrong-password", hasher.hash("original-password")) is False


@pytest.mark.parametrize("password_hash", MALFORMED_HASHES)
def test_when_the_hash_is_missing_or_malformed_then_verify_returns_false(
    hasher, password_hash
):
    """when the stored hash is None, empty or malformed, verify returns False.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    assert hasher.verify("any-password", password_hash) is False


@pytest.mark.parametrize("cost", BCRYPT_COSTS)
def test_when_a_hash_is_made_at_any_legal_cost_then_verify_accepts_it(
    cost,
):
    """when bcrypt hashes at a cost from 4 to 12, the hash is usable and verifies.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    cost_hasher = BcryptPasswordHasher(rounds=cost)
    password_hash = cost_hasher.hash("cost-sweep-password")

    assert BCRYPT_HASH_PATTERN.fullmatch(password_hash.encode())
    assert cost_hasher.verify("cost-sweep-password", password_hash) is True


@pytest.mark.parametrize("last_character", CANONICAL_LAST_SALT_CHARACTERS)
def test_when_the_last_salt_character_is_canonical_then_verify_accepts_the_hash(
    hasher, last_character
):
    """when a hash carries any of the four legal last salt characters, it verifies.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    salt = f"{SALT_PREFIX}{BODY_BEFORE_LAST_SALT_CHARACTER}{last_character}"
    password_hash = bcrypt.hashpw(b"salt-sweep-password", salt.encode()).decode()

    assert hasher.verify("salt-sweep-password", password_hash) is True


@pytest.mark.parametrize("last_character", NON_CANONICAL_LAST_SALT_CHARACTERS)
def test_when_the_last_salt_character_is_not_canonical_then_verify_returns_false(
    hasher, last_character
):
    """when a hash has an illegal last salt character, verify does not raise.

    bcrypt itself raises on such a hash, which would turn a login into a 500.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    password_hash = (
        f"{SALT_PREFIX}{BODY_BEFORE_LAST_SALT_CHARACTER}{last_character}"
        f"{HASH_BODY_AFTER_SALT}"
    )

    assert hasher.verify("any-password", password_hash) is False


@pytest.mark.parametrize("scheme", ["2a", "2y"])
def test_when_a_hash_uses_another_accepted_scheme_then_verify_matches(hasher, scheme):
    """when a $2b$ hash is stored under the $2a$ or $2y$ label, it still verifies.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    password_hash = hasher.hash("scheme-password").replace("$2b$", f"${scheme}$", 1)

    assert hasher.verify("scheme-password", password_hash) is True


def test_when_the_hash_ends_with_a_newline_then_verify_returns_false(hasher):
    """when a valid hash carries a trailing newline, it is treated as malformed.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    password_hash = hasher.hash("correct-password")

    assert hasher.verify("correct-password", password_hash + "\n") is False


@pytest.mark.parametrize("password_hash", MALFORMED_HASHES)
def test_when_the_hash_is_unusable_then_one_bcrypt_comparison_still_runs(
    hasher, password_hash
):
    """when there is no usable hash, verify still performs one comparison.

    Skipping it would make an unknown account answer faster than a wrong
    password, which reveals which emails are registered.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    with patch.object(bcrypt, "checkpw", wraps=bcrypt.checkpw) as checkpw:
        hasher.verify("any-password", password_hash)

    assert checkpw.call_count == 1


def test_when_a_password_has_the_maximum_bytes_then_it_hashes_and_verifies(hasher):
    """when a password is exactly 72 bytes, it hashes and verifies.

    Validates app.infrastructure.security.BcryptPasswordHasher.hash().
    """
    password = "a" * PASSWORD_MAX_BYTES

    assert hasher.verify(password, hasher.hash(password)) is True


@pytest.mark.parametrize(
    "password",
    [
        pytest.param("a" * (PASSWORD_MAX_BYTES + 1), id="ascii"),
        pytest.param("é" * (PASSWORD_MAX_BYTES // 2 + 1), id="multi-byte"),
    ],
)
def test_when_a_password_exceeds_the_maximum_bytes_then_hash_refuses_it(
    hasher, password
):
    """when a password is longer than 72 bytes, hash raises instead of truncating.

    Validates app.infrastructure.security.BcryptPasswordHasher.hash().
    """
    with pytest.raises(ValueError, match="exceeds"):
        hasher.hash(password)


def test_when_a_candidate_extends_the_stored_password_then_verify_returns_false(
    hasher,
):
    """when a candidate extends the stored 72-byte password, it does not match.

    bcrypt 4 would ignore the extra bytes and accept it.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    password = "a" * PASSWORD_MAX_BYTES

    assert hasher.verify(password + "extra", hasher.hash(password)) is False


def test_when_text_cannot_be_encoded_strictly_then_verify_returns_false(hasher):
    """when a candidate holds a lone surrogate, verify returns False and does not raise.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    assert hasher.verify("\ud800 password", hasher.hash("real-password")) is False


def test_when_a_token_is_issued_then_it_round_trips_its_subject(issuer):
    """when a token is issued and verified, the subject comes back.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.subject_of().
    """
    assert issuer.subject_of(issuer.issue(SUBJECT)) == SUBJECT


def test_when_a_token_is_issued_then_it_expires_after_the_configured_minutes():
    """when a token is issued, exp equals the issue time plus the lifetime.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.issue().
    """
    fixed_issuer = JwtAccessTokenIssuer(
        SECRET, "HS256", EXPIRY_MINUTES, clock=lambda: FIXED_NOW
    )

    claims = jwt.get_unverified_claims(fixed_issuer.issue(SUBJECT))

    assert claims["iat"] == int(FIXED_NOW.timestamp())
    assert claims["exp"] - claims["iat"] == EXPIRY_MINUTES * SECONDS_PER_MINUTE


def test_when_a_token_is_expired_then_subject_of_raises_authentication_error():
    """when the token's lifetime has passed, verification fails.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.subject_of().
    """
    long_ago = datetime.now(UTC) - timedelta(hours=2)
    stale_issuer = JwtAccessTokenIssuer(
        SECRET, "HS256", EXPIRY_MINUTES, clock=lambda: long_ago
    )

    with pytest.raises(AuthenticationError) as raised:
        stale_issuer.subject_of(stale_issuer.issue(SUBJECT))

    assert raised.value.log_context == {"reason": "ExpiredSignatureError"}


def test_when_the_signing_key_differs_then_subject_of_raises(issuer):
    """when a token was signed with another key, verification fails.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.subject_of().
    """
    foreign = JwtAccessTokenIssuer(OTHER_SECRET, "HS256", EXPIRY_MINUTES)

    with pytest.raises(AuthenticationError):
        issuer.subject_of(foreign.issue(SUBJECT))


def test_when_the_payload_is_tampered_then_subject_of_raises(issuer):
    """when one character of the payload changes, the signature no longer matches.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.subject_of().
    """
    header, payload, signature = issuer.issue(SUBJECT).split(".")
    flipped = ("B" if payload[0] == "A" else "A") + payload[1:]

    with pytest.raises(AuthenticationError):
        issuer.subject_of(".".join([header, flipped, signature]))


def test_when_the_algorithm_differs_then_subject_of_raises(issuer):
    """when a token is signed with another HMAC algorithm, it is refused.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.subject_of().
    """
    with pytest.raises(AuthenticationError):
        issuer.subject_of(forge_token(valid_claims(), algorithm="HS512"))


def test_when_the_token_is_unsigned_then_subject_of_raises(issuer):
    """when a token declares alg none and carries no signature, it is refused.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.subject_of().
    """
    unsigned = (
        f"{url_safe_json({'alg': 'none', 'typ': 'JWT'})}."
        f"{url_safe_json({'sub': SUBJECT, 'exp': FAR_FUTURE_EPOCH})}."
    )

    with pytest.raises(AuthenticationError):
        issuer.subject_of(unsigned)


def test_when_the_subject_is_missing_then_subject_of_raises(issuer):
    """when a correctly signed token has no sub claim, it is refused.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.subject_of().
    """
    claims = valid_claims()
    del claims["sub"]

    with pytest.raises(AuthenticationError):
        issuer.subject_of(forge_token(claims))


def test_when_the_expiry_is_missing_then_subject_of_raises(issuer):
    """when a correctly signed token never expires, it is refused.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.subject_of().
    """
    claims = valid_claims()
    del claims["exp"]

    with pytest.raises(AuthenticationError):
        issuer.subject_of(forge_token(claims))


def test_when_the_subject_is_not_text_then_subject_of_raises(issuer):
    """when the sub claim is a number, the token is refused.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.subject_of().
    """
    with pytest.raises(AuthenticationError):
        issuer.subject_of(forge_token(valid_claims(sub=42)))


@pytest.mark.parametrize("token", MALFORMED_TOKENS)
def test_when_the_token_is_malformed_then_subject_of_raises_authentication_error(
    issuer, token
):
    """when the token is not a JWT, verification raises AuthenticationError only.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.subject_of().
    """
    with pytest.raises(AuthenticationError) as raised:
        issuer.subject_of(token)

    assert raised.value.public_message == AuthenticationError.default_message


def test_when_the_secret_key_is_empty_then_the_issuer_cannot_be_built():
    """when the key is empty, construction fails; an empty HMAC key forges tokens.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.
    """
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        JwtAccessTokenIssuer(SecretStr(""), "HS256", EXPIRY_MINUTES)


def test_when_built_from_settings_then_it_uses_their_key_algorithm_and_lifetime():
    """when built from settings, tokens follow the configured algorithm and lifetime.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.from_settings().
    """
    auth_settings = AuthSettings(
        jwt_secret_key=SECRET.get_secret_value(),
        jwt_algorithm="HS384",
        access_token_expire_minutes=EXPIRY_MINUTES,
    )

    from_settings = JwtAccessTokenIssuer.from_settings(
        auth_settings, clock=lambda: FIXED_NOW
    )
    token = from_settings.issue(SUBJECT)

    assert jwt.get_unverified_header(token)["alg"] == "HS384"
    claims = jwt.get_unverified_claims(token)
    assert claims["exp"] - claims["iat"] == EXPIRY_MINUTES * SECONDS_PER_MINUTE
