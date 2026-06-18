"""
Tests for issue #6: feat(ui): Button — variants, sizes, loading/disabled states.

Source-blind: authored against acceptance criteria only, before any implementation.

Criteria covered:
  - [UNIT] `variant` (primary|secondary|ghost|danger) and `size` signal inputs
  - [UNIT] `loading` shows a spinner + sets `aria-busy`; `disabled` sets
    `disabled` + `aria-disabled`
  - [UNIT] Emits click only when not disabled/loading

Criteria skipped (not runtime-verifiable per oracle):
  - Min height ≥44px (`min-h-11`); visible `focus-visible` ring; dark-mode via
    tokens — NOT VERIFIABLE: browser-tier rendering concern; no static or
    unit-level observable signal
  - All tests pass — boilerplate suite gate; no per-criterion assertion
  - SOLID, clean code (methods < 10 lines …) — subjective prose; no concrete
    runtime or unit assertion

No Hypothesis property-based tests: the verifiable criteria target static
structural properties of the component source (presence of signal declarations,
ARIA attribute bindings, CSS class references, guard logic). These are existence
checks over a fixed file set, not parametric transforms whose output must obey
a law for all members of a varying input domain. Criterion 4 ("emits click only
when not disabled/loading") does imply a runtime invariant, but exercising it
requires Angular's TestBed; the static-analysis approach used here cannot
instantiate the component to apply Hypothesis strategies over boolean inputs.
"""

import pathlib
import re

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FRONTEND = (
    pathlib.Path(__file__).parent.parent
    / "project_initializer"
    / "templates"
    / "frontend"
)

UI_ROOT = FRONTEND / "src" / "app" / "shared" / "ui"

BUTTON_DIR = UI_ROOT / "button"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts_file() -> pathlib.Path:
    """Return the primary (non-spec) TypeScript file for the button component."""
    candidates = [f for f in BUTTON_DIR.glob("*.ts") if ".spec." not in f.name]
    if not candidates:
        raise FileNotFoundError(f"No non-spec .ts file found in {BUTTON_DIR}")
    primary = [f for f in candidates if "button" in f.name]
    return (primary or candidates)[0]


def _full_source() -> str:
    """Return concatenated source of .ts + any .html files in the button dir."""
    ts_text = _ts_file().read_text(encoding="utf-8")
    html_text = "".join(
        f.read_text(encoding="utf-8") for f in BUTTON_DIR.glob("*.html")
    )
    return ts_text + "\n" + html_text


# ---------------------------------------------------------------------------
# Criterion: `variant` (primary|secondary|ghost|danger) and `size` signal inputs
# ---------------------------------------------------------------------------


def test_when_ui_directory_inspected_then_button_folder_exists():
    """shared/ui/button/ must be a directory.

    Per criterion: 'variant (primary|secondary|ghost|danger) and size signal
    inputs'. The criterion implies a fully-realised Angular component living
    under shared/ui/, following the one-folder-per-component convention from
    requirements §5.
    """
    assert BUTTON_DIR.is_dir(), (
        "Expected shared/ui/button/ to exist as a directory under "
        "templates/frontend/src/app/shared/ui/"
    )


def test_when_button_folder_inspected_then_typescript_source_file_exists():
    """Button folder must contain at least one non-spec .ts source file.

    Per criterion: requirements §5 pattern: 'one folder per component
    (.ts + inline or .html template + .spec.ts)'.
    """
    non_spec_ts = [f for f in BUTTON_DIR.glob("*.ts") if ".spec." not in f.name]
    assert non_spec_ts, (
        "Expected at least one .ts source file (not .spec.ts) in shared/ui/button/"
    )


def test_when_button_ts_read_then_onpush_change_detection_is_set():
    """Button component must declare ChangeDetectionStrategy.OnPush.

    Per criterion: variant/size signal inputs imply a proper Angular shared/ui
    component. CLAUDE.md: 'OnPush change detection: Set changeDetection:
    ChangeDetectionStrategy.OnPush'.
    """
    ts = _ts_file().read_text(encoding="utf-8")
    assert "ChangeDetectionStrategy.OnPush" in ts, (
        "Expected 'ChangeDetectionStrategy.OnPush' in shared/ui/button/ .ts file"
    )


def test_when_button_ts_read_then_standalone_is_not_opted_out():
    """Button component must not opt out of standalone mode.

    CLAUDE.md: Angular 21 components are standalone by default — must NOT set
    standalone: false (opts out of standalone).
    """
    ts = _ts_file().read_text(encoding="utf-8")
    assert "standalone: false" not in ts, (
        "shared/ui/button/ .ts file must not contain 'standalone: false'"
    )


def test_when_button_ts_read_then_variant_signal_input_is_declared():
    """Button must declare a signal input named 'variant'.

    Per criterion: '`variant` (primary|secondary|ghost|danger) ... signal inputs'.
    CLAUDE.md: 'Signals for state: Use signal(), computed(), input(), output()'.
    Interpretation: the .ts file contains a property named 'variant' assigned
    via Angular's input() function (e.g. `readonly variant = input('primary')`).
    """
    ts = _ts_file().read_text(encoding="utf-8")
    assert re.search(r"\bvariant\s*=\s*input[<(]", ts), (
        "Expected a signal input named 'variant' in shared/ui/button/ .ts, "
        "e.g. `readonly variant = input('primary')` or "
        "`readonly variant = input<ButtonVariant>('primary')`. "
        "Per criterion: 'variant (primary|secondary|ghost|danger) signal inputs'."
    )


def test_when_button_ts_read_then_size_signal_input_is_declared():
    """Button must declare a signal input named 'size'.

    Per criterion: '`variant` ... and `size` signal inputs'.
    Interpretation: the .ts file contains a property named 'size' assigned via
    Angular's input() function (e.g. `readonly size = input('md')`).
    """
    ts = _ts_file().read_text(encoding="utf-8")
    assert re.search(r"\bsize\s*=\s*input[<(]", ts), (
        "Expected a signal input named 'size' in shared/ui/button/ .ts, "
        "e.g. `readonly size = input('md')` or `readonly size = input<ButtonSize>('md')`. "
        "Per criterion: 'variant ... and size signal inputs'."
    )


@pytest.mark.parametrize("variant", ["primary", "secondary", "ghost", "danger"])
def test_when_button_source_read_then_variant_value_is_referenced(variant):
    """Each of the four variant values must appear in the Button component source.

    Per criterion: 'variant (primary|secondary|ghost|danger)'.
    The variant names must appear in the .ts (as string literals, type-union
    members, or CSS-class mappings) or in the .html template.
    """
    combined = _full_source()
    assert variant in combined, (
        f"Expected the variant value '{variant}' in the Button component source "
        f"(.ts or .html). Per criterion: 'variant (primary|secondary|ghost|danger)'."
    )


# ---------------------------------------------------------------------------
# Criterion: `loading` shows a spinner + sets `aria-busy`;
#            `disabled` sets `disabled` + `aria-disabled`
# ---------------------------------------------------------------------------


def test_when_button_ts_read_then_loading_signal_input_is_declared():
    """Button must declare a signal input named 'loading'.

    Per criterion: '`loading` shows a spinner + sets `aria-busy`'.
    Interpretation: 'loading' is a signal input so consumers can bind
    `[loading]="isLoading"` from outside the component.
    """
    ts = _ts_file().read_text(encoding="utf-8")
    assert re.search(r"\bloading\s*=\s*input[<(]", ts), (
        "Expected a signal input named 'loading' in shared/ui/button/ .ts, "
        "e.g. `readonly loading = input(false)`. "
        "Per criterion: '`loading` shows a spinner + sets `aria-busy`'."
    )


def test_when_button_ts_read_then_disabled_signal_input_is_declared():
    """Button must declare a signal input named 'disabled'.

    Per criterion: '`disabled` sets `disabled` + `aria-disabled`'.
    Interpretation: 'disabled' is a signal input so consumers can bind
    `[disabled]="true"` from outside the component.
    """
    ts = _ts_file().read_text(encoding="utf-8")
    assert re.search(r"\bdisabled\s*=\s*input[<(]", ts), (
        "Expected a signal input named 'disabled' in shared/ui/button/ .ts, "
        "e.g. `readonly disabled = input(false)`. "
        "Per criterion: '`disabled` sets `disabled` + `aria-disabled`'."
    )


def test_when_button_source_read_then_aria_busy_attribute_is_present():
    """Button template must include an aria-busy attribute binding.

    Per criterion: '`loading` shows a spinner + sets `aria-busy`'.
    Assistive technology uses aria-busy to announce that the widget is updating;
    it must be bound to the loading state so it reflects the runtime value.
    """
    combined = _full_source()
    assert "aria-busy" in combined, (
        "Expected 'aria-busy' in the Button component source (.ts or .html). "
        "Per criterion: '`loading` shows a spinner + sets `aria-busy`'."
    )


def test_when_button_source_read_then_aria_disabled_attribute_is_present():
    """Button template must include an aria-disabled attribute binding.

    Per criterion: '`disabled` sets `disabled` + `aria-disabled`'.
    aria-disabled must be set alongside the native disabled attribute so that
    assistive technology reflects the disabled state correctly.
    """
    combined = _full_source()
    assert "aria-disabled" in combined, (
        "Expected 'aria-disabled' in the Button component source (.ts or .html). "
        "Per criterion: '`disabled` sets `disabled` + `aria-disabled`'."
    )


def test_when_button_source_read_then_native_disabled_binding_is_present():
    """Button template must bind the native HTML disabled attribute.

    Per criterion: '`disabled` sets `disabled` + `aria-disabled`'.
    Both the native HTML boolean attribute (read by browsers) and aria-disabled
    must be set. Accepted forms: `[disabled]`, `[attr.disabled]`, or a host
    binding that maps the disabled input to the button's disabled property.
    """
    combined = _full_source()
    has_disabled_binding = bool(
        re.search(r"\[(?:attr\.)?disabled\]|'?\[disabled\]'?", combined)
    )
    assert has_disabled_binding, (
        "Expected a native 'disabled' attribute binding in the Button component — "
        "e.g. '[disabled]=\"...\"' in the template or a host binding. "
        "Per criterion: '`disabled` sets `disabled` + `aria-disabled`'."
    )


def test_when_button_source_read_then_spinner_element_is_present():
    """Button template must contain a spinner element shown during loading.

    Per criterion: '`loading` shows a spinner'.
    The spinner must be present in the template (shown conditionally with @if or
    class binding). Accepted indicators: role='status', the animate-spin Tailwind
    utility, an <app-spinner> element, SpinnerComponent import, or a literal
    'spinner' reference in the source.
    """
    combined = _full_source()
    has_spinner = (
        'role="status"' in combined
        or "animate-spin" in combined
        or "app-spinner" in combined.lower()
        or "SpinnerComponent" in combined
        or bool(re.search(r"\bspinner\b", combined, re.IGNORECASE))
    )
    assert has_spinner, (
        "Expected a spinner element in the Button component source. Indicators: "
        "role='status', animate-spin, <app-spinner>, SpinnerComponent, or "
        "a 'spinner' reference. Per criterion: '`loading` shows a spinner'."
    )


# ---------------------------------------------------------------------------
# Criterion: Emits click only when not disabled/loading
# ---------------------------------------------------------------------------


def test_when_button_source_read_then_click_output_or_handler_is_declared():
    """Button must define a click output or a click handler method.

    Per criterion: 'Emits click only when not disabled/loading'.
    The component must emit or handle click events so consumers can react to
    user interaction. Accepted forms: an output() call for a click-like event,
    a handleClick/onClick method, or a (click) event binding in the template.
    """
    combined = _full_source()
    has_click = (
        bool(re.search(r"\boutput\s*[<(]", combined))
        or bool(
            re.search(r"\bon[Cc]lick\b|\bhandleClick\b|\bonButtonClick\b", combined)
        )
        or "(click)" in combined
    )
    assert has_click, (
        "Expected a click output (e.g. `readonly clicked = output()`) or a click "
        "handler method in the Button component source. "
        "Per criterion: 'Emits click only when not disabled/loading'."
    )


def test_when_button_source_read_then_click_is_guarded_against_disabled_or_loading():
    """Button click handler must guard against emitting when disabled or loading.

    Per criterion: 'Emits click only when not disabled/loading'.
    Interpretation: the component source must contain logic that prevents click
    emission when disabled or loading is true. Accepted guard forms:
      - Conditional early-return in a handler: `if (this.disabled() || ...) return`
      - Template short-circuit: `(click)="!disabled() && onClick()"`
      - Native HTML button [disabled] binding — a disabled <button> element
        does not fire click events, satisfying the criterion natively.
    The test accepts any of these patterns rather than prescribing one approach.
    """
    combined = _full_source()
    # Native disabled on a host <button> suppresses click events natively
    has_native_disabled_binding = bool(re.search(r"\[(?:attr\.)?disabled\]", combined))
    # Explicit guard: disabled/loading referenced near a guard keyword
    has_explicit_guard = bool(
        re.search(
            r"(disabled\(\)|loading\(\)|this\.disabled|this\.loading)"
            r".{0,60}?"
            r"(return|emit\(|&&|\|\|)",
            combined,
            re.DOTALL,
        )
    )
    assert has_native_disabled_binding or has_explicit_guard, (
        "Expected a click guard in the Button component preventing emission when "
        "disabled or loading. Acceptable: [disabled] host binding (native button "
        "suppresses clicks) or an explicit conditional in the click handler such as "
        "`if (this.disabled() || this.loading()) return;`. "
        "Per criterion: 'Emits click only when not disabled/loading'."
    )
