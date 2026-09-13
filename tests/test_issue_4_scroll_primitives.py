"""
Tests for issue #4: feat(frontend): add scroll primitives and touch-action to the CSS foundation.

Source-blind: authored against acceptance criteria only, before any implementation.
Criteria covered (UNIT-verifiable):
  - touch-action: manipulation is applied to interactive elements in the global
    stylesheet (src/styles.scss since the Material 3 migration) so double-tap
    zoom and the ~300ms delay are removed
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

# The global stylesheet is src/styles.scss since the Material 3 migration. The
# Tailwind src/styles.css is gone and no reader here falls back to it.
STYLES_SCSS = FRONTEND / "src" / "styles.scss"
LAYOUT_HTML = FRONTEND / "src" / "app" / "shared" / "layout" / "layout.html"
INDEX_HTML = FRONTEND / "src" / "index.html"


def _read_styles() -> str:
    """Text of the global stylesheet, src/styles.scss."""
    return STYLES_SCSS.read_text(encoding="utf-8")


def _strip_comments(css: str) -> str:
    """Remove /* block */ and // line comments (SCSS) from *css*."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    return re.sub(r"(?<!:)//[^\n]*", "", css)


def _selector_of_rule_at(css: str, pos: int) -> str:
    """Return the selector of the rule whose body contains offset *pos*."""
    open_brace = css.rfind("{", 0, pos)
    prelude_start = max(css.rfind("}", 0, open_brace), css.rfind(";", 0, open_brace)) + 1
    return _strip_comments(css[prelude_start:open_brace]).strip()


def _read_layout() -> str:
    return LAYOUT_HTML.read_text(encoding="utf-8")


def _read_index() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Criterion: touch-action: manipulation applied to interactive elements in the
#            global stylesheet
# ---------------------------------------------------------------------------


def test_when_styles_css_read_then_touch_action_manipulation_is_declared():
    """src/styles.scss must declare touch-action: manipulation.

    Per criterion: 'touch-action: manipulation is applied to interactive elements
    so double-tap zoom and the ~300ms delay are removed.'  The presence of the
    declaration is the minimum verifiable check.
    """
    css = _read_styles()
    assert re.search(r"touch-action\s*:\s*manipulation", css), (
        "Expected 'touch-action: manipulation' to be declared in src/styles.scss"
    )


def test_when_touch_action_manipulation_found_then_it_targets_interactive_or_base_layer_context():
    """touch-action: manipulation must sit on a rule that targets interactive elements.

    Per criterion: applied 'to interactive elements'. The Tailwind-era check also
    accepted `@layer base` and scanned a 500-character window; the global
    stylesheet is plain SCSS now, so the check reads the selector list of the rule
    that holds the declaration, which must name at least one of:
      a, button, [role=...], input, select, textarea, summary, label.
    """
    css = _read_styles()
    match = re.search(r"touch-action\s*:\s*manipulation", css)
    assert match is not None, "touch-action: manipulation not found — checked by prior test"
    selector = _selector_of_rule_at(css, match.start())
    interactive = re.compile(r"^(a|button|input|select|textarea|summary|label)\b|^\[role\b")
    assert any(interactive.match(part.strip()) for part in selector.split(",")), (
        "touch-action: manipulation must sit in a rule whose selector targets "
        "interactive elements (a, button, [role], input, select, textarea, summary, "
        f"label). Selector found: {selector!r}"
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


# Since the Material 3 migration the shell carries no utility classes: these
# primitives are CSS properties in the global stylesheet (src/styles.scss, which
# replaced styles.css) or in the layout component's own sources
# (layout.ts + layout.html + layout.css).

LAYOUT_DIR = LAYOUT_HTML.parent


def _read_global_styles() -> str:
    """Text of the global stylesheet, src/styles.scss (a missing file fails loudly)."""
    return _read_styles()


def _read_layout_sources() -> dict[str, str]:
    """The shell component's own sources, keyed by extension (.ts, .html, .css)."""
    return {
        ext: (LAYOUT_DIR / f"layout{ext}").read_text(encoding="utf-8")
        for ext in (".ts", ".html", ".css")
        if (LAYOUT_DIR / f"layout{ext}").exists()
    }


def test_when_styles_css_or_layout_html_read_then_overscroll_contain_is_present():
    """overscroll-behavior: contain must be available or applied.

    Per criterion: 'overscroll-contain ... primitives are available/applied for
    scrollable/carousel regions.'  The Tailwind 'overscroll-contain' utility is
    gone, so the property itself must be declared: in layout.css on the shell's
    <main> scroll container, or in the global stylesheet.
    """
    layout_css = _read_layout_sources().get(".css", "")
    declaration = re.compile(r"overscroll-behavior(?:-[a-z]+)?\s*:\s*contain")
    assert declaration.search(layout_css) or declaration.search(_read_global_styles()), (
        "Expected an 'overscroll-behavior: contain' declaration in layout.css "
        "(the shell's scroll container) or in src/styles.scss"
    )


def test_when_styles_css_or_layout_html_read_then_scroll_snap_primitive_is_present():
    """scroll-snap primitives must be available/applied for carousel/scroll regions.

    Per criterion: 'scroll-snap primitives are available/applied for
    scrollable/carousel regions.'  Satisfied if the global stylesheet or the
    layout sources (.ts/.html/.css) mention a scroll-snap-* CSS property; the
    Tailwind snap-* utilities no longer exist.
    """
    sources = _read_global_styles() + "\n".join(_read_layout_sources().values())
    assert "scroll-snap" in sources, (
        "Expected 'scroll-snap' (scroll-snap-type / scroll-snap-align) in "
        "src/styles.scss or the layout component sources"
    )


def test_when_styles_css_or_layout_html_read_then_touch_action_primitive_is_present():
    """A touch-action declaration must be present for scrollable regions.

    Per criterion: 'touch-action ... primitives are available/applied for
    scrollable/carousel regions.'  Any touch-action declaration in the global
    stylesheet or the layout component's CSS satisfies this requirement.
    """
    sources = _read_global_styles() + _read_layout_sources().get(".css", "")
    assert re.search(r"touch-action\s*:", sources), (
        "Expected a 'touch-action' declaration in src/styles.scss or layout.css "
        "for scrollable/carousel regions"
    )


# ---------------------------------------------------------------------------
# Criterion: inline comment documents h-dvh / h-svh / h-lvh trade-offs
# ---------------------------------------------------------------------------


def test_when_styles_css_or_layout_html_read_then_a_comment_documents_dvh_svh_lvh_tradeoffs():
    """A single comment must mention all three of dvh, svh, and lvh together.

    Per criterion: 'An inline comment documents the h-dvh/h-svh/h-lvh trade-offs
    against layout.html usage.'  We require that at least one CSS block comment
    (/* ... */), CSS/SCSS line comment (// ...), or HTML comment (<!-- ... -->) in
    the global stylesheet or the layout component sources (.ts/.html/.css)
    contains all three viewport-height unit names — establishing that the
    trade-offs are explicitly documented, not merely that one unit is used.
    """
    layout = _read_layout_sources()
    css = _read_global_styles() + layout.get(".css", "") + layout.get(".ts", "")
    html = layout.get(".html", "")

    css_block_comments = re.findall(r"/\*.*?\*/", css, re.DOTALL)
    css_line_comments = re.findall(r"//[^\n]*", css)
    html_comments = re.findall(r"<!--.*?-->", html, re.DOTALL)

    all_comments = css_block_comments + css_line_comments + html_comments

    def mentions_all_three(text: str) -> bool:
        return "dvh" in text and "svh" in text and "lvh" in text

    assert any(mentions_all_three(c) for c in all_comments), (
        "Expected at least one comment in src/styles.scss or the layout sources that "
        "mentions all three viewport height units (dvh, svh, lvh) — "
        "documenting the h-dvh/h-svh/h-lvh trade-offs per requirements §4."
    )
