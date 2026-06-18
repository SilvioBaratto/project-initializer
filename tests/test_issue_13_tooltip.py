"""
Tests for issue #13 — Tooltip with touch fallback.

Source-blind: derived entirely from the two UNIT-verifiable acceptance criteria:
  1. role="tooltip", linked to the trigger via aria-describedby
  2. Shows on hover + focus; touch tap fallback; Escape dismisses

Criteria marked NOT VERIFIABLE in the oracle report (dark-mode tokens,
"all tests pass", SOLID/TDD prose) are intentionally skipped.
"""

import re
from pathlib import Path

from hypothesis import given, settings, strategies as st

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

TOOLTIP_DIR = (
    Path(__file__).parent.parent
    / "project_initializer"
    / "templates"
    / "frontend"
    / "src"
    / "app"
    / "shared"
    / "ui"
    / "tooltip"
)


def _tooltip_html() -> str:
    """Return the tooltip component template, failing loudly if not yet created."""
    candidates = list(TOOLTIP_DIR.glob("*.html"))
    assert candidates, (
        f"No .html template found under {TOOLTIP_DIR} — "
        "tooltip component has not been implemented yet"
    )
    return candidates[0].read_text(encoding="utf-8")


def _tooltip_ts() -> str:
    """Return the tooltip component TypeScript, failing loudly if not yet created."""
    candidates = [
        p for p in TOOLTIP_DIR.glob("*.ts") if not p.name.endswith(".spec.ts")
    ]
    assert candidates, (
        f"No .ts source file found under {TOOLTIP_DIR} — "
        "tooltip component has not been implemented yet"
    )
    return candidates[0].read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Criterion 1 — role="tooltip", linked to the trigger via aria-describedby
# ---------------------------------------------------------------------------


def test_when_tooltip_template_is_rendered_then_role_tooltip_is_present():
    """
    The element wrapping tooltip content must carry role="tooltip".
    Criterion: 'role="tooltip"'.
    """
    html = _tooltip_html()
    assert 'role="tooltip"' in html, (
        'Expected role="tooltip" in the tooltip template but it was absent'
    )


def test_when_tooltip_template_is_rendered_then_trigger_has_aria_describedby():
    """
    The trigger element must have aria-describedby so assistive technology
    can announce the tooltip text when the trigger is focused.
    Criterion: 'linked to the trigger via aria-describedby'.
    """
    html = _tooltip_html()
    assert "aria-describedby" in html, (
        "Expected aria-describedby on the trigger element but it was absent"
    )


def test_when_tooltip_template_is_rendered_then_tooltip_element_has_an_id():
    """
    The tooltip element must carry an id so aria-describedby can reference it.
    Criterion: 'linked to the trigger via aria-describedby' implies a referenceable id.
    Accepts both a static id="..." and an Angular-bound [id]="..." form.
    """
    html = _tooltip_html()
    assert re.search(r"\bid=[\"\[]", html), (
        "Expected the tooltip element to have an id attribute (static or bound)"
    )


def test_when_tooltip_id_and_aria_describedby_are_extracted_then_they_are_equal():
    """
    Round-trip structural invariant: the tooltip element's id must equal the
    aria-describedby value on the trigger — that is the definition of 'linked'.
    Criterion: 'linked to the trigger via aria-describedby'.

    Choice: if the template uses Angular property-binding ([id], [attr.aria-describedby])
    with the same variable, the test accepts that the same binding token appears on
    both attributes, which satisfies the link contract at the template level.
    """
    html = _tooltip_html()

    # Try to extract a static id from the tooltip element
    tooltip_id_match = re.search(
        r'role="tooltip"[^>]*\bid="([^"]+)"'
        r"|"
        r'\bid="([^"]+)"[^>]*role="tooltip"',
        html,
    )
    describedby_match = re.search(r'aria-describedby="([^"]+)"', html)

    if tooltip_id_match and describedby_match:
        # Both are static — values must be identical
        tooltip_id = tooltip_id_match.group(1) or tooltip_id_match.group(2)
        describedby_val = describedby_match.group(1)
        assert tooltip_id == describedby_val, (
            f"aria-describedby='{describedby_val}' must equal "
            f"the tooltip element's id='{tooltip_id}'"
        )
    else:
        # At least one is Angular-bound — verify the same binding token appears
        # on both the id and aria-describedby sides (structural link).
        bound_id = re.search(r'\[(?:id|attr\.id)\]="([^"]+)"', html)
        bound_dby = re.search(r'\[attr\.aria-describedby\]="([^"]+)"', html)
        assert bound_id or describedby_match, (
            "Tooltip element must declare an id (static or bound)"
        )
        assert bound_dby or describedby_match, (
            "Trigger must declare aria-describedby (static or bound)"
        )
        if bound_id and bound_dby:
            assert bound_id.group(1) == bound_dby.group(1), (
                f"Bound id expression '{bound_id.group(1)}' must equal "
                f"aria-describedby expression '{bound_dby.group(1)}'"
            )


# ---------------------------------------------------------------------------
# Criterion 2 — Shows on hover + focus; touch tap fallback; Escape dismisses
# ---------------------------------------------------------------------------


def test_when_trigger_is_hovered_then_mouseenter_is_handled():
    """
    Hovering the trigger must show the tooltip.
    Criterion: 'Shows on hover'.
    """
    ts = _tooltip_ts()
    assert re.search(r"mouseenter|mouseover", ts, re.IGNORECASE), (
        "Expected mouseenter/mouseover handler to show the tooltip on hover"
    )


def test_when_trigger_receives_keyboard_focus_then_focus_event_is_handled():
    """
    Keyboard focus on the trigger must show the tooltip.
    Criterion: 'Shows on ... focus'.
    """
    ts = _tooltip_ts()
    assert re.search(r"focusin|focus\b", ts, re.IGNORECASE), (
        "Expected focus/focusin handler to show the tooltip on keyboard focus"
    )


def test_when_trigger_is_touch_tapped_then_touch_fallback_event_is_handled():
    """
    Touch tap must show the tooltip for iOS / touch-only devices that have no hover.
    Criterion: 'touch tap fallback'.
    Simplest valid interpretation: a touchstart or click handler provides the fallback.
    """
    ts = _tooltip_ts()
    assert re.search(r"touchstart|click\b", ts, re.IGNORECASE), (
        "Expected touchstart or click handler as touch-tap fallback for iOS"
    )


def test_when_escape_is_pressed_then_tooltip_is_dismissed():
    """
    The Escape key must dismiss an active tooltip.
    Criterion: 'Escape dismisses'.
    """
    ts = _tooltip_ts()
    assert re.search(r"['\"]Escape['\"]|\"escape\"|'escape'", ts, re.IGNORECASE), (
        "Expected an Escape key check in a keyboard event handler to dismiss the tooltip"
    )


def test_when_escape_handler_is_present_then_it_unconditionally_hides_not_toggles():
    """
    Idempotence invariant: pressing Escape must always hide the tooltip, never toggle it.
    A toggle (e.g. `visible = !visible`) would leave the tooltip open on a second Escape press.
    Criterion: 'Escape dismisses' implies the dismiss operation is idempotent.
    """
    ts = _tooltip_ts()
    # Find the Escape branch (up to 6 lines after the 'Escape' literal)
    escape_region_match = re.search(
        r"['\"]Escape['\"].*?(?:\n.+?){0,6}",
        ts,
        re.IGNORECASE | re.DOTALL,
    )
    assert escape_region_match, "Escape handler must be present"
    region = escape_region_match.group(0)
    # A toggle pattern would be: visible = !visible  /  show = !show  /  .set(!...)
    has_toggle = re.search(r"=\s*!", region)
    assert not has_toggle, (
        "Escape handler must unconditionally hide (set to false), not toggle — "
        "toggling breaks the idempotence guarantee"
    )


def test_when_trigger_mouse_leaves_then_mouseleave_is_handled():
    """
    When the cursor leaves the trigger, the tooltip must be hidden.
    Criterion: hover shows → hover-end hides; tooltip 'visible only when active'.
    """
    ts = _tooltip_ts()
    assert re.search(r"mouseleave|mouseout", ts, re.IGNORECASE), (
        "Expected mouseleave/mouseout handler to hide the tooltip when cursor leaves"
    )


def test_when_trigger_loses_focus_then_blur_or_focusout_is_handled():
    """
    When the trigger loses keyboard focus, the tooltip must be hidden.
    Criterion: focus shows → blur hides; tooltip 'visible only when active'.
    """
    ts = _tooltip_ts()
    assert re.search(r"focusout|blur\b", ts, re.IGNORECASE), (
        "Expected focusout/blur handler to hide the tooltip when focus leaves"
    )


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Invariant from criterion 2: "Shows on hover + focus; touch tap fallback"
# The domain of valid show-trigger event names is: {mouseenter, focusin, touchstart, click}.
# For EVERY event in that domain the TypeScript source must contain a handler.
# This is a "never-raises for valid input" invariant — no valid trigger may be silently ignored.

_SHOW_TRIGGER_EVENTS = ["mouseenter", "focusin", "touchstart", "click"]


@settings(max_examples=len(_SHOW_TRIGGER_EVENTS))
@given(st.sampled_from(_SHOW_TRIGGER_EVENTS))
def test_when_a_valid_show_trigger_event_is_given_then_a_handler_exists_in_source(
    event_name: str,
) -> None:
    """
    Invariant (never-raises for valid input): every event in the spec-defined domain of
    show-triggers must have a corresponding handler in the TypeScript source.
    Criterion: 'Shows on hover + focus; touch tap fallback'.

    The domain {mouseenter, focusin, touchstart, click} is derived directly from the
    criterion text — mouseenter = hover, focusin = focus, touchstart/click = touch tap.
    """
    ts = _tooltip_ts()
    assert re.search(re.escape(event_name), ts, re.IGNORECASE), (
        f"Expected a handler for trigger event '{event_name}' in the tooltip TypeScript "
        f"but none was found. All events in the show-trigger domain must be handled."
    )
