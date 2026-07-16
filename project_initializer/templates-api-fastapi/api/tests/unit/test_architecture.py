"""Architecture-fitness test — enforces the hexagonal dependency rule.

Parses every module in the inner layers with the stdlib ``ast`` and asserts the
import boundaries hold, so a future edit that reaches "outward" (domain importing
infrastructure, application importing FastAPI, ...) fails the build instead of
silently eroding the architecture. Dependency-free by design (``ast`` + ``pathlib``).

Rule:
- ``app/domain`` imports none of: app.application, app.infrastructure, app.api,
  fastapi, sqlalchemy, pydantic_settings.
- ``app/application`` imports none of: app.infrastructure, app.api, fastapi.
"""

import ast
from pathlib import Path

import pytest

# tests/unit/ -> tests/ -> api/ -> api/app
_APP_ROOT = Path(__file__).resolve().parent.parent.parent / "app"


def _imported_modules(path: Path) -> set[str]:
    """Return the set of module names imported by a Python file (via AST)."""
    modules: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
    return modules


def _violations(layer: str, forbidden: tuple[str, ...]) -> list[str]:
    """Return 'file -> forbidden_module' strings for every boundary breach."""
    breaches: list[str] = []
    layer_root = _APP_ROOT / layer
    for path in layer_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for module in _imported_modules(path):
            if any(module == f or module.startswith(f + ".") for f in forbidden):
                rel = path.relative_to(_APP_ROOT)
                breaches.append(f"{rel} imports {module}")
    return breaches


@pytest.mark.unit
def test_domain_layer_has_no_outward_imports():
    """domain/ must not import application, infrastructure, api, or web frameworks."""
    breaches = _violations(
        "domain",
        (
            "app.application",
            "app.infrastructure",
            "app.api",
            "fastapi",
            "sqlalchemy",
            "pydantic_settings",
        ),
    )
    assert breaches == [], "Domain boundary violated:\n" + "\n".join(breaches)


@pytest.mark.unit
def test_application_layer_does_not_import_infrastructure_or_api():
    """application/ must depend on domain only — not infrastructure, api, or FastAPI."""
    breaches = _violations(
        "application",
        ("app.infrastructure", "app.api", "fastapi"),
    )
    assert breaches == [], "Application boundary violated:\n" + "\n".join(breaches)
