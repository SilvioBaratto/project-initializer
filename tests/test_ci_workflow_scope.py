"""Guards for scope coverage in the CI workflow (#20).

Parses ``.github/workflows/test-package.yml`` (no PyYAML dependency — the repo
avoids it) and asserts the matrix exercises ``--scope api`` and
``--scope frontend`` and that scope-specific steps are gated so single-half
jobs do not fail on the missing half.
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
    """Return each ``include:`` entry as {variant, flags, scope}."""
    block = _text().split("include:", 1)[1].split("\n    name:", 1)[0]
    entries = []
    for variant, rest in re.findall(
        r'- variant:\s*"([^"]+)"(.*?)(?=\n\s*- variant:|\Z)', block, re.S
    ):
        flags = re.search(r'flags:\s*"([^"]*)"', rest)
        scope = re.search(r'scope:\s*"?(\w+)"?', rest)
        entries.append(
            {
                "variant": variant,
                "flags": flags.group(1) if flags else None,
                "scope": scope.group(1) if scope else None,
            }
        )
    return entries


def _step_guards() -> dict[str, str]:
    """Map step name -> its ``if:`` guard (or '' when ungated)."""
    steps_block = _text().split("\n    steps:", 1)[1]
    guards = {}
    for chunk in re.split(r"\n      - name:", steps_block):
        chunk = chunk.strip()
        if not chunk:
            continue
        name = chunk.splitlines()[0].strip().strip('"')
        guard = re.search(r"\n?\s*if:\s*(.+)", chunk)
        guards[name] = guard.group(1).strip() if guard else ""
    return guards


def test_when_matrix_read_every_entry_has_a_scope():
    assert all(e["scope"] for e in _matrix_entries())


def test_when_matrix_read_all_three_scopes_are_covered():
    scopes = {e["scope"] for e in _matrix_entries()}
    assert {"fullstack", "api", "frontend"} <= scopes


def test_when_matrix_read_api_scope_covers_both_frameworks():
    api_flags = [e["flags"] for e in _matrix_entries() if e["scope"] == "api"]
    assert any("--fastapi" in f for f in api_flags)
    assert any("--nestjs" in f for f in api_flags)
    assert all("--scope api" in f for f in api_flags)


def test_when_frontend_scope_entry_passes_no_framework_or_auth_flags():
    fe = [e for e in _matrix_entries() if e["scope"] == "frontend"]
    assert fe, "expected at least one --scope frontend entry"
    for entry in fe:
        flags = entry["flags"]
        assert "--scope frontend" in flags
        assert "--fastapi" not in flags
        assert "--nestjs" not in flags
        assert "--auth" not in flags


def test_when_workflow_read_fail_fast_is_disabled():
    assert "fail-fast: false" in _text()


def test_when_frontend_only_steps_are_gated_against_api_scope():
    guards = _step_guards()
    for step in ("Install frontend dependencies", "Build Angular frontend"):
        assert guards.get(step) == "matrix.scope != 'api'", step


def test_when_api_only_steps_are_gated_against_frontend_scope():
    guards = _step_guards()
    for step in ("Install API dependencies", "Generate BAML client"):
        assert guards.get(step) == "matrix.scope != 'frontend'", step


def test_when_verify_steps_are_split_and_gated_per_half():
    guards = _step_guards()
    api_verify = [
        n
        for n, g in guards.items()
        if "scope != 'frontend'" in g and "erif" in n.lower()
    ]
    fe_verify = [
        n for n, g in guards.items() if "scope != 'api'" in g and "erif" in n.lower()
    ]
    assert api_verify, "expected a gated API verify step"
    assert fe_verify, "expected a gated frontend verify step"
