"""
Tests for issue #8: feat(ui): Checkbox + Radio controls.

Source-blind: authored against acceptance criteria only, before any implementation.

Criteria covered:
  - [T3] Checkbox + Radio render with an associated <label>; support
    checked/disabled/error signal inputs

Criteria skipped (not runtime-verifiable per oracle):
  - ≥44×44px effective touch target; visible focus-visible ring; dark-mode
    tokens — NOT VERIFIABLE: browser-tier rendering; no static or unit-level
    observable signal
  - Integrate with FormField error / aria-describedby contract — NOT VERIFIABLE:
    no concrete runtime or unit check inferable from criterion alone
  - All tests pass — boilerplate suite gate; no per-criterion assertion
  - SOLID, clean code (methods < 10 lines …) — subjective prose; no concrete
    runtime or unit assertion

No Hypothesis property-based tests: all verifiable checks are existence
assertions over a fixed file set (Angular component source + template).
There is no parametric transform whose output must obey a law for all members
of a varying input domain — the same reasoning as test_issue_6_button.py.
"""

import pathlib
import re


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

CHECKBOX_DIR = UI_ROOT / "checkbox"
RADIO_DIR = UI_ROOT / "radio"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _primary_ts(component_dir: pathlib.Path) -> pathlib.Path:
    """Return the primary (non-spec) TypeScript source file for a component."""
    candidates = [f for f in component_dir.glob("*.ts") if ".spec." not in f.name]
    if not candidates:
        raise FileNotFoundError(f"No non-spec .ts file found in {component_dir}")
    name = component_dir.name  # e.g. 'checkbox' or 'radio'
    primary = [f for f in candidates if name in f.name]
    return (primary or candidates)[0]


def _full_source(component_dir: pathlib.Path) -> str:
    """Return concatenated source of the non-spec .ts + .html + .css files in component_dir."""
    files = sorted(
        f
        for pattern in ("*.ts", "*.html", "*.css")
        for f in component_dir.glob(pattern)
        if ".spec." not in f.name
    )
    return "\n".join(f.read_text(encoding="utf-8") for f in files)


# ---------------------------------------------------------------------------
# CHECKBOX — folder / file structure
# ---------------------------------------------------------------------------


def test_when_ui_directory_inspected_then_checkbox_folder_exists():
    """shared/ui/checkbox/ must be a directory.

    Per criterion: 'Checkbox + Radio render with an associated <label>'.
    Follows the one-folder-per-component convention from requirements §5.
    """
    assert CHECKBOX_DIR.is_dir(), (
        "Expected shared/ui/checkbox/ to exist as a directory under "
        "templates/frontend/src/app/shared/ui/"
    )


def test_when_checkbox_folder_inspected_then_typescript_source_file_exists():
    """Checkbox folder must contain at least one non-spec .ts source file.

    Per requirements §5: 'one folder per component (.ts + inline or .html
    template + .spec.ts)'.
    """
    non_spec_ts = [f for f in CHECKBOX_DIR.glob("*.ts") if ".spec." not in f.name]
    assert non_spec_ts, (
        "Expected at least one .ts source file (not .spec.ts) in shared/ui/checkbox/"
    )


# ---------------------------------------------------------------------------
# CHECKBOX — Angular conventions (OnPush, standalone)
# ---------------------------------------------------------------------------


def test_when_checkbox_ts_read_then_onpush_change_detection_is_set():
    """Checkbox component must declare ChangeDetectionStrategy.OnPush.

    CLAUDE.md: 'OnPush change detection: Set changeDetection:
    ChangeDetectionStrategy.OnPush'. Per criterion: a properly structured
    shared/ui component.
    """
    ts = _primary_ts(CHECKBOX_DIR).read_text(encoding="utf-8")
    assert "ChangeDetectionStrategy.OnPush" in ts, (
        "Expected 'ChangeDetectionStrategy.OnPush' in shared/ui/checkbox/ .ts file"
    )


def test_when_checkbox_ts_read_then_standalone_is_not_opted_out():
    """Checkbox must not opt out of standalone mode.

    CLAUDE.md: Angular 21 components are standalone by default; must NOT set
    standalone: false.
    """
    ts = _primary_ts(CHECKBOX_DIR).read_text(encoding="utf-8")
    assert "standalone: false" not in ts, (
        "shared/ui/checkbox/ .ts file must not contain 'standalone: false'"
    )


# ---------------------------------------------------------------------------
# CHECKBOX — signal inputs: checked, disabled, error
# ---------------------------------------------------------------------------


def test_when_checkbox_ts_read_then_checked_signal_input_is_declared():
    """Checkbox must declare a signal input named 'checked'.

    Per criterion: 'support checked/disabled/error'.
    CLAUDE.md: 'Signals for state: Use signal(), computed(), input(), output()'.
    Interpretation: the .ts file contains a property named 'checked' assigned
    via Angular's input() function (e.g. `readonly checked = input(false)`).
    """
    ts = _primary_ts(CHECKBOX_DIR).read_text(encoding="utf-8")
    assert re.search(r"\bchecked\s*=\s*input[<(]", ts), (
        "Expected a signal input named 'checked' in shared/ui/checkbox/ .ts, "
        "e.g. `readonly checked = input(false)` or "
        "`readonly checked = input<boolean>(false)`. "
        "Per criterion: 'support checked/disabled/error'."
    )


def test_when_checkbox_ts_read_then_disabled_signal_input_is_declared():
    """Checkbox must declare a signal input named 'disabled'.

    Per criterion: 'support checked/disabled/error'.
    """
    ts = _primary_ts(CHECKBOX_DIR).read_text(encoding="utf-8")
    assert re.search(r"\bdisabled\s*=\s*input[<(]", ts), (
        "Expected a signal input named 'disabled' in shared/ui/checkbox/ .ts, "
        "e.g. `readonly disabled = input(false)`. "
        "Per criterion: 'support checked/disabled/error'."
    )


def test_when_checkbox_ts_read_then_error_signal_input_is_declared():
    """Checkbox must declare a signal input for the error state.

    Per criterion: 'support checked/disabled/error'.
    Interpretation: the .ts file contains a property named 'error' (or
    'errorMessage'/'hasError') assigned via Angular's input() function.
    """
    ts = _primary_ts(CHECKBOX_DIR).read_text(encoding="utf-8")
    has_error_input = bool(re.search(r"\berror\w*\s*=\s*input[<(]", ts))
    assert has_error_input, (
        "Expected a signal input for the error state in shared/ui/checkbox/ .ts, "
        "e.g. `readonly error = input('')` or `readonly errorMessage = input<string>('')`. "
        "Per criterion: 'support checked/disabled/error'."
    )


# ---------------------------------------------------------------------------
# CHECKBOX — associated <label>
# ---------------------------------------------------------------------------


def _checkbox_source() -> str:
    """Return the Checkbox component source: non-spec .ts + .html + .css files."""
    files = sorted(
        f
        for pattern in ("*.ts", "*.html", "*.css")
        for f in CHECKBOX_DIR.glob(pattern)
        if ".spec." not in f.name
    )
    return "\n".join(f.read_text(encoding="utf-8") for f in files)


def test_when_checkbox_source_read_then_label_element_is_present():
    """Checkbox must render a <label> element.

    Per criterion: 'render with an associated <label>'.
    A <label> element is required so assistive technology can announce the
    control's accessible name. The component wraps Angular Material's
    <mat-checkbox>, which renders `<label for="<id>-input">` around its projected
    content, so the source either declares a <label> or uses <mat-checkbox>.
    """
    combined = _checkbox_source()
    assert "<label" in combined or "<mat-checkbox" in combined, (
        "Expected a '<label' element or Angular Material's '<mat-checkbox' (which "
        "renders the <label>) in the Checkbox component source (.ts/.html/.css). "
        "Per criterion: 'render with an associated <label>'."
    )


def test_when_checkbox_source_read_then_label_is_associated_with_control():
    """Checkbox label must be associated with the control.

    Per criterion: 'render with an *associated* <label>'.
    Accepted association patterns:
    - <label [for]="..."> or <label for="..."> pointing to the input's id
    - Label element wrapping the native <input> element (implicit association)
    - The label text projected into <mat-checkbox>, which Material places in a
      `<label [for]="inputId">` that points at its native input
    """
    combined = _checkbox_source()
    has_for = bool(re.search(r"\bfor\s*=", combined))
    has_htmlfor = "htmlFor" in combined
    # Wrapping pattern: label tag occurs before a closing </label> that follows an input
    has_wrapping = bool(
        re.search(r"<label[^>]*>(?:[^<]|<(?!/?label\b))*<input", combined, re.DOTALL)
    )
    projects_label = bool(
        re.search(
            r"<mat-checkbox\b[^>]*>(?:(?!</mat-checkbox>).)*\blabel\(\)"
            r"(?:(?!</mat-checkbox>).)*</mat-checkbox>",
            combined,
            re.DOTALL,
        )
    )
    assert has_for or has_htmlfor or has_wrapping or projects_label, (
        "Expected the Checkbox <label> to be associated with its control. "
        "Accepted: `[for]='...'` / `for='...'` attribute on the label, the "
        "label element wrapping the <input>, or `label()` projected into "
        "<mat-checkbox>. "
        "Per criterion: 'render with an associated <label>'."
    )


# ---------------------------------------------------------------------------
# CHECKBOX — Material 3 structure, target size, tokens
# ---------------------------------------------------------------------------


def test_when_checkbox_folder_inspected_then_template_and_styles_are_separate_files():
    """Checkbox ships checkbox.ts + checkbox.html + checkbox.css.

    The component is wired with templateUrl/styleUrl and has no inline template
    or styles.
    """
    ts = (CHECKBOX_DIR / "checkbox.ts").read_text(encoding="utf-8")
    assert (CHECKBOX_DIR / "checkbox.html").is_file(), "Expected checkbox.html"
    assert (CHECKBOX_DIR / "checkbox.css").is_file(), "Expected checkbox.css"
    assert re.search(r"templateUrl:\s*'\./checkbox\.html'", ts), (
        "Expected templateUrl: './checkbox.html' in checkbox.ts"
    )
    assert re.search(r"styleUrl:\s*'\./checkbox\.css'", ts), (
        "Expected styleUrl: './checkbox.css' in checkbox.ts"
    )
    assert not re.search(r"\btemplate\s*:", ts), "checkbox.ts must not inline a template"
    assert not re.search(r"\bstyles\s*:", ts), "checkbox.ts must not inline styles"


def test_when_checkbox_source_read_then_it_uses_material_checkbox_with_48px_target():
    """Checkbox uses Angular Material's MatCheckbox and keeps a 48px target.

    M3 accessibility: touch targets of at least 48 x 48px. MatCheckbox renders a
    48px touch target at density 0; the component CSS gives each checkbox a 48px
    row so stacked checkboxes never overlap their targets.
    """
    ts = (CHECKBOX_DIR / "checkbox.ts").read_text(encoding="utf-8")
    html = (CHECKBOX_DIR / "checkbox.html").read_text(encoding="utf-8")
    css = (CHECKBOX_DIR / "checkbox.css").read_text(encoding="utf-8")
    assert "@angular/material/checkbox" in ts, "Expected MatCheckbox import"
    assert "<mat-checkbox" in html, "Expected <mat-checkbox> in checkbox.html"
    assert re.search(r"min-(?:block-size|height)\s*:\s*48px", css), (
        "Expected a 48px minimum row height in checkbox.css"
    )


def test_when_checkbox_css_read_then_it_uses_m3_tokens_and_no_color_literals():
    """Checkbox CSS colors come from --mat-sys-* tokens, in both color schemes.

    No hex/rgb/hsl literals, no !important and no ::ng-deep.
    """
    css = (CHECKBOX_DIR / "checkbox.css").read_text(encoding="utf-8")
    assert "var(--mat-sys-" in css, "Expected --mat-sys-* tokens in checkbox.css"
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(", css), (
        "checkbox.css must not contain color literals"
    )
    assert "!important" not in css, "checkbox.css must not use !important"
    assert "::ng-deep" not in css, "checkbox.css must not use ::ng-deep"


_TAILWIND_UTILITY = re.compile(
    r"^(?:[a-z0-9-]+:)?(?:flex|inline-flex|grid|items-\S+|justify-\S+|gap-\S+|"
    r"[pm][xytblr]?-\S+|[wh]-\S+|size-\S+|min-[wh]-\S+|max-w-\S+|text-\S+|"
    r"font-\S+|bg-\S+|border(?:-\S+)?|rounded(?:-\S+)?|shadow(?:-\S+)?|ring-\S+|"
    r"accent-\S+|opacity-\S+|shrink-\S+|select-none|cursor-\S+|sr-only|truncate|"
    r"transition(?:-\S+)?|duration-\S+|animate-\S+)$"
)


def test_when_checkbox_source_read_then_no_tailwind_utilities_remain():
    """Checkbox template and TS carry no Tailwind utility classes."""
    html = (CHECKBOX_DIR / "checkbox.html").read_text(encoding="utf-8")
    ts = (CHECKBOX_DIR / "checkbox.ts").read_text(encoding="utf-8")
    tokens = [
        token
        for value in re.findall(r"\bclass=\"([^\"]*)\"", html)
        for token in value.split()
    ]
    tokens += re.findall(r"\[class\.([^\]]+)\]", html)
    tokens += [
        token
        for literal in re.findall(r"'([^'\n]*)'", ts)
        for token in literal.split()
    ]
    offenders = sorted({t for t in tokens if _TAILWIND_UTILITY.match(t)})
    assert not offenders, f"Tailwind utilities remain in shared/ui/checkbox/: {offenders}"


# ---------------------------------------------------------------------------
# RADIO — folder / file structure
# ---------------------------------------------------------------------------


def test_when_ui_directory_inspected_then_radio_folder_exists():
    """shared/ui/radio/ must be a directory.

    Per criterion: 'Checkbox + Radio render with an associated <label>'.
    Follows the one-folder-per-component convention from requirements §5.
    """
    assert RADIO_DIR.is_dir(), (
        "Expected shared/ui/radio/ to exist as a directory under "
        "templates/frontend/src/app/shared/ui/"
    )


def test_when_radio_folder_inspected_then_typescript_source_file_exists():
    """Radio folder must contain at least one non-spec .ts source file.

    Per requirements §5: 'one folder per component (.ts + inline or .html
    template + .spec.ts)'.
    """
    non_spec_ts = [f for f in RADIO_DIR.glob("*.ts") if ".spec." not in f.name]
    assert non_spec_ts, (
        "Expected at least one .ts source file (not .spec.ts) in shared/ui/radio/"
    )


# ---------------------------------------------------------------------------
# RADIO — Angular conventions (OnPush, standalone)
# ---------------------------------------------------------------------------


def test_when_radio_ts_read_then_onpush_change_detection_is_set():
    """Radio component must declare ChangeDetectionStrategy.OnPush.

    CLAUDE.md: 'OnPush change detection: Set changeDetection:
    ChangeDetectionStrategy.OnPush'.
    """
    ts = _primary_ts(RADIO_DIR).read_text(encoding="utf-8")
    assert "ChangeDetectionStrategy.OnPush" in ts, (
        "Expected 'ChangeDetectionStrategy.OnPush' in shared/ui/radio/ .ts file"
    )


def test_when_radio_ts_read_then_standalone_is_not_opted_out():
    """Radio must not opt out of standalone mode.

    CLAUDE.md: Angular 21 components are standalone by default; must NOT set
    standalone: false.
    """
    ts = _primary_ts(RADIO_DIR).read_text(encoding="utf-8")
    assert "standalone: false" not in ts, (
        "shared/ui/radio/ .ts file must not contain 'standalone: false'"
    )


# ---------------------------------------------------------------------------
# RADIO — signal inputs: checked, disabled, error
# ---------------------------------------------------------------------------


def test_when_radio_ts_read_then_checked_signal_input_is_declared():
    """Radio must declare a signal input named 'checked'.

    Per criterion: 'support checked/disabled/error'.
    Interpretation: the .ts file contains a property named 'checked' assigned
    via Angular's input() function (e.g. `readonly checked = input(false)`).
    """
    ts = _primary_ts(RADIO_DIR).read_text(encoding="utf-8")
    assert re.search(r"\bchecked\s*=\s*input[<(]", ts), (
        "Expected a signal input named 'checked' in shared/ui/radio/ .ts, "
        "e.g. `readonly checked = input(false)`. "
        "Per criterion: 'support checked/disabled/error'."
    )


def test_when_radio_ts_read_then_disabled_signal_input_is_declared():
    """Radio must declare a signal input named 'disabled'.

    Per criterion: 'support checked/disabled/error'.
    """
    ts = _primary_ts(RADIO_DIR).read_text(encoding="utf-8")
    assert re.search(r"\bdisabled\s*=\s*input[<(]", ts), (
        "Expected a signal input named 'disabled' in shared/ui/radio/ .ts, "
        "e.g. `readonly disabled = input(false)`. "
        "Per criterion: 'support checked/disabled/error'."
    )


def test_when_radio_ts_read_then_error_signal_input_is_declared():
    """Radio must declare a signal input for the error state.

    Per criterion: 'support checked/disabled/error'.
    Interpretation: the .ts file contains a property named 'error' (or
    'errorMessage'/'hasError') assigned via Angular's input() function.
    """
    ts = _primary_ts(RADIO_DIR).read_text(encoding="utf-8")
    has_error_input = bool(re.search(r"\berror\w*\s*=\s*input[<(]", ts))
    assert has_error_input, (
        "Expected a signal input for the error state in shared/ui/radio/ .ts, "
        "e.g. `readonly error = input('')` or `readonly errorMessage = input<string>('')`. "
        "Per criterion: 'support checked/disabled/error'."
    )


# ---------------------------------------------------------------------------
# RADIO — associated <label>
# ---------------------------------------------------------------------------


def test_when_radio_source_read_then_label_element_is_present():
    """Radio must render a <label> element.

    Per criterion: 'render with an associated <label>'.
    A <label> element is required so assistive technology can announce the
    control's accessible name. The component wraps Angular Material's
    <mat-radio-button>, which renders `<label for="<id>-input">` around its
    projected content, so the source either declares a <label> or uses
    <mat-radio-button>.
    """
    combined = _full_source(RADIO_DIR)
    assert "<label" in combined or "<mat-radio-button" in combined, (
        "Expected a '<label' element or Angular Material's '<mat-radio-button' "
        "(which renders the <label>) in the Radio component source (.ts/.html/.css). "
        "Per criterion: 'render with an associated <label>'."
    )


def test_when_radio_source_read_then_label_is_associated_with_control():
    """Radio label must be associated with the control.

    Per criterion: 'render with an *associated* <label>'.
    Accepted association patterns:
    - <label [for]="..."> or <label for="..."> pointing to the input's id
    - Label element wrapping the native <input> element (implicit association)
    - The label text projected into <mat-radio-button>, which Material places
      in a `<label [for]="inputId">` that points at its native input
    """
    combined = _full_source(RADIO_DIR)
    has_for = bool(re.search(r"\bfor\s*=", combined))
    has_htmlfor = "htmlFor" in combined
    has_wrapping = bool(
        re.search(r"<label[^>]*>(?:[^<]|<(?!/?label\b))*<input", combined, re.DOTALL)
    )
    projects_label = bool(
        re.search(
            r"<mat-radio-button\b[^>]*>(?:(?!</mat-radio-button>).)*\blabel\(\)"
            r"(?:(?!</mat-radio-button>).)*</mat-radio-button>",
            combined,
            re.DOTALL,
        )
    )
    assert has_for or has_htmlfor or has_wrapping or projects_label, (
        "Expected the Radio <label> to be associated with its control. "
        "Accepted: `[for]='...'` / `for='...'` attribute on the label, the "
        "label element wrapping the <input>, or `label()` projected into "
        "<mat-radio-button>. "
        "Per criterion: 'render with an associated <label>'."
    )


# ---------------------------------------------------------------------------
# RADIO — Material 3 structure, forms integration, target size, tokens
# ---------------------------------------------------------------------------


def test_when_radio_folder_inspected_then_template_and_styles_are_separate_files():
    """Radio ships radio.ts + radio.html + radio.css.

    The component is wired with templateUrl/styleUrl and has no inline template
    or styles.
    """
    ts = (RADIO_DIR / "radio.ts").read_text(encoding="utf-8")
    assert (RADIO_DIR / "radio.html").is_file(), "Expected radio.html"
    assert (RADIO_DIR / "radio.css").is_file(), "Expected radio.css"
    assert re.search(r"templateUrl:\s*'\./radio\.html'", ts), (
        "Expected templateUrl: './radio.html' in radio.ts"
    )
    assert re.search(r"styleUrl:\s*'\./radio\.css'", ts), (
        "Expected styleUrl: './radio.css' in radio.ts"
    )
    assert not re.search(r"\btemplate\s*:", ts), "radio.ts must not inline a template"
    assert not re.search(r"\bstyles\s*:", ts), "radio.ts must not inline styles"


def test_when_radio_ts_read_then_selector_inputs_and_value_accessor_are_kept():
    """Radio keeps its public API: app-radio selector, name/value/label inputs
    and a value-based ControlValueAccessor for reactive and template forms.
    """
    ts = (RADIO_DIR / "radio.ts").read_text(encoding="utf-8")
    assert "selector: 'app-radio'" in ts, "Expected selector 'app-radio'"
    for name in ("id", "name", "value", "label"):
        assert re.search(rf"\b{name}\s*=\s*input[<(]", ts), (
            f"Expected a signal input named '{name}' in radio.ts"
        )
    assert "NG_VALUE_ACCESSOR" in ts, "Expected the NG_VALUE_ACCESSOR provider"
    for method in ("writeValue", "registerOnChange", "registerOnTouched", "setDisabledState"):
        assert re.search(rf"\b{method}\(", ts), f"Expected {method}() in radio.ts"


def test_when_radio_source_read_then_it_uses_material_radio_button_with_48px_target():
    """Radio uses Angular Material's MatRadioButton and keeps a 48px target.

    M3 accessibility: touch targets of at least 48 x 48px. MatRadioButton renders
    a 48px touch target at density 0; the component CSS gives each radio a 48px
    row so stacked radios never overlap their targets.
    """
    ts = (RADIO_DIR / "radio.ts").read_text(encoding="utf-8")
    html = (RADIO_DIR / "radio.html").read_text(encoding="utf-8")
    css = (RADIO_DIR / "radio.css").read_text(encoding="utf-8")
    assert "@angular/material/radio" in ts, "Expected MatRadioButton import"
    assert "<mat-radio-button" in html, "Expected <mat-radio-button> in radio.html"
    assert re.search(r"min-(?:block-size|height)\s*:\s*48px", css), (
        "Expected a 48px minimum row height in radio.css"
    )


def test_when_radio_css_read_then_it_uses_m3_tokens_and_no_color_literals():
    """Radio CSS colors come from --mat-sys-* tokens, in both color schemes.

    No hex/rgb/hsl literals, no !important and no ::ng-deep.
    """
    css = (RADIO_DIR / "radio.css").read_text(encoding="utf-8")
    assert "var(--mat-sys-" in css, "Expected --mat-sys-* tokens in radio.css"
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(", css), (
        "radio.css must not contain color literals"
    )
    assert "!important" not in css, "radio.css must not use !important"
    assert "::ng-deep" not in css, "radio.css must not use ::ng-deep"


def test_when_radio_source_read_then_no_tailwind_utilities_remain():
    """Radio template and TS carry no Tailwind utility classes."""
    html = (RADIO_DIR / "radio.html").read_text(encoding="utf-8")
    ts = (RADIO_DIR / "radio.ts").read_text(encoding="utf-8")
    tokens = [
        token
        for value in re.findall(r"\bclass=\"([^\"]*)\"", html)
        for token in value.split()
    ]
    tokens += re.findall(r"\[class\.([^\]]+)\]", html)
    tokens += [
        token
        for literal in re.findall(r"'([^'\n]*)'", ts)
        for token in literal.split()
    ]
    offenders = sorted({t for t in tokens if _TAILWIND_UTILITY.match(t)})
    assert not offenders, f"Tailwind utilities remain in shared/ui/radio/: {offenders}"
