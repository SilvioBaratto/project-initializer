"""Guard the NestJS 12 manifest sweep (plan T2) across the three overlays.

The base, supabase and entra overlays each own a ``package.json``; the token
overlay ships none and inherits the base pair. This sweep bumps the whole
``@nestjs/*`` set to 12, takes bullmq to 6 with a direct ``ioredis`` dep, moves
the bull-board trio to 9 and the pino stack to 10/11, and **drops** ``nestjs-zod``
(no NestJS 12 peer — it would ERESOLVE ``npm ci``). The native-validation code
refactor that removes the last ``nestjs-zod`` *import* is a later task; here we
only lock the manifest targets. Reads the real template files so the pins cannot
drift from the plan.
"""

import json
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / "project_initializer"
_PACKAGES = {
    "base": TEMPLATES / "templates-api-nestjs" / "api" / "package.json",
    "supabase": TEMPLATES / "templates-supabase-nestjs" / "api" / "package.json",
    "entra": TEMPLATES / "templates-entra-nestjs" / "api" / "package.json",
}

# Exact pins T2 applies in every overlay (repo convention: no caret/tilde ranges).
_DEPENDENCY_TARGETS = {
    "@nestjs/common": "12.1.1",
    "@nestjs/core": "12.1.1",
    "@nestjs/platform-express": "12.1.1",
    "@nestjs/config": "12.0.1",
    "@nestjs/swagger": "12.0.2",
    "@nestjs/terminus": "12.1.0",
    "@nestjs/throttler": "6.7.1",
    "@nestjs/bullmq": "12.0.0",
    "bullmq": "6.3.9",
    "ioredis": "6.0.0",
    "@bull-board/api": "9.10.1",
    "@bull-board/express": "9.10.1",
    "@bull-board/nestjs": "9.10.1",
    "nestjs-pino": "5.2.1",
    "pino": "10.3.1",
    "pino-http": "11.0.0",
}
_DEV_DEPENDENCY_TARGETS = {
    "@nestjs/cli": "12.0.8",
    "@nestjs/schematics": "12.0.6",
    "@nestjs/testing": "12.1.1",
}
# Held deliberately by T2 (bumped elsewhere or not at all); a stray edit is a bug.
_HELD = {
    "dependencies": {"zod": "4.4.3"},
    "devDependencies": {"typescript": "6.0.3", "pino-pretty": "13.1.3"},
}

_OVERLAYS = list(_PACKAGES)


def _load(overlay: str) -> dict:
    return json.loads(_PACKAGES[overlay].read_text(encoding="utf-8"))


@pytest.mark.parametrize("overlay", _OVERLAYS)
def test_package_json_is_valid_and_exact_pinned(overlay):
    """Every manifest parses and pins the swept deps with no range prefix."""
    pkg = _load(overlay)
    for block in ("dependencies", "devDependencies"):
        for name, version in pkg.get(block, {}).items():
            assert not version.startswith(("^", "~")), (
                f"{overlay}: {name}@{version} is a range — repo pins exact versions"
            )


@pytest.mark.parametrize("overlay", _OVERLAYS)
def test_nestjs_12_dependency_targets(overlay):
    """The dependency block carries the NestJS 12 / bullmq 6 / pino 10 matrix."""
    deps = _load(overlay)["dependencies"]
    for name, version in _DEPENDENCY_TARGETS.items():
        assert deps.get(name) == version, (
            f"{overlay}: {name} must be {version}, found {deps.get(name)!r}"
        )


@pytest.mark.parametrize("overlay", _OVERLAYS)
def test_nestjs_12_dev_dependency_targets(overlay):
    """The devDependency block carries the NestJS 12 CLI/schematics/testing set."""
    dev = _load(overlay)["devDependencies"]
    for name, version in _DEV_DEPENDENCY_TARGETS.items():
        assert dev.get(name) == version, (
            f"{overlay}: {name} must be {version}, found {dev.get(name)!r}"
        )


@pytest.mark.parametrize("overlay", _OVERLAYS)
def test_nestjs_zod_is_removed(overlay):
    """nestjs-zod has no NestJS 12 peer — it must be gone from every manifest."""
    pkg = _load(overlay)
    assert "nestjs-zod" not in pkg.get("dependencies", {})
    assert "nestjs-zod" not in pkg.get("devDependencies", {})


@pytest.mark.parametrize("overlay", _OVERLAYS)
def test_ioredis_added_for_bullmq_6(overlay):
    """bullmq 6 unbundles ioredis — it must be a direct dependency now."""
    assert _load(overlay)["dependencies"].get("ioredis") == "6.0.0"


@pytest.mark.parametrize("overlay", _OVERLAYS)
def test_deliberately_held_versions_untouched(overlay):
    """T2 keeps zod, typescript and pino-pretty exactly where they were."""
    pkg = _load(overlay)
    for block, held in _HELD.items():
        for name, version in held.items():
            assert pkg.get(block, {}).get(name) == version, (
                f"{overlay}: {name} should stay {version} (T2 must not touch it)"
            )


def test_swept_versions_consistent_across_overlays():
    """base/supabase/entra must agree on every swept package (targets consistent)."""
    swept = {**_DEPENDENCY_TARGETS, **_DEV_DEPENDENCY_TARGETS}
    loaded = {name: _load(name) for name in _OVERLAYS}
    for pkg_name in swept:
        seen = {
            overlay: pkg.get("dependencies", {}).get(pkg_name)
            or pkg.get("devDependencies", {}).get(pkg_name)
            for overlay, pkg in loaded.items()
        }
        assert len(set(seen.values())) == 1, (
            f"{pkg_name} diverges across overlays: {seen}"
        )
