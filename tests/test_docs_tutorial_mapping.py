"""Doc-drift guards for the FastAPI-tutorial → layered-layout mapping note (#27).

Reads the real generated root ``templates-api-fastapi/CLAUDE.md`` and asserts a
note maps the tutorial's flat ``routers/`` concept onto this scaffold's layered
``app/api/v1/`` layout (router -> service -> repository -> model -> schema), and
that the note states plainly the mapping is conceptual — no code is moved.

token/supabase overlays do NOT ship their own root CLAUDE.md, so guarding the
base doc guards every variant.
"""

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = _ROOT / "project_initializer" / "templates-api-fastapi" / "CLAUDE.md"


def _doc() -> str:
    return CLAUDE_MD.read_text(encoding="utf-8")


def test_when_claude_md_read_then_tutorial_mapping_section_exists():
    """when the doc is read, a section mapping the FastAPI tutorial is present."""
    assert "tutorial" in _doc().lower()


def test_when_claude_md_read_then_routers_maps_to_app_api_v1():
    """when the doc is read, the tutorial routers/ -> app/api/v1/ mapping is stated."""
    doc = _doc()
    assert "routers/" in doc
    assert "app/api/v1/" in doc


def test_when_claude_md_read_then_layer_split_is_spelled_out():
    """when the doc is read, the router->service->repository->model->schema split is named."""
    doc = _doc().lower()
    for layer in ("router", "service", "repository", "model", "schema"):
        assert layer in doc


def test_when_claude_md_read_then_note_states_no_code_is_moved():
    """when the doc is read, the note states the mapping is conceptual with no code moved."""
    doc = _doc().lower()
    assert "no code" in doc
    assert "conceptual" in doc or "documentation only" in doc
