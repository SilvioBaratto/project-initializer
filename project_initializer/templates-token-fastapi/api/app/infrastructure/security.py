"""Pure cryptographic primitives for the token-auth variant.

Design principles
-----------------
- Single Responsibility: each function does exactly one thing.
- Dependency Inversion: callers supply the secret key and algorithm so this
  module has NO coupling to ``app.infrastructure.settings`` or ``settings``.
- KISS / stateless: no class needed — four pure functions that are easy to
  compose, test, and replace.

bcrypt pin note
---------------
``passlib==1.7.4`` reads ``bcrypt.__about__.__version__`` at import time.
``bcrypt>=4.1`` removed ``__about__``, causing an ``AttributeError``.
``bcrypt`` is therefore pinned to ``4.0.1`` in the base ``requirements.txt``.
Do NOT upgrade bcrypt without also upgrading passlib.
"""

from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

# Module-level context — created once, shared across all callers.
# bcrypt is the only active scheme; deprecated="auto" downgrades old hashes
# on next verify() rather than failing.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*.

    The hash includes the salt, cost factor, and algorithm identifier
    so the output is fully self-describing (starts with ``$2b$``).
    """
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return ``True`` when *plain_password* matches *hashed_password*."""
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str,
    secret_key: str,
    algorithm: str = "HS256",
    expires_minutes: int = 30,
) -> str:
    """Return a signed JWT whose ``sub`` claim is *subject*.

    The ``exp`` claim is set to ``now(UTC) + expires_minutes``.
    Callers supply *secret_key* so this function remains decoupled from
    any application-level settings object.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    claims = {"sub": str(subject), "exp": expire}
    return jwt.encode(claims, secret_key, algorithm=algorithm)


def decode_token(token: str, secret_key: str, algorithm: str = "HS256") -> dict:
    """Decode *token* and return the claims as a plain ``dict``.

    Raises ``jose.JWTError`` on any validation failure — wrong key,
    expired token, or tampered signature. Callers decide how to handle
    the error; this function never swallows it.
    """
    return jwt.decode(token, secret_key, algorithms=[algorithm])
