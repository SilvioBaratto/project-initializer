"""Pins what the frontend dependency upgrade moved: the runtime image and the CI actions.

A moving nginx tag would let the runtime stage change nginx branch between two
builds, and an action left on an old major keeps a job on a runtime that GitHub
has retired.
"""

import re
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

_FROM_LINE = re.compile(r"^FROM\s+(?P<image>\S+)", re.M)
_PINNED_NGINX = re.compile(r"nginx:\d+\.\d+(\.\d+)?-alpine")
_ACTION_USE = re.compile(r"uses:\s*(?P<action>actions/[\w-]+)@(?P<ref>\S+)")


def _workflow_id(path: Path) -> str:
    return str(path.relative_to(_REPO))


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
@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=_workflow_id)
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
    assert refs, f"{_workflow_id(workflow)} no longer uses {action}"
    assert set(refs) == {"v7"}, f"{_workflow_id(workflow)} uses {action}@{refs}"
