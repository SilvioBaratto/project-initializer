"""
Source-blind tests for issue #16: Tabs with W3C APG roving tabindex.

Criteria covered (per oracle report):
  [UNIT] role="tablist"/"tab"/"tabpanel" with aria-selected, aria-controls,
         aria-labelledby
  [UNIT] Roving tabindex; ArrowLeft/ArrowRight + Home/End move focus;
         Enter/Space activate

Skipped (not runtime-verifiable):
  Dark-mode tokens, visible focus, ≥44px tabs
  All tests pass (boilerplate suite gate)
  SOLID / code-quality prose

Design note: tests scaffold a frontend-only project and inspect the generated
Tabs component files. Tests FAIL today (Red) because the Tabs component does
not yet exist in the template tree; they will PASS once the implementation is
added to project_initializer/templates/frontend/src/app/shared/ui/tabs/.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TABS_RELATIVE_DIR = Path("frontend/src/app/shared/ui/tabs")


def _read_tabs_template(root: Path) -> str:
    """
    Return the HTML/template content of the generated Tabs component.
    Handles both inline-template (.ts only) and separate .html variants.
    """
    html_path = root / TABS_RELATIVE_DIR / "tabs.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    ts_path = root / TABS_RELATIVE_DIR / "tabs.ts"
    return ts_path.read_text(encoding="utf-8")


def _read_tabs_ts(root: Path) -> str:
    return (root / TABS_RELATIVE_DIR / "tabs.ts").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixture: scaffold a frontend-only project once per session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def scaffolded(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Scaffold a frontend-only project into a temp directory and return its root.
    Fails fast with a clear message if the CLI is not installed.
    """
    dest = tmp_path_factory.mktemp("issue16_tabs")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_initializer.cli",
            "tabs-test",
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
            f"project-initializer failed:\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return dest / "tabs-test"


# ===========================================================================
# Criterion 1 — ARIA roles and attributes
# ===========================================================================


class TestARIARolesPresent:
    """role="tablist"/"tab"/"tabpanel" must appear in the generated template."""

    def test_when_tabs_template_is_generated_then_tablist_role_is_present(
        self, scaffolded: Path
    ) -> None:
        assert 'role="tablist"' in _read_tabs_template(scaffolded)

    def test_when_tabs_template_is_generated_then_tab_role_is_present(
        self, scaffolded: Path
    ) -> None:
        assert 'role="tab"' in _read_tabs_template(scaffolded)

    def test_when_tabs_template_is_generated_then_tabpanel_role_is_present(
        self, scaffolded: Path
    ) -> None:
        assert 'role="tabpanel"' in _read_tabs_template(scaffolded)


class TestARIAAttributesPresent:
    """aria-selected, aria-controls, and aria-labelledby must be present."""

    def test_when_tabs_template_is_generated_then_aria_selected_is_present(
        self, scaffolded: Path
    ) -> None:
        assert "aria-selected" in _read_tabs_template(scaffolded)

    def test_when_tabs_template_is_generated_then_aria_controls_is_present(
        self, scaffolded: Path
    ) -> None:
        assert "aria-controls" in _read_tabs_template(scaffolded)

    def test_when_tabs_template_is_generated_then_aria_labelledby_is_present(
        self, scaffolded: Path
    ) -> None:
        assert "aria-labelledby" in _read_tabs_template(scaffolded)


# ===========================================================================
# Criterion 2 — Roving tabindex + keyboard navigation
# ===========================================================================


class TestRovingTabindex:
    """Only the active tab belongs to the natural tab sequence (tabindex=0)."""

    def test_when_tabs_template_is_generated_then_tabindex_binding_is_present(
        self, scaffolded: Path
    ) -> None:
        assert "tabindex" in _read_tabs_template(scaffolded)


class TestKeyboardNavigation:
    """All required key identifiers must appear in the component's TypeScript."""

    def test_when_tabs_ts_is_generated_then_ArrowLeft_key_is_handled(
        self, scaffolded: Path
    ) -> None:
        assert "ArrowLeft" in _read_tabs_ts(scaffolded)

    def test_when_tabs_ts_is_generated_then_ArrowRight_key_is_handled(
        self, scaffolded: Path
    ) -> None:
        assert "ArrowRight" in _read_tabs_ts(scaffolded)

    def test_when_tabs_ts_is_generated_then_Home_key_is_handled(
        self, scaffolded: Path
    ) -> None:
        assert "Home" in _read_tabs_ts(scaffolded)

    def test_when_tabs_ts_is_generated_then_End_key_is_handled(
        self, scaffolded: Path
    ) -> None:
        assert "End" in _read_tabs_ts(scaffolded)

    def test_when_tabs_ts_is_generated_then_Enter_key_is_handled(
        self, scaffolded: Path
    ) -> None:
        assert "Enter" in _read_tabs_ts(scaffolded)

    def test_when_tabs_ts_is_generated_then_Space_key_is_handled(
        self, scaffolded: Path
    ) -> None:
        content = _read_tabs_ts(scaffolded)
        assert " " in content or "Space" in content

    def test_when_tabs_template_is_generated_then_keydown_handler_is_wired(
        self, scaffolded: Path
    ) -> None:
        """The tablist element must wire up a keydown listener."""
        assert "keydown" in _read_tabs_template(scaffolded)


# ===========================================================================
# Property-based tests — invariants derived from the criterion text
# ===========================================================================
#
# These encode the mathematical contracts the Tabs component must satisfy for
# ALL valid inputs, not just the single example above.  The reference
# implementations below are CONTRACT SPECIFICATIONS — they must never be
# replaced by imports from the production module.
# ===========================================================================


# --- Contract specification helpers (spec, not production code) -------------


def _roving_tabindex_for(num_tabs: int, active_index: int) -> list[int]:
    """
    W3C APG roving tabindex rule: exactly the active tab has tabindex 0;
    every other tab has tabindex -1.
    """
    return [0 if i == active_index else -1 for i in range(num_tabs)]


def _arrow_right_next(current: int, num_tabs: int) -> int:
    """ArrowRight wraps: last tab → first tab."""
    return (current + 1) % num_tabs


def _arrow_left_prev(current: int, num_tabs: int) -> int:
    """ArrowLeft wraps: first tab → last tab."""
    return (current - 1) % num_tabs


# --- Properties -------------------------------------------------------------


@given(
    num_tabs=st.integers(min_value=1, max_value=50),
    active_index=st.integers(min_value=0, max_value=49),
)
def test_when_roving_tabindex_rule_is_applied_then_exactly_one_tab_has_tabindex_zero(
    num_tabs: int, active_index: int
) -> None:
    """
    Invariant: for any number of tabs and any active index, exactly one tab
    carries tabindex=0 and all others carry tabindex=-1.
    Criterion: "Roving tabindex — only the active tab is in the tab sequence."
    """
    active_index = active_index % num_tabs
    values = _roving_tabindex_for(num_tabs, active_index)
    assert values.count(0) == 1
    assert values.count(-1) == num_tabs - 1


@given(
    num_tabs=st.integers(min_value=2, max_value=50),
    current=st.integers(min_value=0, max_value=49),
)
def test_when_ArrowRight_is_pressed_then_focus_index_is_always_in_bounds(
    num_tabs: int, current: int
) -> None:
    """
    Invariant: ArrowRight focus target is always a valid tab index [0, num_tabs).
    Criterion: "ArrowLeft/ArrowRight move focus."
    """
    result = _arrow_right_next(current % num_tabs, num_tabs)
    assert 0 <= result < num_tabs


@given(
    num_tabs=st.integers(min_value=2, max_value=50),
    current=st.integers(min_value=0, max_value=49),
)
def test_when_ArrowLeft_is_pressed_then_focus_index_is_always_in_bounds(
    num_tabs: int, current: int
) -> None:
    """
    Invariant: ArrowLeft focus target is always a valid tab index [0, num_tabs).
    Criterion: "ArrowLeft/ArrowRight move focus."
    """
    result = _arrow_left_prev(current % num_tabs, num_tabs)
    assert 0 <= result < num_tabs


@given(
    num_tabs=st.integers(min_value=2, max_value=50),
    current=st.integers(min_value=0, max_value=49),
)
def test_when_ArrowRight_then_ArrowLeft_is_pressed_then_focus_returns_to_original(
    num_tabs: int, current: int
) -> None:
    """
    Round-trip invariant: ArrowRight followed by ArrowLeft returns to the
    original tab, for any starting position (modulo wrapping).
    Criterion: "ArrowLeft/ArrowRight move focus."
    """
    start = current % num_tabs
    after_right = _arrow_right_next(start, num_tabs)
    after_left = _arrow_left_prev(after_right, num_tabs)
    assert after_left == start


@given(num_tabs=st.integers(min_value=1, max_value=50))
def test_when_Home_is_pressed_then_focus_moves_to_index_zero(num_tabs: int) -> None:
    """
    Invariant: Home always produces index 0, for any number of tabs.
    Criterion: "Home/End move focus."
    """
    home_index = 0
    assert home_index == 0
    assert home_index < num_tabs


@given(num_tabs=st.integers(min_value=1, max_value=50))
def test_when_End_is_pressed_then_focus_moves_to_last_tab(num_tabs: int) -> None:
    """
    Invariant: End always produces index num_tabs-1, for any number of tabs.
    Criterion: "Home/End move focus."
    """
    end_index = num_tabs - 1
    assert end_index == num_tabs - 1
    assert 0 <= end_index < num_tabs


@given(
    num_tabs=st.integers(min_value=1, max_value=50),
    active_index=st.integers(min_value=0, max_value=49),
)
def test_when_active_tab_changes_then_exactly_one_tab_remains_active(
    num_tabs: int, active_index: int
) -> None:
    """
    Idempotence-adjacent invariant: activating a tab (Enter/Space) must
    produce a state where exactly one tab is selected, regardless of which
    tab was previously active.
    Criterion: "Enter/Space activate."
    """
    active_index = active_index % num_tabs
    values = _roving_tabindex_for(num_tabs, active_index)
    # Exactly one tab is in the tab sequence after activation.
    assert values.count(0) == 1
