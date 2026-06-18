"""
Issue #23 — test: add FocusTrapDirective spec (focus trap, inert, keyboard nav)

Source-blind tests authored against acceptance criteria only.
Each test reads the Angular spec file that must be added to the template and
asserts one observable property derived from the criterion text.

Verifiable criteria covered (oracle classification [UNIT]):
  C1 — Spec uses a host component applying [appFocusTrap] with an [active] input
       over >=2 focusable children, appended to document.body
  C2 — An Escape keydown emits the close output
  C3 — When active, sibling elements receive inert and aria-hidden;
       both are removed when inactive

Skipped (oracle: NOT VERIFIABLE):
  - When active, the first focusable child receives focus
  - Tab/Shift+Tab wrapping behaviour
  - Deactivation restores focus to previously focused element
  - All tests pass (suite gate)
  - SOLID / clean code (subjective prose)
"""

import glob
import os
import re
import textwrap

import pytest

_FRONTEND_SRC = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "project_initializer",
        "templates",
        "frontend",
        "src",
    )
)


def _find_focus_trap_spec() -> str:
    """
    Locate the Angular spec file for FocusTrapDirective inside the frontend template.
    The file must match *focus-trap*.spec.ts or *focus_trap*.spec.ts anywhere under src/.
    """
    for pattern in (
        os.path.join(_FRONTEND_SRC, "**", "*focus-trap*.spec.ts"),
        os.path.join(_FRONTEND_SRC, "**", "*focus_trap*.spec.ts"),
    ):
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return matches[0]

    pytest.fail(
        textwrap.dedent(
            """
            No FocusTrapDirective spec file found under
              project_initializer/templates/frontend/src/
            Expected a file matching *focus-trap*.spec.ts or *focus_trap*.spec.ts.
            Issue #23 requires this spec file to be added to the template.
            """
        )
    )


# ---------------------------------------------------------------------------
# Criterion C1 — host component structure
# ---------------------------------------------------------------------------


def test_when_spec_is_found_then_it_references_app_focus_trap_selector():
    """C1: the spec template must wire the [appFocusTrap] directive selector."""
    content = open(_find_focus_trap_spec(), encoding="utf-8").read()
    assert "appFocusTrap" in content, (
        "Spec must reference the 'appFocusTrap' selector in the host component template."
    )


def test_when_spec_is_found_then_host_binds_active_input():
    """C1: the spec must bind the [active] input on the directive host element."""
    content = open(_find_focus_trap_spec(), encoding="utf-8").read()
    # Accept both attribute-binding form [active] and signal-style active()
    assert "[active]" in content or re.search(r"\bactive\b", content), (
        "Spec must bind the [active] input on the FocusTrapDirective host element."
    )


def test_when_spec_is_found_then_host_has_two_or_more_focusable_children():
    """C1: the host component template must contain >=2 focusable child elements."""
    content = open(_find_focus_trap_spec(), encoding="utf-8").read()
    focusable_hits = re.findall(
        r"<(button|input|a\b|select|textarea)[^>]*>",
        content,
    )
    assert len(focusable_hits) >= 2, (
        f"Spec host template must declare >=2 focusable children "
        f"(button/input/a/select/textarea); found {len(focusable_hits)}: {focusable_hits}"
    )


def test_when_spec_is_found_then_fixture_is_appended_to_document_body():
    """C1: the spec must append the host fixture to document.body."""
    content = open(_find_focus_trap_spec(), encoding="utf-8").read()
    assert "document.body" in content, (
        "Spec must append the host fixture element to document.body so that sibling "
        "inert / aria-hidden detection operates on real DOM siblings."
    )


# ---------------------------------------------------------------------------
# Criterion C2 — Escape keydown emits close output
# ---------------------------------------------------------------------------


def test_when_escape_keydown_is_dispatched_then_close_output_is_emitted():
    """C2: spec must test that dispatching an Escape keydown event causes the close output to emit."""
    content = open(_find_focus_trap_spec(), encoding="utf-8").read()
    has_escape = "Escape" in content
    has_close = "close" in content
    assert has_escape, (
        "Spec must dispatch a keydown event with key 'Escape' to test close output emission."
    )
    assert has_close, (
        "Spec must assert the 'close' output emits when Escape is pressed."
    )


# ---------------------------------------------------------------------------
# Criterion C3 — sibling inert + aria-hidden when active; both removed when inactive
# ---------------------------------------------------------------------------


def test_when_active_then_spec_asserts_inert_on_sibling_elements():
    """C3 (active path): spec must assert that sibling elements receive the inert attribute."""
    content = open(_find_focus_trap_spec(), encoding="utf-8").read()
    assert "inert" in content, (
        "Spec must assert sibling elements receive the 'inert' attribute when the trap is active."
    )


def test_when_active_then_spec_asserts_aria_hidden_on_sibling_elements():
    """C3 (active path): spec must assert that sibling elements receive aria-hidden."""
    content = open(_find_focus_trap_spec(), encoding="utf-8").read()
    assert "aria-hidden" in content, (
        "Spec must assert sibling elements receive 'aria-hidden' when the trap is active."
    )


def test_when_inactive_then_spec_asserts_inert_is_removed_from_siblings():
    """C3 (inactive path): spec must verify inert is removed when the trap becomes inactive.

    Assumption: the spec exercises the inactive state by setting active to false
    (or equivalent falsy signal). We check that the spec covers a non-active path
    alongside the inert assertion — if only the active path were tested the
    'removed when inactive' half of C3 would be unverified.
    """
    content = open(_find_focus_trap_spec(), encoding="utf-8").read()
    assert "inert" in content, (
        "Spec must contain the 'inert' keyword to test its removal when inactive."
    )
    covers_inactive = (
        re.search(r"\bfalse\b", content) is not None
        or "inactive" in content.lower()
        or "deactivat" in content.lower()
        or re.search(r"active\s*=\s*false", content) is not None
    )
    assert covers_inactive, (
        "Spec must test the inactive/false state to verify that 'inert' is removed "
        "from siblings when the trap is deactivated."
    )


def test_when_inactive_then_spec_asserts_aria_hidden_is_removed_from_siblings():
    """C3 (inactive path): spec must verify aria-hidden is removed when the trap becomes inactive."""
    content = open(_find_focus_trap_spec(), encoding="utf-8").read()
    assert "aria-hidden" in content, (
        "Spec must contain 'aria-hidden' to test its removal when the trap is inactive."
    )
    covers_inactive = (
        re.search(r"\bfalse\b", content) is not None
        or "inactive" in content.lower()
        or "deactivat" in content.lower()
        or re.search(r"active\s*=\s*false", content) is not None
    )
    assert covers_inactive, (
        "Spec must test the inactive/false state to verify that 'aria-hidden' is removed "
        "from siblings when the trap is deactivated."
    )
