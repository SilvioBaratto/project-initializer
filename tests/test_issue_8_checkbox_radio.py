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
    """Return concatenated source of .ts + any .html files in component_dir."""
    ts_text = _primary_ts(component_dir).read_text(encoding="utf-8")
    html_text = "".join(
        f.read_text(encoding="utf-8") for f in component_dir.glob("*.html")
    )
    return ts_text + "\n" + html_text


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


def test_when_checkbox_source_read_then_label_element_is_present():
    """Checkbox template must contain a <label> element.

    Per criterion: 'render with an associated <label>'.
    A <label> element is required so assistive technology can announce the
    control's accessible name.
    """
    combined = _full_source(CHECKBOX_DIR)
    assert "<label" in combined, (
        "Expected a '<label' element in the Checkbox component source (.ts or .html). "
        "Per criterion: 'render with an associated <label>'."
    )


def test_when_checkbox_source_read_then_label_is_associated_with_control():
    """Checkbox label must be associated with the control via 'for' or by wrapping.

    Per criterion: 'render with an *associated* <label>'.
    Accepted association patterns:
    - <label [for]="..."> or <label for="..."> pointing to the input's id
    - Label element wrapping the native <input> element (implicit association)
    """
    combined = _full_source(CHECKBOX_DIR)
    has_for = bool(re.search(r"\bfor\s*=", combined))
    has_htmlfor = "htmlFor" in combined
    # Wrapping pattern: label tag occurs before a closing </label> that follows an input
    has_wrapping = bool(
        re.search(r"<label[^>]*>(?:[^<]|<(?!/?label\b))*<input", combined, re.DOTALL)
    )
    assert has_for or has_htmlfor or has_wrapping, (
        "Expected the Checkbox <label> to be associated with its control. "
        "Accepted: `[for]='...'` / `for='...'` attribute on the label, or the "
        "label element wrapping the <input>. "
        "Per criterion: 'render with an associated <label>'."
    )


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
    """Radio template must contain a <label> element.

    Per criterion: 'render with an associated <label>'.
    A <label> element is required so assistive technology can announce the
    control's accessible name.
    """
    combined = _full_source(RADIO_DIR)
    assert "<label" in combined, (
        "Expected a '<label' element in the Radio component source (.ts or .html). "
        "Per criterion: 'render with an associated <label>'."
    )


def test_when_radio_source_read_then_label_is_associated_with_control():
    """Radio label must be associated with the control via 'for' or by wrapping.

    Per criterion: 'render with an *associated* <label>'.
    Accepted association patterns:
    - <label [for]="..."> or <label for="..."> pointing to the input's id
    - Label element wrapping the native <input> element (implicit association)
    """
    combined = _full_source(RADIO_DIR)
    has_for = bool(re.search(r"\bfor\s*=", combined))
    has_htmlfor = "htmlFor" in combined
    has_wrapping = bool(
        re.search(r"<label[^>]*>(?:[^<]|<(?!/?label\b))*<input", combined, re.DOTALL)
    )
    assert has_for or has_htmlfor or has_wrapping, (
        "Expected the Radio <label> to be associated with its control. "
        "Accepted: `[for]='...'` / `for='...'` attribute on the label, or the "
        "label element wrapping the <input>. "
        "Per criterion: 'render with an associated <label>'."
    )
