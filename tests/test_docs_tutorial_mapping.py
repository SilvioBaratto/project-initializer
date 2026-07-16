"""Doc-drift guards for the FastAPI-tutorial → hexagonal-layout mapping note (#27).

Reads the real ``templates-api-fastapi/CLAUDE.md`` and asserts a note maps the
tutorial's flat ``routers/`` concept onto this scaffold's hexagonal layout
(router -> service -> repository -> model -> schema across four layers), and that
the note states plainly the code is physically restructured (not just conceptual)
after the hexagonal migration.

token/supabase overlays do NOT ship their own root CLAUDE.md, so guarding the
base doc guards every variant.
"""

from project_initializer.docs_generator import generate_root_claude


def _doc() -> str:
    # Docs are generated per-flag (docs_generator), not shipped static. The
    # tutorial-mapping note lives in the FastAPI root CLAUDE.md; auth is
    # irrelevant to it, so the no-auth FastAPI variant is representative.
    return generate_root_claude("fastapi", None)


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


def test_when_claude_md_read_then_note_states_code_is_physically_restructured():
    """when the doc is read, the note states the code is a real restructure across layers.

    After the hexagonal migration the code IS physically split across
    domain/application/infrastructure/api, so the doc must say so (not claim a
    conceptual-only mapping, which would be stale/false).
    """
    doc = _doc().lower()
    assert "restructure" in doc
    assert "domain" in doc and "application" in doc and "infrastructure" in doc
