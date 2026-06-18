"""
Tests for issue #7: feat(ui): FormField wrapper + Input + Select controls.

Static-analysis tests authored against the acceptance criteria.

Criteria covered:
  - [T3] FormField renders label + projected control + error/help,
           wiring aria-describedby and aria-invalid
  - [UNIT] Input + Select consume tokens, support error/disabled,
            associate the label via `id`

Criteria skipped (not runtime-verifiable per oracle):
  - 16px font floor — already in styles.css base layer, not a component concern
  - Controls ≥44px tall, keyboard operable, focus ring — browser-tier concern
  - All tests pass — boilerplate gate, no per-criterion assertion
  - SOLID / clean code — subjective prose
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

FORM_FIELD_DIR = UI_ROOT / "form-field"
INPUT_DIR = UI_ROOT / "input"
SELECT_DIR = UI_ROOT / "select"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _primary_ts(component_dir: pathlib.Path) -> pathlib.Path:
    candidates = [f for f in component_dir.glob("*.ts") if ".spec." not in f.name]
    if not candidates:
        raise FileNotFoundError(f"No non-spec .ts file found in {component_dir}")
    name = component_dir.name
    primary = [f for f in candidates if name in f.name]
    return (primary or candidates)[0]


def _full_source(component_dir: pathlib.Path) -> str:
    ts_text = _primary_ts(component_dir).read_text(encoding="utf-8")
    html_text = "".join(
        f.read_text(encoding="utf-8") for f in component_dir.glob("*.html")
    )
    return ts_text + "\n" + html_text


# ===========================================================================
# FormFieldComponent — criterion [T3]
# ===========================================================================


class TestFormFieldExists:
    def test_when_ui_directory_inspected_then_form_field_folder_exists(self):
        assert FORM_FIELD_DIR.is_dir(), (
            "Expected shared/ui/form-field/ to exist under templates/frontend/src/app/shared/ui/"
        )

    def test_when_form_field_folder_inspected_then_typescript_source_exists(self):
        non_spec = [f for f in FORM_FIELD_DIR.glob("*.ts") if ".spec." not in f.name]
        assert non_spec, (
            "Expected at least one .ts source file in shared/ui/form-field/"
        )


class TestFormFieldStructure:
    def test_when_form_field_ts_read_then_onpush_change_detection_is_set(self):
        src = _primary_ts(FORM_FIELD_DIR).read_text(encoding="utf-8")
        assert "ChangeDetectionStrategy.OnPush" in src

    def test_when_form_field_ts_read_then_standalone_is_not_opted_out(self):
        src = _primary_ts(FORM_FIELD_DIR).read_text(encoding="utf-8")
        assert "standalone: false" not in src

    def test_when_form_field_ts_read_then_label_signal_input_is_declared(self):
        src = _primary_ts(FORM_FIELD_DIR).read_text(encoding="utf-8")
        assert re.search(r"\blabel\s*=\s*input[<(]", src), (
            "Expected a signal input named 'label' in form-field .ts"
        )

    def test_when_form_field_ts_read_then_error_text_signal_input_is_declared(self):
        src = _primary_ts(FORM_FIELD_DIR).read_text(encoding="utf-8")
        assert re.search(r"\berrorText\s*=\s*input[<(]", src), (
            "Expected a signal input named 'errorText' in form-field .ts"
        )

    def test_when_form_field_ts_read_then_help_text_signal_input_is_declared(self):
        src = _primary_ts(FORM_FIELD_DIR).read_text(encoding="utf-8")
        assert re.search(r"\bhelpText\s*=\s*input[<(]", src), (
            "Expected a signal input named 'helpText' in form-field .ts"
        )


class TestFormFieldAriaWiring:
    """Verify that FormField owns the aria wiring contract."""

    def test_when_form_field_source_read_then_aria_describedby_is_referenced(self):
        combined = _full_source(FORM_FIELD_DIR)
        assert "aria-describedby" in combined, (
            "FormField must set aria-describedby on or for the projected control"
        )

    def test_when_form_field_source_read_then_aria_invalid_is_referenced(self):
        combined = _full_source(FORM_FIELD_DIR)
        assert "aria-invalid" in combined, (
            "FormField must reference aria-invalid (set on projected control when errorText is present)"
        )

    def test_when_form_field_source_read_then_label_element_is_rendered(self):
        combined = _full_source(FORM_FIELD_DIR)
        assert "<label" in combined, "FormField template must contain a <label> element"

    def test_when_form_field_source_read_then_ng_content_projects_the_control(self):
        combined = _full_source(FORM_FIELD_DIR)
        assert "ng-content" in combined, (
            "FormField must use <ng-content> to project the control"
        )

    def test_when_form_field_source_read_then_error_text_is_conditionally_rendered(
        self,
    ):
        combined = _full_source(FORM_FIELD_DIR)
        # Must use either @if (native control flow) or *ngIf
        has_conditional = "@if" in combined or "*ngIf" in combined
        assert has_conditional, (
            "FormField must conditionally render the error/help text"
        )

    def test_when_form_field_source_read_then_generated_id_connects_label_and_control(
        self,
    ):
        """FormField must generate an id to link <label for> to the projected control.

        Per the architectural comment on the issue: FormField owns id generation so
        that the label's `for` attribute can reference the control via a stable id.
        """
        combined = _full_source(FORM_FIELD_DIR)
        # Acceptable: `for`, `htmlFor`, `[attr.for]`, `[for]`
        has_for = bool(re.search(r"\bfor\b", combined))
        assert has_for, (
            "FormField must wire the <label> 'for' attribute to a generated control id"
        )

    def test_when_form_field_source_read_then_aria_wiring_uses_view_lifecycle(self):
        """FormField sets aria attrs on projected content, requiring a view lifecycle hook.

        ngAfterViewChecked, ngAfterViewInit, ElementRef, or afterRender are all
        acceptable — the key is that the component mutates the projected control's
        DOM attributes rather than leaving them to the caller.
        """
        src = _primary_ts(FORM_FIELD_DIR).read_text(encoding="utf-8")
        has_lifecycle = any(
            kw in src
            for kw in (
                "AfterViewChecked",
                "AfterViewInit",
                "afterRender",
                "afterNextRender",
                "ElementRef",
                "setAttribute",
            )
        )
        assert has_lifecycle, (
            "FormField must use a view lifecycle hook or ElementRef to wire aria "
            "attributes onto the projected control (AfterViewChecked, AfterViewInit, "
            "afterRender, or setAttribute)."
        )


# ===========================================================================
# InputComponent — criterion [UNIT]
# ===========================================================================


class TestInputExists:
    def test_when_ui_directory_inspected_then_input_folder_exists(self):
        assert INPUT_DIR.is_dir()

    def test_when_input_folder_inspected_then_typescript_source_exists(self):
        non_spec = [f for f in INPUT_DIR.glob("*.ts") if ".spec." not in f.name]
        assert non_spec


class TestInputStructure:
    def test_when_input_ts_read_then_onpush_change_detection_is_set(self):
        src = _primary_ts(INPUT_DIR).read_text(encoding="utf-8")
        assert "ChangeDetectionStrategy.OnPush" in src

    def test_when_input_ts_read_then_standalone_is_not_opted_out(self):
        src = _primary_ts(INPUT_DIR).read_text(encoding="utf-8")
        assert "standalone: false" not in src

    def test_when_input_ts_read_then_id_signal_input_is_declared(self):
        """Input must expose an `id` signal input so the consumer can link a <label for>."""
        src = _primary_ts(INPUT_DIR).read_text(encoding="utf-8")
        assert re.search(r"\bid\s*=\s*input[<(]", src), (
            "Expected a signal input named 'id' in input .ts"
        )

    def test_when_input_ts_read_then_error_text_signal_input_is_declared(self):
        src = _primary_ts(INPUT_DIR).read_text(encoding="utf-8")
        assert re.search(r"\berrorText\s*=\s*input[<(]", src), (
            "Expected a signal input named 'errorText' in input .ts"
        )

    def test_when_input_ts_read_then_disabled_signal_input_is_declared(self):
        src = _primary_ts(INPUT_DIR).read_text(encoding="utf-8")
        assert re.search(r"\bdisabled\s*=\s*input[<(]", src), (
            "Expected a signal input named 'disabled' in input .ts"
        )

    def test_when_input_ts_read_then_control_value_accessor_is_implemented(self):
        """Input must implement ControlValueAccessor to be reactive-forms-friendly."""
        src = _primary_ts(INPUT_DIR).read_text(encoding="utf-8")
        assert "ControlValueAccessor" in src, (
            "InputComponent must implement ControlValueAccessor for reactive-forms support"
        )

    def test_when_input_ts_read_then_ng_value_accessor_is_provided(self):
        src = _primary_ts(INPUT_DIR).read_text(encoding="utf-8")
        assert "NG_VALUE_ACCESSOR" in src


class TestInputTokens:
    def test_when_input_source_read_then_design_token_class_is_present(self):
        """Input must apply @theme token classes (not be an unstyled bare input).

        Acceptable token names from styles.css: border-border, bg-surface-raised,
        text-text, focus:ring-primary, etc.
        """
        combined = _full_source(INPUT_DIR)
        token_classes = [
            "border-border",
            "bg-surface",
            "text-text",
            "ring-primary",
            "focus:ring",
        ]
        has_token = any(t in combined for t in token_classes)
        assert has_token, (
            f"InputComponent must reference at least one @theme token class. "
            f"Checked: {token_classes}"
        )

    def test_when_input_source_read_then_min_height_class_is_present(self):
        """Input must carry min-h-11 (44px) for the touch-target criterion."""
        combined = _full_source(INPUT_DIR)
        assert "min-h-11" in combined, (
            "InputComponent must include 'min-h-11' for the ≥44px touch-target requirement"
        )


class TestInputAriaWiring:
    def test_when_input_source_read_then_aria_invalid_is_bound_to_error_text(self):
        combined = _full_source(INPUT_DIR)
        assert "aria-invalid" in combined

    def test_when_input_source_read_then_id_binding_is_present_on_native_input(self):
        """The generated id must be placed on the native <input> element."""
        combined = _full_source(INPUT_DIR)
        assert re.search(r"\[id\]|\[attr\.id\]|\bid=", combined), (
            "InputComponent template must bind id to the native <input>"
        )

    def test_when_input_source_read_then_native_disabled_binding_is_present(self):
        combined = _full_source(INPUT_DIR)
        assert re.search(r"\[(?:attr\.)?disabled\]", combined), (
            "InputComponent must bind the native disabled attribute"
        )


# ===========================================================================
# SelectComponent — criterion [UNIT]
# ===========================================================================


class TestSelectExists:
    def test_when_ui_directory_inspected_then_select_folder_exists(self):
        assert SELECT_DIR.is_dir()

    def test_when_select_folder_inspected_then_typescript_source_exists(self):
        non_spec = [f for f in SELECT_DIR.glob("*.ts") if ".spec." not in f.name]
        assert non_spec


class TestSelectStructure:
    def test_when_select_ts_read_then_onpush_change_detection_is_set(self):
        src = _primary_ts(SELECT_DIR).read_text(encoding="utf-8")
        assert "ChangeDetectionStrategy.OnPush" in src

    def test_when_select_ts_read_then_standalone_is_not_opted_out(self):
        src = _primary_ts(SELECT_DIR).read_text(encoding="utf-8")
        assert "standalone: false" not in src

    def test_when_select_ts_read_then_id_signal_input_is_declared(self):
        src = _primary_ts(SELECT_DIR).read_text(encoding="utf-8")
        assert re.search(r"\bid\s*=\s*input[<(]", src)

    def test_when_select_ts_read_then_error_text_signal_input_is_declared(self):
        src = _primary_ts(SELECT_DIR).read_text(encoding="utf-8")
        assert re.search(r"\berrorText\s*=\s*input[<(]", src)

    def test_when_select_ts_read_then_disabled_signal_input_is_declared(self):
        src = _primary_ts(SELECT_DIR).read_text(encoding="utf-8")
        assert re.search(r"\bdisabled\s*=\s*input[<(]", src)

    def test_when_select_ts_read_then_options_signal_input_is_declared(self):
        src = _primary_ts(SELECT_DIR).read_text(encoding="utf-8")
        assert re.search(r"\boptions\s*=\s*input[<(]", src)

    def test_when_select_ts_read_then_control_value_accessor_is_implemented(self):
        src = _primary_ts(SELECT_DIR).read_text(encoding="utf-8")
        assert "ControlValueAccessor" in src

    def test_when_select_ts_read_then_ng_value_accessor_is_provided(self):
        src = _primary_ts(SELECT_DIR).read_text(encoding="utf-8")
        assert "NG_VALUE_ACCESSOR" in src


class TestSelectTokens:
    def test_when_select_source_read_then_design_token_class_is_present(self):
        combined = _full_source(SELECT_DIR)
        token_classes = [
            "border-border",
            "bg-surface",
            "text-text",
            "ring-primary",
            "focus:ring",
        ]
        has_token = any(t in combined for t in token_classes)
        assert has_token, (
            f"SelectComponent must reference at least one @theme token class. "
            f"Checked: {token_classes}"
        )

    def test_when_select_source_read_then_min_height_class_is_present(self):
        combined = _full_source(SELECT_DIR)
        assert "min-h-11" in combined, (
            "SelectComponent must include 'min-h-11' for the ≥44px touch-target requirement"
        )


class TestSelectAriaWiring:
    def test_when_select_source_read_then_aria_invalid_is_bound_to_error_text(self):
        combined = _full_source(SELECT_DIR)
        assert "aria-invalid" in combined

    def test_when_select_source_read_then_id_binding_is_present_on_native_select(self):
        combined = _full_source(SELECT_DIR)
        assert re.search(r"\[id\]|\[attr\.id\]|\bid=", combined)

    def test_when_select_source_read_then_native_disabled_binding_is_present(self):
        combined = _full_source(SELECT_DIR)
        assert re.search(r"\[(?:attr\.)?disabled\]", combined)

    def test_when_select_source_read_then_options_are_rendered_with_for_loop(self):
        """Select must iterate options using @for or *ngFor to render <option> elements."""
        combined = _full_source(SELECT_DIR)
        has_loop = "@for" in combined or "*ngFor" in combined
        assert has_loop, "SelectComponent must iterate over options with @for or *ngFor"
