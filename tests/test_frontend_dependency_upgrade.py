"""Pins what the frontend dependency upgrade moved: the runtime image, the CI actions, the icon library and Angular.

A moving nginx tag would let the runtime stage change nginx branch between two
builds, and an action left on an old major keeps a job on a runtime that GitHub
has retired. ``lucide-angular`` is deprecated and caps its Angular peers at 21,
so the frontends render their icons through ``@lucide/angular`` instead.
Angular, Angular Material and the CDK are on 22 and TypeScript on 6.0, the only
minor the Angular 22 compiler accepts; the APIs Angular 22 deprecates, and the
opt-out from its OnPush default, stay out of the templates.
"""

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from project_initializer.docs_generator import (
    generate_frontend_claude,
    generate_root_claude,
)

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
_BASE_MANIFEST = _TEMPLATES / "templates" / "frontend" / "package.json"
_FRONTEND_LOCK = _TEMPLATES / "templates" / "frontend" / "package-lock.json"
_BASE_INDEX_HTML = _TEMPLATES / "templates" / "frontend" / "src" / "index.html"
_REPO_CLAUDE = _REPO / "CLAUDE.md"

_FROM_LINE = re.compile(r"^FROM\s+(?P<image>\S+)", re.M)
_PINNED_NGINX = re.compile(r"nginx:\d+\.\d+(\.\d+)?-alpine")
_ACTION_USE = re.compile(r"uses:\s*(?P<action>actions/[\w-]+)@(?P<ref>\S+)")
# The frontend manifests declare npm ranges, a caret for most packages and a tilde
# where only patch releases may follow (TypeScript, rxjs); the base lock holds the release.
_RANGE_SPECIFIER = re.compile(r"(?P<operator>[\^~])(?P<version>\d+\.\d+\.\d+)")
_OLD_ICON_IMPORT = re.compile(r"""from\s+['"]lucide-angular['"]""")
# A quoted value is consumed whole, so a ">" inside a binding ("n() > 0", "=>") does not
# end the start tag before the attributes that follow it.
_ATTRIBUTE_NAME = r"""[^\s"'=<>/]+"""
_ATTRIBUTE_VALUE = r"""\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+)"""
_ATTRIBUTE = re.compile(rf"\s+(?P<name>{_ATTRIBUTE_NAME})(?:{_ATTRIBUTE_VALUE})?")
_SVG_OPENING = re.compile(r"<svg\b")
_SVG_START_TAG = re.compile(
    rf"<svg\b(?P<attributes>(?:\s+{_ATTRIBUTE_NAME}(?:{_ATTRIBUTE_VALUE})?)*)\s*/?>"
)
_ICON_INPUTS = {"lucideIcon", "[lucideIcon]"}
# Each of these is marked @deprecated in the @lucide/angular typings in favour of
# the class named after the icon's current name.
_DEPRECATED_ICON_CLASSES = re.compile(
    r"\bLucide(?:CircleAlert|TriangleAlert|Trash2|Home|CheckCircle|Loader2|Sliders|FunctionSquare)\b"
)

# Each group is published together and peers on its own members at the exact same
# release (compiler-cli on compiler, Material on CDK), so a group never splits.
_ANGULAR_RELEASE_GROUPS = {
    "framework": (
        "@angular/common",
        "@angular/compiler",
        "@angular/compiler-cli",
        "@angular/core",
        "@angular/forms",
        "@angular/platform-browser",
        "@angular/router",
    ),
    "cli": ("@angular/build", "@angular/cli"),
    "components": ("@angular/cdk", "@angular/material"),
}
_ANGULAR_PACKAGES = tuple(
    name for group in _ANGULAR_RELEASE_GROUPS.values() for name in group
)
# 22.3.0 is the first Material release whose checkbox and radio DOM agrees with
# its own test harness selectors.
_ANGULAR_FLOOR = (22, 3, 0)
_ANGULAR_CEILING = (23, 0, 0)
# 1.77.0 is the release whose class names icons.ts imports.
_LUCIDE_FLOOR = (1, 77, 0)
_LUCIDE_CEILING = (2, 0, 0)
_TYPESCRIPT_RANGE = re.compile(r"~6\.0\.\d+")
_SHARED_SPECIFIERS = (
    *_ANGULAR_PACKAGES,
    "@lucide/angular",
    "typescript",
    "tslib",
    "rxjs",
)
_PEER_COMPARATOR = re.compile(r"(?P<operator>>=|<)(?P<version>\d+(?:\.\d+)*)")
_WITH_FETCH = re.compile(r"\bwithFetch\b")
# Default is the deprecated alias of Eager; both opt a component out of OnPush.
_CHANGE_DETECTION_OPT_OUT = re.compile(r"ChangeDetectionStrategy\.(?:Eager|Default)\b")
# Angular 22.3 removed both checks; ng update still writes a "suppress" entry for each.
_REMOVED_DIAGNOSTICS = ("nullishCoalescingNotNullable", "optionalChainNotNullable")
_BASE_APP, _TOKEN_APP, _SUPABASE_APP, _ENTRA_APP = (
    layer / "src" / "app" for layer in _FRONTEND_LAYERS
)
_ROOT_SERVICES = (
    _BASE_APP / "services" / "theme.ts",
    _BASE_APP / "services" / "window-size-class.ts",
    _BASE_APP / "shared" / "ui" / "toast" / "toast.service.ts",
    _TOKEN_APP / "services" / "auth.ts",
    _SUPABASE_APP / "services" / "auth.ts",
    _ENTRA_APP / "core" / "services" / "auth.service.ts",
)
_PROVIDED_IN_ROOT = re.compile(r"providedIn\s*:\s*['\"]root['\"]")


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
    """No frontend manifest lists ``lucide-angular``; each declares the same ``@lucide/angular`` caret range.

    The range starts at 1.77.0, the release whose class names ``icons.ts``
    imports, and is the same in the three manifests, so every auth mode installs
    from one release line. The base lock, the only one in the repo, must resolve
    a release inside it.

    Validates project_initializer/templates/frontend/package.json, project_initializer/templates-supabase-frontend/frontend/package.json, project_initializer/templates-entra-frontend/frontend/package.json and project_initializer/templates/frontend/package-lock.json.
    """
    assert len(_FRONTEND_MANIFESTS) == 3, [
        _repo_relative(m) for m in _FRONTEND_MANIFESTS
    ]
    specifiers = {}
    for manifest in _FRONTEND_MANIFESTS:
        package = json.loads(manifest.read_text(encoding="utf-8"))
        declared = {
            **package.get("dependencies", {}),
            **package.get("devDependencies", {}),
        }
        assert "lucide-angular" not in declared, (
            f"{_repo_relative(manifest)} still lists lucide-angular"
        )
        specifiers[_repo_relative(manifest)] = package.get("dependencies", {}).get(
            "@lucide/angular"
        )

    assert all(
        _is_caret_range_within(specifier, _LUCIDE_FLOOR, _LUCIDE_CEILING)
        for specifier in specifiers.values()
    ), specifiers
    assert len(set(specifiers.values())) == 1, (
        f"the manifests declare different ranges: {specifiers}"
    )

    packages = json.loads(_FRONTEND_LOCK.read_text(encoding="utf-8"))["packages"]
    assert "node_modules/lucide-angular" not in packages
    assert _in_npm_range(
        packages["node_modules/@lucide/angular"]["version"],
        next(iter(specifiers.values())),
    )


@pytest.mark.unit
def test_when_the_frontend_sources_are_read_then_no_file_imports_lucide_angular_or_uses_the_lucide_icon_element():
    """No template, component, spec or stylesheet of a frontend layer uses the old library.

    ``<lucide-icon>`` is an unknown element once ``LucideAngularModule`` is gone,
    and a stylesheet that still selects it silently stops styling the icon.

    Validates project_initializer/templates/frontend/src, project_initializer/templates-token-frontend/frontend/src, project_initializer/templates-supabase-frontend/frontend/src and project_initializer/templates-entra-frontend/frontend/src.
    """
    offenders = []
    for path in _frontend_sources(".ts", ".html", ".css", ".scss"):
        text = path.read_text(encoding="utf-8")
        if _OLD_ICON_IMPORT.search(text) or "<lucide-icon" in text:
            offenders.append(_repo_relative(path))
        elif path.suffix in {".css", ".scss"} and re.search(r"\blucide-icon\b", text):
            offenders.append(_repo_relative(path))
    assert offenders == []


def _icon_tags(text: str) -> list[list[str]]:
    """Return the attribute names of every ``<svg>`` start tag in ``text`` that renders a lucide icon.

    Raises:
        ValueError: when an ``<svg`` opening is not a start tag the pattern can read, so
            no icon escapes the guards unread.
    """
    tags = list(_SVG_START_TAG.finditer(text))
    if len(tags) != len(_SVG_OPENING.findall(text)):
        raise ValueError("an <svg start tag could not be read")
    names_per_tag = [
        [match["name"] for match in _ATTRIBUTE.finditer(tag["attributes"])]
        for tag in tags
    ]
    return [names for names in names_per_tag if _ICON_INPUTS & set(names)]


def _frontend_icon_tags() -> list[tuple[str, list[str]]]:
    """List the attribute names of every icon ``svg`` in the templates and inline templates of the frontend layers."""
    return [
        (_repo_relative(path), names)
        for path in _frontend_sources(".html", ".ts")
        for names in _icon_tags(path.read_text(encoding="utf-8"))
    ]


@pytest.mark.unit
def test_when_a_binding_holds_a_greater_than_sign_then_the_icon_tag_scan_reads_the_attributes_after_it():
    """A ``>`` inside a quoted binding does not end the tag, so later attributes are still checked.

    Validates tests/test_frontend_dependency_upgrade.py _icon_tags().
    """
    fixture = (
        "<svg [lucideIcon]=\"count() > 0 ? 'Bell' : 'Inbox'\""
        ' [attr.data-step]="items().map((item) => item.step)"'
        ' [class.icon-alert]="urgent()" matListItemIcon />'
    )

    assert _icon_tags(fixture) == [
        ["[lucideIcon]", "[attr.data-step]", "[class.icon-alert]", "matListItemIcon"]
    ]


@pytest.mark.unit
def test_when_an_icon_element_is_read_then_it_carries_no_class_property_binding():
    """No ``<svg lucideIcon>`` element binds ``[class.x]``.

    The icon writes its whole ``class`` attribute from its ``class`` input, so a
    ``[class.x]`` binding, which bypasses that input, is wiped the next time the
    icon re-renders. A static ``class`` or a ``[class]`` binding reaches the input.

    Validates project_initializer/templates/frontend/src/app, project_initializer/templates-token-frontend/frontend/src/app, project_initializer/templates-supabase-frontend/frontend/src/app and project_initializer/templates-entra-frontend/frontend/src/app.
    """
    icon_tags = _frontend_icon_tags()
    assert icon_tags, (
        "no <svg lucideIcon> found: the scan no longer matches the icon element"
    )
    offenders = [
        f"{path}: {names}"
        for path, names in icon_tags
        if any(name.startswith("[class.") for name in names)
    ]
    assert offenders == []


@pytest.mark.unit
def test_when_an_icon_element_is_read_then_it_carries_no_material_list_slot_directive():
    """``matListItemIcon`` and ``matListItemMeta`` sit on a wrapper, never on the icon ``svg``.

    Both directives mark their host with Material's slot classes
    (``mdc-list-item__start``, ``mdc-list-item__end``), which carry the slot's
    size, spacing and color; on the ``svg`` the icon's own ``class`` attribute
    overwrites them.

    Validates project_initializer/templates/frontend/src/app, project_initializer/templates-token-frontend/frontend/src/app, project_initializer/templates-supabase-frontend/frontend/src/app and project_initializer/templates-entra-frontend/frontend/src/app.
    """
    icon_tags = _frontend_icon_tags()
    assert icon_tags, (
        "no <svg lucideIcon> found: the scan no longer matches the icon element"
    )
    slot_directives = {"matListItemIcon", "matListItemMeta"}
    offenders = [
        f"{path}: {names}" for path, names in icon_tags if slot_directives & set(names)
    ]
    assert offenders == []


@pytest.mark.unit
def test_when_the_frontend_sources_are_read_then_no_file_imports_a_deprecated_icon_class():
    """Icons are imported under their current class names, never a deprecated alias.

    ``LucideCircleAlert``, ``LucideTrash2`` and the like still export, but each is
    marked ``@deprecated`` and can disappear in a later release.

    Validates project_initializer/templates/frontend/src, project_initializer/templates-token-frontend/frontend/src, project_initializer/templates-supabase-frontend/frontend/src and project_initializer/templates-entra-frontend/frontend/src.
    """
    offenders = [
        f"{_repo_relative(path)}: {match}"
        for path in _frontend_sources(".ts")
        for match in _DEPRECATED_ICON_CLASSES.findall(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def _manifest_dependencies(manifest: Path) -> dict[str, str]:
    """Return every runtime and dev dependency ``manifest`` declares, by package name."""
    package = json.loads(manifest.read_text(encoding="utf-8"))
    return {**package.get("dependencies", {}), **package.get("devDependencies", {})}


def _lock_packages() -> dict[str, dict]:
    """Return the ``packages`` map of the base lock, keyed by install path (``""`` is the root)."""
    return json.loads(_FRONTEND_LOCK.read_text(encoding="utf-8"))["packages"]


def _version_tuple(version: str) -> tuple[int, ...]:
    """Turn a dotted version into a tuple padded to three numbers, so ``6.0`` compares as ``6.0.0``."""
    numbers = tuple(int(part) for part in version.split("."))
    return numbers + (0,) * (3 - len(numbers))


def _satisfies(version: str, peer_range: str) -> bool:
    """Tell whether ``version`` meets a peer range written only with ``>=`` and ``<`` comparators.

    Raises:
        ValueError: when the range holds any other syntax, so a reworded range is
            flagged instead of being half read.
    """
    comparators = list(_PEER_COMPARATOR.finditer(peer_range))
    if "".join(match.group(0) for match in comparators) != peer_range.replace(" ", ""):
        raise ValueError(f"unsupported peer range {peer_range!r}")
    candidate = _version_tuple(version)
    return all(
        candidate >= _version_tuple(match["version"])
        if match["operator"] == ">="
        else candidate < _version_tuple(match["version"])
        for match in comparators
    )


def _in_npm_range(version: str, specifier: str) -> bool:
    """Tell whether ``version`` falls inside a ``^x.y.z`` or ``~x.y.z`` npm range.

    Raises:
        ValueError: when ``specifier`` is any other form, an exact version included,
            so a manifest that leaves the range style fails instead of being half read.
    """
    match = _RANGE_SPECIFIER.fullmatch(specifier)
    if not match:
        raise ValueError(f"not a caret or tilde range: {specifier!r}")
    floor = _version_tuple(match["version"])
    candidate = _version_tuple(version)
    if match["operator"] == "~":
        return candidate >= floor and candidate[:2] == floor[:2]
    # Below 1.0.0 a caret holds the minor; from 1.0.0 on it holds the major.
    held = 2 if floor[0] == 0 else 1
    return candidate >= floor and candidate[:held] == floor[:held]


def _is_caret_range_within(
    specifier: str | None, floor: tuple[int, ...], ceiling: tuple[int, ...]
) -> bool:
    """Tell whether ``specifier`` is a caret range whose lower bound is in ``[floor, ceiling)``."""
    match = _RANGE_SPECIFIER.fullmatch(specifier or "")
    return bool(
        match
        and match["operator"] == "^"
        and floor <= _version_tuple(match["version"]) < ceiling
    )


@pytest.mark.unit
def test_when_the_frontend_manifests_are_read_then_every_angular_package_is_on_a_22_caret_range():
    """Every ``@angular/*`` package of each manifest declares a caret range on Angular 22, from 22.3.0 or later.

    A range left on 21 would let npm put an Angular 21 package next to Angular 22
    ones, and a floor below 22.3.0 would admit Material releases whose checkbox and
    radio DOM disagrees with their own harnesses.

    Validates project_initializer/templates/frontend/package.json, project_initializer/templates-supabase-frontend/frontend/package.json and project_initializer/templates-entra-frontend/frontend/package.json.
    """
    assert len(_FRONTEND_MANIFESTS) == 3, [
        _repo_relative(m) for m in _FRONTEND_MANIFESTS
    ]
    offenders = []
    for manifest in _FRONTEND_MANIFESTS:
        declared = _manifest_dependencies(manifest)
        missing = [name for name in _ANGULAR_PACKAGES if name not in declared]
        assert missing == [], f"{_repo_relative(manifest)} lacks {missing}"
        offenders += [
            f"{_repo_relative(manifest)}: {name}@{specifier}"
            for name, specifier in declared.items()
            if name.startswith("@angular/")
            and not _is_caret_range_within(specifier, _ANGULAR_FLOOR, _ANGULAR_CEILING)
        ]
    assert offenders == []


@pytest.mark.unit
def test_when_the_frontend_manifests_are_read_then_a_package_they_share_has_the_same_pin_in_each():
    """A dependency that more than one frontend manifest declares carries the same specifier in all of them.

    The supabase and entra overlays replace the base manifest whole, so a range
    bumped in one copy only would scaffold a different Angular, Material, CDK,
    icon library or TypeScript for one auth mode.

    Validates project_initializer/templates/frontend/package.json, project_initializer/templates-supabase-frontend/frontend/package.json and project_initializer/templates-entra-frontend/frontend/package.json.
    """
    pins: dict[str, dict[str, str]] = {}
    for manifest in _FRONTEND_MANIFESTS:
        for name, pin in _manifest_dependencies(manifest).items():
            pins.setdefault(name, {})[_repo_relative(manifest)] = pin
    shared = {name: found for name, found in pins.items() if len(found) > 1}

    assert sorted(set(_SHARED_SPECIFIERS) - set(shared)) == []
    diverging = {
        name: found for name, found in shared.items() if len(set(found.values())) > 1
    }
    assert diverging == {}


@pytest.mark.unit
@pytest.mark.parametrize("group", sorted(_ANGULAR_RELEASE_GROUPS))
def test_when_a_frontend_manifest_is_read_then_each_angular_release_group_shares_one_version(
    group: str,
):
    """The packages Angular publishes together declare one range in each manifest.

    ``@angular/compiler-cli`` peers on ``@angular/compiler`` and ``@angular/material``
    on ``@angular/cdk`` at exactly their own release, so a group split across two
    ranges can resolve to releases that break the install or the build.

    Validates project_initializer/templates/frontend/package.json, project_initializer/templates-supabase-frontend/frontend/package.json and project_initializer/templates-entra-frontend/frontend/package.json.
    """
    for manifest in _FRONTEND_MANIFESTS:
        declared = _manifest_dependencies(manifest)
        versions = {name: declared.get(name) for name in _ANGULAR_RELEASE_GROUPS[group]}
        assert len(set(versions.values())) == 1, (
            f"{_repo_relative(manifest)}: {versions}"
        )


@pytest.mark.unit
def test_when_typescript_is_read_then_it_is_a_6_0_tilde_range_inside_the_angular_compiler_peer_range():
    """Each manifest declares TypeScript ``~6.0.x``, and the lock resolves it inside the Angular compiler's and builder's peer range.

    The Angular 22 compiler and builder peer on ``typescript >=6.0 <6.1``:
    TypeScript 7 is the registry's latest release, but the compiler rejects it,
    so the range may follow patch releases only.

    Validates project_initializer/templates/frontend/package.json, project_initializer/templates-supabase-frontend/frontend/package.json, project_initializer/templates-entra-frontend/frontend/package.json and project_initializer/templates/frontend/package-lock.json.
    """
    specifiers = {
        _repo_relative(m): _manifest_dependencies(m).get("typescript")
        for m in _FRONTEND_MANIFESTS
    }
    assert all(
        specifier and _TYPESCRIPT_RANGE.fullmatch(specifier)
        for specifier in specifiers.values()
    ), specifiers

    packages = _lock_packages()
    resolved = packages["node_modules/typescript"]["version"]
    assert _in_npm_range(resolved, specifiers[_repo_relative(_BASE_MANIFEST)])
    for dependent in ("@angular/compiler-cli", "@angular/build"):
        peer_range = packages[f"node_modules/{dependent}"]["peerDependencies"][
            "typescript"
        ]
        assert _satisfies(resolved, peer_range), (
            f"typescript {resolved} is outside the {dependent} peer range {peer_range!r}"
        )


@pytest.mark.unit
def test_when_the_base_lock_is_read_then_it_declares_the_manifest_ranges_and_resolves_inside_them():
    """The base lock declares Angular, the icon library, TypeScript, tslib and rxjs with the base manifest's ranges and resolves a release inside each.

    ``npm ci`` in the image build refuses a lock whose root entry disagrees with
    the manifest, and a resolved release outside its range means the lock was
    not regenerated after a manifest change.

    Validates project_initializer/templates/frontend/package.json and project_initializer/templates/frontend/package-lock.json.
    """
    declared = _manifest_dependencies(_BASE_MANIFEST)
    packages = _lock_packages()
    root = {
        **packages[""].get("dependencies", {}),
        **packages[""].get("devDependencies", {}),
    }
    mismatches = []
    for name in _SHARED_SPECIFIERS:
        specifier = declared[name]
        resolved = packages.get(f"node_modules/{name}", {}).get("version", "0.0.0")
        if root.get(name) != specifier or not _in_npm_range(resolved, specifier):
            mismatches.append(
                f"{name}: manifest {specifier}, lock root {root.get(name)}, resolved {resolved}"
            )
    assert mismatches == []


@pytest.mark.unit
def test_when_the_frontend_sources_are_read_then_no_file_calls_the_deprecated_with_fetch():
    """No frontend source or spec passes ``withFetch()`` to ``provideHttpClient``.

    Angular 22 makes ``FetchBackend`` the default ``HttpBackend`` and deprecates
    ``withFetch()``, so the call adds a deprecation without changing the backend.

    Validates project_initializer/templates/frontend/src, project_initializer/templates-token-frontend/frontend/src, project_initializer/templates-supabase-frontend/frontend/src and project_initializer/templates-entra-frontend/frontend/src.
    """
    offenders = [
        _repo_relative(path)
        for path in _frontend_sources(".ts")
        if _WITH_FETCH.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


@pytest.mark.unit
def test_when_the_frontend_sources_are_read_then_no_component_opts_out_of_on_push():
    """No component, test host included, sets ``ChangeDetectionStrategy.Eager`` or ``Default``.

    Angular 22 makes OnPush the default and ``ng update`` writes ``Eager`` into
    every component that sets nothing. The templates keep what a host renders in
    signals, which re-render under OnPush, instead of opting out.

    Validates project_initializer/templates/frontend/src, project_initializer/templates-token-frontend/frontend/src, project_initializer/templates-supabase-frontend/frontend/src and project_initializer/templates-entra-frontend/frontend/src.
    """
    offenders = [
        f"{_repo_relative(path)}: {match}"
        for path in _frontend_sources(".ts")
        for match in _CHANGE_DETECTION_OPT_OUT.findall(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


@pytest.mark.unit
def test_when_the_frontend_tsconfigs_are_read_then_no_removed_extended_diagnostic_is_configured():
    """No tsconfig of a frontend layer configures ``nullishCoalescingNotNullable`` or ``optionalChainNotNullable``.

    Angular 22.3 removed both checks and accepts their names only as no-ops, so
    the ``suppress`` entries ``ng update`` adds for them would be dead settings.

    Validates project_initializer/templates/frontend/tsconfig.json, project_initializer/templates/frontend/tsconfig.app.json and project_initializer/templates/frontend/tsconfig.spec.json.
    """
    tsconfigs = sorted(
        path for layer in _FRONTEND_LAYERS for path in layer.glob("tsconfig*.json")
    )
    assert tsconfigs, "no frontend tsconfig found"
    offenders = [
        f"{_repo_relative(path)}: {name}"
        for path in tsconfigs
        for name in _REMOVED_DIAGNOSTICS
        if name in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


@pytest.mark.unit
def test_when_a_root_service_is_read_then_it_uses_the_service_decorator_and_nothing_is_provided_in_root():
    """The six singleton services are declared with ``@Service()`` and no frontend file keeps ``providedIn: 'root'``.

    Angular 22 documents ``@Service()`` as the shorthand for
    ``@Injectable({providedIn: 'root'})``, and the generated frontend CLAUDE.md
    prescribes it, so a leftover ``providedIn: 'root'`` would contradict the docs.

    Validates project_initializer/templates/frontend/src/app/services/theme.ts, project_initializer/templates/frontend/src/app/services/window-size-class.ts, project_initializer/templates/frontend/src/app/shared/ui/toast/toast.service.ts, project_initializer/templates-token-frontend/frontend/src/app/services/auth.ts, project_initializer/templates-supabase-frontend/frontend/src/app/services/auth.ts and project_initializer/templates-entra-frontend/frontend/src/app/core/services/auth.service.ts.
    """
    undecorated = [
        _repo_relative(path)
        for path in _ROOT_SERVICES
        if "@Service()" not in path.read_text(encoding="utf-8")
    ]
    assert undecorated == []
    provided_in_root = [
        _repo_relative(path)
        for path in _frontend_sources(".ts")
        if _PROVIDED_IN_ROOT.search(path.read_text(encoding="utf-8"))
    ]
    assert provided_in_root == []
    assert "Prefer the `@Service` decorator" in generate_frontend_claude()


@pytest.mark.unit
def test_when_the_docs_name_the_angular_release_then_it_is_the_one_the_manifests_declare():
    """The generated root and frontend CLAUDE.md and the repo CLAUDE.md name the Angular major and Material + CDK minor the base manifest declares.

    Validates project_initializer/docs_generator.py generate_root_claude(), project_initializer/docs_generator.py generate_frontend_claude() and CLAUDE.md.
    """
    declared = _manifest_dependencies(_BASE_MANIFEST)
    angular_floor = _RANGE_SPECIFIER.fullmatch(declared["@angular/core"])
    material_floor = _RANGE_SPECIFIER.fullmatch(declared["@angular/material"])
    assert angular_floor and material_floor, declared
    angular_major = angular_floor["version"].split(".")[0]
    material_minor = ".".join(material_floor["version"].split(".")[:2])

    root_docs = {
        "fullstack": generate_root_claude("fastapi", None),
        "frontend only": generate_root_claude("fastapi", None, api=False),
    }
    for scope, doc in root_docs.items():
        assert f"Angular {angular_major} with Angular Material 3" in doc, scope
    assert f"Angular Material + CDK {material_minor}" in generate_frontend_claude()
    assert (
        f"Angular {angular_major} with Angular Material 3 "
        f"(`@angular/material` + `@angular/cdk` {material_minor})"
    ) in _REPO_CLAUDE.read_text(encoding="utf-8")


@pytest.mark.unit
def test_when_the_csp_nonce_is_described_then_the_stylesheet_and_modulepreload_links_are_named():
    """The generated frontend CLAUDE.md and the nonce comment in ``index.html`` list the link tags the build stamps.

    Since ``@angular/build`` 22.2.3 the production build copies the nonce onto
    ``<link rel="stylesheet">`` and ``<link rel="modulepreload">`` as well, so a
    reader writing another server must know those tags carry it too.

    Validates project_initializer/docs_generator.py generate_frontend_claude() and project_initializer/templates/frontend/src/index.html.
    """
    documents = {
        "frontend CLAUDE.md": generate_frontend_claude(),
        "index.html": _BASE_INDEX_HTML.read_text(encoding="utf-8"),
    }
    for name, text in documents.items():
        assert '<link rel="stylesheet">' in text, name
        assert '<link rel="modulepreload">' in text, name


@pytest.mark.unit
def test_when_a_frontend_manifest_is_read_then_allow_scripts_names_every_locked_package_with_an_install_script():
    """Each manifest's ``allowScripts`` lists, by name only, exactly the packages the base lock marks with an install script.

    npm 11.20 warns on every install about install scripts that ``allowScripts``
    does not cover, and npm 12 blocks them. A ``name@version`` key would stop
    covering the package at the next lock regeneration, and a package the lock
    adds or drops must change the list with it.

    Validates project_initializer/templates/frontend/package.json, project_initializer/templates-supabase-frontend/frontend/package.json, project_initializer/templates-entra-frontend/frontend/package.json and project_initializer/templates/frontend/package-lock.json.
    """
    with_install_script = {
        path.rpartition("node_modules/")[2]
        for path, entry in _lock_packages().items()
        if entry.get("hasInstallScript")
    }
    assert with_install_script, "the base lock marks no package with an install script"

    for manifest in _FRONTEND_MANIFESTS:
        allowed = json.loads(manifest.read_text(encoding="utf-8")).get("allowScripts")
        assert isinstance(allowed, dict), (
            f"{_repo_relative(manifest)} has no allowScripts"
        )
        assert set(allowed) == with_install_script, _repo_relative(manifest)
        assert set(allowed.values()) == {True}, _repo_relative(manifest)
