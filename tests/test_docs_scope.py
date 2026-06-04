"""Doc-drift guards for the ``--scope`` flag in the repo ``CLAUDE.md`` (#19).

Reads the real ``CLAUDE.md`` and asserts the flag, its values, and the
validation constraint are documented. The value list is checked against
``cli.SCOPES`` (the source of truth) so the docs cannot silently drift.
"""

from pathlib import Path

from project_initializer.cli import SCOPES

CLAUDE_MD = Path(__file__).resolve().parent.parent / "CLAUDE.md"


def _doc() -> str:
    return CLAUDE_MD.read_text(encoding="utf-8")


def test_when_claude_md_read_scope_flag_is_documented():
    assert "--scope" in _doc()


def test_when_claude_md_read_every_scope_value_is_documented():
    doc = _doc()
    missing = [value for value in SCOPES if value not in doc]
    assert missing == []


def test_when_claude_md_read_frontend_constraint_is_documented():
    doc = _doc().lower()
    # frontend scope is rejected when combined with a framework or auth flag
    assert "frontend" in doc and "cannot" in doc and "--auth" in doc


def test_when_claude_md_read_overlay_section_mentions_scope():
    doc = _doc()
    overlay = doc.split("## Template Overlay System", 1)[-1]
    assert "scope" in overlay.lower()
