"""
Tests for issue #4: feat(frontend): add scroll primitives and touch-action to the CSS foundation.

Source-blind: authored against acceptance criteria only, before any implementation.
Criteria covered (UNIT-verifiable):
  - touch-action: manipulation is applied to interactive elements (and/or globally
    in @layer base) so double-tap zoom and the ~300ms delay are removed
  - Pinch-to-zoom is preserved: the index.html viewport meta stays scalable with
    no user-scalable=no / maximum-scale=1
  - overscroll-contain, touch-action, and scroll-snap primitives are
    available/applied for scrollable/carousel regions
  - An inline comment documents the h-dvh/h-svh/h-lvh trade-offs against
    layout.html usage

Criteria skipped (not runtime-verifiable per oracle):
  - "ng build and ng test are green with no regressions" — no concrete runtime check
  - "All tests pass" — boilerplate suite gate; no per-criterion assertion
  - SOLID / clean-code prose — subjective; no concrete runtime assertion

No Hypothesis property-based tests: none of the verifiable criteria imply a
parametric invariant (all assertions target static template files with no
input domain to vary over).
"""

import pathlib
import re

FRONTEND = (
    pathlib.Path(__file__).parent.parent
    / "project_initializer"
    / "templates"
    / "frontend"
)

STYLES_CSS = FRONTEND / "src" / "styles.css"
LAYOUT_HTML = FRONTEND / "src" / "app" / "shared" / "layout" / "layout.html"
INDEX_HTML = FRONTEND / "src" / "index.html"


def _read_styles() -> str:
    return STYLES_CSS.read_text(encoding="utf-8")


def _read_layout() -> str:
    return LAYOUT_HTML.read_text(encoding="utf-8")


def _read_index() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Criterion: touch-action: manipulation applied to interactive elements /
#            globally in @layer base
# ---------------------------------------------------------------------------


def test_when_styles_css_read_then_touch_action_manipulation_is_declared():
    """styles.css must declare touch-action: manipulation.

    Per criterion: 'touch-action: manipulation is applied to interactive elements
    (and/or globally in @layer base) so double-tap zoom and the ~300ms delay are
    removed.'  The presence of the declaration is the minimum verifiable check.
    """
    css = _read_styles()
    assert "touch-action: manipulation" in css, (
        "Expected 'touch-action: manipulation' to be declared in src/styles.css"
    )


def test_when_touch_action_manipulation_found_then_it_targets_interactive_or_base_layer_context():
    """touch-action: manipulation must target interactive elements or @layer base.

    Per criterion: applied 'to interactive elements (and/or globally in @layer base)'.
    We inspect a 500-character window before the declaration for at least one
    interactive-element indicator or the @layer base keyword, ruling out it being
    applied exclusively to generic layout containers.

    Interpretation: the window must contain one of:
      @layer base, button, "a,", [role, input, select, textarea, summary.
    """
    css = _read_styles()
    pos = css.find("touch-action: manipulation")
    assert pos != -1, "touch-action: manipulation not found — checked by prior test"
    window = css[max(0, pos - 500) : pos + 50]
    interactive_indicators = [
        "@layer base",
        "button",
        "a,",
        "[role",
        "input",
        "select",
        "textarea",
        "summary",
    ]
    assert any(ind in window for ind in interactive_indicators), (
        "touch-action: manipulation must be inside @layer base or within a selector "
        "that targets interactive elements (button, a, input, select, textarea, "
        "[role], summary). "
        f"Context window: {window!r}"
    )


# ---------------------------------------------------------------------------
# Criterion: pinch-to-zoom preserved — viewport meta stays scalable
# ---------------------------------------------------------------------------


def test_when_index_html_read_then_viewport_meta_does_not_contain_user_scalable_no():
    """The viewport <meta> in index.html must NOT include user-scalable=no.

    Per criterion: 'Pinch-to-zoom is preserved: the index.html viewport meta stays
    scalable with no user-scalable=no / maximum-scale=1.'  user-scalable=no entirely
    disables pinch-to-zoom and is a WCAG 1.4.4 failure on iOS Safari.
    """
    html = _read_index()
    viewport_match = re.search(
        r'<meta\b[^>]*name=["\']viewport["\'][^>]*>',
        html,
        re.IGNORECASE,
    )
    assert viewport_match is not None, (
        "No <meta name='viewport'> tag found in index.html"
    )
    meta_text = viewport_match.group(0)
    assert "user-scalable=no" not in meta_text, (
        f"The viewport meta must not contain 'user-scalable=no'; found: {meta_text!r}"
    )


def test_when_index_html_read_then_viewport_meta_does_not_contain_maximum_scale_1():
    """The viewport <meta> in index.html must NOT include maximum-scale=1.

    Per criterion: 'no user-scalable=no / maximum-scale=1.'  maximum-scale=1 (or
    maximum-scale=1.0) silently prevents scaling on iOS Safari and is a WCAG 1.4.4
    failure.  Values > 1 (e.g., maximum-scale=5) are acceptable.
    """
    html = _read_index()
    viewport_match = re.search(
        r'<meta\b[^>]*name=["\']viewport["\'][^>]*>',
        html,
        re.IGNORECASE,
    )
    assert viewport_match is not None, (
        "No <meta name='viewport'> tag found in index.html"
    )
    meta_text = viewport_match.group(0)
    assert not re.search(r"maximum-scale\s*=\s*1(?:\.0+)?(?!\d)", meta_text), (
        "The viewport meta must not contain 'maximum-scale=1' (or 1.0); "
        f"found: {meta_text!r}"
    )


# ---------------------------------------------------------------------------
# Criterion: overscroll-contain, touch-action, and scroll-snap primitives
#            available/applied for scrollable/carousel regions
# ---------------------------------------------------------------------------


def test_when_styles_css_or_layout_html_read_then_overscroll_contain_is_present():
    """overscroll-contain (overscroll-behavior: contain) must be available or applied.

    Per criterion: 'overscroll-contain ... primitives are available/applied for
    scrollable/carousel regions.'  Satisfied if styles.css declares the CSS property
    or layout.html applies the Tailwind utility class 'overscroll-contain'.
    """
    css = _read_styles()
    html = _read_layout()
    has_in_css = "overscroll-behavior" in css or "overscroll-contain" in css
    has_in_html = "overscroll-contain" in html
    assert has_in_css or has_in_html, (
        "Expected 'overscroll-behavior' (CSS property) or 'overscroll-contain' "
        "(Tailwind utility) to appear in src/styles.css or layout.html"
    )


def test_when_styles_css_or_layout_html_read_then_scroll_snap_primitive_is_present():
    """scroll-snap primitives must be available/applied for carousel/scroll regions.

    Per criterion: 'scroll-snap primitives are available/applied for
    scrollable/carousel regions.'  Satisfied if styles.css defines any
    scroll-snap-* CSS property, or layout.html applies snap-* Tailwind utilities.
    """
    css = _read_styles()
    html = _read_layout()
    has_in_css = "scroll-snap" in css
    has_in_html = bool(re.search(r"\bsnap-[a-z]", html))
    assert has_in_css or has_in_html, (
        "Expected 'scroll-snap' (scroll-snap-type / scroll-snap-align) in "
        "src/styles.css, or a 'snap-*' utility class in layout.html"
    )


def test_when_styles_css_or_layout_html_read_then_touch_action_primitive_is_present():
    """A touch-action declaration must be present for scrollable regions.

    Per criterion: 'touch-action ... primitives are available/applied for
    scrollable/carousel regions.'  Any touch-action declaration in styles.css or
    any touch-action-* class in layout.html satisfies this requirement.
    """
    css = _read_styles()
    html = _read_layout()
    has_in_css = "touch-action" in css
    has_in_html = bool(re.search(r"\btouch-action-[a-z]|touch-action:", html))
    assert has_in_css or has_in_html, (
        "Expected a 'touch-action' declaration in src/styles.css or a "
        "touch-action-* utility in layout.html for scrollable/carousel regions"
    )


# ---------------------------------------------------------------------------
# Criterion: inline comment documents h-dvh / h-svh / h-lvh trade-offs
# ---------------------------------------------------------------------------


def test_when_styles_css_or_layout_html_read_then_a_comment_documents_dvh_svh_lvh_tradeoffs():
    """A single comment must mention all three of dvh, svh, and lvh together.

    Per criterion: 'An inline comment documents the h-dvh/h-svh/h-lvh trade-offs
    against layout.html usage.'  We require that at least one CSS block comment
    (/* ... */), CSS line comment (// ...), or HTML comment (<!-- ... -->) in
    styles.css or layout.html contains all three viewport-height unit names —
    establishing that the trade-offs are explicitly documented, not merely that
    one unit happens to be used as a class.
    """
    css = _read_styles()
    html = _read_layout()

    css_block_comments = re.findall(r"/\*.*?\*/", css, re.DOTALL)
    css_line_comments = re.findall(r"//[^\n]*", css)
    html_comments = re.findall(r"<!--.*?-->", html, re.DOTALL)

    all_comments = css_block_comments + css_line_comments + html_comments

    def mentions_all_three(text: str) -> bool:
        return "dvh" in text and "svh" in text and "lvh" in text

    assert any(mentions_all_three(c) for c in all_comments), (
        "Expected at least one comment in src/styles.css or layout.html that "
        "mentions all three viewport height units (dvh, svh, lvh) — "
        "documenting the h-dvh/h-svh/h-lvh trade-offs per requirements §4."
    )
