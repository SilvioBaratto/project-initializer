"""Doc-drift guard for the token `/auth/validate` 200-on-invalid contract (#28).

Reads the real generated root ``templates-api-fastapi/CLAUDE.md`` and asserts it
documents the locked decision: the token variant's ``/auth/validate`` is a
validity *probe* that returns HTTP 200 with ``authenticated=false`` for an
invalid token, while 401 is reserved for guarded endpoints. token/supabase
overlays ship no root CLAUDE.md of their own, so guarding the base doc guards
every variant.
"""

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = _ROOT / "project_initializer" / "templates-api-fastapi" / "CLAUDE.md"


def _doc() -> str:
    return CLAUDE_MD.read_text(encoding="utf-8")


def test_when_claude_md_read_then_validate_probe_endpoint_documented():
    """when the doc is read, the /auth/validate probe note is present."""
    assert "/auth/validate" in _doc()


def test_when_claude_md_read_then_200_on_invalid_decision_documented():
    """when the doc is read, the 200-with-authenticated-false-on-invalid rule is stated."""
    doc = _doc().lower()
    assert "200" in doc
    assert "authenticated" in doc and "false" in doc


def test_when_claude_md_read_then_401_reserved_for_guarded_routes_documented():
    """when the doc is read, 401 is documented as reserved for guarded endpoints."""
    doc = _doc()
    assert "401" in doc
    assert "/auth/me" in doc


def test_when_claude_md_read_then_supabase_has_no_validate_noted():
    """when the doc is read, the supabase variant is noted to lack /auth/validate."""
    doc = _doc().lower()
    assert "supabase" in doc
    assert "getuser" in doc or "jwt" in doc
