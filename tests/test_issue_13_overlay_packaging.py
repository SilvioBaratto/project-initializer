"""
Issue #13 — Criterion: The three new overlay directories mirror the supabase overlay layout 1:1
so copy_tree merges them with no special-casing, and both pyproject.toml and MANIFEST.in package
all three.
"""

import pathlib

ROOT = pathlib.Path(".")
PYPROJECT = ROOT / "pyproject.toml"
MANIFEST = ROOT / "MANIFEST.in"

ENTRA_OVERLAYS = [
    "templates-entra-fastapi",
    "templates-entra-nestjs",
    "templates-entra-frontend",
]

SUPABASE_OVERLAYS = [
    "templates-supabase-fastapi",
    "templates-supabase-nestjs",
    "templates-supabase-frontend",
]


# ---------------------------------------------------------------------------
# Overlay directory existence
# ---------------------------------------------------------------------------


def test_when_entra_fastapi_overlay_is_checked_then_directory_exists():
    assert (ROOT / "project_initializer" / "templates-entra-fastapi").is_dir()


def test_when_entra_nestjs_overlay_is_checked_then_directory_exists():
    assert (ROOT / "project_initializer" / "templates-entra-nestjs").is_dir()


def test_when_entra_frontend_overlay_is_checked_then_directory_exists():
    assert (ROOT / "project_initializer" / "templates-entra-frontend").is_dir()


# ---------------------------------------------------------------------------
# pyproject.toml packaging
# ---------------------------------------------------------------------------


def test_when_pyproject_toml_is_read_then_entra_fastapi_overlay_is_packaged():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert "templates-entra-fastapi" in text, (
        "pyproject.toml must include templates-entra-fastapi in package-data"
    )


def test_when_pyproject_toml_is_read_then_entra_nestjs_overlay_is_packaged():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert "templates-entra-nestjs" in text, (
        "pyproject.toml must include templates-entra-nestjs in package-data"
    )


def test_when_pyproject_toml_is_read_then_entra_frontend_overlay_is_packaged():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert "templates-entra-frontend" in text, (
        "pyproject.toml must include templates-entra-frontend in package-data"
    )


# ---------------------------------------------------------------------------
# MANIFEST.in packaging
# ---------------------------------------------------------------------------


def test_when_manifest_in_is_read_then_entra_fastapi_overlay_is_included():
    text = MANIFEST.read_text(encoding="utf-8")
    assert "templates-entra-fastapi" in text, (
        "MANIFEST.in must include recursive-include for templates-entra-fastapi"
    )


def test_when_manifest_in_is_read_then_entra_nestjs_overlay_is_included():
    text = MANIFEST.read_text(encoding="utf-8")
    assert "templates-entra-nestjs" in text, (
        "MANIFEST.in must include recursive-include for templates-entra-nestjs"
    )


def test_when_manifest_in_is_read_then_entra_frontend_overlay_is_included():
    text = MANIFEST.read_text(encoding="utf-8")
    assert "templates-entra-frontend" in text, (
        "MANIFEST.in must include recursive-include for templates-entra-frontend"
    )


# ---------------------------------------------------------------------------
# Layout parity with supabase overlays (1:1 mirror invariant)
# Each entra overlay must have the same top-level sub-directories as its
# corresponding supabase overlay — that is what "mirror the supabase overlay
# layout 1:1" means for the CLI's copy_tree to require no special-casing.
# ---------------------------------------------------------------------------


def _top_level_dirs(overlay_name: str) -> set:
    base = ROOT / "project_initializer" / overlay_name
    return {p.name for p in base.iterdir() if p.is_dir()}


def test_when_entra_fastapi_overlay_layout_is_compared_to_supabase_then_top_level_dirs_match():
    entra_dirs = _top_level_dirs("templates-entra-fastapi")
    supabase_dirs = _top_level_dirs("templates-supabase-fastapi")
    assert entra_dirs == supabase_dirs, (
        f"templates-entra-fastapi top-level dirs {entra_dirs!r} must match "
        f"templates-supabase-fastapi {supabase_dirs!r}"
    )


def test_when_entra_nestjs_overlay_layout_is_compared_to_supabase_then_top_level_dirs_match():
    entra_dirs = _top_level_dirs("templates-entra-nestjs")
    supabase_dirs = _top_level_dirs("templates-supabase-nestjs")
    assert entra_dirs == supabase_dirs, (
        f"templates-entra-nestjs top-level dirs {entra_dirs!r} must match "
        f"templates-supabase-nestjs {supabase_dirs!r}"
    )


def test_when_entra_frontend_overlay_layout_is_compared_to_supabase_then_top_level_dirs_match():
    entra_dirs = _top_level_dirs("templates-entra-frontend")
    supabase_dirs = _top_level_dirs("templates-supabase-frontend")
    assert entra_dirs == supabase_dirs, (
        f"templates-entra-frontend top-level dirs {entra_dirs!r} must match "
        f"templates-supabase-frontend {supabase_dirs!r}"
    )
