"""Doc-drift guards for the sync-vs-async DB convention (#19).

Reads the real generated FastAPI ``api/.claude/CLAUDE.md`` and asserts the
route-level concurrency rule is documented: sync ``def`` for DB endpoints
(threadpool + sync ``Session``), ``async def`` only for BAML/LLM calls, with
canonical example citations and a note on the opt-in flag-gated async path.

token/supabase overlays do NOT ship their own CLAUDE.md, so guarding the base
doc guards every variant.
"""

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
API_CLAUDE_MD = (
    _ROOT
    / "project_initializer"
    / "templates-api-fastapi"
    / "api"
    / ".claude"
    / "CLAUDE.md"
)


def _doc() -> str:
    return API_CLAUDE_MD.read_text(encoding="utf-8")


def test_when_api_claude_md_read_sync_async_section_exists():
    """when the doc is read, an explicit Sync vs async section is present."""
    assert "Sync vs async" in _doc()


def test_when_api_claude_md_read_sync_def_db_threadpool_rule_documented():
    """when the doc is read, the sync def + threadpool + sync Session rule is stated."""
    doc = _doc().lower()
    assert "threadpool" in doc
    assert "sync `def`" in doc or "sync def" in doc


def test_when_api_claude_md_read_async_reserved_for_baml_documented():
    """when the doc is read, async def is reserved for BAML/LLM calls only."""
    doc = _doc()
    assert "`async def`" in doc or "async def" in doc
    assert "BAML" in doc


def test_when_api_claude_md_read_canonical_examples_cited():
    """when the doc is read, items.py (sync) and chatbot_service.py (async) are cited."""
    doc = _doc()
    assert "app/api/v1/items.py" in doc
    assert "app/services/chatbot_service.py" in doc


def test_when_api_claude_md_read_optin_flag_gated_async_path_noted():
    """when the doc is read, the opt-in flag-gated async DB path is noted as non-default."""
    doc = _doc().lower()
    assert "opt-in" in doc or "opt in" in doc
    assert "async" in doc and ("flag" in doc and "default" in doc)
