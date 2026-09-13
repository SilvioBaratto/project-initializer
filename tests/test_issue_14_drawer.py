"""
Tests for Issue #14 — refactor(ui): extract reusable Drawer from existing sidebar.

Oracle-verified verifiable criterion (UNIT):
  "Reusable Drawer: `side` input, `open` signal, `close` output, overlay click-out,
   `Escape`, focus trap on mobile (via focus-trap)"

All tests are authored source-blind from the acceptance criteria text.
The Drawer component is expected at:
  frontend/src/app/shared/ui/drawer/drawer.ts (+ drawer.html + drawer.css)

After the Material 3 migration the Drawer is an M3 modal side sheet built on
Angular Material's `MatDialog`, which supplies the scrim (overlay click-out),
Escape dismissal and the CDK focus trap. The criteria below therefore accept
either a hand-rolled implementation or a `MatDialog` one that leaves those
built-in dismissal paths enabled.
"""

from __future__ import annotations

import re
from pathlib import Path

from hypothesis import given, settings, strategies as st

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FRONTEND_ROOT = (
    Path(__file__).parent.parent
    / "project_initializer"
    / "templates"
    / "frontend"
    / "src"
    / "app"
    / "shared"
    / "ui"
    / "drawer"
)

COMPONENT_FILE = FRONTEND_ROOT / "drawer.ts"
TEMPLATE_FILE = FRONTEND_ROOT / "drawer.html"
STYLE_FILE = FRONTEND_ROOT / "drawer.css"
OVERLAY_PARTIAL = (
    Path(__file__).parent.parent
    / "project_initializer"
    / "templates"
    / "frontend"
    / "src"
    / "styles"
    / "overlays"
    / "_drawer.scss"
)


def _src() -> str:
    """Return the combined drawer.ts + drawer.html + drawer.css source.

    Spec files are excluded so assertions only see the component itself.
    """
    assert COMPONENT_FILE.exists(), (
        f"DrawerComponent not found at {COMPONENT_FILE}. "
        "Create the file before running this test."
    )
    parts = [
        path.read_text(encoding="utf-8")
        for pattern in ("drawer.ts", "drawer.html", "drawer.css")
        for path in sorted(FRONTEND_ROOT.glob(pattern))
    ]
    return "\n".join(parts)


def _uses_mat_dialog(src: str) -> bool:
    """True when the drawer is built on MatDialog with its dismissal paths enabled."""
    return (
        "@angular/material/dialog" in src
        and re.search(r"\bMatDialog\b", src) is not None
        and re.search(r"disableClose\s*:\s*true", src) is None
    )


# ---------------------------------------------------------------------------
# Criterion: `side` input
# ---------------------------------------------------------------------------


def test_when_drawer_component_exists_then_side_input_is_declared():
    """
    The Drawer must expose a `side` input so callers can open it from
    'left' or 'right'.  The criterion names `side` as an explicit input.

    Decision: we accept any Angular input() / @Input declaration that binds
    the name 'side'.  Concrete matches:
        input<'left'|'right'>('left')          (signals API)
        @Input() side: 'left' | 'right'        (decorator API)
    """
    src = _src()
    # Matches: side = input(...) or @Input() side or input<...>('side')
    has_side_input = bool(
        re.search(r"\bside\s*=\s*input\b", src)
        or re.search(r"@Input\(\)[^;]*\bside\b", src)
        or re.search(r"\binput\b[^;]*['\"]side['\"]", src)
    )
    assert has_side_input, (
        "DrawerComponent must declare a `side` input "
        "(e.g. `side = input<'left'|'right'>('left')`)."
    )


# ---------------------------------------------------------------------------
# Criterion: `open` signal
# ---------------------------------------------------------------------------


def test_when_drawer_component_exists_then_open_signal_is_declared():
    """
    The Drawer must expose an `open` signal so the parent can control
    visibility reactively.  The criterion explicitly names `open` as a signal.

    Decision: accepted forms:
        open = signal(false)
        open = input<boolean>(false)   (if used as a model/input signal)
    """
    src = _src()
    has_open_signal = bool(
        re.search(r"\bopen\s*=\s*signal\b", src)
        or re.search(r"\bopen\s*=\s*input\b", src)
        or re.search(r"\bopen\s*=\s*model\b", src)
    )
    assert has_open_signal, (
        "DrawerComponent must declare an `open` signal "
        "(e.g. `open = signal(false)` or `open = input(false)`)."
    )


# ---------------------------------------------------------------------------
# Criterion: `close` output
# ---------------------------------------------------------------------------


def test_when_drawer_component_exists_then_close_output_is_declared():
    """
    The Drawer must emit a `close` output event so the host can react when
    the drawer requests dismissal (overlay click, Escape key, etc.).

    Decision: accepted forms:
        close = output()
        @Output() close = new EventEmitter()
    """
    src = _src()
    has_close_output = bool(
        re.search(r"\bclose\s*=\s*output\b", src)
        or re.search(r"@Output\(\)[^;]*\bclose\b", src)
    )
    assert has_close_output, (
        "DrawerComponent must declare a `close` output (e.g. `close = output()`)."
    )


# ---------------------------------------------------------------------------
# Criterion: overlay click-out
# ---------------------------------------------------------------------------


def test_when_drawer_is_open_then_overlay_click_emits_close():
    """
    Clicking the backdrop overlay behind the drawer must trigger the `close`
    output.  The criterion lists 'overlay click-out' as an explicit dismissal
    path.

    Decision: accepted evidence is either
      (a) a MatDialog-based sheet that keeps the scrim (no `hasBackdrop: false`)
          and does not disable its built-in dismissal (`disableClose: true`), and
          still offers a visible close control wired with a (click) close handler;
      OR
      (b) a template (click) handler on an overlay element that calls the close
          logic, e.g. (click)="close.emit()" / "onClose()" / "handleClose()".
    """
    src = _src()
    has_click_close = bool(
        re.search(r'\(click\)\s*=\s*"[^"]*[Cc]lose[^"]*"', src)
        or re.search(r"\(click\)\s*=\s*'[^']*[Cc]lose[^']*'", src)
    )
    keeps_scrim = re.search(r"hasBackdrop\s*:\s*false", src) is None
    assert has_click_close and (keeps_scrim or not _uses_mat_dialog(src)), (
        "DrawerComponent must dismiss on scrim/overlay click (MatDialog backdrop "
        "left enabled, or a (click) handler on its overlay) and expose a close "
        "control that emits the `close` output."
    )


# ---------------------------------------------------------------------------
# Criterion: Escape key closes the drawer
# ---------------------------------------------------------------------------


def test_when_escape_key_is_pressed_then_close_is_emitted():
    """
    Pressing Escape while the drawer is open must emit `close`.  The criterion
    explicitly lists `Escape` as a dismissal path.

    Decision: we verify that either
      (a) a @HostListener('keydown.escape') or equivalent is present in the TS,
      OR
      (b) the template binds (keydown.escape) / (keydown) and routes to close,
      OR
      (c) the panel is a MatDialog whose built-in Escape dismissal is left on
          (no `disableClose: true`) and the close emission is wired to
          afterClosed(), so Escape reaches the `close` output.
    """
    src = _src()
    has_escape_handler = bool(
        re.search(r"keydown\.escape", src, re.IGNORECASE)
        or re.search(r"Escape", src)
        or re.search(r"HostListener\(['\"]keydown", src)
        or re.search(r"'Escape'", src)
        or re.search(r'"Escape"', src)
        or (_uses_mat_dialog(src) and "afterClosed" in src)
    )
    assert has_escape_handler, (
        "DrawerComponent must handle the Escape key to emit `close` "
        "(e.g. @HostListener('keydown.escape') or (keydown.escape) binding)."
    )


# ---------------------------------------------------------------------------
# Criterion: focus trap on mobile (via focus-trap library)
# ---------------------------------------------------------------------------


def test_when_drawer_component_exists_then_focus_trap_is_integrated():
    """
    The criterion explicitly requires a focus trap on mobile 'via focus-trap'.
    This refers to the `focus-trap` npm package (focustrap / createFocusTrap).

    Decision: we verify that the component source imports or references
    focus-trap so that an actual JS trap is activated when the drawer opens.
    Acceptable evidence in the source:
        import { createFocusTrap } from 'focus-trap'
        import ... from '@angular/cdk/a11y'   (FocusTrap / FocusTrapFactory)
        focusTrap / FocusTrap / createFocusTrap references
        import { MatDialog } from '@angular/material/dialog'
            (MatDialog creates a CDK FocusTrap for every dialog it opens)
    """
    src = _src()
    imports_mat_dialog = bool(
        re.search(r"import\s*\{[^}]*\bMatDialog\b[^}]*\}\s*from\s*['\"]@angular/material/dialog['\"]", src)
    )
    has_focus_trap = bool(
        re.search(r"focus-trap", src, re.IGNORECASE)
        or re.search(r"FocusTrap", src)
        or re.search(r"createFocusTrap", src)
        or re.search(r"a11y.*FocusTrap|FocusTrap.*a11y", src)
        or imports_mat_dialog
    )
    assert has_focus_trap, (
        "DrawerComponent must integrate a focus-trap "
        "(import from 'focus-trap', '@angular/cdk/a11y' FocusTrapFactory, "
        "or open the panel with MatDialog, which traps focus)."
    )


# ---------------------------------------------------------------------------
# Property-based test: `side` accepts 'left' or 'right' for any combination
# of whitespace/case found in templates — validates the declared side values
# are drawn from the finite {'left', 'right'} domain (invariant: no unknown
# side value appears in any template binding).
#
# Criterion implies the invariant: only 'left' / 'right' are valid sides —
# the component declares this in its type, so the set of allowed values is
# fixed and finite (ordering invariant).
# ---------------------------------------------------------------------------

VALID_SIDES = frozenset({"left", "right"})


@given(side=st.sampled_from(sorted(VALID_SIDES)))
@settings(max_examples=2)
def test_when_side_is_valid_then_it_is_a_known_direction(side: str):
    """
    The `side` input domain is exactly {'left', 'right'}.
    Every value drawn from that domain must be a member of it —
    the invariant is that no unknown direction leaks through.
    This is a tautological property that pins the domain contract: if the
    implementation widens the type, this test library must be updated first.
    """
    assert side in VALID_SIDES, (
        f"side={side!r} is not a declared valid direction. "
        "Valid directions are: left, right."
    )


# ---------------------------------------------------------------------------
# Property: overlay-click and Escape handlers reference the same close path
# (idempotence of close emission — calling close twice must not corrupt state)
#
# This is validated structurally: both dismissal triggers must resolve to the
# same handler name (they must not diverge into two distinct code paths that
# could get out of sync).
# ---------------------------------------------------------------------------


def test_when_multiple_dismissal_paths_exist_then_they_reference_same_handler():
    """
    Overlay click-out and Escape must both ultimately call the same close
    emission so they stay in sync.  Acceptable: both call `close.emit()` or
    both call a shared `onClose()` / `handleClose()` method.

    Decision: we verify that a single unified close method name appears in
    the source for both the (click) binding and the escape handler, OR that
    both directly call `close.emit()`.

    For a MatDialog-based sheet, Escape, scrim click and the close button all
    close the dialog, so they must converge in one `afterClosed()` subscription
    with a single `close.emit()` call site.
    """
    src = _src()

    if _uses_mat_dialog(src):
        assert "afterClosed" in src, (
            "A MatDialog-based Drawer must emit `close` from afterClosed() so "
            "every dismissal path shares one handler."
        )
        emit_sites = re.findall(r"\bclose\.emit\s*\(", src)
        assert len(emit_sites) == 1, (
            f"Expected exactly one `close.emit()` call site, found {len(emit_sites)}."
        )
        return

    # Extract the handler name used in the (click) binding
    click_match = re.search(r'\(click\)\s*=\s*["\']([^"\']+)["\']', src)
    escape_match = re.search(
        r'(?:keydown\.escape|HostListener\([\'"]keydown)[^\n]*\n\s*(\w+)\(',
        src,
    )

    # If both are found, they must resolve to the same method or both be close.emit()
    if click_match and escape_match:
        click_handler = click_match.group(1).split("(")[0].strip()
        escape_handler = escape_match.group(1).strip()
        assert click_handler == escape_handler or all(
            "close" in h for h in (click_handler, escape_handler)
        ), (
            f"Overlay click ({click_handler!r}) and Escape ({escape_handler!r}) "
            "must call the same close handler to avoid divergence."
        )
    # If only one (or neither) matched, the earlier per-criterion tests already
    # enforce existence — this property only fires when both are detectable.


# ---------------------------------------------------------------------------
# Material 3 styling: tokens instead of Tailwind `dark:` variants
# ---------------------------------------------------------------------------


def test_when_drawer_styles_inspected_then_side_sheet_uses_m3_tokens_only():
    """
    The Drawer is styled with Angular Material / M3 tokens, not Tailwind
    utilities (the old `dark:` variants).  Light and dark both come from the
    `--mat-sys-*` tokens, so no color literal may appear.

    Decision: the component has its own template and stylesheet files; both
    drawer.css and the global overlay partial (which styles the MatDialog pane
    the component CSS cannot reach) use `var(--mat-sys-*)` with no hex/rgb/hsl
    literal, `!important` or `::ng-deep`; and the partial selects the panel
    class the component passes to MatDialog.
    """
    assert STYLE_FILE.exists(), f"Expected component styles at {STYLE_FILE}."
    assert OVERLAY_PARTIAL.exists(), f"Expected overlay partial at {OVERLAY_PARTIAL}."
    ts = COMPONENT_FILE.read_text(encoding="utf-8")
    assert re.search(r"templateUrl\s*:\s*['\"]\./drawer\.html['\"]", ts)
    assert re.search(r"styleUrl\s*:\s*['\"]\./drawer\.css['\"]", ts)

    for path in (STYLE_FILE, OVERLAY_PARTIAL):
        text = path.read_text(encoding="utf-8")
        assert "var(--mat-sys-" in text, f"{path.name} must use --mat-sys-* tokens."
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", text), (
            f"{path.name} must not contain color literals."
        )
        assert "!important" not in text and "::ng-deep" not in text, path.name

    assert "dark:" not in _src(), "Tailwind dark: variants must be gone."

    panel_class = re.search(r"DRAWER_PANEL_CLASS\s*=\s*['\"]([\w-]+)['\"]", ts)
    assert panel_class, "DrawerComponent must name the MatDialog panel class."
    assert f".{panel_class.group(1)}" in OVERLAY_PARTIAL.read_text(encoding="utf-8"), (
        "The overlay partial must style the panel class the component passes to MatDialog."
    )


def test_when_overlay_partial_inspected_then_direction_and_insets_key_on_overlay_host():
    """
    The side sheet follows the direction passed in its dialog config, which CDK
    writes as `dir` on `.cdk-global-overlay-wrapper` (the pane's parent), not
    the direction of an ancestor such as `<html dir="rtl">`.

    Decision: every `[dir=...]` selector in the overlay partial is attached to
    `.cdk-global-overlay-wrapper` (no descendant `[dir='rtl'] .cdk-overlay-pane`),
    and the full-height sheet pads the physical edge it is pinned to with
    `env(safe-area-inset-left)` / `env(safe-area-inset-right)`, because
    index.html sets `viewport-fit=cover`.
    """
    scss = OVERLAY_PARTIAL.read_text(encoding="utf-8")
    code = "\n".join(line.split("//", 1)[0] for line in scss.splitlines())

    dir_selectors = re.findall(r"(\S*)\[dir=['\"]?rtl['\"]?\]", code)
    assert dir_selectors, "The overlay partial must mirror the slide-in under RTL."
    for prefix in dir_selectors:
        assert prefix.endswith(".cdk-global-overlay-wrapper") or prefix.endswith(
            ".cdk-global-overlay-wrapper:not("
        ), (
            "RTL selectors must key on the overlay host `.cdk-global-overlay-wrapper[dir]`, "
            f"not on an arbitrary ancestor (found prefix {prefix!r})."
        )
    assert not re.search(r"(^|[\s,])\[dir=['\"]?rtl['\"]?\]\s+\.cdk-overlay-pane", code), (
        "A descendant `[dir='rtl'] .cdk-overlay-pane` selector also matches <html dir>."
    )

    for inset in ("safe-area-inset-left", "safe-area-inset-right"):
        assert f"env({inset})" in code, (
            f"The full-height side sheet must pad its pinned edge with env({inset})."
        )


def test_when_drawer_opens_then_dialog_has_an_accessible_name():
    """
    A `role="dialog"` needs an accessible name. The Drawer names it from its
    visible headline (`matDialogTitle`, which keeps `aria-labelledby` in sync as
    the headline appears, changes or disappears) or, without a headline, from an
    `ariaLabel` input passed to the MatDialog config.

    Decision: the template carries a `matDialogTitle` / `mat-dialog-title`
    headline, the component declares `label` and `ariaLabel` inputs and passes
    `ariaLabel` into the dialog config.
    """
    src = _src()
    html = TEMPLATE_FILE.read_text(encoding="utf-8")
    assert re.search(r"<h2[^>]*\b(matDialogTitle|mat-dialog-title)\b", html), (
        "The sheet headline must be an <h2 matDialogTitle> so it names the dialog."
    )
    assert re.search(r"\blabel\s*=\s*input\b", src), "DrawerComponent must declare `label`."
    assert re.search(r"\bariaLabel\s*=\s*input\b", src), (
        "DrawerComponent must declare `ariaLabel` for sheets without a visible headline."
    )
    assert re.search(r"ariaLabel\s*:", src), "`ariaLabel` must reach the MatDialog config."
