"""Architecture-fitness tests: the hexagonal dependency rule.

Every module of a layer is parsed with the stdlib ``ast`` and its imports are
compared with what the layer may depend on, so an edit that reaches outward
(the domain importing SQLAlchemy, the application importing FastAPI, an endpoint
building a repository) fails the build. Relative imports are resolved to
absolute names first; otherwise ``from ..infrastructure import x`` would slip
past a check that only reads absolute module names.

The inner layers use an allowlist, not a denylist: a denylist is silent about
every package nobody thought to name (an HTTP client, a JWT or password library,
a database driver), while an allowlist fails on the first third-party import.

Rules:

- ``app/domain`` imports the standard library and ``app.domain`` only.
- ``app/application`` imports the standard library, ``app.domain`` and
  ``app.application`` only.
- Neither inner layer calls ``importlib.import_module`` or ``__import__``,
  because a dynamic import hides a dependency from this scan.
- ``app/infrastructure`` never imports ``app.api`` or ``app.main``.
- ``app/api`` never builds an adapter: it does not import repositories, ORM
  models or ``get_db``. ``deps.py`` and ``auth_deps.py`` are the composition
  roots that wire adapters to the application layer, so they are exempt.
"""

import ast
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

APP_PACKAGE = "app"
APP_ROOT = Path(__file__).resolve().parents[2] / APP_PACKAGE

DYNAMIC_IMPORT_NAMES = frozenset({"__import__", "import_module"})
PROBE_PACKAGE = "nested"
PROBE_FILE = "probe.py"


@dataclass(frozen=True)
class LayerRule:
    """Import boundary of one directory below ``app/``.

    Attributes:
        root: Directory, relative to ``app/``, the rule applies to.
        allowed: When set, the only modules the code may import besides the
            standard library, as dotted prefixes. ``None`` allows everything
            that ``forbidden`` does not name.
        forbidden: Dotted prefixes that must never be imported.
        exempt: Files, relative to ``app/``, that are composition roots and are
            not checked.
        bans_dynamic_imports: Whether ``importlib.import_module`` and
            ``__import__`` calls count as breaches.
    """

    root: str
    allowed: tuple[str, ...] | None = None
    forbidden: tuple[str, ...] = ()
    exempt: tuple[str, ...] = ()
    bans_dynamic_imports: bool = False


LAYER_RULES = (
    LayerRule("domain", allowed=("app.domain",), bans_dynamic_imports=True),
    LayerRule(
        "application",
        allowed=("app.application", "app.domain"),
        bans_dynamic_imports=True,
    ),
    LayerRule("infrastructure", forbidden=("app.api", "app.main")),
    LayerRule(
        "api",
        forbidden=(
            "app.infrastructure.repositories",
            "app.infrastructure.orm",
            "app.infrastructure.database.get_db",
        ),
        exempt=("api/deps.py", "api/auth_deps.py"),
    ),
)
RULE_IDS = [rule.root for rule in LAYER_RULES]
EXEMPTING_RULES = [rule for rule in LAYER_RULES if rule.exempt]
DOMAIN_RULE, APPLICATION_RULE, INFRASTRUCTURE_RULE, API_RULE = LAYER_RULES
INNER_RULES = [DOMAIN_RULE, APPLICATION_RULE]
INNER_RULE_IDS = [rule.root for rule in INNER_RULES]


def package_of(path: Path, app_root: Path) -> str:
    """Return the dotted package that relative imports in ``path`` start from.

    Args:
        path: A Python file below ``app_root``.
        app_root: The directory of the top-level ``app`` package.

    Returns:
        The package of the module; for an ``__init__.py`` that is the package
        it initialises, for any other file the package that contains it.
    """
    relative_dir = path.relative_to(app_root.parent).parent
    return ".".join(relative_dir.parts)


def imported_modules(path: Path, app_root: Path) -> set[str]:
    """Collect every module a file imports, as absolute dotted names.

    A ``from x import y`` statement yields ``x`` and ``x.y``, because ``y`` may
    itself be a module (``from app import infrastructure``).

    Args:
        path: Python file to parse.
        app_root: The directory of the top-level ``app`` package.

    Returns:
        Absolute module names, with relative imports resolved.
    """
    package = package_of(path, app_root)
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level + (node.module or "")
            base = (
                importlib.util.resolve_name(prefix, package) if node.level else prefix
            )
            modules.add(base)
            modules.update(f"{base}.{alias.name}" for alias in node.names)
    return modules


def called_name(call: ast.Call) -> str | None:
    """Return the name a call invokes: ``f`` for ``f()`` and ``g`` for ``m.g()``."""
    function = call.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return None


def dynamic_import_calls(path: Path) -> list[str]:
    """Name every call that imports a module chosen at runtime.

    Args:
        path: Python file to parse.

    Returns:
        The called names (``import_module``, ``__import__``), once per call,
        whether spelled ``importlib.import_module(...)`` or imported bare.
    """
    calls = (
        node
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
    )
    return sorted(
        name for name in map(called_name, calls) if name in DYNAMIC_IMPORT_NAMES
    )


def is_under(module: str, prefix: str) -> bool:
    """Whether ``module`` is ``prefix`` or lives below it (not a lookalike name)."""
    return module == prefix or module.startswith(f"{prefix}.")


def is_breach(module: str, rule: LayerRule) -> bool:
    """Whether importing ``module`` crosses the boundary described by ``rule``.

    A package that merely contains an allowed one (``app`` for ``app.domain``)
    is not a breach: importing it runs no code of its own, and
    ``from app import domain`` must stay legal.
    """
    if any(is_under(module, banned) for banned in rule.forbidden):
        return True
    if rule.allowed is None:
        return False
    if module.partition(".")[0] in sys.stdlib_module_names:
        return False
    return not any(
        is_under(module, prefix) or is_under(prefix, module) for prefix in rule.allowed
    )


def scan_file(path: Path, app_root: Path, rule: LayerRule) -> list[str]:
    """Return the breaches of ``rule`` in one file, as ``"<file> <detail>"`` strings."""
    relative = path.relative_to(app_root).as_posix()
    breaches = [
        f"{relative} imports {module}"
        for module in sorted(imported_modules(path, app_root))
        if is_breach(module, rule)
    ]
    if rule.bans_dynamic_imports:
        breaches.extend(
            f"{relative} calls {name}()" for name in dynamic_import_calls(path)
        )
    return breaches


def scan_layer(rule: LayerRule, app_root: Path) -> tuple[list[str], int]:
    """Check every module below the rule's root against the rule.

    Args:
        rule: Boundary to enforce.
        app_root: The directory of the top-level ``app`` package.

    Returns:
        The breaches as ``"<file> imports <module>"`` or
        ``"<file> calls <name>()"`` strings, and how many files were scanned,
        so an empty layer cannot pass by accident.
    """
    files = sorted((app_root / rule.root).rglob("*.py"))
    breaches: list[str] = []
    for path in files:
        if path.relative_to(app_root).as_posix() not in rule.exempt:
            breaches.extend(scan_file(path, app_root, rule))
    return breaches, len(files)


def write_module(tmp_path: Path, relative_path: str, source: str) -> Path:
    """Create ``app/<relative_path>`` in a scratch tree and return its ``app/``."""
    module = tmp_path / APP_PACKAGE / relative_path
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(source, encoding="utf-8")
    return tmp_path / APP_PACKAGE


def probe_breaches(tmp_path: Path, rule: LayerRule, source: str) -> list[str]:
    """Scan one synthetic module of the rule's layer and return its breaches.

    The module sits in a nested package, so a three-dot relative import reaches
    ``app`` itself, as it does from ``app/domain/entities``.
    """
    app_root = write_module(
        tmp_path, f"{rule.root}/{PROBE_PACKAGE}/{PROBE_FILE}", source + "\n"
    )
    breaches, scanned = scan_layer(rule, app_root)
    assert scanned == 1
    return breaches


def probe_breach(rule: LayerRule, detail: str) -> str:
    """Spell the breach the scanner reports for the probe module of ``rule``."""
    return f"{rule.root}/{PROBE_PACKAGE}/{PROBE_FILE} {detail}"


@pytest.mark.unit
@pytest.mark.parametrize("rule", LAYER_RULES, ids=RULE_IDS)
def test_when_layer_is_scanned_then_its_directory_holds_python_files(rule):
    """when a layer is scanned, its directory exists and contributes files.

    A renamed or moved layer would otherwise be checked against nothing and
    pass silently.

    Validates tests.unit.test_architecture.scan_layer().
    """
    layer_root = APP_ROOT / rule.root

    assert layer_root.is_dir(), f"{rule.root} layer directory is missing"
    _, scanned = scan_layer(rule, APP_ROOT)
    assert scanned > 0, f"no Python file found under {layer_root}"


@pytest.mark.unit
@pytest.mark.parametrize(
    "rule", EXEMPTING_RULES, ids=[rule.root for rule in EXEMPTING_RULES]
)
def test_when_a_rule_exempts_files_then_each_of_them_exists(rule):
    """when a rule exempts composition roots, every exempt path is a real file.

    A renamed composition root would otherwise leave a stale exemption behind.

    Validates tests.unit.test_architecture.LAYER_RULES.
    """
    missing = [path for path in rule.exempt if not (APP_ROOT / path).is_file()]

    assert missing == []


@pytest.mark.unit
@pytest.mark.parametrize("rule", LAYER_RULES, ids=RULE_IDS)
def test_when_layer_imports_are_checked_then_no_boundary_is_crossed(rule):
    """when every module of a layer is parsed, none crosses its boundary.

    Validates app.domain, app.application, app.infrastructure and app.api imports.
    """
    breaches, _ = scan_layer(rule, APP_ROOT)

    assert breaches == [], f"{rule.root} boundary violated:\n" + "\n".join(breaches)


# Packages the former denylist did not name, plus the framework ones it did.
THIRD_PARTY_PACKAGES = (
    "fastapi",
    "starlette",
    "sqlalchemy",
    "pydantic",
    "pydantic_settings",
    "httpx",
    "httpx2",
    "jose",
    "jwt",
    "bcrypt",
    "alembic",
    "psycopg2",
    "asyncpg",
    "supabase",
    "sqlalchemy_like_name",
)
GET_DB_BREACHES = [
    "imports app.infrastructure.database",
    "imports app.infrastructure.database.get_db",
]
OFFENDING_INNER_IMPORTS = [
    pytest.param(
        "from app.infrastructure.database import get_db",
        GET_DB_BREACHES,
        id="absolute-from",
    ),
    pytest.param("import app.api.deps", ["imports app.api.deps"], id="absolute-import"),
    pytest.param("import app.main", ["imports app.main"], id="application-entry-point"),
    pytest.param(
        "import app.domain_extras",
        ["imports app.domain_extras"],
        id="lookalike-of-an-allowed-package",
    ),
    pytest.param(
        "from app import api", ["imports app.api"], id="package-attribute-is-a-module"
    ),
    pytest.param(
        "from ...infrastructure.database import get_db",
        GET_DB_BREACHES,
        id="relative-from",
    ),
    pytest.param(
        "from ... import infrastructure",
        ["imports app.infrastructure"],
        id="relative-bare-package",
    ),
    pytest.param(
        "from sqlalchemy.orm import Session",
        ["imports sqlalchemy.orm", "imports sqlalchemy.orm.Session"],
        id="from-import-of-a-class",
    ),
    *(
        pytest.param(f"import {package}", [f"imports {package}"], id=package)
        for package in THIRD_PARTY_PACKAGES
    ),
]


@pytest.mark.unit
@pytest.mark.parametrize(("source", "details"), OFFENDING_INNER_IMPORTS)
@pytest.mark.parametrize("rule", INNER_RULES, ids=INNER_RULE_IDS)
def test_when_inner_layer_module_crosses_a_boundary_then_the_checker_names_the_module(
    tmp_path, rule, source, details
):
    """when an inner-layer module imports outside its allowlist, each module is named.

    Covers absolute and relative spellings and packages the former denylist
    never named, so neither an import style nor a new library bypasses the guard.

    Validates tests.unit.test_architecture.scan_layer().
    """
    breaches = probe_breaches(tmp_path, rule, source)

    assert breaches == [probe_breach(rule, detail) for detail in details]


API_OFFENDING_IMPORTS = [
    pytest.param(
        "from app.infrastructure.repositories.item import SqlAlchemyItemRepository",
        [
            "imports app.infrastructure.repositories.item",
            "imports app.infrastructure.repositories.item.SqlAlchemyItemRepository",
        ],
        id="repository",
    ),
    pytest.param(
        "from app.infrastructure import orm",
        ["imports app.infrastructure.orm"],
        id="orm-package",
    ),
    pytest.param(
        "from app.infrastructure.orm.item import ItemModel",
        [
            "imports app.infrastructure.orm.item",
            "imports app.infrastructure.orm.item.ItemModel",
        ],
        id="orm-model",
    ),
    pytest.param(
        "from app.infrastructure.database import get_db",
        ["imports app.infrastructure.database.get_db"],
        id="session-factory",
    ),
]


@pytest.mark.unit
@pytest.mark.parametrize(("source", "details"), API_OFFENDING_IMPORTS)
def test_when_api_module_builds_an_adapter_then_the_checker_names_the_module(
    tmp_path, source, details
):
    """when an API module imports a repository, ORM model or get_db, it is reported.

    Validates tests.unit.test_architecture.scan_layer().
    """
    breaches = probe_breaches(tmp_path, API_RULE, source)

    assert breaches == [probe_breach(API_RULE, detail) for detail in details]


INFRASTRUCTURE_OFFENDING_IMPORTS = [
    pytest.param(
        "from app.api import deps",
        ["imports app.api", "imports app.api.deps"],
        id="api",
    ),
    pytest.param("import app.main", ["imports app.main"], id="entry-point"),
]


@pytest.mark.unit
@pytest.mark.parametrize(("source", "details"), INFRASTRUCTURE_OFFENDING_IMPORTS)
def test_when_infrastructure_module_reaches_outward_then_the_checker_names_the_module(
    tmp_path, source, details
):
    """when an infrastructure module imports the API or the entry point, it is reported.

    Validates tests.unit.test_architecture.scan_layer().
    """
    breaches = probe_breaches(tmp_path, INFRASTRUCTURE_RULE, source)

    assert breaches == [probe_breach(INFRASTRUCTURE_RULE, detail) for detail in details]


CLEAN_IMPORTS = [
    pytest.param(
        DOMAIN_RULE, "from app.domain.constants import MAX_OFFSET", id="domain-absolute"
    ),
    pytest.param(
        DOMAIN_RULE, "from ..constants import MAX_OFFSET", id="domain-relative"
    ),
    pytest.param(DOMAIN_RULE, "from . import sibling", id="domain-same-package"),
    pytest.param(DOMAIN_RULE, "from app import domain", id="domain-parent-package"),
    pytest.param(
        DOMAIN_RULE, "from dataclasses import dataclass", id="domain-standard-library"
    ),
    pytest.param(
        DOMAIN_RULE, "from __future__ import annotations", id="domain-future-import"
    ),
    pytest.param(
        APPLICATION_RULE,
        "from app.domain.entities.item import Item",
        id="application-uses-domain",
    ),
    pytest.param(
        APPLICATION_RULE,
        "from app.application.dto.item import ItemDTO",
        id="application-uses-itself",
    ),
    pytest.param(
        INFRASTRUCTURE_RULE,
        "from app.domain.ports.item_repository import ItemRepositoryPort",
        id="infrastructure-implements-a-port",
    ),
    pytest.param(
        INFRASTRUCTURE_RULE,
        "from sqlalchemy.orm import Session",
        id="infrastructure-uses-a-framework",
    ),
    pytest.param(
        INFRASTRUCTURE_RULE,
        "import importlib\nimportlib.import_module('plugin')",
        id="infrastructure-may-import-dynamically",
    ),
    pytest.param(
        API_RULE,
        "from app.application.services.item_service import ItemService",
        id="api-uses-the-application-layer",
    ),
    pytest.param(
        API_RULE,
        "from app.infrastructure.audit import write_audit_log",
        id="api-uses-an-infrastructure-helper",
    ),
    pytest.param(
        API_RULE,
        "from app.infrastructure.database import database_manager",
        id="api-uses-the-database-manager",
    ),
]


@pytest.mark.unit
@pytest.mark.parametrize(("rule", "source"), CLEAN_IMPORTS)
def test_when_module_stays_inside_its_boundary_then_the_checker_is_silent(
    tmp_path, rule, source
):
    """when a synthetic module only imports what its layer allows, nothing is reported.

    Validates tests.unit.test_architecture.scan_layer().
    """
    assert probe_breaches(tmp_path, rule, source) == []


DYNAMIC_IMPORT_SOURCES = [
    pytest.param(
        "import importlib\nimportlib.import_module('x')",
        "import_module",
        id="attribute-call",
    ),
    pytest.param(
        "from importlib import import_module\nimport_module('x')",
        "import_module",
        id="bare-call",
    ),
    pytest.param("__import__('x')", "__import__", id="builtin"),
]


@pytest.mark.unit
@pytest.mark.parametrize(("source", "called"), DYNAMIC_IMPORT_SOURCES)
@pytest.mark.parametrize("rule", INNER_RULES, ids=INNER_RULE_IDS)
def test_when_inner_layer_imports_dynamically_then_the_call_is_reported(
    tmp_path, rule, source, called
):
    """when an inner-layer module imports by a runtime value, the call is reported.

    The standard-library import of ``importlib`` is allowed; the call is what
    hides a dependency from the scan.

    Validates tests.unit.test_architecture.dynamic_import_calls().
    """
    breaches = probe_breaches(tmp_path, rule, source)

    assert breaches == [probe_breach(rule, f"calls {called}()")]


@pytest.mark.unit
def test_when_composition_root_imports_an_adapter_then_only_it_is_skipped(tmp_path):
    """when deps.py and another API module import get_db, only the other is reported.

    Validates tests.unit.test_architecture.scan_layer().
    """
    adapter_import = "from app.infrastructure.database import get_db\n"
    write_module(tmp_path, "api/deps.py", adapter_import)
    app_root = write_module(tmp_path, "api/endpoint.py", adapter_import)

    breaches, scanned = scan_layer(API_RULE, app_root)

    assert scanned == len(list((app_root / "api").glob("*.py")))
    assert breaches == ["api/endpoint.py imports app.infrastructure.database.get_db"]


@pytest.mark.unit
def test_when_package_init_uses_a_relative_import_then_it_resolves_from_its_own_package(
    tmp_path,
):
    """when an __init__.py imports relatively, the base is the package it initialises.

    Validates tests.unit.test_architecture.imported_modules().
    """
    app_root = write_module(
        tmp_path, "infrastructure/__init__.py", "from ..api import deps\n"
    )

    breaches, _ = scan_layer(INFRASTRUCTURE_RULE, app_root)

    assert breaches == [
        "infrastructure/__init__.py imports app.api",
        "infrastructure/__init__.py imports app.api.deps",
    ]
