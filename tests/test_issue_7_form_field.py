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
    candidates = {f.name: f for f in component_dir.glob("*.ts") if ".spec." not in f.name}
    if not candidates:
        raise FileNotFoundError(f"No non-spec .ts file found in {component_dir}")
    # The component class lives in <folder>.ts (or <folder>.component.ts). Match the whole file
    # name: form-field-context.ts also contains "form-field", and glob order differs between
    # filesystems, so a substring match picked the context file on Linux CI.
    name = component_dir.name
    for primary in (f"{name}.ts", f"{name}.component.ts"):
        if primary in candidates:
            return candidates[primary]
    return candidates[sorted(candidates)[0]]


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


def _form_field_sources() -> str:
    """FormField .ts + .html + .css (template and styles live in their own files)."""
    parts = [_primary_ts(FORM_FIELD_DIR)]
    parts += sorted(FORM_FIELD_DIR.glob("*.html")) + sorted(FORM_FIELD_DIR.glob("*.css"))
    return "\n".join(p.read_text(encoding="utf-8") for p in parts)


class TestFormFieldAriaWiring:
    """Verify that FormField owns the aria wiring contract.

    A projected native control is labelled and wired by FormField itself; a projected
    <app-input>/<app-select> takes the label, ids and texts from FORM_FIELD_CONTEXT and
    lets its own Material form field do the wiring.
    """

    def test_when_form_field_source_read_then_aria_describedby_is_referenced(self):
        combined = _form_field_sources()
        assert "aria-describedby" in combined, (
            "FormField must set aria-describedby on or for the projected control"
        )

    def test_when_form_field_source_read_then_aria_invalid_is_referenced(self):
        combined = _form_field_sources()
        assert "aria-invalid" in combined, (
            "FormField must reference aria-invalid (set on projected control when errorText is present)"
        )

    def test_when_form_field_source_read_then_label_element_is_rendered(self):
        combined = _form_field_sources()
        assert "<label" in combined, "FormField template must contain a <label> element"

    def test_when_form_field_source_read_then_ng_content_projects_the_control(self):
        combined = _form_field_sources()
        assert "ng-content" in combined, (
            "FormField must use <ng-content> to project the control"
        )

    def test_when_form_field_source_read_then_error_text_is_conditionally_rendered(
        self,
    ):
        combined = _form_field_sources()
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
        A native control gets it from FormField; <app-input>/<app-select> read it as
        `controlId` from FORM_FIELD_CONTEXT.
        """
        combined = _form_field_sources()
        # Acceptable: `for`, `htmlFor`, `[attr.for]`, `[for]`
        has_for = bool(re.search(r"\bfor\b", combined))
        assert has_for, (
            "FormField must wire the <label> 'for' attribute to a generated control id"
        )

    def test_when_form_field_source_read_then_aria_wiring_uses_view_lifecycle(self):
        """FormField sets aria attrs on a projected native control, requiring a view hook.

        ngAfterViewChecked, ngAfterViewInit, ElementRef, or afterRender are all
        acceptable — the key is that the component mutates the projected native
        control's DOM attributes rather than leaving them to the caller. Projected
        <app-input>/<app-select> are wired by their own Material form field instead.
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

    def test_when_form_field_ts_read_then_form_field_context_is_provided(self):
        """Projected Material controls render the label, hint and error themselves.

        Material's form field only discovers a matInput / mat-select in its own
        template, so FormField provides FORM_FIELD_CONTEXT from its component
        providers and <app-input>/<app-select> inject it.
        """
        ts = re.sub(
            r"/\*.*?\*/|//[^\n]*",
            "",
            _primary_ts(FORM_FIELD_DIR).read_text(encoding="utf-8"),
            flags=re.S,
        )
        assert re.search(r"providers\s*:\s*\[[^\]]*provide\s*:\s*FORM_FIELD_CONTEXT", ts, re.S), (
            "FormField must provide FORM_FIELD_CONTEXT from its component providers"
        )


_FF_COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(")


class TestFormFieldTokens:
    def test_when_form_field_folder_read_then_template_and_styles_are_separate_files(self):
        """FormField keeps its template and styles in form-field.html / form-field.css."""
        assert (FORM_FIELD_DIR / "form-field.html").is_file()
        assert (FORM_FIELD_DIR / "form-field.css").is_file()
        ts = _primary_ts(FORM_FIELD_DIR).read_text(encoding="utf-8")
        assert "templateUrl: './form-field.html'" in ts
        assert "styleUrl: './form-field.css'" in ts
        assert not re.search(r"\btemplate\s*:", ts) and not re.search(r"\bstyles\s*:", ts), (
            "FormField must not declare an inline template or styles"
        )

    def test_when_form_field_css_read_then_label_and_supporting_text_use_material_tokens(self):
        """The fallback label and help/error text of a native control are token-styled.

        Colors and type come from --mat-sys-* roles (error text in --mat-sys-error, help
        text in --mat-sys-on-surface-variant), never from literals, so both color
        schemes stay readable.
        """
        css = (FORM_FIELD_DIR / "form-field.css").read_text(encoding="utf-8")
        assert not _FF_COLOR_LITERAL.search(css), "form-field.css must not contain color literals"
        assert "!important" not in css and "::ng-deep" not in css
        custom_props = re.findall(r"var\(\s*(--[\w-]+)", css)
        assert custom_props and all(p.startswith(("--mat-", "--app-")) for p in custom_props), (
            f"form-field.css may only reference --mat-* / --app-* tokens, found {custom_props}"
        )
        for token in ("--mat-sys-error", "--mat-sys-on-surface-variant"):
            assert token in css, f"form-field.css must color supporting text with {token}"
        assert re.search(r"font:\s*var\(--mat-sys-[\w-]+\)", css), (
            "form-field.css must set typography from a --mat-sys-* type role"
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


def _input_sources() -> str:
    """Input .ts + .html + .css (component styles live in their own file)."""
    parts = [_primary_ts(INPUT_DIR)]
    parts += sorted(INPUT_DIR.glob("*.html")) + sorted(INPUT_DIR.glob("*.css"))
    return "\n".join(p.read_text(encoding="utf-8") for p in parts)


_COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(")


class TestInputTokens:
    def test_when_input_source_read_then_it_is_themed_by_material_tokens(self):
        """Input must be a themed Material control, not an unstyled bare input.

        The outlined mat-form-field + matInput paint every color, type and shape
        from --mat-sys-* tokens; the component CSS adds no color literals and only
        references --mat-* / --app-* custom properties.
        """
        css_files = list(INPUT_DIR.glob("*.css"))
        assert css_files, "InputComponent must have its own .css file"
        html = "".join(f.read_text(encoding="utf-8") for f in INPUT_DIR.glob("*.html"))
        assert "<mat-form-field" in html and 'appearance="outline"' in html, (
            "InputComponent must render an outlined <mat-form-field>"
        )
        assert re.search(r"<input[^>]*\bmatInput\b", html), (
            "InputComponent must render a native <input matInput>"
        )
        css = "".join(f.read_text(encoding="utf-8") for f in css_files)
        assert not _COLOR_LITERAL.search(css), "input.css must not contain color literals"
        assert "!important" not in css and "::ng-deep" not in css
        custom_props = re.findall(r"var\(\s*(--[\w-]+)", css)
        assert all(p.startswith(("--mat-", "--app-")) for p in custom_props), (
            f"input.css may only reference --mat-* / --app-* tokens, found {custom_props}"
        )

    def test_when_input_source_read_then_touch_target_is_at_least_48px(self):
        """The ≥48px target comes from Material's outlined form field.

        Its container is 56px tall at the app's density 0; the component must not
        override the container height or vertical padding tokens to shrink it.
        """
        combined = _input_sources()
        assert "<mat-form-field" in combined, (
            "InputComponent must use mat-form-field, whose container provides the 48px target"
        )
        for token in (
            "--mat-form-field-container-height",
            "--mat-form-field-container-vertical-padding",
        ):
            assert token not in combined, (
                f"InputComponent must not override {token} (it shrinks the 48px target)"
            )


class TestInputAriaWiring:
    def test_when_input_source_read_then_aria_invalid_is_bound_to_error_text(self):
        """MatInput binds aria-invalid from its error state, which errorText drives.

        The matcher must reach MatInput through DI (viewProviders): MatInput builds
        its error state tracker from the injected ErrorStateMatcher in its
        constructor, so a matcher bound only through [errorStateMatcher] arrives
        after the first evaluation and an initial errorText never shows.
        """
        html = "".join(f.read_text(encoding="utf-8") for f in INPUT_DIR.glob("*.html"))
        ts_source = _primary_ts(INPUT_DIR).read_text(encoding="utf-8")
        # Match code, not prose: comments neither satisfy nor break the wiring checks.
        ts = re.sub(r"/\*.*?\*/|//[^\n]*", "", ts_source, flags=re.S)
        assert re.search(r"<input[^>]*\bmatInput\b", html), (
            "the native input must be a matInput, which binds aria-invalid"
        )
        assert re.search(
            r"viewProviders\s*:\s*\[[^\]]*provide\s*:\s*ErrorStateMatcher", ts, re.S
        ), "InputComponent must provide its ErrorStateMatcher to MatInput via viewProviders"
        assert re.search(r"isErrorState[^}]*(hasError|errorText)", ts, re.S), (
            "the ErrorStateMatcher must follow errorText"
        )
        assert re.search(r"<mat-error[^>]*\[id\]", html), "mat-error must carry an id"

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


def _select_sources() -> str:
    """Select .ts + .html + .css (component styles live in their own file)."""
    parts = [_primary_ts(SELECT_DIR)]
    parts += sorted(SELECT_DIR.glob("*.html")) + sorted(SELECT_DIR.glob("*.css"))
    return "\n".join(p.read_text(encoding="utf-8") for p in parts)


def _select_html() -> str:
    return "".join(f.read_text(encoding="utf-8") for f in SELECT_DIR.glob("*.html"))


class TestSelectTokens:
    def test_when_select_source_read_then_it_is_themed_by_material_tokens(self):
        """Select must be a themed Material control, not an unstyled native select.

        The outlined mat-form-field + mat-select paint every color, type and shape
        from --mat-sys-* tokens; the component CSS adds no color literals and only
        references --mat-* / --app-* custom properties.
        """
        css_files = list(SELECT_DIR.glob("*.css"))
        assert css_files, "SelectComponent must have its own .css file"
        html = _select_html()
        assert "<mat-form-field" in html and 'appearance="outline"' in html, (
            "SelectComponent must render an outlined <mat-form-field>"
        )
        assert "<mat-select" in html, "SelectComponent must render a <mat-select>"
        css = "".join(f.read_text(encoding="utf-8") for f in css_files)
        assert not _COLOR_LITERAL.search(css), "select.css must not contain color literals"
        assert "!important" not in css and "::ng-deep" not in css
        custom_props = re.findall(r"var\(\s*(--[\w-]+)", css)
        assert all(p.startswith(("--mat-", "--app-")) for p in custom_props), (
            f"select.css may only reference --mat-* / --app-* tokens, found {custom_props}"
        )

    def test_when_select_source_read_then_touch_target_is_at_least_48px(self):
        """The ≥48px target comes from Material's outlined form field and options.

        The field container is 56px tall and each mat-option 48px at the app's
        density 0; the component must not override the height or padding tokens
        that shrink them.
        """
        combined = _select_sources()
        assert "<mat-form-field" in combined and "<mat-option" in combined, (
            "SelectComponent must use mat-form-field + mat-option, which provide the 48px target"
        )
        for token in (
            "--mat-form-field-container-height",
            "--mat-form-field-container-vertical-padding",
            "--mat-option-",
        ):
            assert token not in combined, (
                f"SelectComponent must not override {token} (it shrinks the 48px target)"
            )


class TestSelectAriaWiring:
    def test_when_select_source_read_then_aria_invalid_is_bound_to_error_text(self):
        """MatSelect binds aria-invalid from its error state, which errorText drives
        through a custom ErrorStateMatcher handed to the mat-select (bound in the
        template or assigned to the MatSelect instance in the component)."""
        html = _select_html()
        ts = _primary_ts(SELECT_DIR).read_text(encoding="utf-8")
        assert re.search(r"<mat-select[^>]*\[errorStateMatcher\]", html) or re.search(
            r"\.errorStateMatcher\s*=\s*this\.errorStateMatcher", ts
        ), "mat-select must receive the component's ErrorStateMatcher"
        assert re.search(r"isErrorState\s*:[^}]*(hasError|errorText)", ts, re.S), (
            "the ErrorStateMatcher must follow errorText"
        )
        assert re.search(r"<mat-error[^>]*\[id\]", html), "mat-error must carry an id"

    def test_when_select_source_read_then_id_binding_is_present_on_mat_select(self):
        """The id must be placed on the mat-select combobox, not left on the host."""
        html = _select_html()
        assert re.search(r"<mat-select[^>]*\[id\]", html), (
            "SelectComponent template must bind id to <mat-select>"
        )

    def test_when_select_source_read_then_disabled_binding_is_present_on_mat_select(self):
        html = _select_html()
        assert re.search(r"<mat-select[^>]*\[disabled\]", html), (
            "SelectComponent must bind disabled on <mat-select>"
        )

    def test_when_select_source_read_then_options_are_rendered_with_for_loop(self):
        """Select must iterate options with @for to render <mat-option> elements."""
        html = _select_html()
        assert re.search(r"@for\s*\([^)]*options\(\)[^)]*\)\s*\{\s*<mat-option", html), (
            "SelectComponent must render one <mat-option> per options() entry with @for"
        )
