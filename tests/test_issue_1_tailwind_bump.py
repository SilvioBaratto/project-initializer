"""
Tests for issue #1: the frontend template's styling dependencies.

History: issue #1 bumped Tailwind to v4.3. The Material 3 migration then removed
Tailwind in favour of Angular Material 3 (Angular Material + CDK 21.2), so the
file keeps its name for the issue history and now pins the new dependency truth:
  - package.json (the base template, and the supabase / entra overlays that ship
    their own) declares no tailwindcss / @tailwindcss/postcss and depends on
    @angular/material and @angular/cdk ^21.2, both on the same range
  - package-lock.json resolves @angular/material to 21.2.x, resolves
    @angular/cdk to the exact release Material peers on, and contains no Tailwind
    package
  - no PostCSS config (.postcssrc.json / postcss.config.*) and no
    tailwind.config.* ships in the frontend template or its auth overlays
  - the editor recommendations no longer suggest the Tailwind extension, and keep
    the Angular language service: both the template files and the layered result
    select_layers() ships per scope, since the api layer overwrites the base file
"""

import json
import pathlib
import re

import pytest

from project_initializer.cli import select_layers

REPO = pathlib.Path(__file__).parent.parent
PACKAGE = REPO / "project_initializer"
FRONTEND = PACKAGE / "templates" / "frontend"
OVERLAY_FRONTENDS = sorted(PACKAGE.glob("templates-*-frontend/frontend"))

# Every frontend package.json a scaffold can end up with. The token overlay ships
# none, so it inherits the base file.
PACKAGE_JSONS = {
    "base": FRONTEND / "package.json",
    "supabase": PACKAGE / "templates-supabase-frontend" / "frontend" / "package.json",
    "entra": PACKAGE / "templates-entra-frontend" / "frontend" / "package.json",
}

TAILWIND_PACKAGES = ("tailwindcss", "@tailwindcss/postcss")
MATERIAL_PACKAGES = ("@angular/material", "@angular/cdk")
_MATERIAL_RANGE = re.compile(r"^\^21\.2\.\d+$")

_DEPENDENCY_SECTIONS = (
    "dependencies",
    "devDependencies",
    "peerDependencies",
    "optionalDependencies",
)


def _load_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_package_lock() -> dict:
    return _load_json(FRONTEND / "package-lock.json")


def _all_dependencies(pkg: dict) -> dict[str, str]:
    """Every declared dependency of a package.json, across all sections."""
    merged: dict[str, str] = {}
    for section in _DEPENDENCY_SECTIONS:
        merged.update(pkg.get(section, {}))
    return merged


def _resolved_entry(lock: dict, package_name: str) -> dict:
    """Return the lock entry for *package_name* from an npm lockfile.

    Supports lockfileVersion 2/3 (packages dict keyed by node_modules/<name>)
    and v1 (dependencies dict keyed by bare name).
    """
    if "packages" in lock:
        return lock["packages"][f"node_modules/{package_name}"]
    return lock["dependencies"][package_name]


def _resolved_version(lock: dict, package_name: str) -> str:
    return _resolved_entry(lock, package_name)["version"]


# ---------------------------------------------------------------------------
# package.json: no Tailwind, Angular Material + CDK ^21.2
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant", sorted(PACKAGE_JSONS))
def test_when_package_json_read_then_no_tailwind_dependency_is_declared(variant):
    """Neither tailwindcss nor @tailwindcss/postcss may be declared in any section."""
    declared = _all_dependencies(_load_json(PACKAGE_JSONS[variant]))
    leftovers = [name for name in TAILWIND_PACKAGES if name in declared]
    assert leftovers == [], f"[{variant}] package.json still declares {leftovers}"


@pytest.mark.parametrize("variant", sorted(PACKAGE_JSONS))
@pytest.mark.parametrize("package_name", MATERIAL_PACKAGES)
def test_when_package_json_read_then_material_package_is_a_21_2_runtime_dependency(
    variant, package_name
):
    """@angular/material and @angular/cdk are runtime dependencies on a ^21.2.x range."""
    dependencies = _load_json(PACKAGE_JSONS[variant]).get("dependencies", {})
    assert package_name in dependencies, (
        f"[{variant}] {package_name} must be listed under dependencies"
    )
    assert _MATERIAL_RANGE.match(dependencies[package_name]), (
        f"[{variant}] expected {package_name} on ^21.2.x, "
        f"got {dependencies[package_name]!r}"
    )


@pytest.mark.parametrize("variant", sorted(PACKAGE_JSONS))
def test_when_package_json_read_then_material_and_cdk_share_one_range(variant):
    """Material peers on the exact CDK release, so both must move together."""
    dependencies = _load_json(PACKAGE_JSONS[variant])["dependencies"]
    assert dependencies["@angular/material"] == dependencies["@angular/cdk"], (
        f"[{variant}] @angular/material and @angular/cdk ranges diverge: "
        f"{dependencies['@angular/material']!r} vs {dependencies['@angular/cdk']!r}"
    )


def test_when_overlays_listed_then_every_frontend_package_json_is_covered():
    """A new overlay package.json must be added to PACKAGE_JSONS, not slip past these checks."""
    shipped = {
        path
        for overlay in OVERLAY_FRONTENDS
        for path in [overlay / "package.json"]
        if path.exists()
    } | {FRONTEND / "package.json"}
    assert shipped <= set(PACKAGE_JSONS.values()), (
        f"uncovered package.json files: {sorted(map(str, shipped - set(PACKAGE_JSONS.values())))}"
    )


# ---------------------------------------------------------------------------
# package-lock.json: Material 21.2.x resolved, no Tailwind
# ---------------------------------------------------------------------------


def test_when_package_lock_read_then_angular_material_resolves_to_21_2():
    """Resolved '@angular/material' version in package-lock.json must start with '21.2.'."""
    version = _resolved_version(_load_package_lock(), "@angular/material")
    assert version.startswith("21.2."), (
        f"expected @angular/material to resolve to 21.2.x, got {version!r}"
    )


def test_when_package_lock_read_then_cdk_resolves_to_the_release_material_peers_on():
    """@angular/cdk resolves to the exact version @angular/material's peer range names."""
    lock = _load_package_lock()
    material = _resolved_entry(lock, "@angular/material")
    cdk_version = _resolved_version(lock, "@angular/cdk")
    expected = material.get("peerDependencies", {}).get("@angular/cdk", material["version"])
    assert cdk_version == expected, (
        f"@angular/cdk resolves to {cdk_version!r}, but @angular/material "
        f"{material['version']} peers on {expected!r}"
    )


def test_when_package_lock_read_then_root_entry_matches_package_json():
    """The lock's root entry declares the same Material/CDK ranges as package.json (lock in sync)."""
    lock = _load_package_lock()
    if "packages" not in lock:
        pytest.skip("lockfile v1 has no root package entry")
    root = _all_dependencies(lock["packages"][""])
    declared = _all_dependencies(_load_json(PACKAGE_JSONS["base"]))
    for name in MATERIAL_PACKAGES:
        assert root.get(name) == declared[name], (
            f"package-lock.json root declares {name}@{root.get(name)!r}, "
            f"package.json declares {declared[name]!r}; regenerate the lock"
        )


def test_when_package_lock_read_then_no_tailwind_package_is_present():
    """No tailwindcss or @tailwindcss/* package may remain anywhere in the lock."""
    lock = _load_package_lock()
    names = lock.get("packages", lock.get("dependencies", {})).keys()
    leftovers = [
        name
        for name in names
        if re.search(r"(^|/)(tailwindcss|@tailwindcss/[^/]+)$", name)
    ]
    assert leftovers == [], f"package-lock.json still resolves {leftovers}"


# ---------------------------------------------------------------------------
# No PostCSS / Tailwind config ships in any frontend layer
# ---------------------------------------------------------------------------


def _frontend_layers() -> list[pathlib.Path]:
    return [FRONTEND, *OVERLAY_FRONTENDS]


def test_when_frontend_layers_listed_then_no_postcss_config_file_exists():
    """PostCSS existed only to run @tailwindcss/postcss; Angular's builder needs no config."""
    found = [
        str(path)
        for layer in _frontend_layers()
        for pattern in (".postcssrc*", "postcss.config.*")
        for path in layer.glob(pattern)
    ]
    assert found == [], f"unexpected PostCSS config file(s): {found}"


def test_when_frontend_layers_listed_then_no_tailwind_config_file_exists():
    """No tailwind.config.* file may exist in the frontend template or its overlays."""
    found = [
        str(path) for layer in _frontend_layers() for path in layer.glob("tailwind.config.*")
    ]
    assert found == [], f"unexpected tailwind config file(s) found: {found}"


# ---------------------------------------------------------------------------
# Editor recommendations: no Tailwind IntelliSense
# ---------------------------------------------------------------------------

EXTENSIONS_JSONS = {
    "repo": REPO / ".vscode" / "extensions.json",
    "templates": PACKAGE / "templates" / ".vscode" / "extensions.json",
}


@pytest.mark.parametrize("location", sorted(EXTENSIONS_JSONS))
def test_when_extensions_json_read_then_tailwind_extension_is_not_recommended(location):
    """bradlc.vscode-tailwindcss has nothing to assist once Tailwind is gone."""
    recommendations = _load_json(EXTENSIONS_JSONS[location])["recommendations"]
    assert "bradlc.vscode-tailwindcss" not in recommendations, (
        f"[{location}] .vscode/extensions.json still recommends the Tailwind extension"
    )


@pytest.mark.parametrize("location", sorted(EXTENSIONS_JSONS))
def test_when_extensions_json_read_then_angular_language_service_is_kept(location):
    """The Angular language service stays recommended for the templates."""
    recommendations = _load_json(EXTENSIONS_JSONS[location])["recommendations"]
    assert "angular.ng-template" in recommendations, (
        f"[{location}] .vscode/extensions.json must keep angular.ng-template"
    )


# A scaffold gets whichever layer's copy of a file lands last. In the fullstack and
# api scopes, select_layers() copies the api layer over the base layer, so checking
# templates/.vscode alone misses a recommendation the api layer puts back.

_SHIPPED_EXTENSIONS_JSONS = (
    pathlib.PurePosixPath(".vscode/extensions.json"),
    pathlib.PurePosixPath("frontend/.vscode/extensions.json"),
)
_FRAMEWORKS = ("fastapi", "nestjs")
_AUTHS = (None, "token", "supabase", "entra")
_TAILWIND_EXTENSION = "bradlc.vscode-tailwindcss"

def _shipped_extensions_jsons(scope: str) -> dict[str, str]:
    """Text of every editor-recommendation file a scaffold in *scope* ships.

    Keys read '<framework>/<auth>:<relative path>' across every framework and auth
    mode. Layers merge in select_layers() order, so the last layer carrying a file
    wins, after that layer's transform; a skipped subdirectory ships nothing.
    """
    shipped: dict[str, str] = {}
    for framework in _FRAMEWORKS:
        for auth in _AUTHS:
            for src, skip_subdirs, transform in select_layers(scope, framework, auth):
                for relative in _SHIPPED_EXTENSIONS_JSONS:
                    candidate = src / relative
                    skipped = any(part in skip_subdirs for part in relative.parts[:-1])
                    if skipped or not candidate.is_file():
                        continue
                    text = transform(candidate) if transform is not None else None
                    shipped[f"{framework}/{auth}:{relative}"] = (
                        text if text is not None else candidate.read_text(encoding="utf-8")
                    )
    return shipped


@pytest.mark.parametrize(
    "scope",
    [
        "fullstack",
        "api",
        "frontend",
    ],
)
def test_when_scaffold_layers_merge_then_no_shipped_extensions_json_recommends_tailwind(
    scope,
):
    """The layered result, not one template file, decides what a project recommends."""
    offenders = sorted(
        key
        for key, text in _shipped_extensions_jsons(scope).items()
        if _TAILWIND_EXTENSION in text
    )
    assert offenders == [], (
        f"[{scope}] scaffold ships the Tailwind extension recommendation in {offenders}"
    )


@pytest.mark.parametrize("scope", ["fullstack", "frontend"])
def test_when_scaffold_layers_merge_then_root_extensions_json_keeps_angular_language_service(
    scope,
):
    """Scopes that ship the Angular app recommend its language service at the root."""
    roots = {
        key: text
        for key, text in _shipped_extensions_jsons(scope).items()
        if key.endswith(":.vscode/extensions.json")
    }
    assert len(roots) == len(_FRAMEWORKS) * len(_AUTHS), (
        f"[{scope}] expected a root .vscode/extensions.json for every framework and "
        f"auth mode, got {sorted(roots)}"
    )
    missing = sorted(key for key, text in roots.items() if "angular.ng-template" not in text)
    assert missing == [], f"[{scope}] angular.ng-template is not recommended in {missing}"
