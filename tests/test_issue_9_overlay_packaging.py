"""
Source-blind tests for issue #9 — criterion 4:
  The three new overlay directories mirror the supabase overlay layout 1:1 so
  copy_tree merges them with no special-casing, and both pyproject.toml and
  MANIFEST.in package all three.

Tests are authored from the acceptance criteria only; no implementation source was read.
"""

from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent
_PKG = _ROOT / "project_initializer"

# The three new overlay directories that must exist (mirroring supabase layout)
_ENTRA_OVERLAYS = [
    "templates-entra-fastapi",
    "templates-entra-nestjs",
    "templates-entra-frontend",
]

# Reference supabase overlays — the entra overlays must mirror their structure 1:1
_SUPABASE_OVERLAYS = {
    "templates-entra-fastapi": "templates-supabase-fastapi",
    "templates-entra-nestjs": "templates-supabase-nestjs",
    "templates-entra-frontend": "templates-supabase-frontend",
}


# ---------------------------------------------------------------------------
# Overlay directories exist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("overlay", _ENTRA_OVERLAYS)
def test_when_entra_overlay_expected_then_directory_exists(overlay):
    """Each of the three entra overlay directories must exist under project_initializer/."""
    assert (_PKG / overlay).is_dir(), f"Missing overlay directory: {overlay}"


# ---------------------------------------------------------------------------
# Mirror check: top-level subdirectory names match their supabase counterpart
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entra_overlay,supabase_overlay",
    list(_SUPABASE_OVERLAYS.items()),
)
def test_when_entra_overlay_compared_to_supabase_then_top_level_subdirs_match(
    entra_overlay, supabase_overlay
):
    """
    The entra overlay must have the same top-level subdirectory names as the
    matching supabase overlay so copy_tree needs no special-casing.
    Assumption: 'mirror layout 1:1' means the same top-level directory structure
    (subdirectory names), not necessarily identical file contents.
    """
    entra_dir = _PKG / entra_overlay
    supabase_dir = _PKG / supabase_overlay

    if not supabase_dir.is_dir():
        pytest.skip(f"Supabase reference overlay missing: {supabase_overlay}")
    if not entra_dir.is_dir():
        pytest.fail(f"Entra overlay directory missing: {entra_overlay}")

    supabase_subdirs = {p.name for p in supabase_dir.iterdir() if p.is_dir()}
    entra_subdirs = {p.name for p in entra_dir.iterdir() if p.is_dir()}

    missing = supabase_subdirs - entra_subdirs
    assert not missing, (
        f"{entra_overlay} is missing subdirectories present in {supabase_overlay}: {missing}"
    )


# ---------------------------------------------------------------------------
# pyproject.toml covers all three overlay dirs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("overlay", _ENTRA_OVERLAYS)
def test_when_pyproject_toml_read_then_entra_overlay_is_in_package_data(overlay):
    """pyproject.toml must declare each entra overlay under package-data so it is installed."""
    pyproject = _ROOT / "pyproject.toml"
    assert pyproject.exists(), "pyproject.toml not found at repository root"
    content = pyproject.read_text(encoding="utf-8")
    assert overlay in content, (
        f"pyproject.toml does not reference overlay '{overlay}'; "
        "add it to [tool.setuptools.package-data]"
    )


# ---------------------------------------------------------------------------
# MANIFEST.in covers all three overlay dirs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("overlay", _ENTRA_OVERLAYS)
def test_when_manifest_in_read_then_entra_overlay_is_included(overlay):
    """MANIFEST.in must contain a recursive-include entry for each entra overlay."""
    manifest = _ROOT / "MANIFEST.in"
    assert manifest.exists(), "MANIFEST.in not found at repository root"
    content = manifest.read_text(encoding="utf-8")
    assert overlay in content, (
        f"MANIFEST.in does not reference overlay '{overlay}'; "
        "add a recursive-include line for it"
    )
