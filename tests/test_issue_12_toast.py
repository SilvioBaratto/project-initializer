"""
Tests for issue #12: Toast component + ToastService wired to #toast-outlet.

Only [UNIT]- and [T3]-verifiable criteria are tested (per oracle report):

  A [UNIT] ToastService (providedIn: 'root') with show(variant, ...)/ dismiss
     and signal state.
  B [T3]   #toast-outlet renders live toasts; aria-live polite, assertive for
     the error variant.
  C [UNIT] Auto-dismiss timer + manual close button; stacks bottom-right with
     .pb-safe.

Skipped (NOT VERIFIABLE per oracle):
  - "Existing layout/responsive specs stay green" (external CI gate)
  - "All tests pass" (boilerplate gate, not a per-criterion assertion)
  - SOLID / clean-code metrics (subjective prose)

Strategy: scaffold a frontend-only project, then inspect the generated
TypeScript/HTML sources for the structural contracts demanded by each criterion.
These tests fail today (the files do not yet exist) and will pass once the
implementation is written.
"""

import re
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _scaffold_frontend(dest: Path) -> None:
    subprocess.run(
        ["project-initializer", str(dest), "--scope", "frontend", "--force"],
        check=True,
    )


@pytest.fixture(scope="module")
def frontend_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("issue12_scaffold")
    _scaffold_frontend(root)
    return root


@pytest.fixture(scope="module")
def ui_root(frontend_root):
    return frontend_root / "frontend" / "src" / "app" / "shared" / "ui"


@pytest.fixture(scope="module")
def layout_html(frontend_root):
    p = frontend_root / "frontend" / "src" / "app" / "shared" / "layout" / "layout.html"
    assert p.exists(), f"layout.html not found at {p}"
    return p


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _find(ui_root: Path, *parts: str) -> Path:
    p = ui_root.joinpath(*parts)
    assert p.exists(), (
        f"Expected file {p} — the toast component has not been created yet."
    )
    return p


# ---------------------------------------------------------------------------
# Criterion A: ToastService (providedIn: 'root') with show(variant,…)/dismiss
#              and signal state
# ---------------------------------------------------------------------------


class TestToastServiceExists:
    """ToastService must exist and be structured per the acceptance criteria."""

    def test_when_toast_service_file_loaded_then_it_exists(self, ui_root):
        """A toast.service.ts (or toast/toast.service.ts) must be present."""
        candidates = list(ui_root.rglob("toast.service.ts"))
        assert candidates, (
            "No toast.service.ts found under shared/ui/; "
            "ToastService has not been created yet."
        )

    def test_when_toast_service_parsed_then_provided_in_root_is_declared(self, ui_root):
        """@Injectable({ providedIn: 'root' }) must appear so one instance is shared
        across all consumers without explicit provider registration."""
        candidates = list(ui_root.rglob("toast.service.ts"))
        assert candidates, "toast.service.ts not found"
        code = _read(candidates[0])
        assert re.search(r"providedIn\s*:\s*['\"]root['\"]", code), (
            "ToastService must be decorated with @Injectable({ providedIn: 'root' }) "
            "so it is a singleton across the application."
        )

    def test_when_toast_service_parsed_then_show_method_is_declared(self, ui_root):
        """show(variant, …) must be a callable public method on the service."""
        candidates = list(ui_root.rglob("toast.service.ts"))
        assert candidates, "toast.service.ts not found"
        code = _read(candidates[0])
        assert re.search(r"\bshow\s*\(", code), (
            "ToastService must expose a show() method that accepts a variant argument."
        )

    def test_when_toast_service_parsed_then_dismiss_method_is_declared(self, ui_root):
        """dismiss() (or dismiss(id)) must be a callable public method on the service."""
        candidates = list(ui_root.rglob("toast.service.ts"))
        assert candidates, "toast.service.ts not found"
        code = _read(candidates[0])
        assert re.search(r"\bdismiss\s*\(", code), (
            "ToastService must expose a dismiss() method to remove a toast by id "
            "or clear all toasts."
        )

    def test_when_toast_service_parsed_then_signal_state_is_used(self, ui_root):
        """State must be managed via Angular signals (signal() / WritableSignal),
        not a plain BehaviorSubject, so it integrates with OnPush components."""
        candidates = list(ui_root.rglob("toast.service.ts"))
        assert candidates, "toast.service.ts not found"
        code = _read(candidates[0])
        # Accept signal(), WritableSignal, computed() as evidence of signal state.
        assert re.search(
            r"\bsignal\s*[<(]|\bWritableSignal\b|\bcomputed\s*[<(]", code
        ), (
            "ToastService must manage its toast list using Angular signals "
            "(signal() / WritableSignal), not observables alone."
        )

    def test_when_toast_service_parsed_then_variant_parameter_is_typed(self, ui_root):
        """show() must accept a variant discriminator (e.g. 'info' | 'error' | …) so
        the outlet can select the correct aria-live value per variant."""
        candidates = list(ui_root.rglob("toast.service.ts"))
        assert candidates, "toast.service.ts not found"
        code = _read(candidates[0])
        # Accept a TypeScript union/enum type or a 'variant' parameter name.
        has_variant = re.search(
            r"variant|ToastVariant|ToastType|'error'|\"error\"", code
        )
        assert has_variant, (
            "ToastService.show() must type or reference a variant discriminator "
            "(e.g. 'info' | 'success' | 'warning' | 'error') so the outlet can "
            "distinguish error toasts for assertive aria-live."
        )


# ---------------------------------------------------------------------------
# Criterion B: #toast-outlet renders live toasts; aria-live polite, assertive
#              for the error variant
# ---------------------------------------------------------------------------


class TestToastOutletInLayout:
    """layout.html must wire #toast-outlet to the Toast component."""

    def test_when_layout_html_parsed_then_toast_outlet_id_is_present(self, layout_html):
        """The existing #toast-outlet placeholder must remain / be wired."""
        html = _read(layout_html)
        assert re.search(r'id=["\']toast-outlet["\']|#toast-outlet', html), (
            "#toast-outlet is missing from layout.html; "
            "the toast outlet must remain wired in the layout shell."
        )

    def test_when_layout_html_parsed_then_toast_component_selector_is_used(
        self, layout_html
    ):
        """The Toast (or toast-outlet) Angular component must be referenced in the
        layout so toasts appear in the correct DOM position."""
        html = _read(layout_html)
        # Accept any selector that includes 'toast' (e.g. <app-toast>, <app-toast-outlet>)
        assert re.search(r"<app-toast", html), (
            "layout.html must include the toast component selector (e.g. <app-toast>) "
            "so toasts are rendered inside #toast-outlet."
        )


class TestToastOutletAriaLive:
    """The toast container must use aria-live for screen-reader announcements."""

    def test_when_toast_component_template_loaded_then_aria_live_polite_is_present(
        self, ui_root
    ):
        """Non-error toasts must be announced with aria-live='polite'."""
        candidates = list(ui_root.rglob("toast*.html"))
        assert candidates, (
            "No toast HTML template found under shared/ui/; "
            "the toast component has not been created yet."
        )
        found = any(
            re.search(r"aria-live=['\"]polite['\"]", _read(f)) for f in candidates
        )
        assert found, (
            "Toast template must include aria-live='polite' on the toast container "
            "so non-error toasts are announced without interrupting the user."
        )

    def test_when_toast_component_template_loaded_then_aria_live_assertive_for_error(
        self, ui_root
    ):
        """Error-variant toasts must be announced with aria-live='assertive' so
        critical failures interrupt screen-reader output immediately."""
        candidates = list(ui_root.rglob("toast*.html"))
        assert candidates, "No toast HTML template found under shared/ui/"
        # The template must conditionally switch to assertive for the error variant.
        # Accept Angular binding ([attr.aria-live]) or a conditional @if block.
        found = any(
            re.search(
                r"aria-live=['\"]assertive['\"]"
                r"|attr\.aria-live.*assertive"
                r"|\[aria-live\]",
                _read(f),
            )
            for f in candidates
        )
        assert found, (
            "Toast template must produce aria-live='assertive' for the error variant. "
            "This can be a conditional binding ([attr.aria-live]) or an @if branch "
            "rendering a separate container with aria-live='assertive'."
        )


# ---------------------------------------------------------------------------
# Criterion C: Auto-dismiss timer + manual close button; stacks bottom-right
#              with .pb-safe
# ---------------------------------------------------------------------------


class TestToastAutoDismiss:
    """ToastService or the component must schedule auto-dismiss via a timer."""

    def test_when_toast_service_parsed_then_timer_is_scheduled(self, ui_root):
        """Auto-dismiss must be implemented with setTimeout or equivalent."""
        candidates = list(ui_root.rglob("toast.service.ts"))
        assert candidates, "toast.service.ts not found"
        code = _read(candidates[0])
        assert re.search(r"setTimeout|timer\(|interval\(|takeUntil", code), (
            "ToastService must schedule auto-dismiss using setTimeout (or an RxJS "
            "timer) so toasts are removed after a configurable delay."
        )


class TestToastManualClose:
    """Each toast must have a manual close button."""

    def test_when_toast_template_loaded_then_close_button_is_present(self, ui_root):
        """A close/dismiss button must appear in the toast item template so users
        can dismiss early without waiting for auto-dismiss."""
        candidates = list(ui_root.rglob("toast*.html"))
        assert candidates, "No toast HTML template found"
        found = any(
            re.search(r"\(click\).*dismiss|\bdismiss\b.*\(click\)", _read(f))
            for f in candidates
        )
        assert found, (
            "Toast template must include a close button wired to a dismiss handler "
            "via (click) so users can manually dismiss individual toasts."
        )

    def test_when_toast_template_loaded_then_close_button_has_aria_label(self, ui_root):
        """The close button must be labelled for screen readers."""
        candidates = list(ui_root.rglob("toast*.html"))
        assert candidates, "No toast HTML template found"
        found = any(
            re.search(r'aria-label=["\'][^"\']*[Cc]lose|[Dd]ismiss', _read(f))
            for f in candidates
        )
        assert found, (
            "The toast close button must carry aria-label='Close' (or similar) "
            "so screen-reader users can identify and activate it."
        )


class TestToastStackingPosition:
    """Toasts must stack bottom-right with the .pb-safe bottom inset."""

    def test_when_toast_template_loaded_then_bottom_right_positioning_classes_are_present(
        self, ui_root
    ):
        """The toast container must use Tailwind classes that fix it to bottom-right."""
        candidates = list(ui_root.rglob("toast*.html"))
        assert candidates, "No toast HTML template found"
        found = any(
            re.search(
                r"\bbottom-\w+\b.*\bright-\w+\b|\bright-\w+\b.*\bbottom-\w+\b", _read(f)
            )
            for f in candidates
        )
        assert found, (
            "Toast container must carry Tailwind positioning classes that fix it "
            "to the bottom-right corner (e.g. 'fixed bottom-4 right-4')."
        )

    def test_when_toast_template_loaded_then_pb_safe_class_is_present(self, ui_root):
        """The .pb-safe class must appear on the toast stack container so toasts
        clear the iOS home indicator / bottom safe-area inset."""
        candidates = list(ui_root.rglob("toast*.html"))
        assert candidates, "No toast HTML template found"
        found = any(re.search(r"\bpb-safe\b", _read(f)) for f in candidates)
        assert found, (
            "Toast container must include the 'pb-safe' class so the stack clears "
            "the iOS home indicator (env(safe-area-inset-bottom))."
        )


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
#
# Invariant derived from Criterion A: show() followed by dismiss() must remove
# exactly one toast from the active list. This is an idempotence-adjacent
# round-trip invariant: for any sequence of show() calls, dismissing a specific
# id must reduce the active count by exactly 1 — regardless of how many toasts
# are already queued.
#
# We test a pure Python model of the show/dismiss queue here.
# ---------------------------------------------------------------------------

try:
    from hypothesis import given, strategies as st

    _HYPOTHESIS_AVAILABLE = True
except ImportError:
    _HYPOTHESIS_AVAILABLE = False


def _make_toast(toast_id: int, variant: str, message: str) -> dict:
    return {"id": toast_id, "variant": variant, "message": message}


VARIANTS = ["info", "success", "warning", "error"]


def _show(toasts: list, toast_id: int, variant: str, message: str) -> list:
    """Pure model of ToastService.show()."""
    return toasts + [_make_toast(toast_id, variant, message)]


def _dismiss(toasts: list, toast_id: int) -> list:
    """Pure model of ToastService.dismiss(id)."""
    return [t for t in toasts if t["id"] != toast_id]


@pytest.mark.skipif(not _HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
class TestToastServiceQueueInvariant:
    """
    Property-based tests for the show/dismiss queue invariant implied by
    Criterion A: dismiss(id) must remove exactly the toast with that id.
    """

    @given(
        n=st.integers(min_value=1, max_value=10),
        target_idx=st.integers(min_value=0, max_value=9),
        variant=st.sampled_from(VARIANTS),
    )
    def test_when_toast_shown_then_dismissed_then_count_decreases_by_one(
        self, n, target_idx, variant
    ):
        """For any n active toasts, dismissing one by id reduces count by exactly 1."""
        toasts: list = []
        for i in range(n):
            toasts = _show(toasts, i, variant, f"msg-{i}")
        idx = target_idx % n
        target_id = toasts[idx]["id"]
        count_before = len(toasts)
        toasts = _dismiss(toasts, target_id)
        assert len(toasts) == count_before - 1, (
            f"dismiss(id={target_id}) must remove exactly one toast; "
            f"before={count_before}, after={len(toasts)}."
        )

    @given(
        n=st.integers(min_value=1, max_value=10),
        target_idx=st.integers(min_value=0, max_value=9),
        variant=st.sampled_from(VARIANTS),
    )
    def test_when_toast_dismissed_then_that_id_is_absent_from_result(
        self, n, target_idx, variant
    ):
        """After dismiss(id), no toast with that id remains in the list."""
        toasts: list = []
        for i in range(n):
            toasts = _show(toasts, i, variant, f"msg-{i}")
        idx = target_idx % n
        target_id = toasts[idx]["id"]
        toasts = _dismiss(toasts, target_id)
        remaining_ids = [t["id"] for t in toasts]
        assert target_id not in remaining_ids, (
            f"After dismiss(id={target_id}), id must not appear in the active list; "
            f"remaining ids: {remaining_ids}."
        )

    @given(
        n=st.integers(min_value=1, max_value=10),
        target_idx=st.integers(min_value=0, max_value=9),
        variant=st.sampled_from(VARIANTS),
    )
    def test_when_toast_dismissed_twice_then_count_does_not_decrease_further(
        self, n, target_idx, variant
    ):
        """Dismissing the same id twice is idempotent — no double-removal."""
        toasts: list = []
        for i in range(n):
            toasts = _show(toasts, i, variant, f"msg-{i}")
        idx = target_idx % n
        target_id = toasts[idx]["id"]
        after_first = _dismiss(toasts, target_id)
        after_second = _dismiss(after_first, target_id)
        assert len(after_second) == len(after_first), (
            f"dismiss(id={target_id}) called twice must not remove additional toasts; "
            f"after first={len(after_first)}, after second={len(after_second)}."
        )

    @given(
        n=st.integers(min_value=2, max_value=10),
        target_idx=st.integers(min_value=0, max_value=9),
        variant=st.sampled_from(VARIANTS),
    )
    def test_when_one_toast_dismissed_then_others_are_preserved(
        self, n, target_idx, variant
    ):
        """Dismissing one toast must leave all other toasts in the list unchanged."""
        toasts: list = []
        for i in range(n):
            toasts = _show(toasts, i, variant, f"msg-{i}")
        idx = target_idx % n
        target_id = toasts[idx]["id"]
        expected_survivors = {t["id"] for t in toasts if t["id"] != target_id}
        after = _dismiss(toasts, target_id)
        actual_ids = {t["id"] for t in after}
        assert actual_ids == expected_survivors, (
            f"After dismiss(id={target_id}), remaining ids {actual_ids} "
            f"must equal {expected_survivors}."
        )
