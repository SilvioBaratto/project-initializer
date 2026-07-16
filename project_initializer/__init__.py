"""Project Initializer - CLI tool to scaffold full-stack projects."""

from importlib.metadata import PackageNotFoundError, version

try:
    # Single source of truth for the version: the installed package metadata,
    # which setuptools populates from pyproject.toml's [project] version. Never
    # hardcode the version here.
    __version__ = version("project-initializer")
except PackageNotFoundError:  # pragma: no cover - running from a source tree, not installed
    __version__ = "0.0.0+unknown"
