"""
Tests for issue #6: feat(ui): Button — variants, sizes, loading/disabled states.

Originally authored against the acceptance criteria; updated for the Material 3
migration (Angular Material `matButton`, no Tailwind).

Criteria covered:
  - [UNIT] `variant` (primary|secondary|ghost|danger) and `size` signal inputs
  - [UNIT] `loading` shows a spinner (`mat-progress-spinner`) + sets `aria-busy`;
    `disabled` sets `disabled` + `aria-disabled`
  - [UNIT] Emits click only when not disabled/loading
  - [STRUCTURE] component split into button.ts + button.html + button.css,
    wired with templateUrl/styleUrl
  - [M3] 48px target: the template renders a Material `matButton`, which ships
    a 48px touch target at density 0; the CSS never hides it
  - [M3] styling through `--mat-sys-*` / `--mat-button-*` tokens only: no color
    literals, no `!important`, no `::ng-deep`, no Tailwind utility classes

Criteria skipped (not runtime-verifiable per oracle):
  - Visible focus ring (supplied globally by `mat.strong-focus-indicators()`)
    and rendered contrast in both schemes — browser-tier rendering concern
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
    candidates = {f.name: f for f in BUTTON_DIR.glob("*.ts") if ".spec." not in f.name}
    if not candidates:
        raise FileNotFoundError(f"No non-spec .ts file found in {BUTTON_DIR}")
    # Match the whole file name, not a substring, and never rely on glob order, which differs
    # between filesystems.
    for primary in ("button.ts", "button.component.ts"):
        if primary in candidates:
            return candidates[primary]
    return candidates[sorted(candidates)[0]]


def _full_source() -> str:
    """Return concatenated source of the non-spec .ts + .html + .css files."""
    files = sorted(
        f
        for pattern in ("*.ts", "*.html", "*.css")
        for f in BUTTON_DIR.glob(pattern)
        if ".spec." not in f.name
    )
    return "\n".join(f.read_text(encoding="utf-8") for f in files)


def _html_text() -> str:
    """Return the button template (button.html)."""
    return (BUTTON_DIR / "button.html").read_text(encoding="utf-8")


def _css_text() -> str:
    """Return the button component stylesheet (button.css)."""
    return (BUTTON_DIR / "button.css").read_text(encoding="utf-8")


# Tailwind utility residue: any of these in a class attribute or TS string means
# the Material 3 migration left a utility class behind.
TAILWIND_RESIDUE = re.compile(
    r"\b(flex|inline-flex|grid-cols|items-|justify-|gap-[0-9]|p[xytblr]?-[0-9]"
    r"|m[xytblr]?-[0-9]|w-[0-9]|h-[0-9]|min-h-|max-w-|text-(xs|sm|base|lg|xl|[0-9])"
    r"|font-(medium|semibold|bold|display|sans|mono)|bg-|border-|rounded|shadow"
    r"|ring-|dark:|md:|lg:|sm:|xl:|hover:|focus:|animate-|sr-only|truncate"
    r"|space-[xy]-|divide-|opacity-[0-9]|transition-|duration-)"
)


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
    """Button must report its busy-disabled state through aria-disabled.

    Per criterion: '`disabled` sets `disabled` + `aria-disabled`'.
    Material 3 migration: `disabled` sets the native attribute, which assistive
    technology already reports as disabled. While `loading`, the inner matButton
    binds Material's `disabledInteractive`, which renders aria-disabled="true"
    instead of the native attribute, so a focused button keeps keyboard focus
    (a natively disabled focused button drops focus to <body>). The ARIA state
    belongs on the inner <button>, not on the generic <app-button> host.
    """
    html = _html_text()
    assert re.search(r"\[disabledInteractive\]=", html), (
        "Expected a '[disabledInteractive]' binding on the matButton in button.html, "
        "so the busy button renders aria-disabled and stays focusable. "
        "Per criterion: '`disabled` sets `disabled` + `aria-disabled`'."
    )
    assert "'[attr.aria-disabled]'" not in _ts_file().read_text(encoding="utf-8"), (
        "aria-disabled must not be bound on the <app-button> host (a generic element); "
        "Material renders it on the inner <button>."
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
    The spinner must be present in the template (shown conditionally with @if).
    Accepted indicators: a Material <mat-progress-spinner> / <mat-spinner>
    element, role='status', an <app-spinner> element, a SpinnerComponent
    import, or a CSS @keyframes animation. The Tailwind animate-spin utility is
    no longer accepted (Material 3 migration).
    """
    combined = _full_source()
    has_spinner = (
        "<mat-progress-spinner" in combined
        or "<mat-spinner" in combined
        or 'role="status"' in combined
        or "app-spinner" in combined.lower()
        or "SpinnerComponent" in combined
        or "@keyframes" in combined
    )
    assert has_spinner, (
        "Expected a spinner element in the Button component source. Indicators: "
        "<mat-progress-spinner>, <mat-spinner>, role='status', <app-spinner>, "
        "SpinnerComponent, or a CSS @keyframes animation. "
        "Per criterion: '`loading` shows a spinner'."
    )
    assert "animate-spin" not in combined, (
        "The Tailwind 'animate-spin' utility must not remain after the Material 3 "
        "migration; use mat-progress-spinner or a CSS animation."
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


# ---------------------------------------------------------------------------
# Material 3 migration: file separation, Material button, tokens only
# ---------------------------------------------------------------------------


def test_when_button_folder_inspected_then_component_is_split_into_ts_html_css():
    """button.ts must wire button.html and button.css via templateUrl/styleUrl.

    Requirement: every component has exactly <name>.ts + <name>.html +
    <name>.css, with no inline template or inline styles.
    """
    for name in ("button.ts", "button.html", "button.css"):
        assert (BUTTON_DIR / name).is_file(), (
            f"Expected shared/ui/button/{name} to exist"
        )
    ts = (BUTTON_DIR / "button.ts").read_text(encoding="utf-8")
    assert re.search(r"templateUrl:\s*'\./button\.html'", ts), (
        "Expected templateUrl: './button.html' in shared/ui/button/button.ts"
    )
    assert re.search(r"styleUrl:\s*'\./button\.css'", ts), (
        "Expected styleUrl: './button.css' in shared/ui/button/button.ts"
    )
    assert not re.search(r"\btemplate:\s*`", ts), (
        "button.ts must not declare an inline template"
    )
    assert not re.search(r"\bstyles:\s*[\[`']", ts), (
        "button.ts must not declare inline styles"
    )


def test_when_button_template_read_then_material_button_provides_the_touch_target():
    """The template must render a native <button matButton> from MatButtonModule.

    Replaces the Tailwind `min-h-11` check: Angular Material's M3 button ships a
    48px touch target at density 0 (M3 target size: 48 x 48dp). The component
    CSS must not hide that target or override the container height.
    """
    html = _html_text()
    ts = _ts_file().read_text(encoding="utf-8")
    assert re.search(r"<button\b[^>]*\[?matButton\]?", html), (
        "Expected a native <button> carrying matButton in shared/ui/button/button.html"
    )
    assert "MatButtonModule" in ts or re.search(r"\bMatButton\b", ts), (
        "Expected MatButtonModule (or MatButton) in the button component imports"
    )
    css = _css_text()
    assert "touch-target-display" not in css, (
        "button.css must not hide Material's 48px touch target"
    )
    assert "container-height" not in css, (
        "button.css must not override the M3 button container height"
    )


def test_when_button_ts_read_then_variants_map_to_m3_appearances():
    """Variants map to M3 appearances: primary=filled, secondary=outlined, ghost=text, danger=filled."""
    ts = _ts_file().read_text(encoding="utf-8")
    for variant, appearance in (
        ("primary", "filled"),
        ("secondary", "outlined"),
        ("ghost", "text"),
        ("danger", "filled"),
    ):
        assert re.search(rf"\b{variant}:\s*'{appearance}'", ts), (
            f"Expected variant '{variant}' to map to the '{appearance}' matButton "
            "appearance in shared/ui/button/button.ts"
        )


def test_when_button_css_read_then_danger_uses_error_roles():
    """The danger variant sets the filled button tokens to the M3 error roles."""
    css = _css_text()
    assert re.search(
        r"--mat-button-filled-container-color:\s*var\(--mat-sys-error\)", css
    ), "Expected danger to set --mat-button-filled-container-color to var(--mat-sys-error)"
    assert re.search(
        r"--mat-button-filled-label-text-color:\s*var\(--mat-sys-on-error\)", css
    ), "Expected danger to set --mat-button-filled-label-text-color to var(--mat-sys-on-error)"


def test_when_button_css_read_then_only_tokens_style_it():
    """button.css styles through --mat-sys-* tokens only.

    Replaces the Tailwind `dark:` check: colors come from --mat-sys-* roles, which
    mat.theme resolves for both color schemes, so no scheme-specific rules or
    color literals are needed.
    """
    css = _css_text()
    assert "var(--mat-sys-" in css, "Expected button.css to use --mat-sys-* tokens"
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css), "button.css must not contain hex colors"
    assert not re.search(r"\b(?:rgba?|hsla?)\(", css), (
        "button.css must not contain rgb()/hsl() color literals"
    )
    assert "!important" not in css, "button.css must not use !important"
    assert "::ng-deep" not in css, "button.css must not use ::ng-deep"


def test_when_button_template_and_ts_read_then_no_tailwind_utility_classes_remain():
    """No Tailwind utility classes in the template's class attributes or TS strings."""
    html = _html_text()
    class_names = re.findall(r'\bclass="([^"]*)"', html) + re.findall(
        r"\[class\.([\w-]+)\]", html
    )
    for value in class_names:
        assert not TAILWIND_RESIDUE.search(value), (
            f"Tailwind utility residue in button.html class: {value!r}"
        )
    ts = _ts_file().read_text(encoding="utf-8")
    for literal in re.findall(r"'([^'\n]*)'", ts):
        assert not TAILWIND_RESIDUE.search(literal), (
            f"Tailwind utility residue in a button.ts string: {literal!r}"
        )


def test_when_button_template_read_then_spinner_tabindex_is_removed():
    """The loading spinner must not carry a tabindex inside the native <button>.

    MatProgressSpinner sets a static tabindex="-1" on its host, and the HTML
    content model forbids a <button> descendant with a tabindex attribute, so the
    template binds [attr.tabindex]="null" on <mat-progress-spinner>.
    """
    html = _html_text()
    spinner = re.search(r"<mat-progress-spinner\b[^>]*>", html)
    assert spinner, "Expected <mat-progress-spinner> in shared/ui/button/button.html"
    assert re.search(r'\[attr\.tabindex\]="null"', spinner.group(0)), (
        "Expected [attr.tabindex]=\"null\" on <mat-progress-spinner> so the button "
        "has no descendant with a tabindex attribute"
    )
