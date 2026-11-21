"""Guard: every scaffolded NestJS variant must have a package-lock in sync.

The NestJS Dockerfile runs `npm ci` when a package-lock.json is present, and
`npm ci` hard-fails when the lock does not match package.json:

    npm error `npm ci` can only install packages when your package.json and
    npm error package-lock.json ... are in sync.

So a drifted lock means the API image never builds — every NestJS variant broken
in Docker, which is exactly what happened: the @bull-board deps were added to
package.json without regenerating the lock, `templates-token-nestjs` shipped an
empty stub lock that overwrote the good base one, and `templates-entra-nestjs`
added jsonwebtoken/jwks-rsa while shipping no lock at all.

The check runs against the **layered** result rather than each overlay in
isolation, because the layering is what hid the drift: an overlay can supply a
package.json while inheriting a lock from the base, and only the merged tree
shows whether the pair actually agrees.
"""

import json
from pathlib import Path

import pytest

from project_initializer.cli import copy_template

_TEMPLATES = Path(__file__).resolve().parent.parent / "project_initializer"

_AUTH_MODES = [None, "token", "supabase", "entra"]


def _root_lock_deps(lock: dict) -> set[str]:
    """Return the dependency names the lock records for the root package."""
    root = lock["packages"][""]
    return set(root.get("dependencies", {})) | set(root.get("devDependencies", {}))


def _package_deps(package_json: dict) -> set[str]:
    """Return the dependency names package.json declares."""
    return set(package_json.get("dependencies", {})) | set(
        package_json.get("devDependencies", {})
    )


@pytest.mark.integration
@pytest.mark.parametrize("auth", _AUTH_MODES)
def test_scaffolded_nestjs_lockfile_matches_package_json(tmp_path, auth):
    """The layered package.json and package-lock.json must agree, or npm ci fails."""
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")

    package_json = json.loads((tmp_path / "api" / "package.json").read_text("utf-8"))
    lock = json.loads((tmp_path / "api" / "package-lock.json").read_text("utf-8"))

    declared = _package_deps(package_json)
    locked = _root_lock_deps(lock)

    assert declared - locked == set(), (
        f"nestjs+{auth or 'none'}: package.json declares deps the lock is missing "
        f"({sorted(declared - locked)}) — `npm ci` will fail. Regenerate with "
        "`npm install --package-lock-only`."
    )
    assert locked - declared == set(), (
        f"nestjs+{auth or 'none'}: the lock records deps package.json no longer "
        f"declares ({sorted(locked - declared)}) — `npm ci` will fail."
    )


@pytest.mark.integration
@pytest.mark.parametrize("auth", _AUTH_MODES)
def test_scaffolded_nestjs_lockfile_is_populated(tmp_path, auth):
    """The lock must actually resolve a tree, not be an empty stub.

    `templates-token-nestjs` shipped `{"packages": {}}`, which overwrote the real
    base lock and made `npm ci` fail with everything "missing from lock file".
    """
    copy_template(tmp_path, "app", auth=auth, framework="nestjs", scope="api")
    lock = json.loads((tmp_path / "api" / "package-lock.json").read_text("utf-8"))

    assert "" in lock["packages"], (
        f"nestjs+{auth or 'none'}: lock has no root package entry — it is a stub"
    )
    # A real NestJS tree resolves hundreds of packages; a stub resolves ~0.
    assert len(lock["packages"]) > 100, (
        f"nestjs+{auth or 'none'}: lock resolves only {len(lock['packages'])} "
        "packages — it looks like an empty stub, not a real tree"
    )


@pytest.mark.parametrize(
    "overlay,ships_manifest",
    [
        ("templates-api-nestjs", True),
        ("templates-supabase-nestjs", True),
        ("templates-entra-nestjs", True),
        ("templates-token-nestjs", False),
    ],
)
def test_nestjs_layer_owns_a_lock_exactly_when_it_ships_a_package_json(
    overlay, ships_manifest
):
    """A lock follows its package.json: an overlay with its own manifest carries its own lock,
    and the token overlay, which has none, inherits the base pair. A lock without its manifest
    would overwrite the base lock with one that matches nothing.

    Validates the package.json and package-lock.json of project_initializer/templates-{api,supabase,entra,token}-nestjs/api.
    """
    api = _TEMPLATES / overlay / "api"
    assert (api / "package.json").is_file() is ships_manifest
    assert (api / "package-lock.json").is_file() is ships_manifest
