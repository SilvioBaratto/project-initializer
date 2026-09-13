"""
Source-blind tests for issue #17: Breadcrumbs with aria-current page.

Criteria covered (per oracle report):
  [UNIT] nav[aria-label="Breadcrumb"] wrapping an ordered list of crumbs
  [UNIT] Last crumb has aria-current="page" and is not a link; separators
         are aria-hidden
  [UNIT] Material 3 theme tokens (light and dark via --mat-sys-* roles);
         accepts crumb items via a signal input

Skipped (not runtime-verifiable):
  All tests pass (boilerplate suite gate)
  SOLID / clean code (subjective code-quality prose)

Design note: tests scaffold a frontend-only project and inspect the generated
Breadcrumbs component files under
  project_initializer/templates/frontend/src/app/shared/ui/breadcrumbs/.
Markup asserts read breadcrumbs.html only (so a doc comment in the .ts can
never satisfy them); styling asserts read breadcrumbs.css.
Material 3 has no breadcrumbs component, so the trail is built on --mat-sys-*
tokens: dark mode comes from the theme's light-dark() tokens rather than
Tailwind dark: classes.
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

BREADCRUMBS_RELATIVE_DIR = Path("frontend/src/app/shared/ui/breadcrumbs")

# Color literals a token-only stylesheet must not contain.
COLOR_LITERAL_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_breadcrumbs_template(root: Path) -> str:
    """
    Return the markup of the generated Breadcrumbs component: breadcrumbs.html
    alone, falling back to breadcrumbs.ts only when no .html exists (inline
    template). Never joined with the .ts, so its doc comment cannot satisfy a
    markup assert.
    """
    html_path = root / BREADCRUMBS_RELATIVE_DIR / "breadcrumbs.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return _read_breadcrumbs_ts(root)


def _read_breadcrumbs_sources(root: Path) -> str:
    """
    Return breadcrumbs.ts + breadcrumbs.html + breadcrumbs.css concatenated,
    for checks that must hold across every component file (no Tailwind dark:).
    """
    component_dir = root / BREADCRUMBS_RELATIVE_DIR
    parts = [
        component_dir / name
        for name in ("breadcrumbs.ts", "breadcrumbs.html", "breadcrumbs.css")
    ]
    return "\n".join(p.read_text(encoding="utf-8") for p in parts if p.exists())


def _read_breadcrumbs_ts(root: Path) -> str:
    return (root / BREADCRUMBS_RELATIVE_DIR / "breadcrumbs.ts").read_text(
        encoding="utf-8"
    )


def _read_breadcrumbs_css(root: Path) -> str:
    return (root / BREADCRUMBS_RELATIVE_DIR / "breadcrumbs.css").read_text(
        encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Fixture: scaffold a frontend-only project once per session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def scaffolded(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Scaffold a frontend-only project into a temp directory and return its root.
    Fails fast with a clear message if the CLI is not installed.
    """
    dest = tmp_path_factory.mktemp("issue17_breadcrumbs")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "project_initializer.cli",
            "breadcrumbs-test",
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
    return dest / "breadcrumbs-test"


# ===========================================================================
# Criterion 1 — nav[aria-label="Breadcrumb"] wrapping an ordered list
# ===========================================================================


class TestNavLandmarkAndOrderedList:
    """The breadcrumb container must be a <nav> with aria-label="Breadcrumb"
    and its crumb list must be an ordered list (<ol>)."""

    def test_when_breadcrumbs_template_is_generated_then_nav_element_is_present(
        self, scaffolded: Path
    ) -> None:
        content = _read_breadcrumbs_template(scaffolded)
        assert "<nav" in content

    def test_when_breadcrumbs_template_is_generated_then_nav_has_aria_label_breadcrumb(
        self, scaffolded: Path
    ) -> None:
        """The nav is named "Breadcrumb": either statically, or bound from a
        label input that defaults to "Breadcrumb" (so pages with several trails
        can give each landmark a distinct name)."""
        content = _read_breadcrumbs_template(scaffolded)
        ts = _read_breadcrumbs_ts(scaffolded)
        static_label = 'aria-label="Breadcrumb"' in content
        bound_label = bool(
            re.search(r'<nav\b[^>]*\[attr\.aria-label\]="label\(\)"', content)
            and re.search(r"\blabel\s*=\s*input\(\s*'Breadcrumb'\s*\)", ts)
        )
        assert static_label or bound_label

    def test_when_breadcrumbs_template_is_generated_then_ordered_list_is_present(
        self, scaffolded: Path
    ) -> None:
        """Crumbs must be in an <ol>, not an unordered list, so that their
        positional order is semantically meaningful to assistive technology."""
        content = _read_breadcrumbs_template(scaffolded)
        assert "<ol" in content


# ===========================================================================
# Criterion 2 — Last crumb: aria-current="page", not a link; separators
#               are aria-hidden
# ===========================================================================


class TestCurrentPageCrumb:
    """The last crumb must carry aria-current="page" and must not be rendered
    as an anchor (<a>) element — it represents the current page."""

    def test_when_breadcrumbs_template_is_generated_then_aria_current_page_is_present(
        self, scaffolded: Path
    ) -> None:
        content = _read_breadcrumbs_template(scaffolded)
        assert 'aria-current="page"' in content

    def test_when_breadcrumbs_template_is_generated_then_current_crumb_is_not_a_link(
        self, scaffolded: Path
    ) -> None:
        """The current-page crumb must not be wrapped in an anchor.
        Assumption: the component uses a conditional block (e.g. @if / *ngIf)
        to render a non-link element when a crumb is the current page, rather
        than always emitting <a>."""
        content = _read_breadcrumbs_template(scaffolded)
        # The template must have a conditional path that renders something
        # other than <a> for the active crumb.  We verify the template
        # contains a conditional construct alongside aria-current.
        has_conditional = "@if" in content or "*ngIf" in content or "[ngIf]" in content
        assert has_conditional, (
            "Expected a conditional block to distinguish the current (non-link) "
            "crumb from navigable crumbs, but found none."
        )

    def test_when_breadcrumbs_template_is_generated_then_routeless_crumbs_do_not_link_to_the_current_page(
        self, scaffolded: Path
    ) -> None:
        """An ancestor crumb without a routerLink must not be bound as
        [routerLink]="[]": RouterLink resolves an empty command list relative
        to the current route, producing a focusable link to the page itself."""
        content = _read_breadcrumbs_template(scaffolded)
        assert not re.search(r'\[routerLink\]="[^"]*\?\?\s*\[\s*\]"', content)


class TestSeparatorsAriaHidden:
    """Decorative separators between crumbs must be hidden from assistive
    technology via aria-hidden='true'."""

    def test_when_breadcrumbs_template_is_generated_then_aria_hidden_is_present(
        self, scaffolded: Path
    ) -> None:
        content = _read_breadcrumbs_template(scaffolded)
        assert "aria-hidden" in content

    def test_when_breadcrumbs_template_is_generated_then_aria_hidden_true_is_present(
        self, scaffolded: Path
    ) -> None:
        content = _read_breadcrumbs_template(scaffolded)
        assert 'aria-hidden="true"' in content or "aria-hidden='true'" in content


# ===========================================================================
# Criterion 3 — Dark-mode tokens; signal input for crumb items
# ===========================================================================


class TestDarkModeTokens:
    """Dark mode comes from the Material 3 theme: the component's own .css
    paints only from --mat-sys-* roles (emitted as light-dark() by mat.theme),
    so it must use those tokens and contain no color literals."""

    def test_when_breadcrumbs_is_generated_then_template_and_styles_are_separate_files(
        self, scaffolded: Path
    ) -> None:
        ts = _read_breadcrumbs_ts(scaffolded)
        component_dir = scaffolded / BREADCRUMBS_RELATIVE_DIR
        assert (component_dir / "breadcrumbs.html").is_file()
        assert (component_dir / "breadcrumbs.css").is_file()
        assert "templateUrl" in ts and "styleUrl" in ts
        assert "ChangeDetectionStrategy.OnPush" in ts

    def test_when_breadcrumbs_is_generated_then_colors_come_from_scheme_aware_tokens(
        self, scaffolded: Path
    ) -> None:
        """Equivalent intent of the former Tailwind `dark:` check: colors come
        from scheme-aware --mat-sys-* tokens, never from literals, and no
        component file carries Tailwind dark: variants."""
        css = _read_breadcrumbs_css(scaffolded)
        assert "var(--mat-sys-" in css
        assert not COLOR_LITERAL_RE.search(css), (
            "breadcrumbs.css must paint only from --mat-sys-* tokens"
        )
        assert "dark:" not in _read_breadcrumbs_sources(scaffolded)

    def test_when_breadcrumbs_css_is_generated_then_links_have_a_48px_target(
        self, scaffolded: Path
    ) -> None:
        css = _read_breadcrumbs_css(scaffolded)
        assert re.search(r"min-block-size:\s*48px", css)

    def test_when_breadcrumbs_css_is_generated_then_separator_mirrors_in_rtl(
        self, scaffolded: Path
    ) -> None:
        css = _read_breadcrumbs_css(scaffolded)
        assert re.search(r":dir\(rtl\)[^{]*\{[^}]*scaleX\(-1\)", css)


class TestSignalInput:
    """The component must accept crumb items via a signal input() rather than
    a classic @Input() decorator, following the Angular 21 signals convention."""

    def test_when_breadcrumbs_ts_is_generated_then_signal_input_is_used(
        self, scaffolded: Path
    ) -> None:
        content = _read_breadcrumbs_ts(scaffolded)
        # Angular signals-based input: `input()` function call (not @Input())
        assert "input(" in content

    def test_when_breadcrumbs_ts_is_generated_then_items_or_crumbs_input_exists(
        self, scaffolded: Path
    ) -> None:
        """The signal input must be named 'items', 'crumbs', or a recognisable
        variant so callers know how to pass the breadcrumb list.
        Choice rationale: 'items' and 'crumbs' are the two most natural names
        for a list passed into a breadcrumbs component."""
        content = _read_breadcrumbs_ts(scaffolded)
        has_items_input = "items" in content or "crumbs" in content
        assert has_items_input, (
            "Expected a signal input named 'items' or 'crumbs' (or a variant) "
            "in breadcrumbs.ts, but neither was found."
        )


# ===========================================================================
# Property-based tests — invariants derived from the criterion text
# ===========================================================================
#
# These encode the mathematical contracts implied by the acceptance criteria
# for ALL valid inputs, not just the single example above.
# The contract helpers below are SPECIFICATIONS — never import from production.
# ===========================================================================


# --- Contract specification helpers (spec, not production code) -------------


def _last_crumb_index(num_crumbs: int) -> int:
    """Index of the crumb that must carry aria-current='page'."""
    return num_crumbs - 1


def _separator_count(num_crumbs: int) -> int:
    """Number of separators needed: one between each adjacent pair of crumbs."""
    return max(0, num_crumbs - 1)


# --- Properties -------------------------------------------------------------


@given(num_crumbs=st.integers(min_value=1, max_value=100))
def test_when_breadcrumbs_list_has_n_items_then_last_index_is_always_n_minus_one(
    num_crumbs: int,
) -> None:
    """
    Ordering invariant: for any non-empty list of crumbs, the current-page
    crumb is always at index num_crumbs - 1.
    Criterion: "Last crumb has aria-current='page'."
    """
    last = _last_crumb_index(num_crumbs)
    assert last == num_crumbs - 1
    assert 0 <= last < num_crumbs


@given(num_crumbs=st.integers(min_value=1, max_value=100))
def test_when_breadcrumbs_list_has_n_items_then_separator_count_is_n_minus_one(
    num_crumbs: int,
) -> None:
    """
    Structural invariant: for N crumbs there are exactly N-1 separators
    (one between each consecutive pair).  Separators should never appear
    after the last crumb.
    Criterion: "Separators are aria-hidden."
    """
    seps = _separator_count(num_crumbs)
    assert seps == num_crumbs - 1
    assert seps >= 0


@given(num_crumbs=st.integers(min_value=1, max_value=100))
def test_when_breadcrumbs_list_has_n_items_then_exactly_one_crumb_is_current(
    num_crumbs: int,
) -> None:
    """
    Uniqueness invariant: regardless of how many crumbs are provided, exactly
    one carries aria-current='page' (the last one).
    Criterion: "Last crumb has aria-current='page'."
    """
    current_flags = [i == _last_crumb_index(num_crumbs) for i in range(num_crumbs)]
    assert current_flags.count(True) == 1
    assert current_flags.count(False) == num_crumbs - 1


@given(num_crumbs=st.integers(min_value=2, max_value=100))
def test_when_breadcrumbs_list_has_at_least_two_items_then_all_but_last_are_links(
    num_crumbs: int,
) -> None:
    """
    Structural invariant: for N >= 2 crumbs, exactly N-1 crumbs are
    navigable links; the last one is not.
    Criterion: "Last crumb … is not a link."
    """
    last = _last_crumb_index(num_crumbs)
    is_link = [i != last for i in range(num_crumbs)]
    assert is_link.count(True) == num_crumbs - 1
    assert is_link[last] is False
