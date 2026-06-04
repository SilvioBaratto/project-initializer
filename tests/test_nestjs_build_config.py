"""Guards for NestJS install/build reliability fixes (#18, Bug 2 + Bug 3).

Asserts the two NestJS ``package.json`` files (base + supabase overlay) carry a
guarded ``postinstall``, a ``tsc-alias`` build step, and the pinned ``tsc-alias``
dev dependency, and that they stay identical except for ``@supabase/supabase-js``.
Reads the real template files so the fixtures cannot drift.
"""

import json
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / "project_initializer"
BASE_PKG = TEMPLATES / "templates-api-nestjs" / "api" / "package.json"
SUPABASE_PKG = TEMPLATES / "templates-supabase-nestjs" / "api" / "package.json"
BASE_TSCONFIG = TEMPLATES / "templates-api-nestjs" / "api" / "tsconfig.json"

PACKAGE_JSONS = [BASE_PKG, SUPABASE_PKG]

EXPECTED_POSTINSTALL = "npx prisma generate || true"
EXPECTED_BUILD = "nest build && tsc-alias -p tsconfig.json"
EXPECTED_TSC_ALIAS = "1.8.16"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", PACKAGE_JSONS, ids=["base", "supabase"])
def test_when_package_read_postinstall_is_guarded(path):
    assert _load_json(path)["scripts"]["postinstall"] == EXPECTED_POSTINSTALL


@pytest.mark.parametrize("path", PACKAGE_JSONS, ids=["base", "supabase"])
def test_when_package_read_build_runs_tsc_alias(path):
    assert _load_json(path)["scripts"]["build"] == EXPECTED_BUILD


@pytest.mark.parametrize("path", PACKAGE_JSONS, ids=["base", "supabase"])
def test_when_package_read_tsc_alias_is_pinned_exactly(path):
    assert _load_json(path)["devDependencies"]["tsc-alias"] == EXPECTED_TSC_ALIAS


def test_when_both_packages_compared_only_supabase_js_differs():
    base, supa = _load_json(BASE_PKG), _load_json(SUPABASE_PKG)
    extra = set(supa["dependencies"]) - set(base["dependencies"])
    assert extra == {"@supabase/supabase-js"}
    # Everything outside the dependencies block must be identical.
    base.pop("dependencies")
    supa.pop("dependencies")
    assert base == supa


def test_when_tsconfig_read_baseurl_deprecation_is_silenced():
    # TypeScript 6.x hard-errors (TS5101) on the deprecated `baseUrl` that the
    # `@generated/*` path aliases rely on; the override keeps `nest build` green.
    assert _load_json(BASE_TSCONFIG)["compilerOptions"]["ignoreDeprecations"] == "6.0"
