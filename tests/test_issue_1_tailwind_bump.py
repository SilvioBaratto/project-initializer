"""
Tests for issue #1: chore: bump Tailwind to v4.3 in the frontend template.

Source-blind: authored against acceptance criteria only, before any implementation.
Criteria covered (UNIT-verifiable):
  - tailwindcss and @tailwindcss/postcss are ^4.3.0 in templates/frontend/package.json
  - package-lock.json is refreshed so both packages resolve to a v4.3 version
  - No tailwind.config.* file is introduced (template stays CSS-first)
"""

import json
import pathlib

FRONTEND = (
    pathlib.Path(__file__).parent.parent
    / "project_initializer"
    / "templates"
    / "frontend"
)


def _load_package_json() -> dict:
    return json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))


def _load_package_lock() -> dict:
    return json.loads((FRONTEND / "package-lock.json").read_text(encoding="utf-8"))


def _resolved_version(lock: dict, package_name: str) -> str:
    """Return the resolved version string for *package_name* from an npm lockfile.

    Supports lockfileVersion 2/3 (packages dict keyed by node_modules/<name>)
    and v1 (dependencies dict keyed by bare name).
    """
    if "packages" in lock:
        key = f"node_modules/{package_name}"
        return lock["packages"][key]["version"]
    return lock["dependencies"][package_name]["version"]


# ---------------------------------------------------------------------------
# Criterion: tailwindcss is ^4.3.0 in package.json
# ---------------------------------------------------------------------------


def test_when_package_json_read_then_tailwindcss_devdependency_is_4_3_0():
    """'tailwindcss' devDependency version range must be exactly '^4.3.0'."""
    pkg = _load_package_json()
    assert pkg["devDependencies"]["tailwindcss"] == "^4.3.0"


# ---------------------------------------------------------------------------
# Criterion: @tailwindcss/postcss is ^4.3.0 in package.json
# ---------------------------------------------------------------------------


def test_when_package_json_read_then_tailwindcss_postcss_devdependency_is_4_3_0():
    """'@tailwindcss/postcss' devDependency version range must be exactly '^4.3.0'."""
    pkg = _load_package_json()
    assert pkg["devDependencies"]["@tailwindcss/postcss"] == "^4.3.0"


# ---------------------------------------------------------------------------
# Criterion: package-lock.json resolves tailwindcss to a v4.3 version
# ---------------------------------------------------------------------------


def test_when_package_lock_read_then_tailwindcss_resolves_to_4_3():
    """Resolved 'tailwindcss' version in package-lock.json must start with '4.3.'."""
    lock = _load_package_lock()
    version = _resolved_version(lock, "tailwindcss")
    assert version.startswith("4.3."), (
        f"expected tailwindcss to resolve to 4.3.x, got {version!r}"
    )


# ---------------------------------------------------------------------------
# Criterion: package-lock.json resolves @tailwindcss/postcss to a v4.3 version
# ---------------------------------------------------------------------------


def test_when_package_lock_read_then_tailwindcss_postcss_resolves_to_4_3():
    """Resolved '@tailwindcss/postcss' version in package-lock.json must start with '4.3.'."""
    lock = _load_package_lock()
    version = _resolved_version(lock, "@tailwindcss/postcss")
    assert version.startswith("4.3."), (
        f"expected @tailwindcss/postcss to resolve to 4.3.x, got {version!r}"
    )


# ---------------------------------------------------------------------------
# Criterion: no tailwind.config.* file is introduced
# ---------------------------------------------------------------------------


def test_when_frontend_directory_listed_then_no_tailwind_config_file_exists():
    """No tailwind.config.* file must exist in the frontend template root.

    The template is CSS-first; introducing a config file would break that
    contract and is explicitly forbidden by the acceptance criteria.
    """
    found = list(FRONTEND.glob("tailwind.config.*"))
    assert found == [], (
        f"unexpected tailwind config file(s) found: {[str(f) for f in found]}"
    )
