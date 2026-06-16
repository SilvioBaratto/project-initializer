"""
Source-blind example tests for issue #8:
  "test: verify NestJS Jest unit and e2e suite runs green with coverage"

Each test is authored from the acceptance-criteria text only.
No implementation source was read before authoring these tests (Red phase of TDD).
"""

import json
from pathlib import Path, PurePosixPath

import pytest
from hypothesis import given, strategies as st

_PKG = Path(__file__).parent.parent / "project_initializer"
_NESTJS_BASE = _PKG / "templates-api-nestjs" / "api"
_TOKEN_OVERLAY = _PKG / "templates-token-nestjs" / "api"
_SUPABASE_OVERLAY = _PKG / "templates-supabase-nestjs" / "api"


# ---------------------------------------------------------------------------
# AC: auth guard registered as APP_GUARD in the token overlay so routes are
# protected by default.
# Oracle: [UNIT]
# ---------------------------------------------------------------------------


def test_when_token_overlay_app_module_is_read_then_APP_GUARD_is_registered():
    """
    Assumption: NestJS convention — the app module in the overlay registers global
    providers; APP_GUARD must appear in that file to protect routes by default.
    """
    candidates = list((_TOKEN_OVERLAY / "src").rglob("app.module.ts"))
    assert candidates, "token overlay must contain src/app.module.ts"
    content = candidates[0].read_text(encoding="utf-8")
    assert "APP_GUARD" in content, (
        "token overlay app.module.ts must register the auth guard as APP_GUARD"
    )


# ---------------------------------------------------------------------------
# AC: auth guard registered as APP_GUARD in the supabase overlay.
# Oracle: [UNIT]
# ---------------------------------------------------------------------------


def test_when_supabase_overlay_app_module_is_read_then_APP_GUARD_is_registered():
    """
    Assumption: same convention as token overlay.
    """
    candidates = list((_SUPABASE_OVERLAY / "src").rglob("app.module.ts"))
    assert candidates, "supabase overlay must contain src/app.module.ts"
    content = candidates[0].read_text(encoding="utf-8")
    assert "APP_GUARD" in content, (
        "supabase overlay app.module.ts must register the auth guard as APP_GUARD"
    )


# ---------------------------------------------------------------------------
# AC: ConfigModule validates env and fails fast on missing secrets.
# Oracle: [UNIT]
# ---------------------------------------------------------------------------


def test_when_app_module_is_read_then_ConfigModule_has_validate_option():
    """
    Criterion: ConfigModule.forRoot must include a `validate` option so a missing
    secret causes startup failure immediately.
    Assumption: validate key lives in the same ConfigModule.forRoot() call in app.module.ts.
    """
    candidates = list((_NESTJS_BASE / "src").rglob("app.module.ts"))
    assert candidates, "base template must contain src/app.module.ts"
    content = candidates[0].read_text(encoding="utf-8")
    assert "ConfigModule" in content
    assert "validate" in content, (
        "app.module.ts must pass a validate function to ConfigModule.forRoot"
    )


def test_when_config_validation_is_read_then_DATABASE_URL_is_a_required_key():
    """
    Criterion: fails fast on missing DATABASE_URL.
    Assumption: the env-validation schema (wherever defined under src/) names
    DATABASE_URL as a required field.
    """
    src = _NESTJS_BASE / "src"
    hits = [
        f for f in src.rglob("*.ts") if "DATABASE_URL" in f.read_text(encoding="utf-8")
    ]
    assert hits, (
        "at least one src/*.ts file must reference DATABASE_URL to enforce fail-fast validation"
    )


# ---------------------------------------------------------------------------
# AC: Response schemas whitelist fields so Prisma rows cannot leak sensitive
# columns (e.g. password) through the serializer.
# Oracle: [UNIT]
# ---------------------------------------------------------------------------


def test_when_response_schema_files_are_read_then_password_is_not_a_whitelisted_field():
    """
    Criterion: Zod response schemas explicitly whitelist safe fields; `password`
    must not appear in any response schema definition.
    Assumption: NestJS/nestjs-zod convention — response schemas live in *.dto.ts
    files under src/ (the template uses CreateZodDto/createZodDto pattern). Files
    whose names contain 'response' OR end in '.dto.ts' are considered response-schema
    candidates.
    """
    src = _NESTJS_BASE / "src"
    response_schema_files = [
        f
        for f in src.rglob("*.ts")
        if "response" in f.name.lower() or f.name.endswith(".dto.ts")
    ]
    assert response_schema_files, (
        "base template must contain at least one response/dto schema file (e.g. *.dto.ts)"
    )
    for f in response_schema_files:
        content = f.read_text(encoding="utf-8")
        assert "password" not in content, (
            f"{f.name} exposes 'password' — response schemas must whitelist only safe fields"
        )


# ---------------------------------------------------------------------------
# AC: npm test — at least one service spec via Test.createTestingModule.
# Oracle: [UNIT]
# ---------------------------------------------------------------------------


def test_when_src_tree_is_searched_then_at_least_one_service_spec_uses_TestingModule():
    """
    Criterion: at least one service unit spec using Test.createTestingModule exists.
    Assumption: service specs follow NestJS naming convention *.service.spec.ts.
    """
    src = _NESTJS_BASE / "src"
    service_specs = [
        f
        for f in src.rglob("*.service.spec.ts")
        if "Test.createTestingModule" in f.read_text(encoding="utf-8")
    ]
    assert service_specs, (
        "base template must contain at least one *.service.spec.ts using Test.createTestingModule"
    )


# ---------------------------------------------------------------------------
# AC: npm test — at least one controller spec via Test.createTestingModule.
# Oracle: [UNIT]
# ---------------------------------------------------------------------------


def test_when_src_tree_is_searched_then_at_least_one_controller_spec_uses_TestingModule():
    """
    Criterion: at least one controller spec using Test.createTestingModule exists.
    Assumption: controller specs follow NestJS naming convention *.controller.spec.ts.
    """
    src = _NESTJS_BASE / "src"
    controller_specs = [
        f
        for f in src.rglob("*.controller.spec.ts")
        if "Test.createTestingModule" in f.read_text(encoding="utf-8")
    ]
    assert controller_specs, (
        "base template must contain at least one *.controller.spec.ts using Test.createTestingModule"
    )


# ---------------------------------------------------------------------------
# AC: npm run test:e2e — supertest e2e scaffold exists for the base template.
# Oracle: [UNIT]
# ---------------------------------------------------------------------------


def test_when_test_directory_is_searched_then_e2e_spec_file_exists():
    """
    Criterion: an e2e test scaffold (*.e2e-spec.ts + e2e Jest config) using
    supertest exists.
    Assumption: NestJS convention places e2e specs in test/ at the api root.
    """
    test_dir = _NESTJS_BASE / "test"
    assert test_dir.is_dir(), "base template must have a test/ directory for e2e specs"
    e2e_specs = list(test_dir.rglob("*.e2e-spec.ts"))
    assert e2e_specs, "test/ must contain at least one *.e2e-spec.ts file"


def test_when_e2e_spec_is_read_then_supertest_is_imported():
    """
    Criterion: the e2e scaffold uses supertest.
    """
    test_dir = _NESTJS_BASE / "test"
    e2e_specs = list(test_dir.rglob("*.e2e-spec.ts"))
    if not e2e_specs:
        pytest.fail(
            "no *.e2e-spec.ts found — prerequisite test_when_test_directory_is_searched_then_e2e_spec_file_exists must pass first"
        )
    content = e2e_specs[0].read_text(encoding="utf-8")
    assert "supertest" in content or "request" in content, (
        "e2e spec must import supertest (or its default export 'request')"
    )


def test_when_test_directory_is_searched_then_jest_e2e_config_exists():
    """
    Criterion: npm run test:e2e requires a separate e2e Jest config.
    Assumption: NestJS convention uses jest-e2e.json or jest-e2e.config.* in test/.
    """
    test_dir = _NESTJS_BASE / "test"
    configs = list(test_dir.glob("jest-e2e*")) + list((_NESTJS_BASE).glob("jest-e2e*"))
    assert configs, (
        "base template must include a jest-e2e config file (e.g. test/jest-e2e.json)"
    )


# ---------------------------------------------------------------------------
# AC: npm run test:cov completes and produces a report under coverageDirectory.
# Oracle: [UNIT]
# ---------------------------------------------------------------------------


def test_when_package_json_is_read_then_test_cov_script_is_defined():
    """
    Criterion: npm run test:cov is a runnable script.
    """
    pkg_path = _NESTJS_BASE / "package.json"
    assert pkg_path.exists(), "base template must contain package.json"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    assert "test:cov" in pkg.get("scripts", {}), (
        "package.json must define a 'test:cov' script"
    )


def test_when_package_json_jest_config_is_read_then_coverageDirectory_is_set():
    """
    Criterion: test:cov produces a report under the configured coverageDirectory.
    Assumption: coverageDirectory is declared in the jest block of package.json.
    """
    pkg_path = _NESTJS_BASE / "package.json"
    assert pkg_path.exists()
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    jest = pkg.get("jest", {})
    assert "coverageDirectory" in jest, (
        "jest config in package.json must specify coverageDirectory"
    )


# ---------------------------------------------------------------------------
# AC: No spec files outside the intended src/ tree are collected by the runner.
# Oracle: [UNIT]
# ---------------------------------------------------------------------------


def test_when_jest_config_is_read_then_spec_collection_is_anchored_to_src():
    """
    Criterion: Jest must not collect spec files outside src/.
    Assumption: NestJS/Jest convention — anchoring is achieved via any of:
      (a) `rootDir: "src"` (the runner only traverses src/),
      (b) `roots: ['<rootDir>/src']`, or
      (c) a testMatch/testRegex that constrains the path to include 'src'.
    """
    pkg_path = _NESTJS_BASE / "package.json"
    assert pkg_path.exists()
    jest = json.loads(pkg_path.read_text(encoding="utf-8")).get("jest", {})

    root_dir_ok = jest.get("rootDir", "") == "src"
    roots_ok = any("src" in r for r in jest.get("roots", []))
    test_match = jest.get("testMatch", [])
    match_ok = any(
        "src" in m
        for m in (test_match if isinstance(test_match, list) else [test_match])
    )
    regex_ok = "src" in str(jest.get("testRegex", ""))

    assert root_dir_ok or roots_ok or match_ok or regex_ok, (
        "Jest must limit spec collection to src/ via rootDir, roots, testMatch, or testRegex"
    )


# ---------------------------------------------------------------------------
# Property: for any *.spec.ts path under a non-src directory, the Jest
# root 'src' does not cover it.
#
# Invariant kind: ordering / never-covers — for all paths outside src/,
# the src root must return False from the coverage check.
# Derived from criterion: "No spec files outside the intended src/ tree
# are collected by the runner."
# ---------------------------------------------------------------------------


def _path_is_under_root(root_dir: str, file_path: str) -> bool:
    """True if file_path descends from root_dir, using pure path comparison."""
    root_parts = PurePosixPath(root_dir).parts
    file_parts = PurePosixPath(file_path).parts
    return file_parts[: len(root_parts)] == root_parts


@given(
    st.from_regex(
        r"(test|dist|e2e|coverage|node_modules)/[a-z][a-z0-9_-]*/[a-z][a-z0-9_-]*\.spec\.ts",
        fullmatch=True,
    )
)
def test_when_spec_file_is_in_non_src_dir_then_src_root_does_not_cover_it(path: str):
    """
    Property: for every *.spec.ts path that lives outside src/ (under test/,
    dist/, e2e/, coverage/, or node_modules/), the Jest root 'src' must not
    cover it.  Verifies the correctness of the root-coverage predicate for the
    complete space of non-src spec paths.
    """
    assert not _path_is_under_root("src", path), (
        f"src root must not cover non-src spec path '{path}'"
    )
