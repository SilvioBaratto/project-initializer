"""
Tests for issue #13 — Tooltip with touch fallback.

Derived from the two UNIT-verifiable acceptance criteria:
  1. role="tooltip", linked to the trigger via aria-describedby
  2. Shows on hover + focus; touch fallback; Escape dismisses

After the Material 3 migration the tooltip is Angular Material's MatTooltip,
composed as a host directive by both <ui-tooltip> (wrapper) and [uiTooltip]
(directive on the trigger). MatTooltip renders the panel, registers the
description through the CDK AriaDescriber (a role="tooltip" message element
referenced by aria-describedby), shows on mouseenter and keyboard focus,
shows on touch & hold (touchstart long press, M3 "touch & hold tooltips"),
and hides on mouseleave, blur and Escape. These tests therefore accept a
behavior either handled in the unit's own source or delegated to MatTooltip;
the runtime link (aria-describedby -> role="tooltip" element on the focusable
trigger) is asserted by the co-located Vitest spec, which this file checks.

Criteria marked NOT VERIFIABLE in the oracle report ("all tests pass",
SOLID/TDD prose) are intentionally skipped; the token-only styling is checked
against the component's .css.
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


def _read_all(pattern: str, *, exclude_suffix: str | None = None) -> str:
    """Concatenate every file in the tooltip folder matching ``pattern``."""
    candidates = sorted(
        p
        for p in TOOLTIP_DIR.glob(pattern)
        if exclude_suffix is None or not p.name.endswith(exclude_suffix)
    )
    assert candidates, (
        f"No {pattern} file found under {TOOLTIP_DIR} — "
        "tooltip component has not been implemented yet"
    )
    return "\n".join(p.read_text(encoding="utf-8") for p in candidates)


def _tooltip_html() -> str:
    """Return every tooltip template (.html), failing loudly if none exists."""
    return _read_all("*.html")


def _tooltip_ts() -> str:
    """Return every non-spec tooltip TypeScript source (component + directive)."""
    return _read_all("*.ts", exclude_suffix=".spec.ts")


def _tooltip_css() -> str:
    """Return every tooltip stylesheet (.css), failing loudly if none exists."""
    return _read_all("*.css")


def _tooltip_spec() -> str:
    """Return the co-located Vitest spec(s)."""
    return _read_all("*.spec.ts")


def _tooltip_sources() -> str:
    """Return the unit's .ts + .html + .css sources (specs excluded)."""
    return "\n".join((_tooltip_ts(), _tooltip_html(), _tooltip_css()))


def _delegates_to_mat_tooltip(ts: str) -> bool:
    """True when the source composes Angular Material's MatTooltip as a host directive.

    MatTooltip owns the hover (mouseenter/mouseleave), keyboard-focus, touch & hold
    (touchstart long press / touchend) and Escape (overlay keydown) handling.
    """
    return bool(
        re.search(r"from\s+['\"]@angular/material/tooltip['\"]", ts)
        and re.search(r"directive:\s*MatTooltip\b", ts)
    )


def _monitors_subtree_focus(ts: str) -> bool:
    """True when <ui-tooltip> extends MatTooltip's focus monitoring to its projected content.

    MatTooltip subscribes to ``FocusMonitor.monitor(host)`` (host only). Calling
    ``FocusMonitor.monitor(host, true)`` from the wrapper reuses that cached entry
    with checkChildren on, so a descendant's focus (the capture-phase focus/blur
    listener that stands in for focusin/focusout) reaches MatTooltip: a 'keyboard'
    origin shows the tooltip and focus leaving the wrapper hides it.
    """
    return bool(
        re.search(
            r"import\s*\{[^}]*\bFocusMonitor\b[^}]*\}\s*from\s*['\"]@angular/cdk/a11y['\"]",
            ts,
        )
        and re.search(r"FocusMonitor\)\s*\.monitor\([^;]*,\s*true\s*\)", ts)
    )


# ---------------------------------------------------------------------------
# Criterion 1 — role="tooltip", linked to the trigger via aria-describedby
# ---------------------------------------------------------------------------


def test_when_tooltip_template_is_rendered_then_role_tooltip_is_present():
    """
    The tooltip text must be exposed through an element with role="tooltip".
    Criterion: 'role="tooltip"'.

    MatTooltip registers its description via the CDK AriaDescriber with role
    "tooltip", so the unit must compose MatTooltip, and the spec must assert the
    rendered role at runtime.
    """
    ts = _tooltip_ts()
    assert _delegates_to_mat_tooltip(ts), (
        "Expected the tooltip to compose MatTooltip (hostDirectives) from "
        "@angular/material/tooltip, which exposes the text with role=\"tooltip\""
    )
    spec = _tooltip_spec()
    assert re.search(r"getAttribute\('role'\)\)\.toBe\('tooltip'\)", spec), (
        'Expected the Vitest spec to assert the description element has role="tooltip"'
    )


def test_when_tooltip_template_is_rendered_then_trigger_has_aria_describedby():
    """
    The focusable trigger must have aria-describedby so assistive technology
    can announce the tooltip text when the trigger is focused.
    Criterion: 'linked to the trigger via aria-describedby'.

    [uiTooltip] sits on the trigger, so MatTooltip describes it directly. The
    <ui-tooltip> wrapper is not focusable, so it must provide an AriaDescriber
    that retargets the description onto the focusable projected element.
    """
    ts = _tooltip_ts()
    assert re.search(r"selector:\s*'\[uiTooltip\]'", ts), (
        "Expected a [uiTooltip] directive that puts MatTooltip on the trigger itself"
    )
    assert re.search(r"provide:\s*AriaDescriber", ts), (
        "Expected <ui-tooltip> to retarget MatTooltip's AriaDescriber onto the "
        "focusable projected trigger"
    )
    assert "querySelector" in ts, (
        "Expected the wrapper to locate the focusable projected trigger"
    )
    spec = _tooltip_spec()
    assert "aria-describedby" in spec, (
        "Expected the Vitest spec to assert aria-describedby on the trigger"
    )


def test_when_tooltip_template_is_rendered_then_tooltip_element_has_an_id():
    """
    The tooltip description element must carry a unique id so aria-describedby
    can reference it.
    Criterion: 'linked to the trigger via aria-describedby' implies a referenceable id.

    AriaDescriber generates the id. The unit's template must not hand-roll a
    second role="tooltip" bubble or aria-describedby, which would duplicate the
    description; the spec must assert the referenced id is unique.
    """
    html = _tooltip_html()
    assert 'role="tooltip"' not in html and "aria-describedby" not in html, (
        "The template must not hand-roll a tooltip bubble or aria-describedby; "
        "MatTooltip + AriaDescriber own the description"
    )
    spec = _tooltip_spec()
    assert re.search(r"querySelectorAll\(`\[id=", spec) and "toHaveLength(1)" in spec, (
        "Expected the Vitest spec to assert the description id is unique"
    )


def test_when_tooltip_id_and_aria_describedby_are_extracted_then_they_are_equal():
    """
    Round-trip invariant: the trigger's aria-describedby must reference the
    element holding the tooltip text — that is the definition of 'linked'.
    Criterion: 'linked to the trigger via aria-describedby'.

    The ids are generated at runtime, so the round trip is asserted by the spec:
    it resolves aria-describedby with document.getElementById and compares the
    text with the tooltip text, on both the wrapper's trigger and [uiTooltip].
    """
    spec = _tooltip_spec()
    assert "document.getElementById(" in spec, (
        "Expected the spec to resolve aria-describedby ids to their elements"
    )
    assert re.search(r"describedText\(trigger\(fixture\)\)\)\.toBe\('Save changes'\)", spec), (
        "Expected the spec to assert the wrapper's trigger is described by the tooltip text"
    )
    assert re.search(r"describedText\(trigger\(fixture\)\)\)\.toBe\('Delete draft'\)", spec), (
        "Expected the spec to assert [uiTooltip]'s host is described by the tooltip text"
    )


# ---------------------------------------------------------------------------
# Criterion 2 — Shows on hover + focus; touch tap fallback; Escape dismisses
# ---------------------------------------------------------------------------


def test_when_trigger_is_hovered_then_mouseenter_is_handled():
    """
    Hovering the trigger must show the tooltip.
    Criterion: 'Shows on hover'. Handled in source or by MatTooltip (mouseenter).
    """
    ts = _tooltip_ts()
    assert re.search(r"mouseenter|mouseover", ts, re.IGNORECASE) or _delegates_to_mat_tooltip(ts), (
        "Expected a mouseenter handler, or MatTooltip, to show the tooltip on hover"
    )


def test_when_trigger_receives_keyboard_focus_then_focus_event_is_handled():
    """
    Keyboard focus on the trigger must show the tooltip.
    Criterion: 'Shows on ... focus'.

    Kept strict: MatTooltip shows on a FocusMonitor 'keyboard' origin on its own
    host, and the <ui-tooltip> wrapper never takes focus, so the wrapper must
    extend that monitoring to its projected trigger (FocusMonitor.monitor(host,
    true)) instead of re-implementing the origin check. The spec must cover
    keyboard focus and a plain focus() call, which matTooltip ignores.
    """
    ts = _tooltip_ts()
    assert _delegates_to_mat_tooltip(ts) and _monitors_subtree_focus(ts), (
        "Expected <ui-tooltip> to extend MatTooltip's FocusMonitor entry to its "
        "projected trigger with FocusMonitor.monitor(host, true)"
    )
    assert "mostRecentModality" not in ts, (
        "The wrapper must not re-implement the origin check: InputModalityDetector's "
        "modality stays 'keyboard' after any key press, so a later focus() from code "
        "would open the tooltip, which matTooltip does not"
    )
    spec = _tooltip_spec()
    assert "shows when the projected trigger receives keyboard focus" in spec, (
        "Expected the Vitest spec to assert keyboard focus on the projected trigger shows it"
    )
    assert "does not show when focus is moved from code" in spec, (
        "Expected the Vitest spec to assert a plain focus() call does not show it"
    )


def test_when_trigger_is_touch_tapped_then_touch_fallback_event_is_handled():
    """
    Touch-only devices (no hover) must still reach the tooltip.
    Criterion: 'touch tap fallback'.

    M3 uses touch & hold for tooltips (accessibility/writing_and_text.md
    "Use touch & hold tooltips"); MatTooltip implements it as a touchstart long
    press, so a touchstart/click handler in source or MatTooltip satisfies it.
    """
    ts = _tooltip_ts()
    assert re.search(r"touchstart|click\b", ts, re.IGNORECASE) or _delegates_to_mat_tooltip(ts), (
        "Expected a touchstart handler, or MatTooltip's touch & hold, as the touch fallback"
    )
    assert "touch & hold" in _tooltip_spec(), (
        "Expected the Vitest spec to exercise the touch & hold path"
    )


def test_when_escape_is_pressed_then_tooltip_is_dismissed():
    """
    The Escape key must dismiss an active tooltip.
    Criterion: 'Escape dismisses'. Handled in source or by MatTooltip, which hides
    on ESCAPE from its overlay keydown stream.
    """
    ts = _tooltip_ts()
    own_handler = re.search(r"['\"]Escape['\"]|\"escape\"|'escape'", ts, re.IGNORECASE)
    assert own_handler or _delegates_to_mat_tooltip(ts), (
        "Expected an Escape key check, or MatTooltip, to dismiss the tooltip"
    )
    assert "pressKey(trigger(fixture), 'Escape', 27)" in _tooltip_spec(), (
        "Expected the Vitest spec to assert Escape dismisses the tooltip"
    )


def test_when_escape_handler_is_present_then_it_unconditionally_hides_not_toggles():
    """
    Idempotence invariant: pressing Escape must always hide the tooltip, never toggle it.
    A toggle (e.g. `visible = !visible`) would leave the tooltip open on a second Escape press.
    Criterion: 'Escape dismisses' implies the dismiss operation is idempotent.

    When the unit has its own Escape branch it must not toggle. When Escape is
    delegated to MatTooltip (which calls hide(0)), the spec must still assert
    that a second Escape keeps it hidden.
    """
    ts = _tooltip_ts()
    # Find the Escape branch (up to 6 lines after the 'Escape' literal)
    escape_region_match = re.search(
        r"['\"]Escape['\"].*?(?:\n.+?){0,6}",
        ts,
        re.IGNORECASE | re.DOTALL,
    )
    if escape_region_match:
        region = escape_region_match.group(0)
        # A toggle pattern would be: visible = !visible  /  show = !show  /  .set(!...)
        has_toggle = re.search(r"=\s*!", region)
        assert not has_toggle, (
            "Escape handler must unconditionally hide (set to false), not toggle — "
            "toggling breaks the idempotence guarantee"
        )
    else:
        assert _delegates_to_mat_tooltip(ts), "Escape handling must be present"
    assert "keeps the tooltip hidden when pressed twice" in _tooltip_spec(), (
        "Expected the Vitest spec to assert Escape is idempotent"
    )


def test_when_trigger_mouse_leaves_then_mouseleave_is_handled():
    """
    When the cursor leaves the trigger, the tooltip must be hidden.
    Criterion: hover shows → hover-end hides; tooltip 'visible only when active'.
    Handled in source or by MatTooltip (mouseleave).
    """
    ts = _tooltip_ts()
    assert re.search(r"mouseleave|mouseout", ts, re.IGNORECASE) or _delegates_to_mat_tooltip(ts), (
        "Expected a mouseleave handler, or MatTooltip, to hide the tooltip when the cursor leaves"
    )


def test_when_trigger_loses_focus_then_blur_or_focusout_is_handled():
    """
    When the trigger loses keyboard focus, the tooltip must be hidden.
    Criterion: focus shows → blur hides; tooltip 'visible only when active'.

    Kept strict: either the unit's own focusout/blur handler, or the wrapper's
    subtree FocusMonitor entry, which emits a null origin when focus leaves the
    wrapper (not when it moves inside it) and MatTooltip turns into hide(0).
    The spec must assert both.
    """
    ts = _tooltip_ts()
    own_handler = re.search(r"\((?:focusout|blur)\)|addEventListener\(\s*['\"](?:focusout|blur)['\"]", ts)
    assert own_handler or _monitors_subtree_focus(ts), (
        "Expected a focusout/blur handler, or subtree FocusMonitor monitoring, to hide "
        "the tooltip when focus leaves"
    )
    spec = _tooltip_spec()
    assert "hides when keyboard focus leaves the wrapper" in spec, (
        "Expected the Vitest spec to assert focus leaving the wrapper hides the tooltip"
    )
    assert "stays open while keyboard focus moves between elements inside the wrapper" in spec, (
        "Expected the Vitest spec to assert focus moving inside the wrapper keeps it open"
    )


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Invariant from criterion 2: "Shows on hover + focus; touch fallback"
# The domain of valid show-trigger event names is {mouseenter, focusin, touchstart}:
# mouseenter = hover, focusin = keyboard focus, touchstart = M3 touch & hold.
# (The pre-migration tap-to-toggle `click` fallback is gone: a tap activates the
# trigger, and M3 specifies touch & hold for tooltips.)
# For EVERY event in that domain a handler must exist in source, or — for events
# MatTooltip listens to on its host — the unit must compose MatTooltip. Focus on a
# projected descendant (focusin) is delegated only when the wrapper also monitors
# its subtree with FocusMonitor (capture-phase focus, the focusin equivalent).

_SHOW_TRIGGER_EVENTS = ["mouseenter", "focusin", "touchstart"]
_MAT_TOOLTIP_HOST_EVENTS = {"mouseenter", "touchstart"}
_FOCUS_MONITOR_SUBTREE_EVENTS = {"focusin"}


@settings(max_examples=len(_SHOW_TRIGGER_EVENTS), deadline=None)
@given(st.sampled_from(_SHOW_TRIGGER_EVENTS))
def test_when_a_valid_show_trigger_event_is_given_then_a_handler_exists_in_source(
    event_name: str,
) -> None:
    """
    Invariant (never-raises for valid input): every event in the domain of
    show-triggers must be handled, in the TypeScript source or by MatTooltip.
    Criterion: 'Shows on hover + focus; touch fallback'.
    """
    ts = _tooltip_ts()
    handled_in_source = re.search(re.escape(event_name), ts, re.IGNORECASE)
    delegated = (
        event_name in _MAT_TOOLTIP_HOST_EVENTS and _delegates_to_mat_tooltip(ts)
    ) or (
        event_name in _FOCUS_MONITOR_SUBTREE_EVENTS
        and _delegates_to_mat_tooltip(ts)
        and _monitors_subtree_focus(ts)
    )
    assert handled_in_source or delegated, (
        f"Expected a handler for trigger event '{event_name}' in the tooltip TypeScript "
        f"(or MatTooltip for {sorted(_MAT_TOOLTIP_HOST_EVENTS)}, or MatTooltip plus "
        f"subtree FocusMonitor monitoring for {sorted(_FOCUS_MONITOR_SUBTREE_EVENTS)}), "
        "but none was found."
    )


# ---------------------------------------------------------------------------
# Structure and M3 styling (Material 3 migration)
# ---------------------------------------------------------------------------


def test_when_tooltip_component_is_read_then_public_api_and_file_split_are_kept():
    """
    <ui-tooltip text="..."> keeps its selector and `text` input (now MatTooltip's
    message exposed as `text`), uses OnPush, and is split into .ts + .html + .css
    wired with templateUrl and styleUrl.
    """
    ts = _tooltip_ts()
    assert "selector: 'ui-tooltip'" in ts
    assert re.search(r"'matTooltip:\s*text'", ts), "Expected the `text` input to be kept"
    assert "ChangeDetectionStrategy.OnPush" in ts
    assert "templateUrl: './tooltip.html'" in ts
    assert "styleUrl: './tooltip.css'" in ts
    for name in ("tooltip.ts", "tooltip.html", "tooltip.css"):
        assert (TOOLTIP_DIR / name).is_file(), f"Expected {name} in {TOOLTIP_DIR}"


def test_when_tooltip_sources_are_read_then_styling_is_token_only_and_tailwind_free():
    """
    Dark mode and theming come from M3 tokens: the unit's CSS has no color
    literals, !important or ::ng-deep, and no source carries Tailwind utilities
    (the panel is Material's plain tooltip on inverse-surface tokens).
    """
    css = _tooltip_css()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", css)
    assert "!important" not in css and "::ng-deep" not in css
    sources = _tooltip_sources()
    tailwind = re.search(
        r"\b(?:dark:|md:|lg:|sm:|hover:|focus:)|\b(?:bg-|text-(?:xs|sm|base)|rounded\b|"
        r"shadow-|px-[0-9]|py-[0-9]|animate-|sr-only|pointer-events-none|whitespace-nowrap)",
        sources,
    )
    assert not tailwind, f"Tailwind utility left in tooltip sources: {tailwind.group(0)!r}"
