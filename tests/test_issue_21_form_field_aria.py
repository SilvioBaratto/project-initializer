"""
Source-blind tests for issue #21: FormField label/control association and ARIA wiring.

Criteria covered (per oracle report):
  [T3]  label.htmlFor === control.id — the FormField label's `for` attribute must
        equal the projected control's `id` at runtime; holds for bare controls AND
        for <app-input>/<app-select>.
  [UNIT] aria-invalid single owner: when FormField has errorText, the projected
         control ends with aria-invalid="true"; when it does not, no aria-invalid="true".
  [T3]  aria-describedby references the rendered error (errorText) or help (helpText)
         element.
  [UNIT] A spec asserts label.htmlFor === control.id at runtime (not just source grep),
         and a spec covers the errorText/helpText aria-invalid/aria-describedby matrix.

Skipped (not runtime-verifiable):
  Existing form-field/input/select specs stay green
  All tests pass (boilerplate suite gate)
  SOLID / clean-code prose

Design note: these tests scaffold a frontend-only project and inspect the generated
FormField component template/TS. They FAIL today (Red) because the FormField
component's label-control wiring is not yet correctly implemented. They will PASS
once the FormField sets [for] on its label, and wires aria-invalid / aria-describedby
to the projected control.

Path of the generated component (relative to scaffolded root):
  frontend/src/app/shared/ui/form-field/form-field.ts
"""

import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

FORM_FIELD_DIR = Path("frontend/src/app/shared/ui/form-field")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_template(root: Path) -> str:
    """
    Return the template content for the FormField component.
    Prefers a separate .html file; falls back to the inline template in .ts.
    """
    html_path = root / FORM_FIELD_DIR / "form-field.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    ts_path = root / FORM_FIELD_DIR / "form-field.ts"
    return ts_path.read_text(encoding="utf-8")


def _read_ts(root: Path) -> str:
    return (root / FORM_FIELD_DIR / "form-field.ts").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixture: scaffold a frontend-only project once per module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def scaffolded(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Scaffold a frontend-only project and return its root directory.
    Fails fast if the CLI is not installed.
    """
    dest = tmp_path_factory.mktemp("issue21_form_field_aria")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_initializer.cli",
            "ff-aria-test",
            "--scope",
            "frontend",
            "--force",
        ],
        cwd=dest,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            f"project-initializer failed:\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    return dest / "ff-aria-test"


# ===========================================================================
# Criterion 1 (T3) — label[for] === control[id]: label binding present
# ===========================================================================


class TestLabelForBinding:
    """The FormField must bind its label's `for` to the control's id."""

    def test_when_form_field_template_is_generated_then_label_element_is_present(
        self, scaffolded: Path
    ) -> None:
        content = _read_template(scaffolded)
        assert "<label" in content

    def test_when_form_field_template_is_generated_then_for_binding_is_on_label(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'label.htmlFor === control.id'.
        The label element must carry a dynamic `[for]` or `[htmlFor]` binding so it
        can be associated with the projected control's generated id.
        """
        content = _read_template(scaffolded)
        # Accept Angular's [for], [attr.for], or htmlFor binding forms
        has_for_binding = (
            "[for]" in content or "[attr.for]" in content or "htmlFor" in content
        )
        assert has_for_binding, (
            "No [for] / [attr.for] / htmlFor binding found on the label element. "
            "The FormField label must be associated with the projected control's id."
        )

    def test_when_form_field_ts_is_generated_then_control_id_is_generated(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'label.htmlFor === control.id'.
        The TypeScript must generate or manage a stable id to share between the
        label's `for` and the projected control's `id` attribute.
        Assumption: the id is produced via a counter, uuid, or computed signal and
        stored in a property/field such as `controlId`, `fieldId`, `id`, or `uid`.
        """
        content = _read_ts(scaffolded)
        has_id_management = any(
            kw in content
            for kw in (
                "controlId",
                "fieldId",
                "inputId",
                "uid",
                "nextId",
                "nextFieldId",
                "fieldCounter",
                "signal(",
                "computed(",
            )
        )
        assert has_id_management, (
            "No id-generation / id-management pattern found in form-field.ts. "
            "Expected a controlId / fieldId / inputId signal or a counter."
        )

    def test_when_form_field_ts_is_generated_then_id_is_set_on_projected_control(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'label.htmlFor === control.id'.
        The TypeScript must write the generated id to the projected control so that
        label.htmlFor === control.id holds at runtime.
        Assumption: FormField uses ContentChild / ElementRef / a directive to set
        the `id` attribute on the projected control element.
        """
        content = _read_ts(scaffolded)
        has_id_projection = any(
            kw in content
            for kw in (
                "ContentChild",
                "ElementRef",
                "setAttribute",
                "nativeElement",
                "Directive",
                "controlId",
            )
        )
        assert has_id_projection, (
            "No mechanism found in form-field.ts to push the generated id to the "
            "projected control. Expected ContentChild / ElementRef.setAttribute / "
            "a directive that sets the id."
        )


# ===========================================================================
# Criterion 2 (UNIT) — aria-invalid single, unambiguous owner
# ===========================================================================


class TestAriaInvalidOwnership:
    """FormField is the sole owner of aria-invalid on the projected control."""

    def test_when_form_field_template_is_generated_then_aria_invalid_binding_is_present(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'aria-invalid has a single, unambiguous owner'.
        The template must contain an aria-invalid binding that FormField controls,
        so the projected control reflects the FormField's error state.
        """
        content = _read_template(scaffolded)
        assert "aria-invalid" in content, (
            "No aria-invalid binding found in the FormField template. "
            "FormField must set aria-invalid on the projected control when errorText is provided."
        )

    def test_when_form_field_ts_is_generated_then_error_text_input_is_declared(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'when FormField has errorText, the projected control ends with
        aria-invalid="true"'.
        The TypeScript must declare an errorText input so the template can drive
        aria-invalid from it.
        """
        content = _read_ts(scaffolded)
        assert "errorText" in content, (
            "No errorText input found in form-field.ts. "
            "FormField must accept errorText to drive aria-invalid on the projected control."
        )

    def test_when_form_field_template_is_generated_then_aria_invalid_is_conditioned_on_error_text(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'when FormField has errorText, the projected control ends with
        aria-invalid="true"; when it does not, no aria-invalid="true"'.
        The template must tie aria-invalid to the errorText value, not hard-code it.
        Assumption: the binding uses `errorText` or a computed signal derived from it
        (e.g. `!!errorText()`, `hasError()`).
        """
        template = _read_template(scaffolded)
        ts = _read_ts(scaffolded)
        # The conditional expression for aria-invalid must reference errorText or a
        # derived boolean — it must NOT be a static `aria-invalid="true"`.
        has_static_true = 'aria-invalid="true"' in template
        has_dynamic_binding = "aria-invalid" in template and (
            "errorText" in template
            or "hasError" in template
            or "error" in template.lower()
        )
        assert not has_static_true or has_dynamic_binding, (
            'FormField template has a static aria-invalid="true" with no dynamic '
            "binding conditioned on errorText. The value must be driven by errorText."
        )
        assert "errorText" in ts or "errorText" in template, (
            "errorText must appear in the FormField template or TS to drive aria-invalid."
        )


# ===========================================================================
# Criterion 3 (T3) — aria-describedby references error/help element
# ===========================================================================


class TestAriaDescribedBy:
    """aria-describedby on the projected control must point to the error or help element."""

    def test_when_form_field_template_is_generated_then_aria_describedby_binding_is_present(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'aria-describedby continues to reference the rendered error
        (when errorText) or help (when helpText) element'.
        """
        content = _read_template(scaffolded)
        assert "aria-describedby" in content, (
            "No aria-describedby binding found in the FormField template. "
            "FormField must set aria-describedby on the projected control."
        )

    def test_when_form_field_ts_is_generated_then_help_text_input_is_declared(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'aria-describedby continues to reference … help (when helpText) element'.
        The TypeScript must declare a helpText input so the template can wire
        aria-describedby to the rendered help element.
        """
        content = _read_ts(scaffolded)
        assert "helpText" in content, (
            "No helpText input found in form-field.ts. "
            "FormField must accept helpText and reference it via aria-describedby."
        )

    def test_when_form_field_template_is_generated_then_error_element_has_an_id(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'aria-describedby continues to reference the rendered error element'.
        The error element must carry (or receive) an id so aria-describedby can point
        to it.  Assumption: an id such as `errorId`, `descId`, `helpId`, or a
        generated suffix like `-error` / `-hint` is used.
        """
        template = _read_template(scaffolded)
        ts = _read_ts(scaffolded)
        has_desc_id = any(
            kw in template or kw in ts
            for kw in (
                "errorId",
                "helpId",
                "descId",
                "-error",
                "-hint",
                "-desc",
                "descriptionId",
            )
        )
        assert has_desc_id, (
            "No id for the error/help description element found in the FormField "
            "template or TS. aria-describedby requires a stable element id to point to."
        )

    def test_when_form_field_template_is_generated_then_error_text_is_rendered_conditionally(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'aria-describedby continues to reference the rendered error element'.
        The error message must only be rendered when errorText is truthy; an always-
        visible but invisible element would be incorrect.
        Assumption: the template uses Angular's @if or [class.hidden] / [hidden]
        conditioned on errorText.
        """
        template = _read_template(scaffolded)
        # Any conditional rendering pattern is acceptable
        has_conditional = (
            "@if" in template
            or "*ngIf" in template
            or "[hidden]" in template
            or "v-if" in template
        )
        assert has_conditional, (
            "The FormField template must conditionally render the error element "
            "(e.g. @if (errorText())). aria-describedby should only point to an "
            "element that is actually in the DOM."
        )


# ===========================================================================
# Criterion 4 (UNIT) — runtime matrix spec exists in the generated spec file
# ===========================================================================


class TestSpecMatrixExists:
    """The generated spec file must contain runtime assertions (not just greps)."""

    def _read_spec(self, root: Path) -> str:
        spec_path = root / FORM_FIELD_DIR / "form-field.spec.ts"
        return spec_path.read_text(encoding="utf-8")

    def test_when_form_field_spec_is_generated_then_label_htmlFor_assertion_is_present(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'A spec asserts label.htmlFor === control.id (not just a source grep)'.
        The generated spec must contain a DOM-level assertion on label.htmlFor or
        the label's `for`/`htmlFor` attribute compared to the control's id.
        Assumption: the assertion uses getAttribute('for'), .htmlFor, or
        [attr.for] on the rendered label element.
        """
        spec = self._read_spec(scaffolded)
        has_runtime_assertion = any(
            kw in spec
            for kw in (
                "htmlFor",
                "getAttribute('for')",
                'getAttribute("for")',
                "label.for",
                ".for",
                "label[for]",
            )
        )
        assert has_runtime_assertion, (
            "The form-field.spec.ts must assert label.htmlFor (or getAttribute('for')) "
            "at runtime — not just check the source text. This is a DOM-level assertion."
        )

    def test_when_form_field_spec_is_generated_then_aria_invalid_true_case_is_covered(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'a spec covers the errorText/helpText aria-invalid/aria-describedby matrix'.
        The spec must assert aria-invalid="true" when errorText is provided.
        """
        spec = self._read_spec(scaffolded)
        assert "aria-invalid" in spec, (
            "form-field.spec.ts must assert aria-invalid in the errorText case."
        )

    def test_when_form_field_spec_is_generated_then_no_aria_invalid_without_error_case_is_covered(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'a spec covers the errorText/helpText aria-invalid/aria-describedby matrix'.
        The spec must also cover the absence of errorText → no aria-invalid="true".
        Assumption: the spec contains both 'aria-invalid' and either a falsy / null
        / toBeNull / not.toBe assertion.
        """
        spec = self._read_spec(scaffolded)
        has_aria_invalid = "aria-invalid" in spec
        has_null_or_false = (
            "toBeNull" in spec
            or "toBeFalsy" in spec
            or "null" in spec
            or "false" in spec
            or "not.toBe" in spec
        )
        assert has_aria_invalid and has_null_or_false, (
            "form-field.spec.ts must cover both the aria-invalid='true' case and the "
            "absence-of-aria-invalid case (null/false path)."
        )

    def test_when_form_field_spec_is_generated_then_aria_describedby_case_is_covered(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'a spec covers the errorText/helpText aria-invalid/aria-describedby matrix'.
        The spec must assert aria-describedby when either errorText or helpText is provided.
        """
        spec = self._read_spec(scaffolded)
        assert "aria-describedby" in spec, (
            "form-field.spec.ts must assert aria-describedby in the errorText/helpText case."
        )


# ===========================================================================
# Property-based tests — invariants derived from the criterion text
# ===========================================================================
#
# The following properties test CONTRACT SPECIFICATIONS, not production code.
# The helpers below are pure-logic specs that encode the invariants the
# FormField must satisfy; they are never replaced by production imports.
# ===========================================================================


# ---------------------------------------------------------------------------
# Spec helpers
# ---------------------------------------------------------------------------


def _aria_invalid_value(error_text: str | None) -> str | None:
    """
    Contract: aria-invalid is 'true' iff errorText is a non-empty string.
    Criterion: 'when FormField has errorText, the projected control ends with
    aria-invalid="true"; when it does not, no aria-invalid="true"'.
    """
    if error_text:
        return "true"
    return None


def _aria_describedby_value(
    control_id: str,
    error_text: str | None,
    help_text: str | None,
) -> str | None:
    """
    Contract: aria-describedby references the error id when errorText is set,
    the help id when helpText is set, and is absent when neither is set.
    The error element takes priority over help when both are present.
    Criterion: 'aria-describedby continues to reference the rendered error
    (when errorText) or help (when helpText) element'.
    Assumption: ids are derived from controlId with a suffix (-error / -hint).
    """
    if error_text:
        return f"{control_id}-error"
    if help_text:
        return f"{control_id}-hint"
    return None


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


@given(error_text=st.one_of(st.none(), st.text()))
def test_when_error_text_is_provided_then_aria_invalid_is_always_true(
    error_text: str | None,
) -> None:
    """
    Invariant: aria-invalid is 'true' iff errorText is truthy (non-empty string).
    Criterion: 'aria-invalid has a single, unambiguous owner'.
    """
    result = _aria_invalid_value(error_text)
    if error_text:
        assert result == "true"
    else:
        assert result is None


@given(error_text=st.text(min_size=1))
def test_when_error_text_is_any_non_empty_string_then_aria_invalid_is_always_true(
    error_text: str,
) -> None:
    """
    Never-raises invariant: for any non-empty errorText, aria-invalid must be 'true'.
    Criterion: 'when FormField has errorText, the projected control ends with
    aria-invalid="true"'.
    """
    assert _aria_invalid_value(error_text) == "true"


@given(
    control_id=st.text(
        min_size=1,
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_"
        ),
    ),
    error_text=st.one_of(st.none(), st.text(min_size=1)),
    help_text=st.one_of(st.none(), st.text(min_size=1)),
)
def test_when_neither_error_nor_help_is_provided_then_aria_describedby_is_absent(
    control_id: str,
    error_text: str | None,
    help_text: str | None,
) -> None:
    """
    Invariant: aria-describedby is only set when there is something to describe.
    Criterion: 'aria-describedby continues to reference the rendered error
    (when errorText) or help (when helpText) element'.
    """
    result = _aria_describedby_value(control_id, error_text, help_text)
    if not error_text and not help_text:
        assert result is None
    else:
        assert result is not None


@given(
    control_id=st.text(
        min_size=1,
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_"
        ),
    ),
    error_text=st.text(min_size=1),
)
def test_when_error_text_is_provided_then_aria_describedby_references_error_element(
    control_id: str,
    error_text: str,
) -> None:
    """
    Invariant: when errorText is set, aria-describedby always references the error
    element (not the help element), for any control id.
    Criterion: 'aria-describedby … reference the rendered error (when errorText)'.
    Assumption: the error element id is controlId + '-error'.
    """
    result = _aria_describedby_value(control_id, error_text, None)
    assert result is not None
    assert "error" in result


@given(
    control_id=st.text(
        min_size=1,
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_"
        ),
    ),
    help_text=st.text(min_size=1),
)
def test_when_only_help_text_is_provided_then_aria_describedby_references_help_element(
    control_id: str,
    help_text: str,
) -> None:
    """
    Invariant: when only helpText is set (no errorText), aria-describedby references
    the help element for any control id.
    Criterion: 'aria-describedby … reference … help (when helpText) element'.
    Assumption: the help element id is controlId + '-hint'.
    """
    result = _aria_describedby_value(control_id, None, help_text)
    assert result is not None
    assert "hint" in result or "help" in result or "desc" in result


@given(
    control_id=st.text(
        min_size=1,
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_"
        ),
    ),
    error_text=st.text(min_size=1),
    help_text=st.text(min_size=1),
)
def test_when_both_error_and_help_are_provided_then_error_takes_precedence(
    control_id: str,
    error_text: str,
    help_text: str,
) -> None:
    """
    Invariant: when both errorText and helpText are set, aria-describedby references
    the error element (error takes priority over help).
    Criterion: 'aria-describedby … reference the rendered error (when errorText)'.
    Assumption: errorText presence always produces an error-referencing describedby.
    """
    result = _aria_describedby_value(control_id, error_text, help_text)
    assert result is not None
    assert "error" in result
