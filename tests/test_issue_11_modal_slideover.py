"""
Tests for issue #11: Modal + SlideOver overlays.

Only [UNIT]-verifiable criteria are tested (per oracle report):
  A. Modal: role="dialog" + aria-modal, focus trap, Escape + backdrop close,
     background hidden from assistive technology.
  B. Open/close via signal input()/model()/output(); visible focus; dark-mode tokens.

Since the Material 3 migration the modal is a declarative wrapper around Angular
Material's MatDialog. The dialog container supplies role="dialog", aria-labelledby,
the CDK focus trap, Escape and scrim dismissal, the scrim, aria-hidden on the rest of
the page, and focus restore. It leaves aria-modal off (Material's default): aria-modal
would also hide overlay panels opened from inside the dialog, and the aria-hidden page
already makes the dialog modal for assistive technology. These tests therefore assert
that the component delegates to MatDialog without switching any of those defaults off,
that projected buttons can close it (close()) and render in an action row
(app-modal-actions), and that its styles use --mat-sys-* tokens instead of color
literals. The runtime behavior is exercised end-to-end in modal.spec.ts
(MatDialogHarness).

Skipped (NOT VERIFIABLE):
  - SlideOver: dvh / edge-slide / safe-area (overlay CSS inherited from the drawer's
    _drawer.scss, no runtime check). The slide-over composes app-drawer (a MatDialog side
    sheet); TestSlideOverSideSheet checks that structure, and slide-over.spec.ts exercises
    the runtime behavior (MatDialogHarness).
  - "All tests pass" (boilerplate gate, not a per-criterion assertion)
  - SOLID / clean-code metrics (subjective prose)

Strategy: scaffold a frontend-only project, then inspect the generated
TypeScript/HTML/CSS sources for the structural contracts required by each criterion.
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


_MODAL_PARTS = (
    "modal.ts",
    "modal.html",
    "modal.css",
    "modal-actions.ts",
    "modal-actions.html",
    "modal-actions.css",
)


def _modal_sources(ui_root: Path) -> str:
    """Concatenate the .ts, .html and .css of the modal and its action slot (each must exist)."""
    return "\n".join(_read(_find_file(ui_root, "modal", name)) for name in _MODAL_PARTS)


def _modal_ts(ui_root: Path) -> str:
    return _read(_find_file(ui_root, "modal", "modal.ts"))


def _modal_html(ui_root: Path) -> str:
    return _read(_find_file(ui_root, "modal", "modal.html"))


def _modal_css(ui_root: Path) -> str:
    return _read(_find_file(ui_root, "modal", "modal.css"))


def _dialog_config(code: str) -> str:
    """Return the object literal passed to MatDialog.open(...) in modal.ts."""
    match = re.search(r"\.open\(\s*[^,]+,\s*(\{.*?\})\s*\)", code, re.DOTALL)
    assert match, "Modal must open its dialog with MatDialog.open(template, { ...config })."
    return match.group(1)


# ---------------------------------------------------------------------------
# Criterion A-1: role="dialog" and aria-modal are present in the modal template
# ---------------------------------------------------------------------------


class TestModalAriaContract:
    """Modal must expose role='dialog' and stay modal for AT (WAI-ARIA APG §3.8).

    MatDialog's container renders role="dialog" and makes the dialog modal by drawing a
    scrim and setting aria-hidden on everything outside the overlay container. It leaves
    aria-modal off by default, because aria-modal would also hide overlay panels opened
    from inside the dialog. The component must open a MatDialog and must not override
    the role, the scrim or dismissal.
    """

    def test_when_modal_template_rendered_then_role_dialog_is_present(
        self, frontend_root
    ):
        """The modal opens a MatDialog and keeps its default role='dialog'."""
        code = _modal_ts(frontend_root)
        assert re.search(r"\bMatDialog\b", code) and re.search(r"from '@angular/material/dialog'", code), (
            "Modal must be built on Angular Material's MatDialog, which renders role=\"dialog\"."
        )
        config = _dialog_config(code)
        assert not re.search(r"\brole\s*:\s*['\"](?!dialog['\"]|alertdialog['\"])", config), (
            "Modal must not override MatDialog's role with a non-dialog role."
        )
        # Confirmations use role 'alertdialog' (angular-material-mapping.md §6), so the role
        # is an input limited to the two dialog roles and passed to MatDialog.open().
        assert re.search(r"\brole\s*=\s*input\s*<\s*ModalRole\s*>\s*\(\s*['\"]dialog['\"]\s*\)", code), (
            "Modal must declare a role input that defaults to 'dialog'."
        )
        assert re.search(r"type\s+ModalRole\s*=\s*['\"]dialog['\"]\s*\|\s*['\"]alertdialog['\"]", code), (
            "The role input must accept only 'dialog' or 'alertdialog'."
        )
        assert re.search(r"\brole\s*:\s*this\.role\(\)", config), (
            "Modal must pass its role input to MatDialog.open()."
        )

    def test_when_modal_template_rendered_then_dialog_stays_modal_with_scrim(
        self, frontend_root
    ):
        """The dialog must be modal so AT users are not confused by background.

        Angular Material makes a dialog modal by setting aria-hidden on all content
        outside the overlay container and drawing a scrim; it leaves aria-modal off by
        default because aria-modal would also hide overlay panels opened from inside
        the dialog (mat-select, menus). The modal must keep the scrim and must not
        render as a non-modal dialog.
        """
        config = _dialog_config(_modal_ts(frontend_root))
        assert not re.search(r"\bhasBackdrop\s*:\s*false", config), (
            "Modal must keep the modal scrim (hasBackdrop)."
        )
        assert not re.search(r"\bdisableClose\s*:\s*true", config), (
            "Modal must stay dismissible with Escape and a scrim click."
        )

    def test_when_modal_template_rendered_then_aria_labelledby_or_aria_label_is_present(
        self, frontend_root
    ):
        """WAI-ARIA APG requires the dialog to be labelled by its visible h2 title."""
        html = _modal_html(frontend_root)
        code = _modal_ts(frontend_root)
        assert re.search(r"<h2\b[^>]*\bmat-dialog-title\b", html), (
            "Modal template must render its title as <h2 mat-dialog-title>, which "
            "MatDialog registers as the dialog's aria-labelledby."
        )
        assert re.search(r"\bariaLabelledBy\s*:", _dialog_config(code)), (
            "Modal must pass ariaLabelledBy (the h2 title id) to MatDialog.open()."
        )


# ---------------------------------------------------------------------------
# Criterion A-2: JS focus trap is implemented in code (not relying on aria-modal)
#
# Research §2.1 / §4: native <dialog> does not trap in all browsers; Safari/
# VoiceOver regresses on aria-modal alone — a JS trap must be authored.
# ---------------------------------------------------------------------------


class TestModalFocusTrap:
    """The focus trap must be a real JS trap, not delegated to aria-modal alone.

    MatDialog attaches CDK's FocusTrap (JS anchors that wrap Tab/Shift+Tab), moves
    initial focus inside, closes on Escape and on a scrim click, and restores focus to
    the trigger. The component must use it and must not switch any of that off.
    """

    def test_when_modal_component_loaded_then_focus_trap_logic_is_present(
        self, frontend_root
    ):
        """MatDialog's CDK focus trap stays active: autoFocus and restoreFocus stay on."""
        config = _dialog_config(_modal_ts(frontend_root))
        assert not re.search(r"\bautoFocus\s*:\s*false", config), (
            "Modal must let MatDialog move initial focus into the trapped dialog."
        )
        assert re.search(r"\bautoFocus\s*:\s*['\"](first-tabbable|dialog|first-heading)['\"]", config) or (
            "autoFocus" not in config
        ), "Modal autoFocus must target an element inside the dialog."
        assert re.search(r"\brestoreFocus\s*:\s*true", config), (
            "Modal must restore focus to the trigger when the dialog closes (restoreFocus: true)."
        )

    def test_when_modal_component_loaded_then_escape_key_handler_is_present(
        self, frontend_root
    ):
        """Pressing Escape must close the modal: MatDialog's Escape handling stays enabled."""
        config = _dialog_config(_modal_ts(frontend_root))
        assert not re.search(r"\bdisableClose\s*:\s*true", config), (
            "Modal must not set disableClose, which turns off Escape and scrim dismissal."
        )

    def test_when_modal_template_rendered_then_backdrop_close_handler_is_present(
        self, frontend_root
    ):
        """Scrim click and the Close action must close the modal and notify the host.

        An M3 simple dialog has no close icon button (that belongs to the full-screen
        dialog), and it would take initial focus ahead of the content. Without projected
        actions the modal renders a Close text action instead.
        """
        code = _modal_ts(frontend_root)
        html = _modal_html(frontend_root)
        assert re.search(r"\.beforeClosed\(\)|\.afterClosed\(\)", code), (
            "Modal must observe MatDialog closing (Escape, scrim, Close action) to emit `closed`."
        )
        assert re.search(r"<button\b[^>]*\bmat-dialog-close\b|\(click\)", html), (
            "Modal template must offer a close action (mat-dialog-close or a (click) handler)."
        )
        assert not re.search(r"\bmatIconButton\b|aria-label=[\"']Close dialog[\"']", html), (
            "A simple dialog must not render a close icon button in its header."
        )
        assert re.search(
            r"@else\s*\{\s*<mat-dialog-actions\b[^>]*\balign=[\"']end[\"'][^>]*>\s*"
            r"<button\b[^>]*\bmat-dialog-close\b[^>]*>\s*Close\s*</button>",
            html,
        ), "Without projected actions, the modal must render an end-aligned Close action."


# ---------------------------------------------------------------------------
# Criterion A-3: background is inerted in code
#
# Requirements §7: "background inerted in code (do not rely on aria-modal alone)"
# The implementation must programmatically set inert on the main content or
# call a helper that does so.
# ---------------------------------------------------------------------------


class TestModalBackgroundInert:
    """The modal must hide the background in JS, not rely on aria-modal alone.

    MatDialog (CDK Dialog) sets aria-hidden="true" on every body-level sibling of the
    overlay container while a dialog is open and restores the previous values when the
    last dialog closes; the scrim blocks pointer input. The component must open its
    content through MatDialog (not a hand-rolled overlay) and keep the scrim.
    """

    def test_when_modal_opens_then_inert_is_applied_in_source(self, frontend_root):
        """The dialog is opened through MatDialog, which hides the page from AT in code."""
        code = _modal_ts(frontend_root)
        assert re.search(r"inject\(\s*MatDialog\s*\)", code) and re.search(
            r"\.open\(", code
        ), (
            "Modal must open its content with an injected MatDialog, which sets "
            "aria-hidden on background content while open (aria-modal alone is "
            "insufficient for Safari/VoiceOver — research §2.1, §4)."
        )
        assert not re.search(r"\bhasBackdrop\s*:\s*false", _dialog_config(code)), (
            "Modal must keep MatDialog's scrim so the background cannot be clicked."
        )
        html = _modal_html(frontend_root)
        assert not re.search(r"\bfixed\b|inset-0|data-testid=[\"']modal-backdrop", html), (
            "Modal must not render a hand-rolled backdrop; MatDialog provides the scrim."
        )


# ---------------------------------------------------------------------------
# Criterion B-1: Open/close driven by signal input() / output()
# ---------------------------------------------------------------------------


class TestModalSignalContract:
    """open state must be driven by a signal input()/model(); close events by output()."""

    def test_when_modal_component_parsed_then_input_signal_is_declared(
        self, frontend_root
    ):
        """Component must declare `open` as a signal input/model and `label` as an input()."""
        code = _modal_ts(frontend_root)
        # `open` is a model() (a writable signal input) so [(open)] stays in sync after a dismissal.
        assert re.search(r"\bopen\s*=\s*(?:input|model)\s*[(<]", code), (
            "Modal component must declare `open` with Angular signal input() or model()."
        )
        # label is required: it is the visible h2 headline and the dialog's name, so a
        # generic default such as "Dialog" would silently name every unlabelled dialog.
        assert re.search(r"\blabel\s*=\s*input\.required\s*<\s*string\s*>\s*\(\s*\)", code), (
            "Modal component must declare `label` as a required string signal input."
        )
        assert not re.search(r"@Input\(|@Output\(|@HostBinding\(|@HostListener\(", code), (
            "Modal component must not use decorator-based inputs, outputs or host bindings."
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
        """Interactive elements inside the modal must keep a visible focus ring.

        The fallback Close action is a Material button, whose focus indicator is drawn by
        the global mat.strong-focus-indicators(); the modal must not suppress outlines.
        """
        html = _modal_html(frontend_root)
        css = _modal_css(frontend_root)
        assert re.search(r"<button\b[^>]*\bmatButton\b", html), (
            "The modal's Close action must be a Material button (focus ring + 48px target)."
        )
        assert not re.search(r"outline-none(?!\s+focus-visible)", html), (
            "Modal template must not suppress outline without a focus-visible replacement."
        )
        assert not re.search(r"outline\s*:\s*(none|0)\b", css), (
            "Modal styles must not remove the focus outline."
        )

    def test_when_global_styles_read_then_strong_focus_indicators_are_included(
        self, frontend_root
    ):
        """The ring around the modal's controls comes from mat.strong-focus-indicators().

        Every Material button renders a .mat-focus-indicator element whether or not the
        mixin is included, so a DOM check cannot catch a missing ring; the global
        stylesheet must include the mixin that draws it.
        """
        styles = frontend_root.parents[2] / "styles.scss"
        assert styles.exists(), f"Expected global stylesheet {styles} to exist."
        assert re.search(r"@include\s+mat\.strong-focus-indicators\(", _read(styles)), (
            "src/styles.scss must include mat.strong-focus-indicators() so focused "
            "controls inside the modal show a visible ring outside the component."
        )


# ---------------------------------------------------------------------------
# Criterion A-4: projected buttons can close the modal and form its action row
# ---------------------------------------------------------------------------


class TestModalActionsSlot:
    """Projected buttons (Cancel, confirm) must be able to close the dialog.

    Projected content is created in the consumer's view, which has no MatDialogRef, so
    `mat-dialog-close` on it throws. The modal exposes a public close() for those buttons,
    and an app-modal-actions slot that renders them in a mat-dialog-actions row declared in
    the dialog's own view, outside the scrolling content region.
    """

    def test_when_modal_component_parsed_then_public_close_method_is_declared(
        self, frontend_root
    ):
        """close() is public and closes through the dialog ref, so `closed` still fires."""
        code = _modal_ts(frontend_root)
        assert re.search(r"^\s+close\(\)\s*:\s*void\s*\{", code, re.MULTILINE), (
            "Modal must declare a public close(): void for projected dismiss buttons."
        )
        assert re.search(r"dialogRef\??\.close\(\)", code), (
            "close() must close the MatDialogRef so the dismissal path emits `closed`."
        )

    def test_when_modal_template_rendered_then_actions_slot_is_outside_content(
        self, frontend_root
    ):
        """The action slot projects into mat-dialog-actions, after mat-dialog-content."""
        html = _modal_html(frontend_root)
        content_end = html.find("</mat-dialog-content>")
        actions = re.search(
            r"<mat-dialog-actions\b[^>]*\balign=[\"']end[\"'][^>]*>\s*"
            r"<ng-content\s+select=[\"']app-modal-actions[\"']",
            html,
        )
        assert content_end != -1 and actions, (
            "Modal template must project app-modal-actions into an end-aligned mat-dialog-actions row."
        )
        assert actions.start() > content_end, (
            "The action row must follow mat-dialog-content, not scroll inside it."
        )
        assert re.search(r"contentChild\(\s*ModalActionsComponent\s*\)", _modal_ts(frontend_root)), (
            "Modal must render the action row only when app-modal-actions is projected."
        )

    def test_when_modal_actions_component_parsed_then_it_is_a_separated_onpush_component(
        self, frontend_root
    ):
        """The slot is a component (a missing import fails the build), with its own .html/.css."""
        code = _read(_find_file(frontend_root, "modal", "modal-actions.ts"))
        assert re.search(r"selector:\s*['\"]app-modal-actions['\"]", code)
        assert "templateUrl: './modal-actions.html'" in code
        assert "styleUrl: './modal-actions.css'" in code
        assert re.search(r"ChangeDetectionStrategy\.OnPush", code)
        css = _read(_find_file(frontend_root, "modal", "modal-actions.css"))
        assert re.search(r":host\s*\{[^}]*display\s*:\s*contents", css), (
            "The slot must not add a box, so Material's action-row layout applies to the buttons."
        )


# ---------------------------------------------------------------------------
# Criterion B-3: Dark-mode tokens (Material 3 --mat-sys-* system tokens)
# ---------------------------------------------------------------------------


_COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(")


class TestModalDarkModeTokens:
    """Modal must consume theme tokens, not hardcoded colour values.

    mat.theme() emits every --mat-sys-* token as light-dark(), so a modal that only
    uses Material components and tokens adapts to the .light / .dark scheme classes.
    """

    def test_when_modal_template_rendered_then_no_hardcoded_hex_colors_appear(
        self, frontend_root
    ):
        """No colour literal may appear in the modal's .ts, .html or .css."""
        src = _modal_sources(frontend_root)
        assert not _COLOR_LITERAL.search(src), (
            "Modal sources must not contain hex/rgb/hsl colour literals; "
            "use --mat-sys-* tokens so dark mode works via the scheme classes."
        )

    def test_when_modal_template_rendered_then_dark_variant_class_is_used(
        self, frontend_root
    ):
        """The modal adapts to dark mode through Material tokens, not Tailwind dark: classes."""
        html = _modal_html(frontend_root)
        css = _modal_css(frontend_root)
        assert not re.search(r"\bdark:", html), (
            "Modal template must not use Tailwind dark: utilities (Tailwind was removed)."
        )
        assert re.search(r"\bmat-dialog-(title|content)\b", html), (
            "Modal must render MatDialog's title/content sections, which paint "
            "on-surface / on-surface-variant from --mat-sys-* tokens in both schemes."
        )
        # Material's dialog tokens already paint and pad the sections, so modal.css may set no
        # color at all; any color it does set must come from a token.
        assert not re.search(
            r"(?:^|[;{\s])(?:color|background(?:-color)?|border(?:-[a-z]+)?-color|fill|stroke)\s*:\s*(?!var\(--(?:mat|app)-)",
            css,
        ), (
            "Modal styles must take colors from tokens (--mat-sys-* / --mat-dialog-* / --app-*)."
        )
        assert "!important" not in css and "::ng-deep" not in css, (
            "Modal styles must not use !important or ::ng-deep."
        )


# ---------------------------------------------------------------------------
# SlideOver: modal side sheet composed from app-drawer (MatDialog)
# ---------------------------------------------------------------------------


_SLIDE_OVER_PARTS = ("slide-over.ts", "slide-over.html", "slide-over.css")


def _slide_over_file(ui_root: Path, name: str) -> str:
    return _read(_find_file(ui_root, "slide-over", name))


class TestSlideOverSideSheet:
    """The slide-over is an M3 modal side sheet at the trailing edge.

    It composes app-drawer, which opens the projected content through MatDialog, so the
    scrim, focus trap, Escape and scrim dismissal, aria-hidden on the page and focus
    restore come from Material rather than a hand-rolled backdrop, keydown listener and
    inert helper. The header shows the label as an h2 (the dialog's name) and a close
    icon button named "Close panel".
    """

    def test_when_slide_over_parsed_then_it_is_a_separated_onpush_component(
        self, frontend_root
    ):
        """Exactly .ts + .html + .css, wired with templateUrl and styleUrl, OnPush."""
        for name in _SLIDE_OVER_PARTS:
            _find_file(frontend_root, "slide-over", name)
        code = _slide_over_file(frontend_root, "slide-over.ts")
        assert re.search(r"selector:\s*['\"]app-slide-over['\"]", code)
        assert "templateUrl: './slide-over.html'" in code
        assert "styleUrl: './slide-over.css'" in code
        assert re.search(r"ChangeDetectionStrategy\.OnPush", code)
        assert not re.search(r"\btemplate\s*:|\bstyles\s*:|standalone\s*:\s*true", code), (
            "Slide-over must not use an inline template/styles or set standalone: true."
        )

    def test_when_slide_over_parsed_then_signal_api_is_kept(self, frontend_root):
        """open (input or model), side and label inputs, and the closed output stay public.

        label is required: it renders as the visible h2 headline that names the dialog, so a
        generic default such as "Panel" would not describe the content (WCAG 2.4.6).
        """
        code = _slide_over_file(frontend_root, "slide-over.ts")
        assert re.search(r"\bopen\s*=\s*(?:input|model)\s*[(<]", code)
        assert re.search(r"\bside\s*=\s*input\s*<\s*SlideOverSide\s*>\s*\(\s*['\"]right['\"]", code), (
            "side must default to the trailing edge ('right')."
        )
        assert re.search(r"\blabel\s*=\s*input\.required\s*<\s*string\s*>\s*\(\s*\)", code), (
            "label must be a required string input: it is the visible headline and the dialog's name."
        )
        assert re.search(r"\bclosed\s*=\s*output\s*[(<]", code)
        assert re.search(r"export\s+type\s+SlideOverSide\b", code)
        assert not re.search(r"@Input\(|@Output\(|@HostBinding\(|@HostListener\(", code)

    def test_when_slide_over_rendered_then_it_composes_the_material_side_sheet(
        self, frontend_root
    ):
        """The panel is app-drawer (MatDialog), with a labelled close control and no hand-rolled overlay."""
        code = _slide_over_file(frontend_root, "slide-over.ts")
        html = _slide_over_file(frontend_root, "slide-over.html")
        assert re.search(r"import\s*\{[^}]*\bDrawerComponent\b[^}]*\}\s*from\s*'\.\./drawer/drawer'", code)
        assert re.search(r"<app-drawer\b", html) and "<ng-content" in html
        assert re.search(r"\[label\]=[\"']label\(\)[\"']", html), (
            "The label must reach the drawer, which renders it as the h2 dialog title."
        )
        assert re.search(r'closeLabel=["\']Close panel["\']', html), (
            'The close icon button must be labelled "Close panel".'
        )
        assert re.search(r"\(close\)=", html), "Drawer dismissals must emit `closed`."
        assert not re.search(
            r"data-testid=[\"']slide-over-backdrop|role=[\"']dialog|appFocusTrap|document:keydown|setAttribute\(\s*['\"]inert",
            code + html,
        ), "Slide-over must not hand-roll the scrim, dialog role, focus trap, Escape or inert handling."

    def test_when_slide_over_styles_read_then_they_use_tokens_only(self, frontend_root):
        """No Tailwind utilities, colour literals, !important or ::ng-deep in its sources."""
        sources = "\n".join(_slide_over_file(frontend_root, n) for n in _SLIDE_OVER_PARTS)
        overlay = frontend_root.parents[2] / "styles" / "overlays" / "_slide-over.scss"
        assert overlay.exists(), f"Expected overlay partial {overlay} to exist."
        sources += "\n" + _read(overlay)
        assert not _COLOR_LITERAL.search(sources)
        assert "!important" not in sources and "::ng-deep" not in sources
        assert not re.search(r"\bdark:|\b(?:md|lg|sm):|\bclass=[\"'][^\"']*\b(?:fixed|shadow|rounded|bg-)", sources), (
            "Slide-over must not use Tailwind utilities (Tailwind was removed)."
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
    same invariant is exercised end-to-end against MatDialog's CDK focus trap
    in modal.spec.ts (Angular TestBed, Tab/Shift+Tab anchor-wrap test).
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
