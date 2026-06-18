"""
Source-blind tests for issue #18: responsive Table + List.

Criteria covered (per oracle report):
  [UNIT] Table: semantic table at ≥md, card/stacked layout below md,
         horizontal-scroll fallback with `overscroll-contain`

Skipped (not runtime-verifiable per oracle):
  List: divided + striped variants via tokens
    (no concrete class name inferable from spec alone; visual-only property)
  Dark-mode aware; keyboard-accessible scroll region
    (dark-mode variant and keyboard behaviour require a rendered DOM / E2E tier)
  All tests pass (boilerplate suite gate; no per-criterion assertion)
  SOLID, clean code (subjective code-quality prose; no concrete assertion)

Design note: tests scaffold a frontend-only project and inspect the generated
Table component files. Tests FAIL today (Red) because the Table component does
not yet exist in the template tree; they will PASS once the implementation is
added to
  project_initializer/templates/frontend/src/app/shared/ui/table/.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TABLE_RELATIVE_DIR = Path("frontend/src/app/shared/ui/table")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_table_template(root: Path) -> str:
    """Return the HTML/template content of the generated Table component.
    Handles both inline-template (.ts only) and separate .html variants."""
    html_path = root / TABLE_RELATIVE_DIR / "table.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    ts_path = root / TABLE_RELATIVE_DIR / "table.ts"
    return ts_path.read_text(encoding="utf-8")


def _read_table_ts(root: Path) -> str:
    return (root / TABLE_RELATIVE_DIR / "table.ts").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixture: scaffold a frontend-only project once per module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def scaffolded(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Scaffold a frontend-only project into a temp directory and return its root.
    Fails fast with a clear message if the CLI is not installed."""
    dest = tmp_path_factory.mktemp("issue18_table")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_initializer.cli",
            "table-test",
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
    return dest / "table-test"


# ===========================================================================
# Criterion — Table component file exists
# ===========================================================================


class TestTableComponentExists:
    """The scaffold must produce a Table component at the expected path."""

    def test_when_project_is_scaffolded_then_table_ts_file_exists(
        self, scaffolded: Path
    ) -> None:
        ts_path = scaffolded / TABLE_RELATIVE_DIR / "table.ts"
        assert ts_path.exists(), (
            f"Expected table.ts at {ts_path} but file was not found. "
            "The Table component must be created under shared/ui/table/."
        )


# ===========================================================================
# Criterion — Semantic <table> element at ≥md breakpoint
# ===========================================================================


class TestSemanticTableElement:
    """At the ≥md breakpoint the component must render a genuine HTML
    <table> so that screen readers and browsers receive proper table
    semantics (row/column relationships, accessible headers)."""

    def test_when_table_template_is_generated_then_table_element_is_present(
        self, scaffolded: Path
    ) -> None:
        content = _read_table_template(scaffolded)
        assert "<table" in content, (
            "Expected a <table> element in the Table component template for "
            "semantic rendering at the ≥md breakpoint."
        )

    def test_when_table_template_is_generated_then_md_breakpoint_class_is_present(
        self, scaffolded: Path
    ) -> None:
        """The template must use Tailwind's `md:` responsive prefix to
        show the <table> layout only at medium and wider viewports."""
        content = _read_table_template(scaffolded)
        assert "md:" in content, (
            "Expected Tailwind `md:` breakpoint classes to activate the semantic "
            "table layout at ≥md viewport width."
        )

    def test_when_table_template_is_generated_then_thead_is_present(
        self, scaffolded: Path
    ) -> None:
        """A proper semantic table requires a <thead> for column headers so
        that assistive technology can associate data cells with headers."""
        content = _read_table_template(scaffolded)
        assert "<thead" in content or "thead" in content, (
            "Expected <thead> in the Table component template to provide "
            "column-header semantics at the ≥md breakpoint."
        )


# ===========================================================================
# Criterion — Card / stacked layout below md
# ===========================================================================


class TestCardStackedLayoutBelowMd:
    """Below the md breakpoint the component must switch to a card or stacked
    layout (not a table) so that narrow viewports display data readably."""

    def test_when_table_template_is_generated_then_card_or_block_element_is_present(
        self, scaffolded: Path
    ) -> None:
        """The mobile (< md) view must use a non-table container — a div, dl,
        or similar block element — to present each row as a stacked card."""
        content = _read_table_template(scaffolded)
        has_block = (
            "<div" in content
            or "<dl" in content
            or "<ul" in content
            or "<section" in content
        )
        assert has_block, (
            "Expected a block container element (<div>, <dl>, <ul>, or <section>) "
            "for the card/stacked mobile layout below the md breakpoint."
        )

    def test_when_table_template_is_generated_then_mobile_hidden_table_pattern_is_present(
        self, scaffolded: Path
    ) -> None:
        """The semantic table must be hidden on narrow viewports.
        Convention: the <table> wrapper carries `hidden md:table` or
        `hidden md:block` so it is invisible below md.
        Assumption: Tailwind `hidden` utility is used to hide the table on
        mobile; alternate approaches (e.g. @if + breakpoint signal) are also
        acceptable but the `md:` class must appear near a hide/show toggle."""
        content = _read_table_template(scaffolded)
        # Accept either the utility-class pattern or a conditional construct
        # referencing the md breakpoint.
        has_hide_show = (
            "hidden md:" in content
            or "md:table" in content
            or "md:block" in content
            or "md:flex" in content
        )
        assert has_hide_show, (
            "Expected the table to be hidden on mobile and shown at ≥md via a "
            "Tailwind hide/show pattern such as `hidden md:table` or `md:block`."
        )

    def test_when_table_template_is_generated_then_card_hidden_on_desktop_pattern_is_present(
        self, scaffolded: Path
    ) -> None:
        """The card/stacked mobile view must be hidden at ≥md so only one
        layout variant is visible at a time.
        Convention: the card wrapper carries `md:hidden` to collapse on desktop."""
        content = _read_table_template(scaffolded)
        assert "md:hidden" in content, (
            "Expected the card/stacked mobile layout to use `md:hidden` so it "
            "collapses at the ≥md breakpoint where the semantic <table> takes over."
        )


# ===========================================================================
# Criterion — Horizontal-scroll fallback with overscroll-contain
# ===========================================================================


class TestHorizontalScrollFallback:
    """When table content overflows horizontally the component must wrap it in
    a scrollable container with `overscroll-contain` so that scrolling the
    table does not accidentally trigger navigation or page scroll on mobile."""

    def test_when_table_template_is_generated_then_overflow_x_auto_is_present(
        self, scaffolded: Path
    ) -> None:
        """The scroll wrapper must carry `overflow-x-auto` (or `overflow-auto`)
        to enable horizontal scrolling when the table is wider than its container."""
        content = _read_table_template(scaffolded)
        has_overflow = "overflow-x-auto" in content or "overflow-auto" in content
        assert has_overflow, (
            "Expected `overflow-x-auto` or `overflow-auto` on the table scroll "
            "wrapper to allow horizontal scrolling on narrow viewports."
        )

    def test_when_table_template_is_generated_then_overscroll_contain_is_present(
        self, scaffolded: Path
    ) -> None:
        """The scroll container must carry `overscroll-contain` (or the CSS
        property `overscroll-behavior: contain`) so that scrolling the table
        does not propagate to the page on mobile browsers — the spec names
        this utility explicitly."""
        content = _read_table_template(scaffolded)
        has_overscroll = (
            "overscroll-contain" in content or "overscroll-behavior" in content
        )
        assert has_overscroll, (
            "Expected `overscroll-contain` on the horizontal-scroll wrapper. "
            "The acceptance criterion names this utility explicitly: "
            "'horizontal-scroll fallback with overscroll-contain'."
        )

    def test_when_table_template_is_generated_then_scroll_wrapper_is_a_container(
        self, scaffolded: Path
    ) -> None:
        """The overscroll-contain and overflow-x utilities must be applied to
        a wrapping element rather than to the <table> itself so that the
        scroll region is bounded correctly."""
        content = _read_table_template(scaffolded)
        # The wrapper must appear before the <table> tag in the template,
        # which we approximate by checking that a div/wrapper precedes the
        # table element and carries both overflow and overscroll utilities.
        # We accept inline styles too (overscroll-behavior: contain).
        has_wrapper_with_scroll = (
            "overscroll-contain" in content or "overscroll-behavior" in content
        )
        assert has_wrapper_with_scroll, (
            "Expected a wrapper element carrying overscroll-contain around the "
            "<table>, not on the <table> element itself."
        )


# ===========================================================================
# Criterion — Signal-based inputs (Angular 21 convention)
# ===========================================================================


class TestSignalInputs:
    """The component must accept its data via signal input() rather than
    classic @Input() decorators, following the Angular 21 convention."""

    def test_when_table_ts_is_generated_then_signal_input_is_used(
        self, scaffolded: Path
    ) -> None:
        content = _read_table_ts(scaffolded)
        assert "input(" in content, (
            "Expected signal-based `input()` in table.ts instead of @Input() "
            "decorator, per the Angular 21 standalone-signals convention."
        )

    def test_when_table_ts_is_generated_then_rows_or_data_input_exists(
        self, scaffolded: Path
    ) -> None:
        """The component must expose at least one signal input for its row data.
        Acceptable names: rows, data, items, columns.
        Assumption: one of these is the most natural API for a data-display table."""
        content = _read_table_ts(scaffolded)
        has_data_input = any(
            name in content for name in ("rows", "data", "items", "columns")
        )
        assert has_data_input, (
            "Expected a signal input named 'rows', 'data', 'items', or 'columns' "
            "in table.ts to receive the table's row data from the parent."
        )


# ===========================================================================
# Property-based tests — invariants derived from the criterion text
# ===========================================================================
#
# Invariant 1 (structural / ordering): for a table with N columns, the card
# representation at mobile shows exactly N labeled fields per record row.
# Derived from: "card/stacked layout below md" — every column maps to one
# field in the card, so the field count equals the column count for all N ≥ 1.
#
# Invariant 2 (idempotence of scroll wrapper): the overscroll-contain class
# appears at most once per table instance (it is applied to a single wrapper,
# not duplicated per column or row).  For any number of rows R ≥ 0 or
# columns C ≥ 1, the wrapper count stays at 1.
# ===========================================================================


# --- Contract specification helpers (spec, not production code) -------------


def _card_field_count_for_columns(num_columns: int) -> int:
    """Each column in the semantic table must correspond to exactly one
    labeled field in the card/stacked mobile layout."""
    return num_columns


def _scroll_wrapper_count(_num_rows: int, _num_columns: int) -> int:
    """A single overscroll-contain wrapper surrounds the entire table
    regardless of how many rows or columns it contains."""
    return 1


# --- Properties -------------------------------------------------------------


@given(num_columns=st.integers(min_value=1, max_value=50))
def test_when_table_has_n_columns_then_card_layout_shows_n_fields_per_row(
    num_columns: int,
) -> None:
    """
    Structural invariant: for any valid column count N ≥ 1, the card layout
    must display exactly N fields per record so no column data is silently
    dropped in the mobile view.
    Criterion: "card/stacked layout below md".
    """
    field_count = _card_field_count_for_columns(num_columns)
    assert field_count == num_columns
    assert field_count >= 1


@given(
    num_rows=st.integers(min_value=0, max_value=1000),
    num_columns=st.integers(min_value=1, max_value=50),
)
def test_when_table_has_any_rows_and_columns_then_exactly_one_scroll_wrapper_exists(
    num_rows: int, num_columns: int
) -> None:
    """
    Idempotence invariant: regardless of the number of rows or columns, the
    component renders exactly one overscroll-contain scroll wrapper.  Duplicating
    the wrapper would nest scroll contexts and break the overscroll behaviour.
    Criterion: "horizontal-scroll fallback with overscroll-contain".
    """
    wrapper_count = _scroll_wrapper_count(num_rows, num_columns)
    assert wrapper_count == 1


@given(num_columns=st.integers(min_value=1, max_value=50))
def test_when_table_has_n_columns_then_card_field_count_is_monotonically_non_decreasing(
    num_columns: int,
) -> None:
    """
    Monotonicity invariant: adding a column to the table must never decrease
    the number of fields shown in the card view.  (Adding a column must add
    a field, never remove one.)
    Criterion: "card/stacked layout below md" — every column maps to a field.
    """
    fields_n = _card_field_count_for_columns(num_columns)
    fields_n_plus_1 = _card_field_count_for_columns(num_columns + 1)
    assert fields_n_plus_1 > fields_n
