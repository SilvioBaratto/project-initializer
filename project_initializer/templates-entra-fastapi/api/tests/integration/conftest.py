"""Shared fixtures for Entra JWT integration tests.

Generates a local RSA keypair and patches the JWKS client singleton so
no live tenant or network call is needed. The issuer string is derived from
the patched settings singleton at call time — never hard-coded here.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from fastapi.testclient import TestClient

from app.main import app

_PUBLIC_EXPONENT = 65537
_KEY_SIZE = 2048
_SCOPE = "access_as_user"
_TENANT_ID = "test-tenant-id"
_CLIENT_ID = "test-client-id"
_OID = "test-user-oid"
_EMAIL = "testuser@example.com"

# Bare TestClient — no context manager, no DB engine (JSONB incompatible with
# SQLite), no lifespan init_db. Auth routes 401/200 before any DB access.
client = TestClient(app)


class _SigningKeyStub:
    """Minimal stub satisfying jwt.decode's signing_key.key usage."""

    def __init__(self, public_key):
        self.key = public_key


@pytest.fixture(scope="session")
def rsa_keypair():
    """Generate a single RSA keypair for the entire test session."""
    private_key = generate_private_key(
        public_exponent=_PUBLIC_EXPONENT,
        key_size=_KEY_SIZE,
    )
    return private_key, private_key.public_key()


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    """Override settings singleton with known test values."""
    import app.config as cfg

    monkeypatch.setattr(cfg.settings, "entra_tenant_id", _TENANT_ID)
    monkeypatch.setattr(cfg.settings, "entra_api_client_id", _CLIENT_ID)
    monkeypatch.setattr(cfg.settings, "entra_api_audience", "")
    monkeypatch.setattr(cfg.settings, "entra_api_scope", _SCOPE)


@pytest.fixture(autouse=True)
def patch_jwks_client(monkeypatch, rsa_keypair):
    """Patch _jwks_client.get_signing_key_from_jwt to return the test public key."""
    _, public_key = rsa_keypair
    stub = _SigningKeyStub(public_key)

    import app.dependencies as deps

    monkeypatch.setattr(
        deps._jwks_client, "get_signing_key_from_jwt", lambda _token: stub
    )


@pytest.fixture(scope="session")
def make_token(rsa_keypair):
    """Factory: build a signed RS256 JWT with valid default claims, accepting overrides.

    The iss claim is derived from settings.entra_issuer at call time so the
    fixture does not embed any environment-specific URLs.
    """
    private_key, _ = rsa_keypair

    def _build(**overrides):
        import app.config as cfg

        now = int(time.time())
        claims = {
            "iss": cfg.settings.entra_issuer,
            "aud": _CLIENT_ID,
            "tid": _TENANT_ID,
            "oid": _OID,
            "preferred_username": _EMAIL,
            "scp": _SCOPE,
            "iat": now,
            "exp": now + 3600,
        }
        claims.update(overrides)
        return jwt.encode(
            claims,
            private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

    return _build
