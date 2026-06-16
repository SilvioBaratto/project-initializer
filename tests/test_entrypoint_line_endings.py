"""
Regression tests: scaffolded projects must never hit
"exec /entrypoint.sh: no such file or directory" from CRLF line endings.

Root cause: on a Windows clone (Git default core.autocrlf=true) without a
.gitattributes, git rewrites checked-out text files to CRLF. The shell script's
shebang then ends with \r, so the Linux container looks for the interpreter
"/bin/bash\r" and Docker fails the ENTRYPOINT with a misleading "no such file"
error.

Three independent guards, each asserted below so removing any one fails CI:
  1. templates/.gitattributes ships and forces *.sh to eol=lf for every clone.
  2. Every entrypoint.sh in the template sources is committed with LF.
  3. Every Dockerfile that COPYs entrypoint.sh strips CR at build time
     (sed 's/\r$//') as defense-in-depth, before chmod +x.

These tests parse files as bytes/text; they never import production source.
"""

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
TEMPLATES = REPO_ROOT / "project_initializer"
GITATTRIBUTES = TEMPLATES / "templates" / ".gitattributes"

ENTRYPOINTS = sorted(
    p
    for p in TEMPLATES.rglob("entrypoint.sh")
    if "node_modules" not in p.parts
)

DOCKERFILES_WITH_ENTRYPOINT = sorted(
    p
    for p in TEMPLATES.rglob("Dockerfile")
    if "node_modules" not in p.parts
    and "COPY entrypoint.sh" in p.read_text(encoding="utf-8")
)


# ---------------------------------------------------------------------------
# Guard 1: .gitattributes ships and normalizes shell scripts to LF
# ---------------------------------------------------------------------------


def test_gitattributes_ships_in_base_template():
    """The base template root carries a .gitattributes so every scaffold gets it."""
    assert GITATTRIBUTES.exists(), (
        f".gitattributes missing at {GITATTRIBUTES}; Windows clones will "
        "checkout entrypoint.sh as CRLF and Docker ENTRYPOINT will fail."
    )


def test_gitattributes_forces_sh_to_lf():
    """*.sh must be pinned to eol=lf so the rule survives any core.autocrlf."""
    text = GITATTRIBUTES.read_text(encoding="utf-8")
    assert "*.sh" in text and "eol=lf" in text, (
        ".gitattributes must contain a '*.sh ... eol=lf' rule"
    )


def test_gitattributes_is_packaged_in_manifest():
    """MANIFEST.in must explicitly include the dotfile (sdist drops dotfiles)."""
    manifest = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "templates/.gitattributes" in manifest, (
        "MANIFEST.in must `include project_initializer/templates/.gitattributes` "
        "or the sdist ships without it."
    )


# ---------------------------------------------------------------------------
# Guard 2: every entrypoint.sh source is committed with LF
# ---------------------------------------------------------------------------


def test_entrypoint_scripts_exist():
    assert ENTRYPOINTS, "expected at least one entrypoint.sh in the templates"


@pytest.mark.parametrize(
    "script", ENTRYPOINTS, ids=lambda p: str(p.relative_to(TEMPLATES))
)
def test_entrypoint_source_has_no_crlf(script):
    """The committed script must be pure LF — no \\r bytes anywhere."""
    raw = script.read_bytes()
    assert b"\r" not in raw, (
        f"{script} contains CR bytes; commit it with LF line endings."
    )


@pytest.mark.parametrize(
    "script", ENTRYPOINTS, ids=lambda p: str(p.relative_to(TEMPLATES))
)
def test_entrypoint_shebang_is_clean(script):
    """First line is a POSIX shebang with no trailing CR.

    FastAPI (debian) uses bash; NestJS (alpine) uses sh — both valid, neither
    may carry a \\r.
    """
    first = script.read_bytes().split(b"\n", 1)[0]
    assert first in (b"#!/bin/bash", b"#!/bin/sh"), (
        f"{script} shebang is {first!r}; expected b'#!/bin/bash' or "
        "b'#!/bin/sh' with no trailing CR."
    )


# ---------------------------------------------------------------------------
# Guard 3: Dockerfiles strip CR at build time (defense-in-depth)
# ---------------------------------------------------------------------------


def test_dockerfiles_copying_entrypoint_are_found():
    assert DOCKERFILES_WITH_ENTRYPOINT, (
        "expected at least one Dockerfile that COPYs entrypoint.sh"
    )


@pytest.mark.parametrize(
    "dockerfile",
    DOCKERFILES_WITH_ENTRYPOINT,
    ids=lambda p: str(p.relative_to(TEMPLATES)),
)
def test_dockerfile_strips_cr_before_running_entrypoint(dockerfile):
    r"""Every Dockerfile copying entrypoint.sh must `sed -i 's/\r$//'` it."""
    text = dockerfile.read_text(encoding="utf-8")
    assert "sed -i 's/\\r$//' /entrypoint.sh" in text, (
        f"{dockerfile} copies entrypoint.sh but does not strip CR; a CRLF "
        r"checkout would still break the shebang. Add: sed -i 's/\r$//' /entrypoint.sh"
    )
