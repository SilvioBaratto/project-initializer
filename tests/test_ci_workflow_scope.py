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
    """The API dependency install is skipped on the frontend-only matrix entry.

    Validates .github/workflows/test-package.yml "Install API dependencies" step guard.
    """
    guards = _step_guards()
    assert guards.get("Install API dependencies") == "matrix.scope != 'frontend'"


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


_DOCKERFILE = (
    Path(__file__).resolve().parent.parent
    / "project_initializer"
    / "templates-api-fastapi"
    / "api"
    / "Dockerfile"
)
_PYTHON_FLOOR = "3.12"


def _suite_job() -> str:
    """Return the text of the ``test-variant-suites`` job."""
    return _text().split("\n  test-variant-suites:", 1)[1]


def _suite_entries() -> list[dict]:
    """Return each ``include:`` entry of the suites job as {suite, stack, flags, python}."""
    block = _suite_job().split("include:", 1)[1].split("\n    name:", 1)[0]
    entries = []
    for suite, rest in re.findall(
        r'- suite:\s*"([^"]+)"(.*?)(?=\n\s*- suite:|\Z)', block, re.S
    ):
        fields = {
            key: re.search(rf'\n\s*{key}:\s*"([^"]*)"', rest)
            for key in ("stack", "flags", "python")
        }
        entries.append(
            {
                "suite": suite,
                **{key: m.group(1) if m else None for key, m in fields.items()},
            }
        )
    return entries


def test_when_the_workflow_runs_the_api_suite_then_python_floor_and_image_version_are_both_tested():
    """Every FastAPI suite runs on the 3.12 floor and on the Python the image ships.

    The twin entries carry the same flags, so the 3.15 row proves the same scaffold
    on the interpreter of ``python:3.N-slim`` while the floor row keeps guarding
    ``requires-python``. The matrix has no axes: a version exists only where an
    entry carries a ``python`` key, and a step after the scaffolding switches the
    API suite to it, so the CLI itself stays on the floor.

    Validates .github/workflows/test-package.yml test-variant-suites matrix.
    """
    image_python = re.search(
        r"^FROM python:(\d+\.\d+)-slim", _DOCKERFILE.read_text("utf-8"), re.M
    ).group(1)
    assert re.search(
        r"name: Set up Python for the API suite\n\s+if: matrix\.python\n"
        r"\s+uses: actions/setup-python@v\d+\n\s+with:\n"
        r"\s+python-version: \$\{\{ matrix\.python \}\}",
        _suite_job(),
    ), "no step switches the suite to matrix.python when an entry sets it"

    versions_by_flags: dict[str, set[str]] = {}
    for entry in _suite_entries():
        if entry["stack"] == "fastapi":
            versions_by_flags.setdefault(entry["flags"], set()).add(
                entry["python"] or _PYTHON_FLOOR
            )

    assert len(versions_by_flags) == 5, "expected the five FastAPI flavours"
    for flags, versions in versions_by_flags.items():
        assert versions == {_PYTHON_FLOOR, image_python}, flags


def test_when_the_suites_matrix_is_read_then_nestjs_runs_once_and_every_suite_name_is_unique():
    """The matrix has no axes, so a Python entry must be a separate ``include`` row.

    A ``python-version`` axis with an ``exclude`` on the stack would match nothing
    (the stack exists only inside the entries) and run every NestJS suite twice
    under one job name.

    Validates .github/workflows/test-package.yml test-variant-suites matrix.
    """
    entries = _suite_entries()
    names = [e["suite"] for e in entries]

    assert len(names) == len(set(names))
    assert all(e["python"] is None for e in entries if e["stack"] == "nestjs")
    assert "python-version" not in _suite_job().split("include:", 1)[0]
