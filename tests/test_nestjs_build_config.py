"""Guards for NestJS install/build reliability fixes (#18, Bug 2 + Bug 3).

Asserts the two NestJS ``package.json`` files (base + supabase overlay) carry a
guarded ``postinstall``, a ``tsc-alias`` build step, and the pinned ``tsc-alias``
dev dependency, and that they stay identical except for ``@supabase/supabase-js``.
The three that ship a ``package.json`` (base, supabase, entra) also carry the same lint,
format and coverage-gate tooling. Reads the real template files so the fixtures cannot drift.
"""

import json
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / "project_initializer"
BASE_PKG = TEMPLATES / "templates-api-nestjs" / "api" / "package.json"
SUPABASE_PKG = TEMPLATES / "templates-supabase-nestjs" / "api" / "package.json"
ENTRA_PKG = TEMPLATES / "templates-entra-nestjs" / "api" / "package.json"
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
    """The supabase manifest differs from the base one only by the supabase-js dependency.

    Validates project_initializer/templates-api-nestjs/api/package.json and project_initializer/templates-supabase-nestjs/api/package.json.
    """
    base, supa = _load_json(BASE_PKG), _load_json(SUPABASE_PKG)
    base_deps, supa_deps = set(base["dependencies"]), set(supa["dependencies"])
    # Symmetric check: supabase adds only @supabase/supabase-js, and drops nothing
    # the base carries (guards against an overlay omitting a base dependency such
    # as @nestjs/terminus, which the shared health module imports).
    assert supa_deps - base_deps == {"@supabase/supabase-js"}
    assert base_deps - supa_deps == set()
    # Everything outside the dependencies block must be identical, including the jest
    # moduleNameMapper: the specs import the real base sources, so no overlay needs stubs.
    base.pop("dependencies")
    supa.pop("dependencies")
    assert base == supa, "packages diverged beyond allowed differences"


def test_when_tsconfig_read_baseurl_deprecation_is_silenced():
    # TypeScript 6.x hard-errors (TS5101) on the deprecated `baseUrl` that the
    # `@generated/*` path aliases rely on; the override keeps `nest build` green.
    assert _load_json(BASE_TSCONFIG)["compilerOptions"]["ignoreDeprecations"] == "6.0"


TOOLED_PACKAGE_JSONS = [BASE_PKG, SUPABASE_PKG, ENTRA_PKG]
TOOLED_IDS = ["base", "supabase", "entra"]
MIN_LINE_COVERAGE = 75


@pytest.mark.parametrize("path", TOOLED_PACKAGE_JSONS, ids=TOOLED_IDS)
def test_when_package_read_lint_and_format_scripts_fail_on_findings(path):
    """The lint script fails on warnings and the format scripts run prettier.

    Validates the scripts of project_initializer/templates-{api,supabase,entra}-nestjs/api/package.json.
    """
    scripts = _load_json(path)["scripts"]
    assert "--max-warnings 0" in scripts["lint"], "lint must fail on warnings"
    assert scripts["format:check"].startswith("prettier --check")
    assert scripts["format"].startswith("prettier --write")


@pytest.mark.parametrize("path", TOOLED_PACKAGE_JSONS, ids=TOOLED_IDS)
def test_when_package_read_coverage_threshold_is_enforced(path):
    """The jest global coverage threshold holds the minimum line coverage.

    Validates the jest.coverageThreshold of project_initializer/templates-{api,supabase,entra}-nestjs/api/package.json.
    """
    threshold = _load_json(path)["jest"]["coverageThreshold"]["global"]
    assert threshold["lines"] >= MIN_LINE_COVERAGE
    assert threshold["statements"] >= MIN_LINE_COVERAGE


@pytest.mark.parametrize("path", TOOLED_PACKAGE_JSONS, ids=TOOLED_IDS)
def test_when_package_read_jest_loads_the_test_environment_first(path):
    """The env schema is validated at import time, so the variables must exist before any spec.

    Validates the jest.setupFiles of project_initializer/templates-{api,supabase,entra}-nestjs/api/package.json.
    """
    setup_files = _load_json(path)["jest"]["setupFiles"]
    assert "<rootDir>/../test/support/test-env.ts" in setup_files


@pytest.mark.parametrize("path", TOOLED_PACKAGE_JSONS, ids=TOOLED_IDS)
def test_when_package_read_lint_tooling_is_pinned_exactly(path):
    """The lint and format tools are present and pinned to an exact version.

    Validates the devDependencies of project_initializer/templates-{api,supabase,entra}-nestjs/api/package.json.
    """
    dev = _load_json(path)["devDependencies"]
    for name in (
        "eslint",
        "typescript-eslint",
        "@eslint/js",
        "eslint-config-prettier",
        "prettier",
    ):
        assert name in dev, f"{name} missing from devDependencies"
        assert not dev[name].startswith(("^", "~")), f"{name} must be pinned exactly"
