"""
Issue #13 — Criteria:
  (a) Root README.md contains no remaining "3 auth modes" wording; entra is listed in the
      Authentication Modes section with a --auth entra example.
  (b) Root README.md "All 6 Variants" section is retitled (8 variants) and its table includes
      the FastAPI-entra and NestJS-entra rows.
"""

import pathlib
import re

README = pathlib.Path("README.md")


def _readme_text() -> str:
    return README.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Criterion (a): no "3 auth modes" wording; entra listed with --auth entra example
# ---------------------------------------------------------------------------


def test_when_readme_is_read_then_three_auth_modes_wording_is_absent():
    text = _readme_text()
    # Match "3 auth modes" or "three auth modes" (case-insensitive)
    match = re.search(
        r"\b3\s+auth\s+modes?\b|\bthree\s+auth\s+modes?\b", text, re.IGNORECASE
    )
    assert not match, (
        "README.md must not contain '3 auth modes' — update to '4 auth modes' for entra"
    )


def test_when_readme_is_read_then_entra_appears_in_authentication_modes_section():
    text = _readme_text()
    # Locate an "Authentication Modes" heading (or similar)
    section_match = re.search(r"#{1,4}\s*authentication\s+modes?", text, re.IGNORECASE)
    assert section_match, "README.md must have an 'Authentication Modes' section"
    section_body = text[section_match.start() :]
    assert "entra" in section_body.lower(), (
        "The Authentication Modes section must mention entra"
    )


def test_when_readme_is_read_then_auth_entra_example_command_is_present():
    text = _readme_text()
    assert "--auth entra" in text, (
        "README.md must include a --auth entra example command"
    )


# ---------------------------------------------------------------------------
# Criterion (b): section retitled to 8 variants; table has fastapi-entra + nestjs-entra rows
# ---------------------------------------------------------------------------


def test_when_readme_is_read_then_eight_variants_heading_is_present():
    text = _readme_text()
    # "8 Variants" or "8 variants" (digit or word)
    match = re.search(r"\b8\s+variants?\b|\beight\s+variants?\b", text, re.IGNORECASE)
    assert match, (
        "README.md must retitle the variants section to '8 variants' (was '6 variants')"
    )


def test_when_readme_is_read_then_six_variants_heading_is_absent():
    """The old '6 Variants' title must be replaced — no remaining '6 variants' wording."""
    text = _readme_text()
    # Allow "6 variants" only inside code blocks or inline code (edge case), but not in headings
    match = re.search(r"#{1,4}[^\n]*\b6\s+variants?\b", text, re.IGNORECASE)
    assert not match, (
        "README.md must not retain a '6 Variants' heading — it should now read '8 Variants'"
    )


def test_when_readme_is_read_then_fastapi_entra_row_is_in_variants_table():
    text = _readme_text()
    has_fastapi_entra = (
        re.search(r"fastapi.{0,20}entra", text, re.IGNORECASE) is not None
        or re.search(r"entra.{0,20}fastapi", text, re.IGNORECASE) is not None
    )
    assert has_fastapi_entra, (
        "README.md variants table must include a FastAPI + entra row"
    )


def test_when_readme_is_read_then_nestjs_entra_row_is_in_variants_table():
    text = _readme_text()
    has_nestjs_entra = (
        re.search(r"nestjs.{0,20}entra", text, re.IGNORECASE) is not None
        or re.search(r"entra.{0,20}nestjs", text, re.IGNORECASE) is not None
    )
    assert has_nestjs_entra, (
        "README.md variants table must include a NestJS + entra row"
    )
