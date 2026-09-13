"""
Tests for issue #12: ToastService + ToastComponent, built on the Angular Material 3
snackbar (MatSnackBar).

Only [UNIT]- and [T3]-verifiable criteria are tested (per oracle report):

  A [UNIT] ToastService (providedIn: 'root') with show(variant, ...)/ dismiss
     and signal state. toasts() holds the one toast on screen: a new show()
     replaces it and dismiss(id) of a replaced toast is a no-op (Hypothesis
     model, anchored to toast.service.ts).
  B [T3]   Each toast opens as a MatSnackBar whose content is ToastComponent
     (toast.ts + toast.html + toast.css); the snackbar live region is polite,
     assertive for the error variant.
  C [UNIT] Auto-dismiss through the snackbar duration, or a labelled dismiss icon
     button (48px target), never both on one toast; the snackbar sits bottom
     center, lifted above the navigation bar (64px + safe-area inset) at the
     compact window size by the global overlay partial _toast.scss.

Skipped (NOT VERIFIABLE per oracle):
  - "Existing layout/responsive specs stay green" (external CI gate)
  - "All tests pass" (boilerplate gate, not a per-criterion assertion)
  - SOLID / clean-code metrics (subjective prose)

Strategy: scaffold a frontend-only project, then inspect the generated
TypeScript/HTML/CSS sources and the global overlay partial for the structural
contracts demanded by each criterion.
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
def toast_overlay_scss(frontend_root):
    p = frontend_root / "frontend" / "src" / "styles" / "overlays" / "_toast.scss"
    assert p.exists(), f"_toast.scss not found at {p}"
    return p


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _toast_sources(ui_root: Path) -> list[Path]:
    """Every toast source a behavior can live in: .ts + .html + .css (specs excluded)."""
    return sorted(
        p
        for pattern in ("toast*.ts", "toast*.html", "toast*.css")
        for p in ui_root.rglob(pattern)
        if not p.name.endswith(".spec.ts")
    )


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
# Criterion B: each toast opens as a MatSnackBar whose content is
#              ToastComponent; live region polite, assertive for errors
# ---------------------------------------------------------------------------


class TestToastSnackBar:
    """ToastService must open every toast as an Angular Material snackbar."""

    def test_when_toast_component_loaded_then_ts_html_and_css_files_exist(self, ui_root):
        """ToastComponent is split into toast.ts + toast.html + toast.css."""
        for name in ("toast.ts", "toast.html", "toast.css"):
            _find(ui_root, "toast", name)

    def test_when_toast_component_parsed_then_onpush_and_external_template_and_styles(
        self, ui_root
    ):
        """The component uses OnPush and wires templateUrl + styleUrl (no inline template)."""
        code = _read(_find(ui_root, "toast", "toast.ts"))
        assert "ChangeDetectionStrategy.OnPush" in code, "ToastComponent must use OnPush."
        assert re.search(r"templateUrl\s*:\s*['\"]\./toast\.html['\"]", code), (
            "ToastComponent must load its template from toast.html."
        )
        assert re.search(r"styleUrl\s*:\s*['\"]\./toast\.css['\"]", code), (
            "ToastComponent must load its styles from toast.css."
        )

    def test_when_toast_service_parsed_then_toast_component_opens_in_a_snackbar(
        self, ui_root
    ):
        """Each show() opens ToastComponent with MatSnackBar.openFromComponent, so the
        snackbar renders in the overlay container and no layout outlet is needed."""
        code = _read(_find(ui_root, "toast", "toast.service.ts"))
        assert re.search(r"inject\(\s*MatSnackBar\s*\)", code), (
            "ToastService must inject Angular Material's MatSnackBar."
        )
        assert re.search(r"openFromComponent\s*(<[^>]*>)?\s*\(\s*ToastComponent\b", code), (
            "ToastService must open ToastComponent as the snackbar content "
            "(snackBar.openFromComponent(ToastComponent, ...))."
        )

    def test_when_toast_template_loaded_then_snackbar_label_and_actions_are_used(
        self, ui_root
    ):
        """The snackbar content marks its message and its action area for Material."""
        html = _read(_find(ui_root, "toast", "toast.html"))
        assert "matSnackBarLabel" in html, "The message must sit in a matSnackBarLabel."
        assert "matSnackBarActions" in html, "The action must sit in matSnackBarActions."


class TestToastOutletAriaLive:
    """The snackbar live region must announce toasts: polite, assertive for errors."""

    def test_when_toast_sources_loaded_then_aria_live_polite_is_present(self, ui_root):
        """Non-error toasts must be announced politely: MatSnackBarConfig.politeness
        sets aria-live on the snackbar's live region."""
        sources = _toast_sources(ui_root)
        assert sources, (
            "No toast sources found under shared/ui/; "
            "the toast component has not been created yet."
        )
        found = any(
            re.search(
                r"aria-live=['\"]polite['\"]|politeness\s*:[^\n]*['\"]polite['\"]",
                _read(f),
            )
            for f in sources
        )
        assert found, (
            "Toasts must be announced with aria-live='polite' (snackbar politeness "
            "'polite') so non-error toasts do not interrupt the user."
        )

    def test_when_toast_sources_loaded_then_aria_live_assertive_for_error(self, ui_root):
        """Error-variant toasts must be announced assertively so failures interrupt
        screen-reader output immediately, and only errors."""
        sources = _toast_sources(ui_root)
        assert sources, "No toast sources found under shared/ui/"
        found = any(
            re.search(
                r"politeness\s*:\s*variant\s*===\s*['\"]error['\"]\s*\?\s*['\"]assertive['\"]"
                r"|attr\.aria-live.*error.*assertive",
                _read(f),
            )
            for f in sources
        )
        assert found, (
            "The error variant must map to politeness 'assertive' "
            "(politeness: variant === 'error' ? 'assertive' : 'polite')."
        )


# ---------------------------------------------------------------------------
# Criterion C: Auto-dismiss or a dismiss button (never both); bottom center,
#              above the navigation bar at compact, clear of the safe area
# ---------------------------------------------------------------------------


class TestToastAutoDismiss:
    """Toasts without an action must auto-dismiss after a delay."""

    def test_when_toast_service_parsed_then_timer_is_scheduled(self, ui_root):
        """Auto-dismiss uses the snackbar `duration` (MatSnackBar schedules the timer),
        or setTimeout / an RxJS timer."""
        code = _read(_find(ui_root, "toast", "toast.service.ts"))
        assert re.search(r"\bduration\s*:|setTimeout|timer\(|interval\(|takeUntil", code), (
            "ToastService must schedule auto-dismiss (MatSnackBarConfig.duration, "
            "setTimeout or an RxJS timer) so toasts are removed after a delay."
        )

    def test_when_toast_service_parsed_then_a_toast_with_an_action_has_no_duration(
        self, ui_root
    ):
        """A snackbar with an action is never auto-dismissed, so keyboard and
        screen-reader users have time to reach it."""
        code = _read(_find(ui_root, "toast", "toast.service.ts"))
        assert re.search(r"duration\s*:\s*dismissible\s*\?\s*0\s*:", code), (
            "A dismissible toast (one with the dismiss action) must get duration 0."
        )


class TestToastManualClose:
    """A toast that waits for the user must have a labelled dismiss button."""

    def test_when_toast_template_loaded_then_close_button_is_present(self, ui_root):
        """A close/dismiss button must appear in the toast template so users
        can dismiss the toast."""
        html = _read(_find(ui_root, "toast", "toast.html"))
        assert re.search(r"\(click\).*dismiss|\bdismiss\b.*\(click\)", html), (
            "Toast template must include a close button wired to a dismiss handler "
            "via (click) so users can manually dismiss the toast."
        )

    def test_when_toast_template_loaded_then_close_button_has_aria_label(self, ui_root):
        """The close button must be labelled for screen readers."""
        html = _read(_find(ui_root, "toast", "toast.html"))
        assert re.search(r'aria-label=["\'][^"\']*(?:[Cc]lose|[Dd]ismiss)', html), (
            "The toast close button must carry an aria-label that names the action "
            "(for example 'Dismiss notification')."
        )

    def test_when_toast_template_loaded_then_close_button_is_a_material_icon_button(
        self, ui_root
    ):
        """A Material icon button gives the dismiss action its 48px touch target
        and state layers."""
        html = _read(_find(ui_root, "toast", "toast.html"))
        assert re.search(r"<button[^>]*\bmatIconButton\b", html), (
            "The dismiss button must be a Material icon button (matIconButton) "
            "so it keeps the 48px touch target."
        )


class TestToastSnackBarPosition:
    """The snackbar sits bottom center, above the navigation bar at compact, and
    clears the bottom safe-area inset (replaces the old bottom-right .pb-safe
    container)."""

    def test_when_toast_service_parsed_then_snackbar_is_bottom_center(self, ui_root):
        """MatSnackBar is positioned at the bottom center of the window."""
        code = _read(_find(ui_root, "toast", "toast.service.ts"))
        assert re.search(r"verticalPosition\s*:\s*['\"]bottom['\"]", code), (
            "The snackbar must open at the bottom (verticalPosition: 'bottom')."
        )
        assert re.search(r"horizontalPosition\s*:\s*['\"]center['\"]", code), (
            "The snackbar must open centered (horizontalPosition: 'center')."
        )

    def test_when_toast_service_parsed_then_panel_class_does_not_follow_window_size(
        self, ui_root
    ):
        """The panel class is fixed. MatSnackBar applies panelClass once, when the
        container is created, so a class picked from the window size at open time goes
        stale on resize, and it would lift toasts on pages routed outside the shell
        (login), where no navigation bar renders. The offset lives in _toast.scss."""
        code = _read(_find(ui_root, "toast", "toast.service.ts"))
        assert re.search(r"panelClass\s*:", code), "ToastService must pass a panelClass."
        assert not re.search(r"isCompact\(\)|WindowSizeClassService", code), (
            "The panel class must not follow the window size class."
        )
        assert "app-toast-above-nav-bar" not in code, (
            "The navigation bar offset belongs to _toast.scss, not to a panel class."
        )

    def test_when_toast_overlay_styles_loaded_then_offsets_clear_nav_bar_and_safe_area(
        self, toast_overlay_scss
    ):
        """The global overlay partial clears env(safe-area-inset-bottom) and, while the
        shell's navigation bar (.shell-nav-bar) is on screen, the bar itself: its published
        --app-nav-bar-block-size, falling back to its 64px + env(safe-area-inset-bottom)
        minimum."""
        scss = _read(toast_overlay_scss)
        assert re.search(
            r"\.app-toast\s*\{[^}]*env\(safe-area-inset-bottom\)", scss
        ), "The .app-toast snackbar container must clear env(safe-area-inset-bottom)."
        # The fallback sits in its own calc(): Sass evaluates var() arguments, and a bare
        # `64px + env(...)` there compiles to the invalid `64pxenv(...)`.
        assert re.search(
            r"body:has\(\.shell-nav-bar\)\s+\.mat-mdc-snack-bar-container\.app-toast\s*\{[^}]*"
            r"var\(\s*--app-nav-bar-block-size\s*,\s*calc\(\s*64px\s*\+\s*env\(safe-area-inset-bottom\)\s*\)\s*\)",
            scss,
        ), (
            "While .shell-nav-bar is on screen, the snackbar must be offset by the bar's "
            "block size (--app-nav-bar-block-size, falling back to 64px + env(safe-area-inset-bottom))."
        )
        assert "app-toast-above-nav-bar" not in scss, (
            "The offset must follow the bar's presence, not a panel class chosen at open time."
        )

    def test_when_toast_styles_loaded_then_they_use_tokens_without_color_literals(
        self, ui_root, toast_overlay_scss
    ):
        """Dark mode comes from the theme: toast styles paint from var(--mat-sys-*)
        and --app-* roles, with no color literals and no !important."""
        css = _read(_find(ui_root, "toast", "toast.css"))
        assert "var(--mat-sys-" in css, "toast.css must use --mat-sys-* tokens."
        for text in (css, _read(toast_overlay_scss)):
            assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", text), (
                "Toast styles must not contain color literals."
            )
            assert "!important" not in text, "Toast styles must not use !important."


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
#
# Invariant derived from Criteria A and B: MatSnackBar shows one snackbar at a
# time, so ToastService.show() replaces the toast on screen and toasts() holds
# at most one entry, always the most recently shown toast. dismiss(id) empties
# the list only when id is the toast on screen; dismissing a replaced or an
# already dismissed id is a no-op.
#
# The properties run against a pure Python model of that show/dismiss state.
# TestToastServiceReplaceSource anchors the model to toast.service.ts, and
# toast.spec.ts exercises the real service through MatSnackBarHarness.
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
    """Pure model of ToastService.show(): the new toast replaces the one on screen."""
    return [_make_toast(toast_id, variant, message)]


def _dismiss(toasts: list, toast_id: int) -> list:
    """Pure model of ToastService.dismiss(id): removes only the toast with that id."""
    return [t for t in toasts if t["id"] != toast_id]


def _show_many(n: int, variant: str) -> list:
    """Model n show() calls; ids count up from 0 like ToastService._nextId."""
    toasts: list = []
    for i in range(n):
        toasts = _show(toasts, i, variant, f"msg-{i}")
    return toasts


class TestToastServiceReplaceSource:
    """The model above mirrors toast.service.ts: show() sets the signal to the new
    toast alone, and dismiss() filters the signal by id."""

    def test_when_toast_service_parsed_then_show_replaces_the_toast_on_screen(
        self, ui_root
    ):
        """show() sets toasts() to a one-element list instead of appending to it."""
        code = _read(_find(ui_root, "toast", "toast.service.ts"))
        assert re.search(r"_toasts\.set\(\s*\[\s*\w+\s*\]\s*\)", code), (
            "ToastService.show() must replace the toast on screen "
            "(this._toasts.set([toast])), since MatSnackBar shows one snackbar at a time."
        )

    def test_when_toast_service_parsed_then_dismiss_removes_only_that_id(self, ui_root):
        """dismiss(id) filters toasts() by id, so a replaced id leaves the list unchanged."""
        code = _read(_find(ui_root, "toast", "toast.service.ts"))
        assert re.search(
            r"\.filter\(\s*\(?\s*(\w+)\s*\)?\s*=>\s*\1\.id\s*!==\s*id\s*\)", code
        ), "ToastService must remove a toast by filtering on its id (t.id !== id)."


@pytest.mark.skipif(not _HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
class TestToastServiceReplaceInvariant:
    """
    Property-based tests for the one-snackbar-at-a-time invariant implied by
    Criteria A and B: toasts() holds at most the latest toast, and dismiss(id)
    only affects the toast on screen.
    """

    @given(
        n=st.integers(min_value=1, max_value=10),
        variant=st.sampled_from(VARIANTS),
    )
    def test_when_toasts_shown_then_only_the_last_one_is_on_screen(self, n, variant):
        """After n show() calls, toasts() holds exactly the last toast shown."""
        toasts = _show_many(n, variant)
        assert [t["id"] for t in toasts] == [n - 1], (
            f"After {n} show() calls only the last toast (id={n - 1}) may be on screen; "
            f"got ids {[t['id'] for t in toasts]}."
        )

    @given(
        ops=st.lists(
            st.one_of(
                st.tuples(st.just("show"), st.sampled_from(VARIANTS)),
                st.tuples(st.just("dismiss"), st.integers(min_value=0, max_value=30)),
            ),
            max_size=30,
        )
    )
    def test_when_any_sequence_runs_then_at_most_the_latest_toast_is_on_screen(
        self, ops
    ):
        """Across any mix of show()/dismiss() calls, toasts() never holds more than
        one entry, and never a toast that a later show() replaced."""
        toasts: list = []
        shown: list[int] = []
        for op, arg in ops:
            if op == "show":
                toast_id = len(shown)
                toasts = _show(toasts, toast_id, arg, f"msg-{toast_id}")
                shown.append(toast_id)
            else:
                toasts = _dismiss(toasts, arg)
            assert len(toasts) <= 1, (
                f"toasts() must hold at most one entry; got {len(toasts)}."
            )
            if toasts:
                assert toasts[0]["id"] == shown[-1], (
                    f"The toast on screen must be the latest shown (id={shown[-1]}); "
                    f"got id={toasts[0]['id']}."
                )

    @given(
        n=st.integers(min_value=1, max_value=10),
        variant=st.sampled_from(VARIANTS),
    )
    def test_when_the_toast_on_screen_is_dismissed_then_none_remain(self, n, variant):
        """dismiss(id of the toast on screen) empties toasts()."""
        toasts = _show_many(n, variant)
        after = _dismiss(toasts, n - 1)
        assert after == [], (
            f"dismiss(id={n - 1}) must close the toast on screen; got {after}."
        )

    @given(
        n=st.integers(min_value=2, max_value=10),
        target_idx=st.integers(min_value=0, max_value=9),
        variant=st.sampled_from(VARIANTS),
    )
    def test_when_a_replaced_id_is_dismissed_then_the_toast_on_screen_is_preserved(
        self, n, target_idx, variant
    ):
        """dismiss(id of a replaced toast) is a no-op."""
        toasts = _show_many(n, variant)
        replaced_id = target_idx % (n - 1)
        after = _dismiss(toasts, replaced_id)
        assert after == toasts, (
            f"dismiss(id={replaced_id}) targets a replaced toast and must not change "
            f"toasts(); before={toasts}, after={after}."
        )

    @given(
        n=st.integers(min_value=1, max_value=10),
        variant=st.sampled_from(VARIANTS),
    )
    def test_when_toast_dismissed_twice_then_second_call_changes_nothing(
        self, n, variant
    ):
        """Dismissing the same id twice is idempotent."""
        toasts = _show_many(n, variant)
        after_first = _dismiss(toasts, n - 1)
        after_second = _dismiss(after_first, n - 1)
        assert after_second == after_first, (
            f"dismiss(id={n - 1}) called twice must not change toasts() again; "
            f"after first={after_first}, after second={after_second}."
        )
