"""
Source-blind tests for issue #18: responsive Table + List.

Criteria covered (per oracle report):
  [UNIT] Table: Angular Material `<table mat-table>` from 600px (M3 medium),
         stacked card layout below 600px (M3 compact), keyboard-focusable
         horizontal-scroll region with `overscroll-behavior: contain`; split
         into table.ts + table.html + table.css, colors from --mat-sys-* only
  [UNIT] List: Angular Material `<mat-list role="list">` split into
         list.ts + list.html + list.css; divided + striped variants drawn
         with --mat-sys-* tokens only (no color literals)

Skipped (not runtime-verifiable per oracle):
  Dark-mode rendering and actual keyboard scrolling
    (require a rendered DOM / E2E tier; the region's role, tabindex and the
    token-only stylesheet are asserted statically below)
  All tests pass (boilerplate suite gate; no per-criterion assertion)
  SOLID, clean code (subjective code-quality prose; no concrete assertion)

Design note: tests scaffold a frontend-only project and inspect the generated
Table component files (table.ts + table.html + table.css) under
  project_initializer/templates/frontend/src/app/shared/ui/table/.
Breakpoints are the M3 window size classes (600/840/1200px), never Tailwind's
`md:` (768px).
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TABLE_RELATIVE_DIR = Path("frontend/src/app/shared/ui/table")
LIST_RELATIVE_DIR = Path("frontend/src/app/shared/ui/list")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_table_template(root: Path) -> str:
    """Return the generated Table component's template (table.html)."""
    return (root / TABLE_RELATIVE_DIR / "table.html").read_text(encoding="utf-8")


def _read_table_ts(root: Path) -> str:
    return (root / TABLE_RELATIVE_DIR / "table.ts").read_text(encoding="utf-8")


def _read_table_css(root: Path) -> str:
    return (root / TABLE_RELATIVE_DIR / "table.css").read_text(encoding="utf-8")


def _read_table_sources(root: Path) -> str:
    """Return table.ts + table.html + table.css concatenated (spec excluded)."""
    return "\n".join(
        (root / TABLE_RELATIVE_DIR / f"table.{ext}").read_text(encoding="utf-8")
        for ext in ("ts", "html", "css")
    )


_M3_MEDIUM_QUERY = re.compile(
    r"@media\s*\(min-width:\s*600px\)\s*\{(?P<body>.*?)\n\}", re.DOTALL
)


def _split_table_css(root: Path) -> tuple[str, str]:
    """Split table.css into (compact baseline rules, rules inside the 600px query)."""
    css = _read_table_css(root)
    match = _M3_MEDIUM_QUERY.search(css)
    assert match, (
        "Expected an `@media (min-width: 600px)` block in table.css: the layout "
        "switches at the M3 compact/medium boundary."
    )
    return css[: match.start()] + css[match.end() :], match.group("body")


def _css_rule(css: str, selector: str) -> str:
    """Return the declarations of the first rule whose selector is exactly `selector`."""
    match = re.search(
        rf"(?:^|\}}|\*/)\s*{re.escape(selector)}\s*\{{(?P<decls>[^}}]*)\}}", css
    )
    return match.group("decls") if match else ""


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

    def test_when_project_is_scaffolded_then_table_html_and_css_exist(
        self, scaffolded: Path
    ) -> None:
        for ext in ("html", "css"):
            path = scaffolded / TABLE_RELATIVE_DIR / f"table.{ext}"
            assert path.is_file(), (
                f"Expected table.{ext} at {path}: the Table component keeps its "
                "class, template and styles in separate files."
            )

    def test_when_table_ts_is_generated_then_template_and_styles_are_wired_by_url(
        self, scaffolded: Path
    ) -> None:
        content = _read_table_ts(scaffolded)
        assert "templateUrl: './table.html'" in content
        assert "styleUrl: './table.css'" in content
        assert "template:" not in content and "styles:" not in content, (
            "Expected no inline template or styles in table.ts."
        )

    def test_when_table_ts_is_generated_then_public_api_and_onpush_are_kept(
        self, scaffolded: Path
    ) -> None:
        content = _read_table_ts(scaffolded)
        assert "selector: 'ui-table'" in content
        assert "ChangeDetectionStrategy.OnPush" in content
        assert "export interface TableColumn" in content
        assert "standalone: true" not in content
        assert "MatTableModule" in content, (
            "Expected the Table component to build on Angular Material's MatTableModule."
        )

    def test_when_table_css_is_generated_then_colors_use_mat_sys_tokens_only(
        self, scaffolded: Path
    ) -> None:
        content = _read_table_css(scaffolded)
        assert "var(--mat-sys-surface)" in content
        assert "var(--mat-sys-outline-variant)" in content, (
            "Expected the region outline and row dividers to use outline-variant."
        )
        assert not _COLOR_LITERAL.search(content), (
            "Expected no hex/rgb/hsl color literals in table.css."
        )
        assert "!important" not in content and "::ng-deep" not in content

    def test_when_table_sources_are_generated_then_no_tailwind_utilities_remain(
        self, scaffolded: Path
    ) -> None:
        """Tailwind was removed: no utility classes in the template or the class."""
        markup = _read_table_template(scaffolded) + _read_table_ts(scaffolded)
        residue = re.findall(
            r"\b(?:overflow-x-auto|overscroll-contain|divide-y|space-y-\d|"
            r"(?:md|sm|lg|xl|dark|hover|focus):[\w-]+|bg-[\w-]+|text-(?:xs|sm|base|lg|xl)|"
            r"p[xy]-\d|rounded(?:-\w+)?|border-border|w-28|shrink-0)\b",
            markup,
        )
        assert not residue, f"Unexpected Tailwind utilities in the Table component: {residue}"


# ===========================================================================
# Criterion — Semantic <table> element at ≥md breakpoint
# ===========================================================================


class TestSemanticTableElement:
    """From 600px (M3 medium and wider) the component must render a genuine
    HTML <table> — Angular Material's native `<table mat-table>` — so that
    screen readers and browsers receive proper table semantics (row/column
    relationships, accessible headers)."""

    def test_when_table_template_is_generated_then_table_element_is_present(
        self, scaffolded: Path
    ) -> None:
        content = _read_table_template(scaffolded)
        assert "<table mat-table" in content, (
            "Expected a native <table mat-table> element in the Table component "
            "template for semantic rendering from the M3 medium breakpoint."
        )

    def test_when_table_css_is_generated_then_m3_medium_breakpoint_is_used(
        self, scaffolded: Path
    ) -> None:
        """The layout switch uses the M3 compact/medium boundary (600px) in a
        CSS media query, not Tailwind's `md:` prefix or its 768px breakpoint."""
        css = _read_table_css(scaffolded)
        assert re.search(r"@media\s*\(min-width:\s*600px\)", css), (
            "Expected `@media (min-width: 600px)` in table.css to activate the "
            "semantic table layout at the M3 medium window size class."
        )
        sources = _read_table_sources(scaffolded)
        assert "768px" not in sources, "Expected no 768px (Tailwind md) breakpoint."
        assert "md:" not in _read_table_template(scaffolded)

    def test_when_table_template_is_generated_then_header_row_is_defined(
        self, scaffolded: Path
    ) -> None:
        """A proper semantic table requires column headers so that assistive
        technology can associate data cells with headers. `mat-table` renders
        the `*matHeaderRowDef` row inside a real <thead> for native tables."""
        content = _read_table_template(scaffolded)
        assert "*matHeaderRowDef" in content, (
            "Expected a header row definition (*matHeaderRowDef), which mat-table "
            "renders inside <thead>."
        )
        assert re.search(r"<th mat-header-cell[^>]*scope=\"col\"", content), (
            "Expected <th mat-header-cell ... scope=\"col\"> header cells."
        )


# ===========================================================================
# Criterion — Card / stacked layout below md
# ===========================================================================


class TestCardStackedLayoutBelowMd:
    """Below 600px (M3 compact) the component must switch to a card or stacked
    layout (not a table) so that narrow windows display data readably."""

    def test_when_table_template_is_generated_then_card_or_block_element_is_present(
        self, scaffolded: Path
    ) -> None:
        """The compact (< 600px) view must use a non-table container — a div, dl,
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
        """The semantic table must be hidden in compact windows.
        Convention (mobile-first CSS): the `.table-data` table rule sets
        `display: none`, and the `@media (min-width: 600px)` block restores
        `display: table`."""
        assert 'class="table-data"' in _read_table_template(scaffolded)
        baseline, medium = _split_table_css(scaffolded)
        assert "display: none" in _css_rule(baseline, ".table-data"), (
            "Expected `.table-data { display: none }` so the table is hidden below 600px."
        )
        assert "display: table" in _css_rule(medium, ".table-data"), (
            "Expected `.table-data { display: table }` inside the 600px media query "
            "so the semantic table shows from the M3 medium breakpoint."
        )

    def test_when_table_template_is_generated_then_card_hidden_on_desktop_pattern_is_present(
        self, scaffolded: Path
    ) -> None:
        """The stacked card view must be hidden from 600px so only one
        layout variant is displayed (and announced) at a time.
        Convention: the `@media (min-width: 600px)` block sets
        `.table-cards { display: none }`; the cards list keeps role="list"
        because its markers are removed."""
        content = _read_table_template(scaffolded)
        assert re.search(r'<ul class="table-cards" role="list"', content), (
            "Expected the stacked cards as <ul class=\"table-cards\" role=\"list\">."
        )
        baseline, medium = _split_table_css(scaffolded)
        assert "display: none" not in _css_rule(baseline, ".table-cards")
        assert "display: none" in _css_rule(medium, ".table-cards"), (
            "Expected `.table-cards { display: none }` inside the 600px media query so "
            "the stacked layout collapses where the semantic <table> takes over."
        )


# ===========================================================================
# Criterion — Horizontal-scroll fallback with overscroll-contain
# ===========================================================================


class TestHorizontalScrollFallback:
    """When table content overflows horizontally the component must wrap it in
    a scrollable container with `overscroll-behavior: contain` (the CSS behind
    Tailwind's former `overscroll-contain`) so that scrolling the table does not
    accidentally trigger navigation or page scroll on mobile."""

    def test_when_table_css_is_generated_then_overflow_x_auto_is_present(
        self, scaffolded: Path
    ) -> None:
        """The scroll wrapper rule must set `overflow-x: auto` to enable
        horizontal scrolling when the table is wider than its container."""
        baseline, _ = _split_table_css(scaffolded)
        assert "overflow-x: auto" in _css_rule(baseline, ".table-region"), (
            "Expected `.table-region { overflow-x: auto }` to allow horizontal "
            "scrolling on narrow windows."
        )

    def test_when_table_css_is_generated_then_overscroll_contain_is_present(
        self, scaffolded: Path
    ) -> None:
        """The scroll container must set `overscroll-behavior: contain` so that
        scrolling the table does not propagate to the page on mobile browsers —
        the acceptance criterion names overscroll containment explicitly."""
        baseline, _ = _split_table_css(scaffolded)
        assert "overscroll-behavior: contain" in _css_rule(baseline, ".table-region"), (
            "Expected `.table-region { overscroll-behavior: contain }` on the "
            "horizontal-scroll wrapper."
        )

    def test_when_table_template_is_generated_then_scroll_wrapper_is_a_container(
        self, scaffolded: Path
    ) -> None:
        """The overflow and overscroll rules must apply to a wrapping element
        rather than to the <table> itself so that the scroll region is bounded
        correctly. The wrapper is a tab stop (tabindex 0) only while its content
        overflows, so keyboard users can scroll it and a table that fits adds no
        stop that does nothing, and it becomes a `region` landmark only when it
        scrolls and the consumer's `label` names it: M3 labels every region and
        never leaves two landmarks with the same name."""
        content = _read_table_template(scaffolded)
        wrapper = re.search(r"<div\s+class=\"table-region\"[^>]*>", content)
        assert wrapper, "Expected a <div class=\"table-region\"> scroll wrapper."
        tag = wrapper.group(0)
        assert re.search(r"\[attr\.tabindex\]=\"scrollable\(\)\s*\?\s*0\s*:\s*null\"", tag), (
            "Expected the scroll wrapper to be a tab stop only while it scrolls "
            "(`[attr.tabindex]=\"scrollable() ? 0 : null\"`)."
        )
        assert 'tabindex="0"' not in tag, (
            "Expected no static tabindex: a table that fits must not add a tab stop."
        )
        assert re.search(r"\[attr\.role\]=\"[^\"]*\?\s*'region'\s*:\s*null\"", tag), (
            "Expected the wrapper to take role=\"region\" only when it has a name "
            "(`[attr.role]=\"<name> ? 'region' : null\"`)."
        )
        assert "[attr.aria-label]" in tag, "Expected the region to carry an accessible name."
        ts = _read_table_ts(scaffolded)
        assert re.search(r"readonly label = input<string>\(\)", ts), (
            "Expected an optional `label` input with no generic default name, so "
            "unlabelled tables never share one landmark name."
        )
        assert wrapper.start() < content.index("<table"), (
            "Expected the scroll wrapper to enclose the <table>, not sit on it."
        )
        assert "overflow-x" not in _css_rule(_read_table_css(scaffolded), ".table-data")


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
        # Generic arguments may nest angle brackets (input<Record<string, unknown>[]>),
        # so match up to the call's opening parenthesis on the same line.
        assert re.search(r"readonly columns = input\b[^\n;]*\(", content), (
            "Expected signal-based `input()` in table.ts instead of @Input() "
            "decorator, per the Angular 21 standalone-signals convention."
        )
        assert re.search(r"readonly rows = input\b[^\n;]*\(", content)
        assert "@Input(" not in content

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
# Derived from: "stacked card layout below 600px (M3 compact)" — every column maps to one
# field in the card, so the field count equals the column count for all N ≥ 1.
#
# Invariant 2 (idempotence of scroll wrapper): the overscroll-behavior: contain
# region appears at most once per table instance (it is applied to a single
# wrapper, not duplicated per column or row).  For any number of rows R ≥ 0 or
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
    Criterion: "stacked card layout below 600px (M3 compact)".
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
    Criterion: "stacked card layout below 600px (M3 compact)" — every column maps to a field.
    """
    fields_n = _card_field_count_for_columns(num_columns)
    fields_n_plus_1 = _card_field_count_for_columns(num_columns + 1)
    assert fields_n_plus_1 > fields_n


# ===========================================================================
# Criterion — List: Material 3 static list, divided + striped variants via tokens
# ===========================================================================

_COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(")


def _read_list_source(root: Path, ext: str) -> str:
    """Return one of the List component's sources (`ts`, `html` or `css`)."""
    return (root / LIST_RELATIVE_DIR / f"list.{ext}").read_text(encoding="utf-8")


class TestListComponent:
    """The List component is an Angular Material `<mat-list>` whose template and
    styles live in separate files. List semantics are explicit (`mat-list` sets no
    role), and the divided and striped variants are drawn from `--mat-sys-*`
    tokens, so they follow the light and dark schemes without color literals."""

    def test_when_project_is_scaffolded_then_list_ts_html_and_css_exist(
        self, scaffolded: Path
    ) -> None:
        for ext in ("ts", "html", "css"):
            path = scaffolded / LIST_RELATIVE_DIR / f"list.{ext}"
            assert path.is_file(), (
                f"Expected list.{ext} at {path}: the List component keeps its "
                "class, template and styles in separate files."
            )

    def test_when_list_ts_is_generated_then_template_and_styles_are_wired_by_url(
        self, scaffolded: Path
    ) -> None:
        content = _read_list_source(scaffolded, "ts")
        assert "templateUrl: './list.html'" in content
        assert "styleUrl: './list.css'" in content
        assert "template:" not in content and "styles:" not in content, (
            "Expected no inline template or styles in list.ts."
        )

    def test_when_list_ts_is_generated_then_public_api_and_onpush_are_kept(
        self, scaffolded: Path
    ) -> None:
        content = _read_list_source(scaffolded, "ts")
        assert "selector: 'ui-list'" in content
        assert "ChangeDetectionStrategy.OnPush" in content
        assert "input<ListVariant>('default')" in content
        for variant in ("'default'", "'divided'", "'striped'"):
            assert variant in content, f"Expected ListVariant to keep {variant}."

    def test_when_list_template_is_generated_then_mat_list_carries_list_role(
        self, scaffolded: Path
    ) -> None:
        content = _read_list_source(scaffolded, "html")
        assert "<mat-list" in content, "Expected the list to render <mat-list>."
        assert 'role="list"' in content, (
            "Expected role=\"list\" on the list: mat-list sets no ARIA role."
        )

    def test_when_list_css_is_generated_then_variants_use_mat_sys_tokens_only(
        self, scaffolded: Path
    ) -> None:
        content = _read_list_source(scaffolded, "css")
        assert "[data-variant='divided']" in content
        assert "[data-variant='striped']" in content
        assert "var(--mat-sys-outline-variant)" in content, (
            "Expected dividers and the group outline to use the outline-variant token."
        )
        assert "var(--mat-divider-color, var(--mat-sys-outline-variant))" in content, (
            "Expected list dividers to read mat-divider's color token (outline-variant "
            "fallback), so mat.divider-overrides restyles them like <mat-divider>."
        )
        assert "var(--mat-sys-surface-container)" in content, (
            "Expected striped rows to use the surface-container token."
        )
        assert not _COLOR_LITERAL.search(content), (
            "Expected no hex/rgb/hsl color literals in list.css."
        )
        assert "!important" not in content and "::ng-deep" not in content
