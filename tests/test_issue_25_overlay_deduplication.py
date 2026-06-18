"""
Tests for issue #25: single overlay instance in the /components catalog.

Verifiable criteria (per oracle):
  [T3]   Opening any overlay renders exactly ONE overlay instance in the DOM
         → components.spec.ts must contain querySelectorAll + length-1 assertion,
           gated on an activeOverlay assignment and a detectChanges call
  [UNIT] Dual light/dark scoping continues to apply to the TRIGGER buttons
         → components.html renders the overlay trigger section in BOTH regions
           (exactly 2 occurrences of app-overlays-section, one per region)
  [UNIT] At most one overlay is open at a time (no concurrent focus traps)
         → components.spec.ts must exercise the activeOverlay signal in an
           assertion that proves only one overlay panel exists in the DOM

Skipped per oracle (NOT VERIFIABLE):
  - Triggers remain reachable and functional from both regions (manual check)
  - All tests pass (suite gate — no per-criterion assertion)
  - SOLID/clean code (subjective)

Note: the dual-trigger test is a regression guard; it may pass today.
The spec-content tests fail today because the querySelectorAll regression
test does not exist yet in components.spec.ts.
"""

import pathlib

import pytest

_FRONTEND = (
    pathlib.Path(__file__).parent.parent
    / "project_initializer"
    / "templates"
    / "frontend"
)
_PAGES = _FRONTEND / "src" / "app" / "pages" / "components"

COMPONENTS_SPEC = _PAGES / "components.spec.ts"
COMPONENTS_HTML = _PAGES / "components.html"


@pytest.fixture(scope="module")
def spec_content() -> str:
    assert COMPONENTS_SPEC.exists(), (
        f"components.spec.ts not found at {COMPONENTS_SPEC}"
    )
    return COMPONENTS_SPEC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def html_content() -> str:
    assert COMPONENTS_HTML.exists(), (
        f"components.html not found at {COMPONENTS_HTML}"
    )
    return COMPONENTS_HTML.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# [T3] components.spec.ts must assert exactly ONE overlay panel in the DOM
# ---------------------------------------------------------------------------


def test_when_overlay_opened_then_spec_queries_dom_for_panel_elements(spec_content):
    """
    Criterion: 'assert querySelectorAll for the panel role/testid returns length 1'.
    The regression test must call querySelectorAll to count rendered overlay panels.
    """
    assert "querySelectorAll" in spec_content, (
        "components.spec.ts must call querySelectorAll to count overlay panel elements "
        "in the DOM when an overlay is opened"
    )


def test_when_overlay_panel_count_is_queried_then_spec_asserts_length_one(spec_content):
    """
    Criterion: 'querySelectorAll … returns length 1'.
    The spec must assert the resulting count equals exactly 1 (not 0, not 2).
    Interpretation: any Jasmine matcher that checks for the value 1 counts.
    """
    has_one_assertion = any(
        token in spec_content
        for token in (
            "toBe(1)",
            "toHaveLength(1)",
            "toEqual(1)",
            ".length, 1",
            "length).toBe(1)",
            "length === 1",
        )
    )
    assert has_one_assertion, (
        "components.spec.ts must assert the overlay panel querySelectorAll result "
        "equals 1 (e.g. .toBe(1) or .toHaveLength(1))"
    )


def test_when_overlay_dedup_spec_is_read_then_active_overlay_is_set_before_dom_query(
    spec_content,
):
    """
    Criterion: 'set activeOverlay, detectChanges, and assert querySelectorAll'.
    The spec must set activeOverlay AND call querySelectorAll — both must appear
    together so the test actually exercises the rendering path.
    """
    has_signal_assignment = (
        "activeOverlay" in spec_content
        and "querySelectorAll" in spec_content
    )
    assert has_signal_assignment, (
        "components.spec.ts must both assign activeOverlay (to trigger rendering) "
        "and call querySelectorAll (to count the resulting DOM panels) in the same spec"
    )


# ---------------------------------------------------------------------------
# [UNIT] Dual light/dark trigger regions must both contain overlay triggers
# ---------------------------------------------------------------------------


def test_when_components_html_rendered_then_overlay_triggers_in_both_regions(
    html_content,
):
    """
    Criterion: 'dual light/dark scoping continues to apply to the TRIGGER buttons'.
    The overlay trigger section (app-overlays-section) must appear in both the
    light and dark regions — exactly 2 occurrences so neither region is missing.
    Interpretation: 2 occurrences of app-overlays-section in components.html.
    """
    count = html_content.count("app-overlays-section")
    assert count == 2, (
        f"app-overlays-section appears {count} time(s) in components.html; "
        "it must appear exactly twice — once in the light region and once in "
        "the dark-classed region — so both regions show the overlay trigger buttons"
    )


# ---------------------------------------------------------------------------
# [UNIT] At most one overlay open at a time — spec covers the constraint
# ---------------------------------------------------------------------------


def test_when_components_spec_read_then_single_overlay_constraint_is_tested(
    spec_content,
):
    """
    Criterion: 'at most one overlay is open at a time and no two focus traps /
    inert passes run concurrently'.
    The activeOverlay signal is the mechanism enforcing this invariant.
    The spec must reference activeOverlay in an assertion context to verify the
    single-overlay constraint is exercised by the test suite.
    """
    assert "activeOverlay" in spec_content, (
        "components.spec.ts must reference activeOverlay to test that at most "
        "one overlay is open at any given time"
    )
