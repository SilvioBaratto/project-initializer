"""Lazy access to ``tomllib`` for tests that must still collect on Python 3.10.

``tomllib`` joined the standard library in 3.11, while the package supports 3.10.
A module-level ``import tomllib`` would break collection of a whole module there,
and a module-level ``importorskip`` would skip its unrelated tests too; resolving
the module on first use skips only the test that reads TOML.
"""

import pytest


class _LazyTomllib:
    def __getattr__(self, name: str):
        return getattr(pytest.importorskip("tomllib"), name)


tomllib = _LazyTomllib()
