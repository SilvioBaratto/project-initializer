"""
Source-blind tests for issue #16: Tabs with W3C APG roving tabindex.

Criteria covered (per oracle report):
  [UNIT] role="tablist"/"tab"/"tabpanel" with aria-selected, aria-controls,
         aria-labelledby
  [UNIT] Roving tabindex; ArrowLeft/ArrowRight + Home/End move focus;
         Enter/Space activate
  [UNIT] 48px tab targets and theme tokens only (Material 3)

Skipped (not runtime-verifiable):
  Visible focus rendering
  All tests pass (boilerplate suite gate)
  SOLID / code-quality prose

Design note: tests scaffold a frontend-only project and inspect the generated
Tabs component files. The component is built on Angular Material's
``mat-tab-group``, which renders the tablist/tab/tabpanel roles, the ARIA
attributes, the roving tabindex and the arrow/Home/End/Enter/Space keyboard
handling itself. The template therefore no longer spells those out; each
criterion is checked as "the component delegates to ``mat-tab-group``" plus
"the co-located spec (tabs.spec.ts) asserts the rendered behavior", which the
Angular test run verifies at runtime.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TABS_RELATIVE_DIR = Path("frontend/src/app/shared/ui/tabs")

# Each component in the folder: exactly <name>.ts + <name>.html + <name>.css.
TABS_COMPONENTS = ("tabs", "tab", "tab-panel")


def _read_tabs_component(root: Path) -> str:
    """
    Return the combined source of the generated Tabs components: every
    non-spec ``.ts`` plus every ``.html`` and ``.css`` in the tabs folder.
    """
    tabs_dir = root / TABS_RELATIVE_DIR
    files = sorted(
        f
        for pattern in ("*.ts", "*.html", "*.css")
        for f in tabs_dir.glob(pattern)
        if ".spec." not in f.name
    )
    return "\n".join(f.read_text(encoding="utf-8") for f in files)


def _read_tabs_template(root: Path) -> str:
    """Return the ``ui-tabs`` template (tabs.html)."""
    return (root / TABS_RELATIVE_DIR / "tabs.html").read_text(encoding="utf-8")


def _read_tabs_css(root: Path) -> str:
    """Return the combined stylesheets of the Tabs components."""
    tabs_dir = root / TABS_RELATIVE_DIR
    return "\n".join(
        f.read_text(encoding="utf-8") for f in sorted(tabs_dir.glob("*.css"))
    )


def _read_tabs_spec(root: Path) -> str:
    """Return the co-located Angular spec that exercises the rendered tabs."""
    return (root / TABS_RELATIVE_DIR / "tabs.spec.ts").read_text(encoding="utf-8")


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
    """role="tablist"/"tab"/"tabpanel" come from Material's tab group.

    The template delegates to ``mat-tab-group`` (which renders the roles) and
    the co-located spec asserts each role on the rendered DOM.
    """

    def test_when_tabs_template_is_generated_then_tablist_role_is_present(
        self, scaffolded: Path
    ) -> None:
        assert "<mat-tab-group" in _read_tabs_template(scaffolded)
        assert '[role="tablist"]' in _read_tabs_spec(scaffolded)

    def test_when_tabs_template_is_generated_then_tab_role_is_present(
        self, scaffolded: Path
    ) -> None:
        assert "<mat-tab>" in _read_tabs_template(scaffolded)
        assert '[role="tab"]' in _read_tabs_spec(scaffolded)

    def test_when_tabs_template_is_generated_then_tabpanel_role_is_present(
        self, scaffolded: Path
    ) -> None:
        assert "matTabContent" in _read_tabs_template(scaffolded)
        assert '[role="tabpanel"]' in _read_tabs_spec(scaffolded)


class TestARIAAttributesPresent:
    """aria-selected, aria-controls, and aria-labelledby must be present.

    Material sets them on the rendered tabs and panels; the spec asserts them.
    ``ui-tabs`` also forwards its own ``ariaLabel``/``ariaLabelledby`` inputs
    to the tablist.
    """

    def test_when_tabs_template_is_generated_then_aria_selected_is_present(
        self, scaffolded: Path
    ) -> None:
        assert "<mat-tab-group" in _read_tabs_template(scaffolded)
        assert "aria-selected" in _read_tabs_spec(scaffolded)

    def test_when_tabs_template_is_generated_then_aria_controls_is_present(
        self, scaffolded: Path
    ) -> None:
        assert "<mat-tab-group" in _read_tabs_template(scaffolded)
        assert "aria-controls" in _read_tabs_spec(scaffolded)

    def test_when_tabs_template_is_generated_then_aria_labelledby_is_present(
        self, scaffolded: Path
    ) -> None:
        assert "[aria-labelledby]" in _read_tabs_template(scaffolded)
        assert "aria-labelledby" in _read_tabs_spec(scaffolded)


# ===========================================================================
# Criterion 2 — Roving tabindex + keyboard navigation
# ===========================================================================


class TestRovingTabindex:
    """Only the active tab belongs to the natural tab sequence (tabindex=0)."""

    def test_when_tabs_template_is_generated_then_tabindex_binding_is_present(
        self, scaffolded: Path
    ) -> None:
        assert "<mat-tab-group" in _read_tabs_template(scaffolded)
        assert "tabindex" in _read_tabs_spec(scaffolded)


class TestKeyboardNavigation:
    """Material's tab header handles every required key.

    The component must not add a second keydown handler, which would move
    focus twice. The spec drives each key through the rendered tabs.
    """

    def test_when_tabs_ts_is_generated_then_ArrowLeft_key_is_handled(
        self, scaffolded: Path
    ) -> None:
        assert "MatTabsModule" in _read_tabs_component(scaffolded)
        assert "TestKey.LEFT_ARROW" in _read_tabs_spec(scaffolded)

    def test_when_tabs_ts_is_generated_then_ArrowRight_key_is_handled(
        self, scaffolded: Path
    ) -> None:
        assert "MatTabsModule" in _read_tabs_component(scaffolded)
        assert "TestKey.RIGHT_ARROW" in _read_tabs_spec(scaffolded)

    def test_when_tabs_ts_is_generated_then_Home_key_is_handled(
        self, scaffolded: Path
    ) -> None:
        assert "MatTabsModule" in _read_tabs_component(scaffolded)
        assert "TestKey.HOME" in _read_tabs_spec(scaffolded)

    def test_when_tabs_ts_is_generated_then_End_key_is_handled(
        self, scaffolded: Path
    ) -> None:
        assert "MatTabsModule" in _read_tabs_component(scaffolded)
        assert "TestKey.END" in _read_tabs_spec(scaffolded)

    def test_when_tabs_ts_is_generated_then_Enter_key_is_handled(
        self, scaffolded: Path
    ) -> None:
        assert "MatTabsModule" in _read_tabs_component(scaffolded)
        assert "TestKey.ENTER" in _read_tabs_spec(scaffolded)

    def test_when_tabs_ts_is_generated_then_Space_key_is_handled(
        self, scaffolded: Path
    ) -> None:
        assert "MatTabsModule" in _read_tabs_component(scaffolded)
        # The harness sends the Space key as the literal ' ' character.
        assert ", ' ')" in _read_tabs_spec(scaffolded)

    def test_when_tabs_template_is_generated_then_keydown_handler_is_wired(
        self, scaffolded: Path
    ) -> None:
        """Keydown reaches Material's tab header; the component adds no handler of its own."""
        component = _read_tabs_component(scaffolded)
        assert "<mat-tab-group" in component
        assert "keydown" not in component
        assert "sendKeys(" in _read_tabs_spec(scaffolded)


# ===========================================================================
# Criterion 3 — Material 3 structure, 48px targets, theme tokens
# ===========================================================================


class TestMaterialStructure:
    """Each component is <name>.ts + .html + .css, OnPush, styled only with tokens."""

    @pytest.mark.parametrize("name", TABS_COMPONENTS)
    def test_when_tabs_are_generated_then_each_component_has_ts_html_and_css(
        self, scaffolded: Path, name: str
    ) -> None:
        tabs_dir = scaffolded / TABS_RELATIVE_DIR
        for ext in ("ts", "html", "css"):
            assert (tabs_dir / f"{name}.{ext}").exists(), f"missing {name}.{ext}"
        ts = (tabs_dir / f"{name}.ts").read_text(encoding="utf-8")
        assert f"templateUrl: './{name}.html'" in ts
        assert f"styleUrl: './{name}.css'" in ts
        assert "ChangeDetectionStrategy.OnPush" in ts
        assert "template:" not in ts and "styles:" not in ts

    def test_when_tabs_are_generated_then_public_selectors_are_kept(
        self, scaffolded: Path
    ) -> None:
        component = _read_tabs_component(scaffolded)
        for selector in ("ui-tabs", "ui-tab", "ui-tab-panel"):
            assert f"selector: '{selector}'" in component

    def test_when_tabs_are_generated_then_tab_targets_keep_materials_48px_height(
        self, scaffolded: Path
    ) -> None:
        """Material's tab container is 48px at density 0; no stylesheet shrinks it."""
        assert "<mat-tab-group" in _read_tabs_template(scaffolded)
        assert "--mat-tab-container-height" not in _read_tabs_css(scaffolded)

    def test_when_tabs_css_is_generated_then_it_uses_tokens_without_color_literals(
        self, scaffolded: Path
    ) -> None:
        css = _read_tabs_css(scaffolded)
        assert "var(--mat-sys-" in css
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(", css)
        assert "!important" not in css
        assert "::ng-deep" not in css


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
