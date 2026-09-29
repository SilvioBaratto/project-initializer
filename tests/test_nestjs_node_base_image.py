"""Guard the NestJS API Docker base image on the Node 24 Active-LTS line.

The lockfiles are regenerated on ``node:24-alpine`` (see ``tasks/plan.md``), so the
build image must match — a lock resolved on one Node major pins native/optional
packages the other's ``npm ci`` then rejects. Reads the real template Dockerfile so
the pin cannot drift.
"""

import re
from pathlib import Path

_TEMPLATES = Path(__file__).resolve().parent.parent / "project_initializer"
_NESTJS_DOCKERFILE = _TEMPLATES / "templates-api-nestjs" / "api" / "Dockerfile"

_FROM_NODE = re.compile(r"^FROM\s+(node:[\w.-]+)", re.MULTILINE)


def _dockerfile_text() -> str:
    return _NESTJS_DOCKERFILE.read_text(encoding="utf-8")


def test_all_node_from_lines_pin_node_24_alpine():
    """Every ``FROM node:`` stage (dev + production) resolves to ``node:24-alpine``."""
    tags = _FROM_NODE.findall(_dockerfile_text())
    assert tags == ["node:24-alpine", "node:24-alpine"], (
        f"expected both node FROM stages on node:24-alpine, found {tags}"
    )


def test_no_node_22_base_remains():
    """No superseded ``node:22`` base tag lingers anywhere in the Dockerfile."""
    assert "node:22" not in _dockerfile_text()
