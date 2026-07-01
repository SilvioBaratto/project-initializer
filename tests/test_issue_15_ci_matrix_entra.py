"""Source-blind tests for issue #15 — CI matrix entra rows.

Criteria covered (from the acceptance criteria text only):
  - The matrix includes a `fastapi-entra` row with the exact key/value set specified.
  - The matrix includes a `nestjs-entra` row with the exact key/value set specified.
  - Existing tests/test_ci_workflow_scope.py assertions are not broken by the two new rows.
"""

import re
from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parent.parent
    / ".github"
    / "workflows"
    / "test-package.yml"
)


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _matrix_entries() -> list[dict]:
    """Parse every ``include:`` entry from the matrix block into a dict."""
    block = _text().split("include:", 1)[1].split("\n    name:", 1)[0]
    entries = []
    for variant, rest in re.findall(
        r'- variant:\s*"([^"]+)"(.*?)(?=\n\s*- variant:|\Z)', block, re.S
    ):
        flags_m = re.search(r'flags:\s*"([^"]*)"', rest)
        scope_m = re.search(r'scope:\s*"?(\w+)"?', rest)
        install_m = re.search(r'install_cmd:\s*"([^"]*)"', rest)
        baml_m = re.search(r'baml_cmd:\s*"([^"]*)"', rest)
        entries.append(
            {
                "variant": variant,
                "flags": flags_m.group(1) if flags_m else None,
                "scope": scope_m.group(1) if scope_m else None,
                "install_cmd": install_m.group(1) if install_m else None,
                "baml_cmd": baml_m.group(1) if baml_m else None,
            }
        )
    return entries


def _entry_for(variant: str) -> dict | None:
    return next((e for e in _matrix_entries() if e["variant"] == variant), None)


# ---------------------------------------------------------------------------
# fastapi-entra row (criterion: matrix includes a fastapi-entra row with
# flags "--fastapi --auth entra", scope "fullstack",
# install_cmd "pip install baml-py", baml_cmd "baml-cli generate")
# ---------------------------------------------------------------------------


def test_when_matrix_read_fastapi_entra_row_is_present():
    """A row with variant == 'fastapi-entra' must appear in the matrix."""
    assert _entry_for("fastapi-entra") is not None


def test_when_fastapi_entra_row_flags_are_fastapi_and_auth_entra():
    entry = _entry_for("fastapi-entra")
    assert entry is not None, "fastapi-entra row missing"
    assert entry["flags"] == "--fastapi --auth entra"


def test_when_fastapi_entra_row_scope_is_fullstack():
    entry = _entry_for("fastapi-entra")
    assert entry is not None, "fastapi-entra row missing"
    assert entry["scope"] == "fullstack"


def test_when_fastapi_entra_row_install_cmd_is_pip_install_baml_py():
    entry = _entry_for("fastapi-entra")
    assert entry is not None, "fastapi-entra row missing"
    assert entry["install_cmd"] == "pip install baml-py"


def test_when_fastapi_entra_row_baml_cmd_is_baml_cli_generate():
    entry = _entry_for("fastapi-entra")
    assert entry is not None, "fastapi-entra row missing"
    assert entry["baml_cmd"] == "baml-cli generate"


# ---------------------------------------------------------------------------
# nestjs-entra row (criterion: matrix includes a nestjs-entra row with
# flags "--nestjs --auth entra", scope "fullstack",
# install_cmd "npm install --prefix /tmp/test-project/api",
# baml_cmd "npx baml-cli generate")
# ---------------------------------------------------------------------------


def test_when_matrix_read_nestjs_entra_row_is_present():
    """A row with variant == 'nestjs-entra' must appear in the matrix."""
    assert _entry_for("nestjs-entra") is not None


def test_when_nestjs_entra_row_flags_are_nestjs_and_auth_entra():
    entry = _entry_for("nestjs-entra")
    assert entry is not None, "nestjs-entra row missing"
    assert entry["flags"] == "--nestjs --auth entra"


def test_when_nestjs_entra_row_scope_is_fullstack():
    entry = _entry_for("nestjs-entra")
    assert entry is not None, "nestjs-entra row missing"
    assert entry["scope"] == "fullstack"


def test_when_nestjs_entra_row_install_cmd_is_npm_install():
    entry = _entry_for("nestjs-entra")
    assert entry is not None, "nestjs-entra row missing"
    assert entry["install_cmd"] == "npm install --prefix /tmp/test-project/api"


def test_when_nestjs_entra_row_baml_cmd_is_npx_baml_cli_generate():
    entry = _entry_for("nestjs-entra")
    assert entry is not None, "nestjs-entra row missing"
    assert entry["baml_cmd"] == "npx baml-cli generate"


# ---------------------------------------------------------------------------
# Regression: existing test_ci_workflow_scope assertions still hold with the
# two new rows present (criterion 9 — "existing test still passes").
# ---------------------------------------------------------------------------


def test_when_matrix_has_entra_rows_every_entry_still_has_a_scope():
    """Adding entra rows must not introduce a scope-less matrix entry."""
    assert all(e["scope"] for e in _matrix_entries())


def test_when_matrix_has_entra_rows_all_three_scopes_are_still_covered():
    scopes = {e["scope"] for e in _matrix_entries()}
    assert {"fullstack", "api", "frontend"} <= scopes


def test_when_matrix_has_entra_rows_fastapi_entra_is_fullstack_not_api_or_frontend():
    """Entra rows must be fullstack — they must not dilute api/frontend coverage checks."""
    entry = _entry_for("fastapi-entra")
    assert entry is not None
    assert entry["scope"] not in ("api", "frontend")


def test_when_matrix_has_entra_rows_nestjs_entra_is_fullstack_not_api_or_frontend():
    entry = _entry_for("nestjs-entra")
    assert entry is not None
    assert entry["scope"] not in ("api", "frontend")
