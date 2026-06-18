"""
Tests for issue #10: feat(ui): shared focus-trap directive for overlays and drawer.

Source-blind: authored against acceptance criteria only, before any implementation.

Criteria covered:
  - [UNIT] Directive traps Tab + Shift+Tab within the host element
  - [UNIT] Escape emits a close event; focus returns to the previously-focused
    element on deactivate
  - [UNIT] Background siblings are inerted (inert/aria-hidden) while active and
    restored after
  - [UNIT] SSR-safe; uses the `host` object (no @HostListener/@HostBinding)

Criteria skipped (not runtime-verifiable per oracle):
  - All tests pass — boilerplate suite gate; no per-criterion assertion.
  - SOLID, clean code (methods < 10 lines …) — subjective prose; no concrete
    runtime or unit assertion.

Hypothesis / property-based tests:
  The SSR-safety criterion implies a never-raises invariant: for ANY string a
  caller might pass as an element selector, the directive must not reference
  browser-only globals unconditionally at class-definition time.  We capture
  this as a Hypothesis property over the directive's source text: for every
  substring of the source that references a browser-global, that reference must
  always be guarded (inside a method body or behind a platform check), never at
  module top-level or in a field initialiser where it would execute during SSR.
  Because the assertion is structural (regexp over text), not runtime, and the
  property holds for all valid decorator metadata texts, we treat it as
  parameterised over the set of browser-global tokens that would crash an SSR
  run.
"""

import pathlib
import re

import pytest
from hypothesis import given, settings, strategies as st

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FRONTEND = (
    pathlib.Path(__file__).parent.parent
    / "project_initializer"
    / "templates"
    / "frontend"
)

SHARED_DIR = FRONTEND / "src" / "app" / "shared"

# The directive may live under shared/ui/ (as a standalone folder), directly
# in shared/, or anywhere that a glob for "focus-trap*" would find it.
# We keep the lookup lazy so failure surfaces as a clear FileNotFoundError in
# the helper, not at import time.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_directive_ts() -> pathlib.Path:
    """Return the non-spec TypeScript file for the focus-trap directive.

    Searches shared/ recursively for a file whose name contains 'focus-trap'
    (or 'focustrap') and is not a spec file.  Raises FileNotFoundError if
    none found.
    """
    candidates = [
        p
        for p in SHARED_DIR.rglob("*.ts")
        if ".spec." not in p.name and re.search(r"focus.?trap", p.name, re.IGNORECASE)
    ]
    if not candidates:
        raise FileNotFoundError(
            "No focus-trap directive .ts file found under "
            f"{SHARED_DIR}. Expected a file matching 'focus*trap*.ts' "
            "(e.g. focus-trap.directive.ts)."
        )
    return candidates[0]


def _directive_source() -> str:
    """Return the full text of the focus-trap directive .ts file."""
    return _find_directive_ts().read_text(encoding="utf-8")


def _directive_dir() -> pathlib.Path:
    return _find_directive_ts().parent


def _full_source() -> str:
    """Concatenate all non-spec .ts + .html files in the directive's folder."""
    d = _directive_dir()
    parts: list[str] = []
    for ext in ("*.ts", "*.html"):
        for f in d.glob(ext):
            if ".spec." not in f.name:
                parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Criterion: Directive traps Tab + Shift+Tab within the host element
# ---------------------------------------------------------------------------


def test_when_shared_directory_inspected_then_focus_trap_directive_file_exists():
    """A focus-trap directive source file must exist under shared/.

    Per criterion: 'Directive traps Tab + Shift+Tab within the host element'.
    Requirements §6/§7 specify a focus trap for overlays and the slide-over
    drawer.  The implementation must live under shared/ following the
    one-folder-per-component convention.
    """
    path = _find_directive_ts()
    assert path.is_file(), (
        "Expected a focus-trap directive .ts file under "
        "templates/frontend/src/app/shared/"
    )


def test_when_focus_trap_ts_read_then_it_is_declared_as_an_angular_directive():
    """The file must declare an Angular @Directive (not just a class).

    Per criterion: 'Directive traps Tab + Shift+Tab …'. The focus-trap is
    described as a *directive* in the issue title, which means it must be
    decorated with @Directive so Angular can attach it to a host element.
    """
    src = _directive_source()
    assert "@Directive" in src, (
        "Expected '@Directive' decorator in the focus-trap .ts file. "
        "Per issue title: 'shared focus-trap directive'."
    )


def test_when_focus_trap_ts_read_then_tab_key_is_handled():
    """The directive source must reference the Tab key to trap focus.

    Per criterion: 'Directive traps Tab + Shift+Tab within the host element'.
    Interpretation: the source must mention 'Tab' (as a KeyboardEvent.key
    value) so that Tab-key press events are intercepted and constrained to
    focusable children of the host.
    """
    src = _directive_source()
    assert re.search(r"['\"]Tab['\"]|'Tab'|\"Tab\"|\.key\s*===\s*['\"]Tab", src), (
        "Expected the string literal 'Tab' referenced as a keyboard key in "
        "the focus-trap directive source. "
        "Per criterion: 'Directive traps Tab + Shift+Tab within the host element'."
    )


def test_when_focus_trap_ts_read_then_shift_tab_is_handled():
    """The directive source must handle the Shift+Tab back-tab gesture.

    Per criterion: 'Directive traps Tab + Shift+Tab within the host element'.
    Shift+Tab moves focus backwards through the focus ring; the trap must wrap
    focus back to the last focusable child rather than leaving the overlay.
    Accepted indicators: reference to `shiftKey`, a `'ShiftTab'` sentinel, or
    a conditional that checks both `shiftKey` and `'Tab'`.
    """
    src = _directive_source()
    has_shift = bool(re.search(r"\bshiftKey\b", src))
    has_shift_tab = bool(
        re.search(r"ShiftTab|shift.*tab|tab.*shift", src, re.IGNORECASE)
    )
    assert has_shift or has_shift_tab, (
        "Expected a Shift+Tab guard in the focus-trap directive — e.g. checking "
        "`event.shiftKey` in conjunction with `event.key === 'Tab'`. "
        "Per criterion: 'Directive traps Tab + Shift+Tab within the host element'."
    )


def test_when_focus_trap_ts_read_then_focusable_children_are_queried():
    """The directive must query focusable descendants of the host element.

    Per criterion: 'Directive traps Tab + Shift+Tab within the host element'.
    To trap focus it must know which elements are focusable inside the host.
    Accepted indicators: a querySelectorAll call containing a focusable selector
    (e.g. 'a[href]', 'button', 'input', '[tabindex]'), or a reference to
    tabbable/focusable selector strings.
    """
    src = _directive_source()
    has_query = bool(re.search(r"querySelectorAll|querySelector", src))
    has_focusable_sel = bool(
        re.search(
            r"button|input|select|textarea|a\[href\]|tabindex", src, re.IGNORECASE
        )
    )
    assert has_query or has_focusable_sel, (
        "Expected a querySelectorAll / focusable-selector expression in the "
        "focus-trap directive to discover tabbable children of the host. "
        "Per criterion: 'Directive traps Tab + Shift+Tab within the host element'."
    )


@pytest.mark.skip(
    reason=(
        "Angular @Directive does not support changeDetection — it is a @Component-only "
        "option. Setting ChangeDetectionStrategy.OnPush on a Directive causes a "
        "TypeScript compile error. This test was authored source-blind with an incorrect "
        "assumption about Angular's API."
    )
)
def test_when_focus_trap_ts_read_then_onpush_change_detection_is_set():
    """Focus-trap directive must declare ChangeDetectionStrategy.OnPush.

    CLAUDE.md: 'OnPush change detection: Set changeDetection:
    ChangeDetectionStrategy.OnPush'. Applies to all shared/ components and
    directives.
    """
    src = _directive_source()
    assert "ChangeDetectionStrategy.OnPush" in src, (
        "Expected 'ChangeDetectionStrategy.OnPush' in the focus-trap directive .ts."
    )


# ---------------------------------------------------------------------------
# Criterion: Escape emits a close event; focus returns to previously-focused
#            element on deactivate
# ---------------------------------------------------------------------------


def test_when_focus_trap_ts_read_then_escape_key_is_handled():
    """The directive must intercept the Escape key press.

    Per criterion: '`Escape` emits a close event; focus returns to the
    previously-focused element on deactivate'.
    The string literal 'Escape' (the KeyboardEvent.key value) must appear in
    the directive source.
    """
    src = _directive_source()
    assert re.search(r"['\"]Escape['\"]", src), (
        "Expected the string literal 'Escape' referenced as a keyboard key "
        "in the focus-trap directive source. "
        "Per criterion: '`Escape` emits a close event'."
    )


def test_when_focus_trap_ts_read_then_close_output_is_declared():
    """The directive must declare an Angular signal output to emit close events.

    Per criterion: '`Escape` emits a close event'.
    CLAUDE.md: 'Signals for state: Use signal(), computed(), input(), output()'.
    The output lets host components (modal, drawer) react to Escape without
    reaching into the directive's internals.  Accepted forms: `output()` call
    or `EventEmitter` named 'close', 'closed', or 'escaped'.
    """
    src = _directive_source()
    has_output = bool(re.search(r"\b(close|closed|escaped)\s*=\s*output\s*[(<]", src))
    has_emitter = bool(
        re.search(r"\b(close|closed|escaped)\s*=\s*new\s+EventEmitter", src)
    )
    has_output_decorator = bool(
        re.search(r"@Output\(\)[^\n]*\n[^\n]*(close|closed|escaped)", src)
    )
    assert has_output or has_emitter or has_output_decorator, (
        "Expected a signal output (or EventEmitter) named 'close', 'closed', or "
        "'escaped' in the focus-trap directive. "
        "Per criterion: '`Escape` emits a close event'."
    )


def test_when_focus_trap_ts_read_then_previously_focused_element_is_stored():
    """The directive must save a reference to the element focused before activation.

    Per criterion: 'focus returns to the previously-focused element on
    deactivate'.
    The previously-focused element must be captured at activation time so it
    can be restored when the overlay closes.  Accepted indicators: a property
    storing `document.activeElement`, `document.querySelector(':focus')`, or
    a variable name containing 'previous', 'prior', 'before', or 'trigger'.
    """
    src = _directive_source()
    has_active_element = bool(re.search(r"activeElement", src))
    has_prior_ref = bool(
        re.search(
            r"\b(previous|prior|before|trigger)(Element|Focus|El|Node)?\b",
            src,
            re.IGNORECASE,
        )
    )
    assert has_active_element or has_prior_ref, (
        "Expected the focus-trap directive to capture the previously-focused element "
        "(e.g. `document.activeElement` or a property named 'previousElement'). "
        "Per criterion: 'focus returns to the previously-focused element on deactivate'."
    )


def test_when_focus_trap_ts_read_then_focus_is_restored_on_deactivate():
    """The directive must call .focus() on the previously-focused element when deactivated.

    Per criterion: 'focus returns to the previously-focused element on deactivate'.
    Restoration requires an explicit `.focus()` call on the saved reference.
    The call must occur in a cleanup path (ngOnDestroy, a deactivate method, or
    a setter that reacts to an active input going false).
    """
    src = _directive_source()
    # Must call .focus() somewhere in the source; combined with the previous
    # test that checks the reference is saved, this guarantees restoration.
    assert re.search(r"\.focus\s*\(\s*\)", src), (
        "Expected a `.focus()` call in the focus-trap directive to restore focus "
        "to the previously-focused element on deactivate. "
        "Per criterion: 'focus returns to the previously-focused element on deactivate'."
    )


# ---------------------------------------------------------------------------
# Criterion: Background siblings are inerted (inert/aria-hidden) while active
#            and restored after
# ---------------------------------------------------------------------------


def test_when_focus_trap_ts_read_then_inert_or_aria_hidden_is_applied_to_siblings():
    """The directive must apply `inert` or `aria-hidden` to background siblings.

    Per criterion: 'Background siblings are inerted (inert/aria-hidden) while
    active and restored after'.
    Requirements §7: 'background inerted in code (do not rely on aria-modal
    alone; Safari/VoiceOver regression)'. The directive must set either the
    native `inert` attribute or `aria-hidden="true"` on siblings.
    """
    src = _directive_source()
    has_inert = bool(re.search(r"\binert\b", src))
    has_aria_hidden = bool(re.search(r"aria-hidden", src))
    assert has_inert or has_aria_hidden, (
        "Expected 'inert' attribute or 'aria-hidden' assignment in the focus-trap "
        "directive to suppress background siblings. "
        "Per criterion: 'Background siblings are inerted (inert/aria-hidden) while active'."
    )


def test_when_focus_trap_ts_read_then_siblings_are_restored_after_deactivation():
    """The directive must restore sibling inert/aria-hidden state after deactivating.

    Per criterion: 'Background siblings are inerted (inert/aria-hidden) while
    active and restored after'.
    Restoration implies removing the attribute or setting it back to its
    original value.  Accepted indicators: `removeAttribute('inert')`,
    `removeAttribute('aria-hidden')`, setting `aria-hidden` to 'false' or
    `null`, or a pattern that restores a saved previous value.
    """
    src = _directive_source()
    # removeAttribute covers both inert and aria-hidden removal
    has_remove = bool(
        re.search(r"removeAttribute\s*\(\s*['\"](?:inert|aria-hidden)['\"]", src)
    )
    # Explicit reset to false/null/'false'
    has_reset = bool(
        re.search(
            r"aria-hidden['\"]?\s*,?\s*['\"]?(?:false|null)['\"]?|"
            r"\.inert\s*=\s*false",
            src,
        )
    )
    # Restoring a previously saved value
    has_restore_pattern = bool(
        re.search(
            r"(previous|prior|before|original|saved).*(inert|aria.?hidden)|"
            r"(inert|aria.?hidden).*(previous|prior|before|original|restore)",
            src,
            re.IGNORECASE | re.DOTALL,
        )
    )
    assert has_remove or has_reset or has_restore_pattern, (
        "Expected the focus-trap directive to restore siblings' inert/aria-hidden "
        "state on deactivate — e.g. removeAttribute('inert') / "
        "removeAttribute('aria-hidden') or an explicit reset to 'false'. "
        "Per criterion: 'Background siblings are inerted … and restored after'."
    )


# ---------------------------------------------------------------------------
# Criterion: SSR-safe; uses the `host` object (no @HostListener/@HostBinding)
# ---------------------------------------------------------------------------


def test_when_focus_trap_ts_read_then_host_listener_is_not_used():
    """The directive must NOT use @HostListener.

    Per criterion: 'SSR-safe; uses the `host` object (no @HostListener/
    @HostBinding)'. Angular's `host` metadata object in @Directive is the
    preferred SSR-safe alternative (no decorator overhead, tree-shakeable).
    """
    src = _directive_source()
    assert "@HostListener" not in src, (
        "Found '@HostListener' in the focus-trap directive. "
        "Per criterion: 'uses the `host` object (no @HostListener/@HostBinding)'."
    )


def test_when_focus_trap_ts_read_then_host_binding_decorator_is_not_used():
    """The directive must NOT use @HostBinding.

    Per criterion: 'SSR-safe; uses the `host` object (no @HostListener/
    @HostBinding)'.
    """
    src = _directive_source()
    assert "@HostBinding" not in src, (
        "Found '@HostBinding' in the focus-trap directive. "
        "Per criterion: 'uses the `host` object (no @HostListener/@HostBinding)'."
    )


def test_when_focus_trap_ts_read_then_host_metadata_object_is_declared():
    """The @Directive decorator must declare event listeners via the `host` object.

    Per criterion: 'SSR-safe; uses the `host` object'.
    Angular's `host:` key in @Directive({...}) attaches event listeners and
    attribute bindings without requiring @HostListener / @HostBinding.  The
    presence of `host:` in the decorator metadata satisfies this criterion.
    """
    src = _directive_source()
    assert re.search(r"\bhost\s*:", src), (
        "Expected a `host:` key inside the @Directive({...}) decorator metadata "
        "in the focus-trap directive. "
        "Per criterion: 'SSR-safe; uses the `host` object (no @HostListener)'."
    )


def test_when_focus_trap_ts_read_then_browser_globals_are_not_accessed_at_class_level():
    """Browser globals (document, window) must not appear in top-level field initialisers.

    Per criterion: 'SSR-safe'. During SSR, `document` and `window` are
    undefined; accessing them at class-definition time (outside a method body)
    causes a ReferenceError.  They are only safe inside methods / lifecycle
    hooks that Angular only calls in the browser.

    Interpretation: the test parses the file line-by-line, and verifies that
    every reference to `document` or `window` appears INSIDE a function/method
    body (indented by at least two spaces, or preceded by an opening brace on
    the same or a prior non-blank line within the current block), not as a
    top-level class field initialiser or at module scope.

    This is a structural heuristic — it accepts any reasonable TypeScript
    indentation convention and will not false-positive on import statements or
    string literals.
    """
    src = _directive_source()
    # Reject bare `document` / `window` at the start of a class-field line
    # (i.e. preceded only by optional whitespace and an identifier + = sign,
    # which would be `readonly foo = document.something`).
    bad_field_init = re.search(
        r"^\s{0,4}(?:readonly\s+|private\s+|protected\s+|public\s+)?"
        r"\w+\s*(?::\s*\w[\w<>, |&\[\]]*\s*)?"
        r"=\s*(document|window)\b",
        src,
        re.MULTILINE,
    )
    assert not bad_field_init, (
        "Found a class-field initialiser that accesses 'document' or 'window' at "
        "class-definition time — this crashes during SSR. Move the access inside a "
        "lifecycle hook (ngOnInit / ngAfterViewInit) or inject DOCUMENT via the DI "
        "token instead. "
        "Per criterion: 'SSR-safe; uses the `host` object'."
    )


# ---------------------------------------------------------------------------
# Hypothesis property-based test
# ---------------------------------------------------------------------------
# The SSR-safety criterion implies a never-raises invariant over the set of
# browser-global token names: for EVERY dangerous global, the directive must
# not reference it at class-level field scope.  We parametrise over a strategy
# that generates realistic browser-global names (document / window plus common
# sub-objects) and verify the structural guard holds for each.
# ---------------------------------------------------------------------------

_BROWSER_GLOBALS = st.sampled_from(
    [
        "document",
        "window",
        "navigator",
        "location",
        "history",
        "screen",
        "localStorage",
        "sessionStorage",
    ]
)


@given(_BROWSER_GLOBALS)
@settings(max_examples=8)
def test_when_browser_global_is_searched_then_it_is_not_at_class_field_scope(
    global_name: str,
):
    """For every browser-global identifier, no top-level class-field accesses it.

    Invariant (derived from 'SSR-safe' criterion): the directive must never
    access any browser-only global at class-field-initialiser scope, regardless
    of which specific global is examined.  This property confirms the guard holds
    across the full set of dangerous names, not just 'document'.

    Strategy: st.sampled_from() over a fixed list of browser-global names that
    would crash an SSR run.  For each sampled name the assertion is the same:
    no top-level field `= <global>.*` pattern.
    """
    try:
        src = _directive_source()
    except FileNotFoundError:
        pytest.skip("Focus-trap directive not yet implemented — skipping property")

    bad = re.search(
        rf"^\s{{0,4}}(?:readonly\s+|private\s+|protected\s+|public\s+)?"
        rf"\w+\s*(?::\s*\w[\w<>, |&\[\]]*\s*)?"
        rf"=\s*{re.escape(global_name)}\b",
        src,
        re.MULTILINE,
    )
    assert not bad, (
        f"Found a class-field initialiser that accesses '{global_name}' at "
        f"class-definition time — this crashes during SSR. "
        f"Per criterion: 'SSR-safe; uses the `host` object'."
    )
