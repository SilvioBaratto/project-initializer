"""Pins what the frontend dependency upgrade moved: the runtime image, the CI actions and the icon library.

A moving nginx tag would let the runtime stage change nginx branch between two
builds, and an action left on an old major keeps a job on a runtime that GitHub
has retired. ``lucide-angular`` is deprecated and caps its Angular peers at 21,
so the frontends render their icons through ``@lucide/angular`` instead.
"""

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_TEMPLATES = _REPO / "project_initializer"

_FRONTEND_DOCKERFILE = _TEMPLATES / "templates" / "frontend" / "Dockerfile"
_REPO_WORKFLOW = _REPO / ".github" / "workflows" / "test-package.yml"
_TEMPLATE_WORKFLOW = (
    _TEMPLATES / "templates" / ".github" / "workflows" / "test-package.yml"
)
_WORKFLOWS = (_REPO_WORKFLOW, _TEMPLATE_WORKFLOW)

_FRONTEND_LAYERS = tuple(
    _TEMPLATES / layer / "frontend"
    for layer in (
        "templates",
        "templates-token-frontend",
        "templates-supabase-frontend",
        "templates-entra-frontend",
    )
)
# The token layer ships no package.json, so it inherits the base manifest.
_FRONTEND_MANIFESTS = tuple(
    layer / "package.json"
    for layer in _FRONTEND_LAYERS
    if (layer / "package.json").is_file()
)
_FRONTEND_LOCK = _TEMPLATES / "templates" / "frontend" / "package-lock.json"

_FROM_LINE = re.compile(r"^FROM\s+(?P<image>\S+)", re.M)
_PINNED_NGINX = re.compile(r"nginx:\d+\.\d+(\.\d+)?-alpine")
_ACTION_USE = re.compile(r"uses:\s*(?P<action>actions/[\w-]+)@(?P<ref>\S+)")
_EXACT_VERSION = re.compile(r"\d+\.\d+\.\d+")
_OLD_ICON_IMPORT = re.compile(r"""from\s+['"]lucide-angular['"]""")
_SVG_START_TAG = re.compile(r"<svg\b[^>]*>", re.S)
# Each of these is marked @deprecated in the @lucide/angular typings in favour of
# the class named after the icon's current name.
_DEPRECATED_ICON_CLASSES = re.compile(
    r"\bLucide(?:CircleAlert|TriangleAlert|Trash2|Home|CheckCircle|Loader2|Sliders|FunctionSquare)\b"
)


def _repo_relative(path: Path) -> str:
    return str(path.relative_to(_REPO))


def _frontend_sources(*suffixes: str) -> Iterator[Path]:
    """Yield every file under ``src`` of each frontend layer whose suffix is in ``suffixes``."""
    for layer in _FRONTEND_LAYERS:
        for path in sorted((layer / "src").rglob("*")):
            if path.suffix in suffixes:
                yield path


def _action_refs(text: str, action: str) -> list[str]:
    """Return the ref of every ``uses:`` line of ``action``, in file order."""
    return [m["ref"] for m in _ACTION_USE.finditer(text) if m["action"] == action]


@pytest.mark.unit
def test_when_the_frontend_dockerfile_is_read_then_the_runtime_stage_pins_an_nginx_branch():
    """The runtime stage names a stable nginx branch, never the moving tag.

    The tag must carry a version (``nginx:1.30-alpine``), not ``nginx:alpine`` or
    ``latest``: an unpinned tag follows the mainline branch and changes security
    level between two builds of the same template.

    Validates project_initializer/templates/frontend/Dockerfile.
    """
    images = [
        m["image"]
        for m in _FROM_LINE.finditer(_FRONTEND_DOCKERFILE.read_text(encoding="utf-8"))
    ]
    assert len(images) == 2, f"expected a builder and a runtime stage, got {images}"

    runtime_image = images[-1]
    assert _PINNED_NGINX.fullmatch(runtime_image), (
        f"runtime stage must pin an nginx branch, got {runtime_image}"
    )
    assert runtime_image not in {"nginx:alpine", "nginx:latest"}


@pytest.mark.unit
@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=_repo_relative)
@pytest.mark.parametrize("action", ["actions/checkout", "actions/setup-node"])
def test_when_a_workflow_is_read_then_every_use_of_checkout_and_setup_node_is_v7(
    workflow: Path, action: str
):
    """Every ``uses:`` line of actions/checkout and actions/setup-node is on v7.

    Each line is checked, not only the first: the repo workflow checks out twice
    and sets Node up twice, and one stale line keeps a job on the old major.

    Validates .github/workflows/test-package.yml and project_initializer/templates/.github/workflows/test-package.yml.
    """
    refs = _action_refs(workflow.read_text(encoding="utf-8"), action)
    assert refs, f"{_repo_relative(workflow)} no longer uses {action}"
    assert set(refs) == {"v7"}, f"{_repo_relative(workflow)} uses {action}@{refs}"


@pytest.mark.unit
def test_when_the_frontend_manifests_are_read_then_the_deprecated_lucide_package_is_gone():
    """No frontend manifest lists ``lucide-angular``; each pins the same ``@lucide/angular``.

    The pin is exact and shared by the three manifests because the package
    renames icons in minor releases: a range, or two layers on different
    releases, could resolve names that ``icons.ts`` no longer matches. The base
    lock, the only one in the repo, must resolve that same release.

    Validates project_initializer/templates/frontend/package.json, project_initializer/templates-supabase-frontend/frontend/package.json, project_initializer/templates-entra-frontend/frontend/package.json and project_initializer/templates/frontend/package-lock.json.
    """
    assert len(_FRONTEND_MANIFESTS) == 3, [_repo_relative(m) for m in _FRONTEND_MANIFESTS]
    pins = {}
    for manifest in _FRONTEND_MANIFESTS:
        package = json.loads(manifest.read_text(encoding="utf-8"))
        declared = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
        assert "lucide-angular" not in declared, f"{_repo_relative(manifest)} still lists lucide-angular"
        pins[_repo_relative(manifest)] = package.get("dependencies", {}).get("@lucide/angular")

    assert all(pin and _EXACT_VERSION.fullmatch(pin) for pin in pins.values()), pins
    assert len(set(pins.values())) == 1, f"the manifests pin different releases: {pins}"

    packages = json.loads(_FRONTEND_LOCK.read_text(encoding="utf-8"))["packages"]
    assert "node_modules/lucide-angular" not in packages
    assert packages["node_modules/@lucide/angular"]["version"] == next(iter(pins.values()))


@pytest.mark.unit
def test_when_the_frontend_sources_are_read_then_no_file_imports_lucide_angular_or_uses_the_lucide_icon_element():
    """No template, component, spec or stylesheet of a frontend layer uses the old library.

    ``<lucide-icon>`` is an unknown element once ``LucideAngularModule`` is gone,
    and a stylesheet that still selects it silently stops styling the icon.

    Validates the src trees of project_initializer/templates/frontend and of the token, supabase and entra frontend overlays.
    """
    offenders = []
    for path in _frontend_sources(".ts", ".html", ".css", ".scss"):
        text = path.read_text(encoding="utf-8")
        if _OLD_ICON_IMPORT.search(text) or "<lucide-icon" in text:
            offenders.append(_repo_relative(path))
        elif path.suffix in {".css", ".scss"} and re.search(r"\blucide-icon\b", text):
            offenders.append(_repo_relative(path))
    assert offenders == []


def _icon_tags_containing(fragments: tuple[str, ...]) -> list[str]:
    """List every ``<svg lucideIcon>`` start tag, in templates and inline templates, holding one of ``fragments``."""
    return [
        f"{_repo_relative(path)}: {' '.join(tag.split())}"
        for path in _frontend_sources(".html", ".ts")
        for tag in _SVG_START_TAG.findall(path.read_text(encoding="utf-8"))
        if "lucideIcon" in tag and any(fragment in tag for fragment in fragments)
    ]


@pytest.mark.unit
def test_when_an_icon_element_is_read_then_it_carries_no_class_property_binding():
    """No ``<svg lucideIcon>`` element binds ``[class.x]``.

    The icon writes its whole ``class`` attribute from its ``class`` input, so a
    ``[class.x]`` binding, which bypasses that input, is wiped the next time the
    icon re-renders. A static ``class`` or a ``[class]`` binding reaches the input.

    Validates the html templates and inline spec templates of project_initializer/templates/frontend and of the token, supabase and entra frontend overlays.
    """
    assert _icon_tags_containing(("[class.",)) == []


@pytest.mark.unit
def test_when_an_icon_element_is_read_then_it_carries_no_material_list_slot_directive():
    """``matListItemIcon`` and ``matListItemMeta`` sit on a wrapper, never on the icon ``svg``.

    Both directives mark their host with Material's slot classes
    (``mdc-list-item__start``, ``mdc-list-item__end``), which carry the slot's
    size, spacing and color; on the ``svg`` the icon's own ``class`` attribute
    overwrites them.

    Validates the html templates and inline spec templates of project_initializer/templates/frontend and of the token, supabase and entra frontend overlays.
    """
    assert _icon_tags_containing(("matListItemIcon", "matListItemMeta")) == []


@pytest.mark.unit
def test_when_the_frontend_sources_are_read_then_no_file_imports_a_deprecated_icon_class():
    """Icons are imported under their current class names, never a deprecated alias.

    ``LucideCircleAlert``, ``LucideTrash2`` and the like still export, but each is
    marked ``@deprecated`` and can disappear in a later release.

    Validates the TypeScript sources of project_initializer/templates/frontend and of the token, supabase and entra frontend overlays.
    """
    offenders = [
        f"{_repo_relative(path)}: {match}"
        for path in _frontend_sources(".ts")
        for match in _DEPRECATED_ICON_CLASSES.findall(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
