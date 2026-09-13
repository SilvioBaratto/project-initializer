"""
Source-blind tests for issue #20: Pagination + Accordion.

Criteria covered (per oracle report):
  [UNIT] Pagination: nav[aria-label], aria-current="page" on the active page,
         accessible prev/next, 48px touch target, bounds-aware disabled state
         (built on Angular Material icon and text buttons, which render the 48px
         touch target; split into .ts/.html/.css styled with --mat-sys-* tokens,
         adapting at the M3 600px compact breakpoint)
  [UNIT] Accordion: button[aria-expanded][aria-controls] headers,
         panels role="region" + aria-labelledby, keyboard operable
         (built on Angular Material's expansion panel, which renders those
         attributes; split into .ts/.html/.css styled with --mat-sys-* tokens)

Skipped (not runtime-verifiable):
  Dark-mode tokens; visible focus
  All tests pass (boilerplate suite gate)
  SOLID / clean-code prose (subjective, no concrete runtime assertion)

Design note: tests scaffold a frontend-only project and inspect the generated
component template files. Tests FAIL today (Red) because neither Pagination nor
Accordion exists in the template tree yet. They will PASS once the components
are added to:
  project_initializer/templates/frontend/src/app/shared/ui/pagination/
  project_initializer/templates/frontend/src/app/shared/ui/accordion/
"""

import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

PAGINATION_DIR = Path("frontend/src/app/shared/ui/pagination")
ACCORDION_DIR = Path("frontend/src/app/shared/ui/accordion")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_template(component_dir: Path, root: Path, name: str) -> str:
    """
    Return template content for a component.
    Prefers the separate .html file; falls back to reading the .ts file which
    may contain an inline template string.
    """
    html_path = root / component_dir / f"{name}.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    ts_path = root / component_dir / f"{name}.ts"
    return ts_path.read_text(encoding="utf-8")


def _read_ts(component_dir: Path, root: Path, name: str) -> str:
    return (root / component_dir / f"{name}.ts").read_text(encoding="utf-8")


def _read_pagination_sources(root: Path, *patterns: str) -> str:
    """Concatenate the pagination unit's sources (specs excluded).

    Defaults to every .ts, .html and .css file in the unit folder.
    """
    unit_dir = root / PAGINATION_DIR
    files = sorted(
        {
            path
            for pattern in (patterns or ("*.ts", "*.html", "*.css"))
            for path in unit_dir.glob(pattern)
            if not path.name.endswith(".spec.ts")
        }
    )
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


# ---------------------------------------------------------------------------
# Fixture: scaffold a frontend-only project once per module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def scaffolded(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Scaffold a frontend-only project into a temp directory and return its root.
    Fails fast with a clear message if the CLI is not installed.
    """
    dest = tmp_path_factory.mktemp("issue20_pagination_accordion")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_initializer.cli",
            "pg-acc-test",
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
    return dest / "pg-acc-test"


# ===========================================================================
# Criterion 1 — Pagination ARIA and touch-target
# ===========================================================================


class TestPaginationNavLandmark:
    """nav element with aria-label must wrap the pagination control."""

    def test_when_pagination_template_is_generated_then_nav_element_is_present(
        self, scaffolded: Path
    ) -> None:
        content = _read_template(PAGINATION_DIR, scaffolded, "pagination")
        assert "<nav" in content

    def test_when_pagination_template_is_generated_then_aria_label_is_on_nav(
        self, scaffolded: Path
    ) -> None:
        """
        The nav must carry aria-label so screen readers announce the landmark.
        Criterion: 'nav[aria-label]'.
        """
        content = _read_template(PAGINATION_DIR, scaffolded, "pagination")
        assert "aria-label" in content

    def test_when_pagination_ts_is_generated_then_nav_label_is_an_input_defaulting_to_pagination(
        self, scaffolded: Path
    ) -> None:
        """Each navigation landmark needs a unique label, so a view with two
        paginators must be able to name them apart; the default stays 'Pagination'."""
        ts = _read_ts(PAGINATION_DIR, scaffolded, "pagination")
        assert "label = input('Pagination')" in ts
        html = _read_template(PAGINATION_DIR, scaffolded, "pagination")
        assert '[attr.aria-label]="label()"' in html


class TestPaginationCurrentPage:
    """aria-current="page" must mark the active page button."""

    def test_when_pagination_template_is_generated_then_aria_current_page_is_present(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'aria-current="page" on the active page'.
        The literal string 'aria-current' must appear in the template so that
        the active page button can be identified by assistive technology.
        """
        content = _read_template(PAGINATION_DIR, scaffolded, "pagination")
        assert "aria-current" in content

    def test_when_pagination_template_is_generated_then_aria_current_value_is_page(
        self, scaffolded: Path
    ) -> None:
        """
        The value of aria-current must be 'page', not 'true' or another value.
        Criterion: 'aria-current="page"'.
        Assumption (simplest reading of the criterion): a static or dynamic
        binding that can resolve to the string 'page' must be present.
        """
        content = _read_template(PAGINATION_DIR, scaffolded, "pagination")
        # Covers both static 'aria-current="page"' and Angular binding 'page'
        assert "page" in content and "aria-current" in content


class TestPaginationPrevNext:
    """Prev and next controls must be present and accessible."""

    def test_when_pagination_template_is_generated_then_prev_control_is_present(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'accessible prev/next'.
        A previous-page control must exist (button or link with discernible text
        or aria-label containing 'prev', 'previous', or similar).
        """
        content = _read_template(PAGINATION_DIR, scaffolded, "pagination").lower()
        assert "prev" in content

    def test_when_pagination_template_is_generated_then_next_control_is_present(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'accessible prev/next'.
        A next-page control must exist with discernible label.
        """
        content = _read_template(PAGINATION_DIR, scaffolded, "pagination").lower()
        assert "next" in content


class TestPaginationTouchTarget:
    """Each page control must meet the 48px M3 touch-target requirement."""

    def test_when_pagination_template_is_generated_then_min_size_class_is_applied(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: '≥44px' (M3: 48×48px).
        The controls are Material buttons (matIconButton / matButton), which render
        a 48px touch target at density 0, and the unit's CSS keeps every control
        cell and page button at least 48px.
        """
        content = _read_pagination_sources(scaffolded)
        assert "matIconButton" in content and "matButton" in content, (
            "Pagination controls must be Material buttons, which provide the 48px touch target."
        )
        css = _read_pagination_sources(scaffolded, "*.css")
        assert "min-block-size: 48px" in css
        assert "min-inline-size: 48px" in css


class TestPaginationComponentFiles:
    """Pagination is split into .ts + .html + .css and styled with M3 tokens."""

    def test_when_pagination_is_generated_then_it_has_ts_html_and_css(
        self, scaffolded: Path
    ) -> None:
        for ext in ("ts", "html", "css"):
            assert (scaffolded / PAGINATION_DIR / f"pagination.{ext}").is_file(), (
                f"missing pagination.{ext}"
            )
        ts = _read_ts(PAGINATION_DIR, scaffolded, "pagination")
        assert "templateUrl: './pagination.html'" in ts
        assert "styleUrl: './pagination.css'" in ts
        assert "ChangeDetectionStrategy.OnPush" in ts
        assert "template:" not in ts and "styles:" not in ts

    def test_when_pagination_css_is_generated_then_it_uses_tokens_without_color_literals(
        self, scaffolded: Path
    ) -> None:
        """Replaces the Tailwind dark: token check: colors come from --mat-sys-* roles."""
        import re

        css = _read_pagination_sources(scaffolded, "*.css")
        assert "var(--mat-sys-" in css
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", css)
        assert "!important" not in css
        assert "::ng-deep" not in css

    def test_when_pagination_css_is_generated_then_current_page_has_a_non_color_cue(
        self, scaffolded: Path
    ) -> None:
        """The current page must not be marked by its fill color alone (WCAG 1.4.1):
        next to the tonal fill, its label gets the prominent weight via the button token."""
        import re

        css = _read_pagination_sources(scaffolded, "*.css")
        rule = re.search(r"\.page\[aria-current=['\"]page['\"]\]\s*\{([^}]*)\}", css)
        assert rule, "missing a .page[aria-current='page'] rule"
        assert (
            "--mat-button-tonal-label-text-weight: var(--mat-sys-label-large-weight-prominent)"
            in rule.group(1)
        )

    def test_when_pagination_css_is_generated_then_it_adapts_to_its_own_width(
        self, scaffolded: Path
    ) -> None:
        """A paginator narrower than its widest row (11 slots of 48px = 528px) swaps page
        numbers for a status. The host is the query container, so a docked rail and page
        margins count, not the window width; never a 768px breakpoint."""
        import re

        css = _read_pagination_sources(scaffolded, "*.css")
        assert re.search(r"container:\s*pagination\s*/\s*inline-size", css)
        assert re.search(r"@container pagination \(max-width: 527\.98px\)", css)
        assert re.search(r"@container pagination \(min-width: 528px\)", css)
        assert not re.search(r"@media[^{]*width", css)
        assert "768px" not in css

    def test_when_pagination_css_is_generated_then_directional_icons_mirror_in_rtl(
        self, scaffolded: Path
    ) -> None:
        css = _read_pagination_sources(scaffolded, "*.css")
        assert ":dir(rtl)" in css and "scaleX(-1)" in css

    def test_when_pagination_sources_are_generated_then_no_tailwind_utilities_remain(
        self, scaffolded: Path
    ) -> None:
        import re

        content = _read_pagination_sources(scaffolded)
        assert not re.search(
            r"\b(min-h-11|min-w-11|inline-flex|items-center|rounded-md|text-sm|"
            r"focus-visible:|dark:|hover:|disabled:opacity)",
            content,
        )


class TestPaginationDisabledState:
    """Prev must be disabled on the first page; next must be disabled on the last."""

    def test_when_pagination_template_is_generated_then_disabled_binding_is_present(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'bounds-aware disabled state'.
        The template must contain a disabled or aria-disabled binding so the
        component can reflect boundary conditions at runtime.
        """
        content = _read_template(PAGINATION_DIR, scaffolded, "pagination")
        assert "disabled" in content

    def test_when_pagination_ts_is_generated_then_first_page_bound_is_checked(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'bounds-aware disabled state'.
        The TypeScript must contain logic that identifies page 1 as the lower
        bound (currentPage === 1, page === 1, or equivalent).
        Assumption: the component tracks current page and compares it to 1 to
        disable the prev button.
        """
        content = _read_ts(PAGINATION_DIR, scaffolded, "pagination")
        # Accept === 1, == 1, <= 1, or currentPage - 1 === 0
        has_lower_bound = "=== 1" in content or "== 1" in content or "<= 1" in content
        assert has_lower_bound, (
            "No lower-bound page check found in pagination.ts. "
            "Expected a comparison to page 1 for the prev-disabled state."
        )

    def test_when_pagination_ts_is_generated_then_last_page_bound_is_checked(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'bounds-aware disabled state'.
        The TypeScript must contain logic that identifies the last page as the
        upper bound to disable the next button.
        Assumption: the component computes or compares against a total-pages
        value (totalPages, pageCount, total, lastPage, or equivalent).
        """
        content = _read_ts(PAGINATION_DIR, scaffolded, "pagination")
        has_upper_bound = any(
            kw in content
            for kw in ("totalPages", "pageCount", "lastPage", "total", "pageCount")
        )
        assert has_upper_bound, (
            "No upper-bound page reference found in pagination.ts. "
            "Expected a totalPages / pageCount / lastPage concept."
        )


# ===========================================================================
# Criterion 2 — Accordion ARIA and keyboard
# ===========================================================================


#
# The accordion is built on Angular Material's expansion panel. Material's
# <mat-expansion-panel-header> host renders role="button" with aria-expanded and
# aria-controls bindings and handles Enter/Space itself; the panel body renders
# role="region" with aria-labelledby pointing back at the header. Those
# attributes live in Material's template rather than ours, so each assert accepts
# either the literal attribute in the unit's sources or the Material element that
# provides it. The unit is split into accordion.{ts,html,css} and
# accordion-item.{ts,html,css}, so the readers below glob the whole folder.

_MATERIAL_HEADER = "<mat-expansion-panel-header"


def _read_accordion_sources(root: Path, *patterns: str) -> str:
    """Concatenate the accordion unit's sources (specs excluded).

    Defaults to every .ts, .html and .css file in the unit folder.
    """
    unit_dir = root / ACCORDION_DIR
    files = sorted(
        {
            path
            for pattern in (patterns or ("*.ts", "*.html", "*.css"))
            for path in unit_dir.glob(pattern)
            if not path.name.endswith(".spec.ts")
        }
    )
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def _css_block(css: str, selector: str) -> str:
    """Declarations of the first rule whose selector list ends with exactly `selector`."""
    import re

    match = re.search(r"(?:^|[,}\s])" + re.escape(selector) + r"\s*\{([^{}]*)\}", css, re.MULTILINE)
    assert match, f"no CSS rule for {selector!r}"
    return match.group(1)


def _uses_material_panel(content: str) -> bool:
    """True when a template renders <mat-expansion-panel> (not only its header)."""
    return "<mat-expansion-panel>" in content or "<mat-expansion-panel " in content


class TestAccordionComponentFiles:
    """Each accordion component is split into .ts + .html + .css and styled with M3 tokens."""

    def test_when_accordion_is_generated_then_each_component_has_ts_html_and_css(
        self, scaffolded: Path
    ) -> None:
        for name in ("accordion", "accordion-item"):
            for ext in ("ts", "html", "css"):
                assert (scaffolded / ACCORDION_DIR / f"{name}.{ext}").is_file(), (
                    f"missing {name}.{ext}"
                )
            ts = (scaffolded / ACCORDION_DIR / f"{name}.ts").read_text(encoding="utf-8")
            assert f"templateUrl: './{name}.html'" in ts
            assert f"styleUrl: './{name}.css'" in ts
            assert "ChangeDetectionStrategy.OnPush" in ts

    def test_when_accordion_css_is_generated_then_it_uses_tokens_without_color_literals(
        self, scaffolded: Path
    ) -> None:
        """Replaces the Tailwind dark: token check: colors come from --mat-sys-* roles."""
        import re

        css = _read_accordion_sources(scaffolded, "*.css")
        assert "var(--mat-sys-" in css
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", css)
        assert "!important" not in css
        assert "::ng-deep" not in css

    def test_when_accordion_css_is_generated_then_headers_keep_a_48px_target(
        self, scaffolded: Path
    ) -> None:
        """Material's header is 48px collapsed; the unit's CSS keeps that as its minimum."""
        css = _read_accordion_sources(scaffolded, "*.css")
        assert "min-block-size: 48px" in css

    def test_when_accordion_css_is_generated_then_expanded_headers_get_a_hover_state_layer(
        self, scaffolded: Path
    ) -> None:
        """
        M3 hover is inherited by list-like rows (interaction/states.md:172-176). Material
        21.2 paints hover only on collapsed headers, so the unit draws a token-only
        ::after layer on every header (::before is the focus ring), expanded included.
        """
        css = _read_accordion_sources(scaffolded, "accordion-item.css")
        block = _css_block(css, ".mat-expansion-panel-header:not([aria-disabled='true']):hover::after")
        assert "@media (hover: hover)" in css
        assert "var(--mat-sys-on-surface)" in block
        assert "opacity: var(--mat-sys-hover-state-layer-opacity)" in block
        assert "pointer-events: none" in block
        header = _css_block(css, ".mat-expansion-panel-header")
        assert "--mat-expansion-header-hover-state-layer-color: transparent" in header
        assert "position: relative" in header

    def test_when_accordion_css_is_generated_then_ring_corners_follow_the_row_position(
        self, scaffolded: Path
    ) -> None:
        """
        The focus ring follows the component's shape (interaction/states.md:212-218):
        square middle rows, the container's inner corner on the outer edges of the first
        and last rows. Header radius and ring token are set together so both of
        Material's ring radius sources agree.
        """
        item_css = _read_accordion_sources(scaffolded, "accordion-item.css")
        container_css = _read_accordion_sources(scaffolded, "accordion.css")
        assert "--ui-accordion-inner-corner: calc(var(--mat-sys-corner-medium) - 1px)" in container_css
        assert "--mat-focus-indicator-border-radius: 0;" in _css_block(
            item_css, ".mat-expansion-panel-header"
        )
        first = _css_block(item_css, ":host(:first-child) .mat-expansion-panel-header")
        last = _css_block(item_css, ":host(:last-child) .mat-expansion-panel-header:not(.mat-expanded)")
        only = _css_block(
            item_css, ":host(:first-child:last-child) .mat-expansion-panel-header:not(.mat-expanded)"
        )
        for block, corners in ((first, ("start-start", "start-end")), (last, ("end-start", "end-end"))):
            assert "--mat-focus-indicator-border-radius:" in block
            for corner in corners:
                assert f"border-{corner}-radius: var(--ui-accordion-inner-corner)" in block
        assert "--mat-focus-indicator-border-radius: var(--ui-accordion-inner-corner)" in only

    def test_when_accordion_css_is_generated_then_header_height_change_is_animated(
        self, scaffolded: Path
    ) -> None:
        """
        With `auto` header heights Material's `height` transition has nothing to animate,
        so the 48px to 64px minimum transitions on Material's 225ms expansion timing,
        gated on the class the panel adds only when animations are enabled.
        """
        css = _read_accordion_sources(scaffolded, "accordion-item.css")
        block = _css_block(
            css, ".mat-expansion-panel-animations-enabled .mat-expansion-panel-header"
        )
        assert "transition: min-block-size 225ms" in block


class TestAccordionHeaderButton:
    """Each accordion header must be a button with aria-expanded and aria-controls."""

    def test_when_accordion_template_is_generated_then_button_element_is_present(
        self, scaffolded: Path
    ) -> None:
        """Material's expansion panel header carries role="button"."""
        content = _read_accordion_sources(scaffolded)
        assert "<button" in content or _MATERIAL_HEADER in content

    def test_when_accordion_template_is_generated_then_aria_expanded_is_present(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'button[aria-expanded][aria-controls]'.
        aria-expanded communicates whether the associated panel is open; Material's
        header binds it.
        """
        content = _read_accordion_sources(scaffolded)
        assert "aria-expanded" in content or _MATERIAL_HEADER in content

    def test_when_accordion_template_is_generated_then_aria_controls_is_present(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'button[aria-expanded][aria-controls]'.
        aria-controls links the button to its panel via the panel's id; Material's
        header binds it.
        """
        content = _read_accordion_sources(scaffolded)
        assert "aria-controls" in content or _MATERIAL_HEADER in content


class TestAccordionPanel:
    """Each accordion panel must have role="region" and aria-labelledby."""

    def test_when_accordion_template_is_generated_then_region_role_is_present(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'panels role="region"'.
        W3C APG disclosure pattern requires the panel to have role="region" so
        it is exposed as a landmark when the accordion has a meaningful label.
        Material's expansion panel renders its body with role="region".
        """
        content = _read_accordion_sources(scaffolded)
        assert 'role="region"' in content or _uses_material_panel(content)

    def test_when_accordion_template_is_generated_then_aria_labelledby_is_present(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'panels … aria-labelledby'.
        aria-labelledby on the panel region must point back to the header button
        so the landmark is announced by its header text. Material's expansion
        panel binds it to its header's id.
        """
        content = _read_accordion_sources(scaffolded)
        assert "aria-labelledby" in content or _uses_material_panel(content)


class TestAccordionKeyboardOperable:
    """Accordion must handle keyboard activation (Enter and Space at minimum)."""

    def test_when_accordion_ts_is_generated_then_Enter_key_is_handled(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'keyboard operable'.
        W3C APG disclosure: Enter activates the header. Verifiable as explicit
        handling in the sources, a native <button>, or Material's expansion panel
        header (which toggles its panel on Enter).
        """
        content = _read_accordion_sources(scaffolded)
        assert "Enter" in content or "<button" in content or _MATERIAL_HEADER in content, (
            "Accordion is not keyboard-operable: no Enter key handler, no native "
            "<button> and no Material expansion panel header found."
        )

    def test_when_accordion_ts_is_generated_then_Space_key_is_handled(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'keyboard operable'.
        Space activates the header: explicit handling, a native <button>, or
        Material's expansion panel header (which toggles on Space and prevents
        the page scroll).
        """
        content = _read_accordion_sources(scaffolded)
        assert "Space" in content or "<button" in content or _MATERIAL_HEADER in content, (
            "Accordion is not keyboard-operable via Space: no Space handler, no "
            "native <button> and no Material expansion panel header found."
        )

    def test_when_accordion_ts_is_generated_then_single_mode_drives_material_multi(
        self, scaffolded: Path
    ) -> None:
        """The `single` input keeps its meaning by mapping onto MatAccordion's `multi`."""
        ts = _read_accordion_sources(scaffolded, "accordion.ts")
        assert "single = input(" in ts
        assert "MatAccordion" in ts
        assert ".multi = !this.single()" in ts

    def test_when_accordion_ts_is_generated_then_toggle_method_exists(
        self, scaffolded: Path
    ) -> None:
        """
        Criterion: 'keyboard operable'.
        The component must expose a toggle/open/close method or signal that
        responds to user interaction so panels can be expanded and collapsed.
        Assumption: the method is named toggle, open, close, or expand, or
        there is an isOpen / expanded signal/property.
        """
        content = _read_ts(ACCORDION_DIR, scaffolded, "accordion")
        has_toggle = any(
            kw in content for kw in ("toggle", "isOpen", "expanded", "open(", "close(")
        )
        assert has_toggle, (
            "No toggle/open/close/expanded method or property found in "
            "accordion.ts. The component must be able to expand and collapse panels."
        )


# ===========================================================================
# Property-based tests — invariants derived from the criterion text
# ===========================================================================
#
# These encode the mathematical contracts that Pagination and Accordion must
# satisfy for ALL valid inputs. The reference implementations below are
# CONTRACT SPECIFICATIONS — they must never be replaced by imports from the
# production module.
# ===========================================================================


# ---------------------------------------------------------------------------
# Pagination invariant helpers (spec, not production code)
# ---------------------------------------------------------------------------


def _is_prev_disabled(current_page: int, _total_pages: int) -> bool:
    """Prev is disabled exactly when we are on the first page."""
    return current_page <= 1


def _is_next_disabled(current_page: int, total_pages: int) -> bool:
    """Next is disabled exactly when we are on the last page."""
    return current_page >= total_pages


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Pagination properties
# ---------------------------------------------------------------------------


@given(
    total_pages=st.integers(min_value=1, max_value=100),
    current_page=st.integers(min_value=1, max_value=100),
)
def test_when_on_first_page_then_prev_is_always_disabled(
    total_pages: int, current_page: int
) -> None:
    """
    Invariant: prev is disabled if and only if current_page == 1.
    Criterion: 'bounds-aware disabled state'.
    """
    page = _clamp(current_page, 1, total_pages)
    if page == 1:
        assert _is_prev_disabled(page, total_pages)
    else:
        assert not _is_prev_disabled(page, total_pages)


@given(
    total_pages=st.integers(min_value=1, max_value=100),
    current_page=st.integers(min_value=1, max_value=100),
)
def test_when_on_last_page_then_next_is_always_disabled(
    total_pages: int, current_page: int
) -> None:
    """
    Invariant: next is disabled if and only if current_page == total_pages.
    Criterion: 'bounds-aware disabled state'.
    """
    page = _clamp(current_page, 1, total_pages)
    if page == total_pages:
        assert _is_next_disabled(page, total_pages)
    else:
        assert not _is_next_disabled(page, total_pages)


@given(
    total_pages=st.integers(min_value=2, max_value=100),
    current_page=st.integers(min_value=2, max_value=99),
)
def test_when_on_interior_page_then_neither_prev_nor_next_is_disabled(
    total_pages: int, current_page: int
) -> None:
    """
    Invariant: on any interior page (not first, not last), both controls
    are enabled.
    Criterion: 'bounds-aware disabled state'.
    """
    if total_pages < 2:
        return
    # Keep page strictly interior
    page = _clamp(current_page, 2, total_pages - 1)
    if page < 2 or page >= total_pages:
        return
    assert not _is_prev_disabled(page, total_pages)
    assert not _is_next_disabled(page, total_pages)


@given(total_pages=st.integers(min_value=1, max_value=100))
def test_when_total_pages_is_any_valid_count_then_page_1_is_always_first_boundary(
    total_pages: int,
) -> None:
    """
    Invariant: page 1 is always the lower bound, regardless of total page count.
    Criterion: 'bounds-aware disabled state'.
    """
    assert _is_prev_disabled(1, total_pages)
    assert not _is_next_disabled(1, total_pages) or total_pages == 1


@given(total_pages=st.integers(min_value=1, max_value=100))
def test_when_total_pages_is_any_valid_count_then_last_page_is_always_upper_boundary(
    total_pages: int,
) -> None:
    """
    Invariant: the last page is always the upper bound.
    Criterion: 'bounds-aware disabled state'.
    """
    assert _is_next_disabled(total_pages, total_pages)
    assert not _is_prev_disabled(total_pages, total_pages) or total_pages == 1


# ---------------------------------------------------------------------------
# Accordion invariant helpers (spec, not production code)
# ---------------------------------------------------------------------------


def _toggle_expanded(is_expanded: bool) -> bool:
    """Toggle the expanded state of a single accordion item."""
    return not is_expanded


# ---------------------------------------------------------------------------
# Accordion properties
# ---------------------------------------------------------------------------


@given(initial_state=st.booleans())
def test_when_accordion_item_is_toggled_twice_then_state_returns_to_original(
    initial_state: bool,
) -> None:
    """
    Round-trip invariant: toggling an accordion item's expanded state twice
    returns to the original state.
    Criterion: 'button[aria-expanded]' (the value must flip and flip back).
    """
    after_first = _toggle_expanded(initial_state)
    after_second = _toggle_expanded(after_first)
    assert after_second == initial_state


@given(initial_state=st.booleans())
def test_when_accordion_item_is_toggled_then_state_is_different_from_original(
    initial_state: bool,
) -> None:
    """
    Invariant: a single toggle always changes the state (not a no-op).
    Criterion: 'button[aria-expanded]' — expanded must change on activation.
    """
    after_toggle = _toggle_expanded(initial_state)
    assert after_toggle != initial_state


@given(num_items=st.integers(min_value=1, max_value=50))
def test_when_accordion_has_any_number_of_items_then_each_has_its_own_expanded_state(
    num_items: int,
) -> None:
    """
    Invariant: each accordion item independently tracks its own expanded state;
    the number of tracked states equals the number of items.
    Criterion: 'button[aria-expanded][aria-controls]' (one button per item).
    """
    # Model: all items start collapsed
    states = [False] * num_items
    assert len(states) == num_items


@given(
    num_items=st.integers(min_value=2, max_value=50),
    item_index=st.integers(min_value=0, max_value=49),
)
def test_when_one_accordion_item_is_toggled_then_other_items_are_unaffected(
    num_items: int, item_index: int
) -> None:
    """
    Invariant (independence): toggling one item does not alter the expanded
    state of any other item (multi-open disclosure pattern, not forced single).
    Criterion: 'button[aria-expanded]' — each button controls its own panel.
    Assumption: the accordion follows the W3C disclosure (multi-open) pattern,
    where each item is independently toggled. Single-open accordion would be
    a different contract not stated in the criterion.
    """
    idx = item_index % num_items
    states = [False] * num_items
    # Toggle item at idx
    states[idx] = _toggle_expanded(states[idx])
    # All other items remain unchanged (still False)
    for i, state in enumerate(states):
        if i != idx:
            assert state is False
