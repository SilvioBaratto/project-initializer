"""
Issue #13 — Criterion: CLAUDE.md Project Overview reads "8 variants ... 4 auth modes" and the
overlay listing includes the three templates-entra-* directories.
"""

import pathlib
import re

CLAUDE_MD = pathlib.Path("CLAUDE.md")


def _claude_md_text() -> str:
    return CLAUDE_MD.read_text(encoding="utf-8")


def test_when_claude_md_is_read_then_eight_variants_is_stated_in_project_overview():
    text = _claude_md_text()
    match = re.search(r"\b8\s+variants?\b|\beight\s+variants?\b", text, re.IGNORECASE)
    assert match, "CLAUDE.md Project Overview must read '8 variants' (was '6 variants')"


def test_when_claude_md_is_read_then_four_auth_modes_is_stated_in_project_overview():
    text = _claude_md_text()
    match = re.search(
        r"\b4\s+auth\s+modes?\b|\bfour\s+auth\s+modes?\b", text, re.IGNORECASE
    )
    assert match, (
        "CLAUDE.md Project Overview must read '4 auth modes' (was '3 auth modes')"
    )


def test_when_claude_md_is_read_then_three_auth_modes_wording_is_absent():
    text = _claude_md_text()
    match = re.search(
        r"\b3\s+auth\s+modes?\b|\bthree\s+auth\s+modes?\b", text, re.IGNORECASE
    )
    assert not match, "CLAUDE.md must not retain '3 auth modes' wording"


def test_when_claude_md_is_read_then_templates_entra_fastapi_is_listed():
    text = _claude_md_text()
    assert "templates-entra-fastapi" in text, (
        "CLAUDE.md overlay listing must include templates-entra-fastapi"
    )


def test_when_claude_md_is_read_then_templates_entra_nestjs_is_listed():
    text = _claude_md_text()
    assert "templates-entra-nestjs" in text, (
        "CLAUDE.md overlay listing must include templates-entra-nestjs"
    )


def test_when_claude_md_is_read_then_templates_entra_frontend_is_listed():
    text = _claude_md_text()
    assert "templates-entra-frontend" in text, (
        "CLAUDE.md overlay listing must include templates-entra-frontend"
    )
