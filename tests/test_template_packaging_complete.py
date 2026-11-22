"""Every file in a template tree is covered by the packaging config, without building.

The release process builds the wheel from a ``git archive`` snapshot, so what ships is
decided by three things: the ``package-data`` globs in ``pyproject.toml``, the rules in
``MANIFEST.in``, and ``.gitignore`` (an ignored file is not in the snapshot). The template
trees keep gaining new file kinds: dotfiles such as ``.prettierrc``, ``eslint.config.mjs``,
``*.sql`` rollback scripts, ``test/support/*.ts``, ``tests/*.py``. A kind that none of the
three covers would be missing from every scaffold built from the PyPI package while the
checkout still works, so these tests compare the config against the file tree directly.
``test_package_data.py`` covers the full build; these run in milliseconds.
"""

from __future__ import annotations

import fnmatch
import glob
import shutil
import subprocess
import tomllib
from pathlib import Path, PurePosixPath

import pytest

_ROOT = Path(__file__).parent.parent
_PACKAGE = _ROOT / "project_initializer"

# Output of tooling run inside a template tree; the packaging rules drop it on purpose.
_BUILD_OUTPUT_DIRS = frozenset(
    {"node_modules", "__pycache__", "dist", "build", "generated", "coverage"}
)


def _template_dirs() -> list[str]:
    return sorted(path.name for path in _PACKAGE.glob("templates*") if path.is_dir())


def _template_files() -> list[str]:
    """Template files as posix paths relative to the package, build output excluded."""
    files: list[str] = []
    for name in _template_dirs():
        for path in (_PACKAGE / name).rglob("*"):
            relative = path.relative_to(_PACKAGE)
            if not path.is_file() or _BUILD_OUTPUT_DIRS & set(relative.parts):
                continue
            if path.suffix == ".pyc":
                continue
            files.append(relative.as_posix())
    return sorted(files)


def _pyproject() -> dict:
    return tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _manifest_rules(text: str) -> dict[str, list[tuple[str, ...]]]:
    """Group MANIFEST.in lines by command: ``{"recursive-include": [(dir, *patterns)], ...}``."""
    rules: dict[str, list[tuple[str, ...]]] = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts or parts[0].startswith("#"):
            continue
        rules.setdefault(parts[0], []).append(tuple(parts[1:]))
    return rules


def _manifest_includes(rules: dict[str, list[tuple[str, ...]]], relative: str) -> bool:
    """Whether MANIFEST.in puts ``relative`` (package-relative) in the sdist."""
    path = f"project_initializer/{relative}"
    name = PurePosixPath(path).name
    if (path,) in rules.get("include", []):
        return True
    return any(
        path.startswith(f"{directory}/")
        and any(fnmatch.fnmatch(name, pattern) for pattern in patterns)
        for directory, *patterns in rules.get("recursive-include", [])
    )


def _manifest_excludes(rules: dict[str, list[tuple[str, ...]]], relative: str) -> bool:
    """Whether a ``global-exclude`` or ``prune`` rule drops ``relative`` from the sdist."""
    path = f"project_initializer/{relative}"
    name = PurePosixPath(path).name
    if any(
        fnmatch.fnmatch(name, pattern)
        for patterns in rules.get("global-exclude", [])
        for pattern in patterns
    ):
        return True
    return any(
        path.startswith(f"{directory}/") for (directory,) in rules.get("prune", [])
    )


def _has_hidden_directory(relative: str) -> bool:
    return any(part.startswith(".") for part in PurePosixPath(relative).parts[:-1])


def _expand_package_data(patterns: list[str]) -> set[str]:
    """Files the wheel's ``package-data`` globs match, expanded the way setuptools does."""
    matched: set[str] = set()
    for pattern in patterns:
        for hit in glob.glob(pattern, root_dir=_PACKAGE, recursive=True):
            if (_PACKAGE / hit).is_file():
                matched.add(PurePosixPath(hit).as_posix())
    return matched


# --- the config names every template directory ------------------------------


@pytest.mark.parametrize("directory", _template_dirs())
def test_when_template_dir_listed_then_pyproject_has_both_package_data_globs(
    directory: str,
) -> None:
    """A new template directory needs a regular-file glob and a dotfile glob, or the wheel omits it.

    Validates pyproject.toml tool.setuptools.package-data.
    """
    patterns = _pyproject()["tool"]["setuptools"]["package-data"]["project_initializer"]
    assert f"{directory}/**/*" in patterns
    assert f"{directory}/**/.*" in patterns


@pytest.mark.parametrize("directory", _template_dirs())
def test_when_template_dir_listed_then_manifest_has_both_recursive_includes(
    directory: str,
) -> None:
    """A new template directory needs both recursive-include lines, or the sdist omits it.

    Validates MANIFEST.in recursive-include rules.
    """
    rules = _manifest_rules((_ROOT / "MANIFEST.in").read_text(encoding="utf-8"))
    includes = rules.get("recursive-include", [])
    assert (f"project_initializer/{directory}", "*") in includes
    assert (f"project_initializer/{directory}", ".*") in includes


# --- the config covers every file -------------------------------------------


def test_when_template_tree_walked_then_it_is_not_empty() -> None:
    """The checks below iterate the tree; an empty walk would make them pass vacuously.

    Validates project_initializer/templates*/ file tree.
    """
    assert len(_template_files()) > 100


def test_when_template_files_checked_then_the_sdist_manifest_includes_each() -> None:
    """Whatever the file kind, a MANIFEST.in rule must pull it into the sdist.

    Validates MANIFEST.in.
    """
    rules = _manifest_rules((_ROOT / "MANIFEST.in").read_text(encoding="utf-8"))

    missing = [
        path for path in _template_files() if not _manifest_includes(rules, path)
    ]

    assert not missing, (
        f"MANIFEST.in leaves {len(missing)} template files out of the sdist: {missing[:10]}"
    )


def test_when_template_files_checked_then_no_manifest_exclude_rule_drops_one() -> None:
    """``global-exclude`` and ``prune`` must only ever hit caches and build output.

    Validates MANIFEST.in global-exclude and prune rules.
    """
    rules = _manifest_rules((_ROOT / "MANIFEST.in").read_text(encoding="utf-8"))

    dropped = [path for path in _template_files() if _manifest_excludes(rules, path)]

    assert not dropped, (
        f"MANIFEST.in excludes {len(dropped)} template files: {dropped[:10]}"
    )


def test_when_template_files_checked_then_no_package_data_exclude_drops_one() -> None:
    """``exclude-package-data`` may only name node_modules, never a template file kind.

    Validates pyproject.toml tool.setuptools.exclude-package-data.
    """
    excludes = (
        _pyproject()["tool"]["setuptools"]
        .get("exclude-package-data", {})
        .get("project_initializer", [])
    )

    dropped = [
        path
        for path in _template_files()
        if any(fnmatch.fnmatch(path, pattern) for pattern in excludes)
    ]

    assert not dropped, (
        f"exclude-package-data drops {len(dropped)} template files: {dropped[:10]}"
    )


def test_when_package_data_globs_expanded_then_only_hidden_directory_files_are_left_to_the_manifest() -> (
    None
):
    """The globs reach every file except those under a dot-directory (``.vscode/``, ``.github/``).

    Those ship through MANIFEST.in, which the wheel honours only while
    ``include-package-data`` is on. Anything else the globs miss is a real packaging gap.

    Validates pyproject.toml tool.setuptools.package-data and include-package-data.
    """
    setuptools_config = _pyproject()["tool"]["setuptools"]
    matched = _expand_package_data(
        setuptools_config["package-data"]["project_initializer"]
    )

    unmatched = [path for path in _template_files() if path not in matched]

    assert all(_has_hidden_directory(path) for path in unmatched), [
        path for path in unmatched if not _has_hidden_directory(path)
    ][:10]
    if unmatched:
        assert setuptools_config["include-package-data"] is True


# --- git sees every file ----------------------------------------------------


def _git_ignored_template_files() -> list[str]:
    """Template files that ``.gitignore`` hides from ``git archive``; skips outside a checkout."""
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "--",
            "project_initializer",
        ],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("not a git checkout")

    return [
        line
        for line in result.stdout.splitlines()
        if not _BUILD_OUTPUT_DIRS & set(PurePosixPath(line).parts)
        and not line.endswith(".pyc")
    ]


def test_when_template_tree_checked_against_gitignore_then_no_file_is_ignored() -> None:
    """A file that .gitignore hides is absent from ``git archive``, hence from the wheel.

    Validates .gitignore rules against project_initializer/templates*/.
    """
    ignored = _git_ignored_template_files()

    assert not ignored, (
        f"git ignores {len(ignored)} template files, so a release build drops them: {ignored[:10]}"
    )


# --- the helpers detect what they claim to ----------------------------------


@pytest.mark.parametrize(
    ("manifest", "path", "included"),
    [
        (
            "recursive-include project_initializer/templates-x *",
            "templates-x/api/down.sql",
            True,
        ),
        (
            "recursive-include project_initializer/templates-x *",
            "templates-x/api/.prettierrc",
            True,
        ),
        (
            "recursive-include project_initializer/templates-x .*",
            "templates-x/api/.prettierrc",
            True,
        ),
        (
            "recursive-include project_initializer/templates-x .*",
            "templates-x/api/down.sql",
            False,
        ),
        (
            "recursive-include project_initializer/templates-x *",
            "templates-y/api/down.sql",
            False,
        ),
        ("include project_initializer/env_defaults.env", "env_defaults.env", True),
    ],
)
def test_when_manifest_text_given_then_inclusion_follows_recursive_include(
    manifest: str, path: str, included: bool
) -> None:
    """The inclusion check follows ``recursive-include`` and ``include`` semantics.

    Validates tests/test_template_packaging_complete.py _manifest_includes().
    """
    assert _manifest_includes(_manifest_rules(manifest), path) is included


@pytest.mark.parametrize(
    ("manifest", "path", "excluded"),
    [
        ("global-exclude *.sql", "templates-x/api/down.sql", True),
        ("global-exclude .git", "templates-x/.gitignore", False),
        (
            "prune project_initializer/templates-x/api/generated",
            "templates-x/api/generated/a.ts",
            True,
        ),
        (
            "prune project_initializer/templates-x/api/generated",
            "templates-x/api/src/a.ts",
            False,
        ),
    ],
)
def test_when_manifest_text_given_then_exclusion_follows_global_exclude_and_prune(
    manifest: str, path: str, excluded: bool
) -> None:
    """The exclusion check follows ``global-exclude`` and ``prune`` semantics.

    Validates tests/test_template_packaging_complete.py _manifest_excludes().
    """
    assert _manifest_excludes(_manifest_rules(manifest), path) is excluded
