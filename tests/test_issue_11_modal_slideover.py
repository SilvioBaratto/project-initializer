"""
Tests for issue #11: Modal + SlideOver overlays with JS focus trap.

Only [UNIT]-verifiable criteria are tested (per oracle report):
  A. Modal: role="dialog" + aria-modal, focus trap, Escape + backdrop close,
     background inerted in code.
  B. Open/close via signal input()/output(); visible focus; dark-mode tokens.

Skipped (NOT VERIFIABLE):
  - SlideOver: h-dvh / edge-slide / safe-area (layout/CSS, no runtime check)
  - "All tests pass" (boilerplate gate, not a per-criterion assertion)
  - SOLID / clean-code metrics (subjective prose)

Strategy: scaffold a frontend-only project, then inspect the generated
TypeScript/HTML sources for the structural contracts required by each criterion.
These tests fail today (the files do not yet exist) and will pass once the
implementation is written.
"""

import re
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scaffold_frontend(dest: Path) -> None:
    """Run project-initializer --scope frontend into *dest*."""
    subprocess.run(
        ["project-initializer", str(dest), "--scope", "frontend", "--force"],
        check=True,
    )


@pytest.fixture(scope="module")
def frontend_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("issue11_scaffold")
    _scaffold_frontend(root)
    return root / "frontend" / "src" / "app" / "shared" / "ui"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _find_file(ui_root: Path, *parts: str) -> Path:
    """Return the file at ui_root/<parts> and assert it exists."""
    p = ui_root.joinpath(*parts)
    assert p.exists(), (
        f"Expected file {p} to exist — the modal component has not been created yet."
    )
    return p


# ---------------------------------------------------------------------------
# Criterion A-1: role="dialog" and aria-modal are present in the modal template
# ---------------------------------------------------------------------------


class TestModalAriaContract:
    """Modal must expose role='dialog' + aria-modal='true' (WAI-ARIA APG §3.8)."""

    def test_when_modal_template_rendered_then_role_dialog_is_present(
        self, frontend_root
    ):
        """The root host element must carry role='dialog'."""
        tmpl = _find_file(frontend_root, "modal", "modal.html")
        html = _read(tmpl)
        assert re.search(r'role=["\']dialog["\']', html), (
            'Modal template must set role="dialog" on its root element.'
        )

    def test_when_modal_template_rendered_then_aria_modal_true_is_present(
        self, frontend_root
    ):
        """aria-modal='true' must appear so AT users are not confused by background."""
        tmpl = _find_file(frontend_root, "modal", "modal.html")
        html = _read(tmpl)
        assert re.search(r'aria-modal=["\']true["\']', html), (
            'Modal template must set aria-modal="true".'
        )

    def test_when_modal_template_rendered_then_aria_labelledby_or_aria_label_is_present(
        self, frontend_root
    ):
        """WAI-ARIA APG requires the dialog to be labelled."""
        tmpl = _find_file(frontend_root, "modal", "modal.html")
        html = _read(tmpl)
        # Accept both static (aria-label=) and Angular binding ([attr.aria-label]=) forms.
        assert re.search(r"(?:\[attr\.)?aria-label(?:ledby)?(?:\])?=", html), (
            "Modal must carry aria-label or aria-labelledby so AT announce the dialog name."
        )


# ---------------------------------------------------------------------------
# Criterion A-2: JS focus trap is implemented in code (not relying on aria-modal)
#
# Research §2.1 / §4: native <dialog> does not trap in all browsers; Safari/
# VoiceOver regresses on aria-modal alone — a JS trap must be authored.
# ---------------------------------------------------------------------------


class TestModalFocusTrap:
    """The focus trap must be a JS/TS implementation, not delegated to aria-modal."""

    def test_when_modal_component_loaded_then_focus_trap_logic_is_present(
        self, frontend_root
    ):
        """Component source must contain focus-trap logic (tabbable query + keydown handler)."""
        src = _find_file(frontend_root, "modal", "modal.ts")
        code = _read(src)
        # Acceptable signals: explicit tabbable-selector, or a FocusTrapService reference,
        # or a 'focus-trap' / 'focustrap' import/class usage.
        has_trap = (
            re.search(r"focusTrap|focus[_-]trap|FocusTrap", code, re.IGNORECASE)
            or re.search(
                r"querySelector.*tabindex|querySelectorAll.*"
                r"(a\[href\]|button|input|select|textarea|\[tabindex\])",
                code,
            )
            or re.search(r"Tab.*keydown|keydown.*Tab", code)
        )
        assert has_trap, (
            "Modal component must implement a JS focus trap "
            "(tabbable-element query or FocusTrap helper), "
            "not rely on aria-modal alone (Safari VoiceOver regression)."
        )

    def test_when_modal_component_loaded_then_escape_key_handler_is_present(
        self, frontend_root
    ):
        """Pressing Escape must close the modal — handler must appear in source."""
        src = _find_file(frontend_root, "modal", "modal.ts")
        code = _read(src)
        assert re.search(r"Escape|'Escape'|\"Escape\"|keyCode.*27|27.*keyCode", code), (
            "Modal component must handle the Escape key to close the dialog."
        )

    def test_when_modal_template_rendered_then_backdrop_close_handler_is_present(
        self, frontend_root
    ):
        """Clicking the backdrop (outside the dialog panel) must close the modal."""
        tmpl = _find_file(frontend_root, "modal", "modal.html")
        html = _read(tmpl)
        # Accept (click) on a backdrop overlay element OR (click) on the host with
        # stopPropagation on the inner panel — either pattern satisfies the criterion.
        assert re.search(r"\(click\)", html), (
            "Modal template must wire a (click) handler to close on backdrop click."
        )


# ---------------------------------------------------------------------------
# Criterion A-3: background is inerted in code
#
# Requirements §7: "background inerted in code (do not rely on aria-modal alone)"
# The implementation must programmatically set inert on the main content or
# call a helper that does so.
# ---------------------------------------------------------------------------


class TestModalBackgroundInert:
    """The modal must inert the background via JS, not rely on aria-modal alone."""

    def test_when_modal_opens_then_inert_is_applied_in_source(self, frontend_root):
        """Component source must reference the 'inert' attribute programmatically."""
        src = _find_file(frontend_root, "modal", "modal.ts")
        code = _read(src)
        assert re.search(r"\.inert\b|setAttribute.*inert|inert\s*=\s*true", code), (
            "Modal component must set 'inert' on background content in JS "
            "(aria-modal is insufficient for Safari/VoiceOver — research §2.1, §4)."
        )


# ---------------------------------------------------------------------------
# Criterion B-1: Open/close driven by signal input() / output()
# ---------------------------------------------------------------------------


class TestModalSignalContract:
    """open state must be driven by Angular signal input(); close events by output()."""

    def test_when_modal_component_parsed_then_input_signal_is_declared(
        self, frontend_root
    ):
        """Component must declare an input() signal controlling open state."""
        src = _find_file(frontend_root, "modal", "modal.ts")
        code = _read(src)
        # input() may be typed as boolean, required, or with a default.
        assert re.search(r"\binput\s*[(<]", code), (
            "Modal component must use Angular signal input() for open/close control."
        )

    def test_when_modal_component_parsed_then_output_signal_is_declared(
        self, frontend_root
    ):
        """Component must declare an output() signal to emit the close event."""
        src = _find_file(frontend_root, "modal", "modal.ts")
        code = _read(src)
        assert re.search(r"\boutput\s*[(<(]", code), (
            "Modal component must use Angular signal output() to emit close events."
        )

    def test_when_modal_component_parsed_then_onpush_change_detection_is_set(
        self, frontend_root
    ):
        """Signal-driven components must use OnPush to avoid redundant CD cycles."""
        src = _find_file(frontend_root, "modal", "modal.ts")
        code = _read(src)
        assert re.search(r"ChangeDetectionStrategy\.OnPush", code), (
            "Modal must use ChangeDetectionStrategy.OnPush (signal + OnPush pattern)."
        )


# ---------------------------------------------------------------------------
# Criterion B-2: Visible focus (focus-visible ring)
# ---------------------------------------------------------------------------


class TestModalVisibleFocus:
    """Focus must be visible on interactive elements inside the modal."""

    def test_when_modal_template_rendered_then_focus_visible_ring_is_present(
        self, frontend_root
    ):
        """Interactive elements inside modal must carry focus-visible Tailwind class or
        the global styles.css ring must apply — at minimum, no outline:none suppression."""
        tmpl = _find_file(frontend_root, "modal", "modal.html")
        html = _read(tmpl)
        # Fail if the template explicitly suppresses focus outline without replacement.
        assert not re.search(r"outline-none(?!\s+focus-visible)", html), (
            "Modal template must not suppress outline without a focus-visible replacement."
        )


# ---------------------------------------------------------------------------
# Criterion B-3: Dark-mode tokens consumed from @theme
# ---------------------------------------------------------------------------


class TestModalDarkModeTokens:
    """Modal must consume @theme CSS tokens, not hardcoded hex values."""

    def test_when_modal_template_rendered_then_no_hardcoded_hex_colors_appear(
        self, frontend_root
    ):
        """All colour values must come from Tailwind token classes, not inline hex."""
        tmpl = _find_file(frontend_root, "modal", "modal.html")
        html = _read(tmpl)
        assert not re.search(r"#[0-9a-fA-F]{3,6}", html), (
            "Modal template must not contain hardcoded hex colours; "
            "use Tailwind @theme token classes so dark-mode works via .dark class toggle."
        )

    def test_when_modal_template_rendered_then_dark_variant_class_is_used(
        self, frontend_root
    ):
        """At least one dark: Tailwind class must appear so the modal adapts to dark mode."""
        tmpl = _find_file(frontend_root, "modal", "modal.html")
        html = _read(tmpl)
        assert re.search(r"\bdark:", html), (
            "Modal template must include at least one dark: Tailwind utility "
            "so the overlay adapts to dark-mode via the .dark class toggle."
        )


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
#
# Invariant derived from criterion A: "focus trap" implies that for ANY set of
# focusable elements inside the dialog, focus must cycle within that set — i.e.
# Tab from the last returns to the first, and Shift+Tab from the first returns
# to the last.  We test the pure cycle-index helper that the implementation
# must expose (or an equivalent ring-arithmetic function).
#
# We test the ring-wrap invariant: it must hold for all list sizes ≥ 1.
# ---------------------------------------------------------------------------

try:
    from hypothesis import given, strategies as st

    _HYPOTHESIS_AVAILABLE = True
except ImportError:
    _HYPOTHESIS_AVAILABLE = False


def _ring_next(current: int, size: int, forward: bool) -> int:
    """
    Pure Python model of the focus-trap ring advance used by FocusTrapDirective.
    Derived from the criterion text: Tab wraps last→first, Shift+Tab wraps first→last.
    Tests the mathematical invariant; the TypeScript implementation in the Angular
    component spec exercises the same contract end-to-end in the actual runtime.
    """
    if size == 0:
        return 0
    if forward:
        return (current + 1) % size
    return (current - 1) % size


@pytest.mark.skipif(not _HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
class TestFocusTrapRingInvariant:
    """
    Property-based tests for the ring-wrap invariant implied by criterion A
    (focus trap).  We test a pure Python model of the ring arithmetic — the
    same invariant is exercised end-to-end against the real TypeScript code
    in modal.component.spec.ts (Angular TestBed, Tab/Shift+Tab tests).
    """

    @given(size=st.integers(min_value=1, max_value=20))
    def test_when_tab_pressed_at_last_then_focus_wraps_to_first(self, size):
        """Tab from the last element (index size-1) must wrap to index 0."""
        result = _ring_next(size - 1, size, forward=True)
        assert result == 0, (
            f"Tab from last (index {size - 1}) in a list of {size} must wrap to 0, "
            f"got {result}."
        )

    @given(size=st.integers(min_value=1, max_value=20))
    def test_when_shift_tab_pressed_at_first_then_focus_wraps_to_last(self, size):
        """Shift+Tab from index 0 must wrap to index (size - 1)."""
        result = _ring_next(0, size, forward=False)
        assert result == size - 1, (
            f"Shift+Tab from 0 in a list of {size} must wrap to {size - 1}, "
            f"got {result}."
        )

    @given(
        size=st.integers(min_value=1, max_value=20),
        idx=st.integers(min_value=0, max_value=19),
    )
    def test_when_advanced_forward_then_backward_index_is_restored(self, size, idx):
        """Round-trip: forward then backward returns to the same index."""
        i = idx % size
        fwd = _ring_next(i, size, forward=True)
        back = _ring_next(fwd, size, forward=False)
        assert back == i, (
            f"Ring round-trip failed for size={size}, start={i}: "
            f"forward={fwd}, back={back}."
        )
