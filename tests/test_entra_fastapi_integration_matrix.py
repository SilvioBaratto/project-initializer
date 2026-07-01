"""TDD guard for issue #14: JWKS-mocked FastAPI integration matrix.

Asserts that templates-entra-fastapi/api/tests/integration/ ships:
  - conftest.py: RSA-keypair fixture that patches _jwks_client without any
    live network call
  - test_auth.py: five @pytest.mark.integration cases covering the full
    security matrix (valid→200+claims, bad-sig→401, wrong-aud→401,
    wrong-tid→401, missing-scp→403), with existing offline tests intact

These tests run in the repo suite (testpaths = ["tests"]) and act as a red
gate that turns green once the overlay implementation is merged.
"""

import re
from pathlib import Path

_OVERLAY_TESTS = (
    Path(__file__).resolve().parent.parent
    / "project_initializer"
    / "templates-entra-fastapi"
    / "api"
    / "tests"
    / "integration"
)

_CONFTEST = _OVERLAY_TESTS / "conftest.py"
_TEST_AUTH = _OVERLAY_TESTS / "test_auth.py"


def _conftest_text() -> str:
    return _CONFTEST.read_text(encoding="utf-8")


def _test_auth_text() -> str:
    return _TEST_AUTH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Criterion: shared fixture generates RSA keypair, patches _jwks_client,
#            signs tokens with headers={"kid": "test-key"}, no network call.
# ---------------------------------------------------------------------------


def test_when_conftest_read_then_file_exists():
    """when integration conftest.py is inspected, it exists in the overlay."""
    assert _CONFTEST.exists(), f"conftest.py not found at {_CONFTEST}"


def test_when_conftest_read_then_rsa_private_key_generation_is_present():
    """when conftest.py is read, it generates an RSA private key at fixture time."""
    text = _conftest_text()
    # cryptography library's RSA keygen function
    assert "generate_private_key" in text


def test_when_conftest_read_then_kid_test_key_header_is_used():
    """when conftest.py is read, tokens are signed with kid='test-key' in the header."""
    assert "test-key" in _conftest_text()


def test_when_conftest_read_then_jwks_singleton_is_patched():
    """when conftest.py is read, it patches app.dependencies._jwks_client."""
    text = _conftest_text()
    assert "_jwks_client" in text


def test_when_conftest_read_then_get_signing_key_from_jwt_is_patched():
    """when conftest.py is read, the patch targets get_signing_key_from_jwt."""
    text = _conftest_text()
    assert "get_signing_key_from_jwt" in text


def test_when_conftest_read_then_no_live_discovery_endpoint_is_called():
    """when conftest.py is read, it does not open the live Entra JWKS discovery URL."""
    # A mock fixture must not reach out to the real Entra key endpoint
    assert "login.microsoftonline.com" not in _conftest_text()


# ---------------------------------------------------------------------------
# Criterion: valid token → 200 with mapped id and email claims
# ---------------------------------------------------------------------------


def test_when_test_auth_read_then_valid_token_200_case_is_present():
    """when test_auth.py is read, it asserts a fully valid token returns HTTP 200."""
    assert "200" in _test_auth_text()


def test_when_test_auth_read_then_valid_token_case_asserts_id_claim():
    """when test_auth.py is read, the valid-token case checks the id field in the response."""
    text = _test_auth_text()
    assert '"id"' in text or "'id'" in text


def test_when_test_auth_read_then_valid_token_case_asserts_email_claim():
    """when test_auth.py is read, the valid-token case checks the email field in the response."""
    text = _test_auth_text()
    assert '"email"' in text or "'email'" in text


# ---------------------------------------------------------------------------
# Criterion: bad-signature token → 401
# ---------------------------------------------------------------------------


def test_when_test_auth_read_then_bad_signature_scenario_is_present():
    """when test_auth.py is read, it references a token signed by a different key."""
    text = _test_auth_text()
    # A second keypair or an explicit "wrong key" / "bad signature" label must appear
    assert (
        "signature" in text.lower()
        or "wrong_key" in text.lower()
        or "bad_key" in text.lower()
        or "other_key" in text.lower()
        or "different_key" in text.lower()
    )


# ---------------------------------------------------------------------------
# Criterion: wrong-audience token → 401
# ---------------------------------------------------------------------------


def test_when_test_auth_read_then_wrong_audience_scenario_references_aud():
    """when test_auth.py is read, it includes a test scenario that varies the aud claim."""
    assert "aud" in _test_auth_text()


# ---------------------------------------------------------------------------
# Criterion: wrong-tid token → 401
# ---------------------------------------------------------------------------


def test_when_test_auth_read_then_wrong_tid_scenario_references_tid():
    """when test_auth.py is read, it includes a test scenario that varies the tid claim."""
    assert "tid" in _test_auth_text()


# ---------------------------------------------------------------------------
# Criterion: missing-scope token → 403
# ---------------------------------------------------------------------------


def test_when_test_auth_read_then_missing_scope_returns_403():
    """when test_auth.py is read, it asserts a token lacking the required scope gives 403."""
    text = _test_auth_text()
    assert "403" in text


def test_when_test_auth_read_then_missing_scope_scenario_references_scp():
    """when test_auth.py is read, the 403 scenario manipulates the scp claim."""
    text = _test_auth_text()
    assert "scp" in text or "scope" in text.lower()


# ---------------------------------------------------------------------------
# Criterion: matrix completeness — at least five integration-marked cases
# ---------------------------------------------------------------------------


def test_when_test_auth_read_then_five_or_more_integration_cases_exist():
    """when test_auth.py is read, it carries at least five @pytest.mark.integration cases."""
    text = _test_auth_text()
    count = len(re.findall(r"@pytest\.mark\.integration", text))
    assert count >= 5, f"expected ≥5 @pytest.mark.integration cases, found {count}"


# ---------------------------------------------------------------------------
# Criterion (implicit): pre-existing offline tests are preserved
# ---------------------------------------------------------------------------


def test_when_test_auth_read_then_existing_missing_header_test_is_preserved():
    """when test_auth.py is read, the pre-existing missing-header 401 test still exists."""
    text = _test_auth_text()
    # The offline guard added before this issue must not be removed
    assert (
        "without_token" in text.lower()
        or "without token" in text.lower()
        or "Missing authorization header" in text
    )
