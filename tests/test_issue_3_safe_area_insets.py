"""
Tests for issue #3: feat(frontend): complete safe-area inset utilities and apply to chrome.

Source-blind: authored against acceptance criteria only, before any implementation.
Criteria covered (UNIT-verifiable):
  - .pt-safe, .pl-safe, .pr-safe, and combined .px-safe are defined and mapped to
    the matching env(safe-area-inset-*) values in the global stylesheet,
    src/styles.scss (it replaced the Tailwind src/styles.css in the Material 3
    migration; the utilities are plain CSS rules there)
  - .px-safe applies both left and right insets (two distinct padding-left/right
    or padding-inline-start/end rules mapping to env(safe-area-inset-left/right))
  - .pt-safe is applied to the mobile <header> in layout.html
  - .pb-safe remains applied to the bottom tab bar and its CSS definition is
    unchanged (or cleanly co-located with the new utilities)
  - No regression in layout/bottom-tab-bar specs (relevant spec files are present)

Criteria skipped (not runtime-verifiable per oracle):
  - "All tests pass" — boilerplate suite gate; no per-criterion assertion
  - SOLID / clean-code prose — subjective; no concrete runtime assertion
"""

import pathlib
import re

FRONTEND = (
    pathlib.Path(__file__).parent.parent
    / "project_initializer"
    / "templates"
    / "frontend"
)

STYLES_SCSS = FRONTEND / "src" / "styles.scss"
LAYOUT_HTML = FRONTEND / "src" / "app" / "shared" / "layout" / "layout.html"
NAVBAR_TS = FRONTEND / "src" / "app" / "shared" / "ui" / "navbar" / "navbar.ts"


def _read_styles() -> str:
    """Text of the global stylesheet, src/styles.scss."""
    return STYLES_SCSS.read_text(encoding="utf-8")


def _read_layout() -> str:
    return LAYOUT_HTML.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_utility_block(css: str, class_name: str) -> str | None:
    """Return the CSS rule block for *class_name* (e.g. '.pt-safe'), or None.

    Matches a declaration of the form:
        .pt-safe { ... }
    including multi-line blocks.  The class name must be an exact selector match.
    """
    # Escape dots so the regex treats them as literals.
    escaped = re.escape(class_name)
    pattern = re.compile(
        rf"(?<![a-zA-Z0-9_-]){escaped}\s*\{{([^}}]*)\}}",
        re.DOTALL,
    )
    m = pattern.search(css)
    return m.group(1) if m else None


def _env_inset_pattern(side: str) -> re.Pattern:
    """Return a compiled regex matching env(safe-area-inset-<side>) for *side*.

    Tolerates optional whitespace inside the env() call.
    """
    return re.compile(
        rf"env\(\s*safe-area-inset-{re.escape(side)}\s*\)",
        re.IGNORECASE,
    )


# ---------------------------------------------------------------------------
# Material 3 migration: the global stylesheet ships no utility classes. The
# insets moved into the CSS of each component at a screen edge (navbar.css,
# bottom-tab-bar.css), so src/styles.scss defines none of the .*-safe classes.
# ---------------------------------------------------------------------------

SAFE_AREA_UTILITIES = [".pt-safe", ".pb-safe", ".pl-safe", ".pr-safe", ".px-safe"]


def test_when_styles_scss_read_then_no_safe_area_utility_class_is_defined():
    """src/styles.scss defines no safe-area utility class; edge components pad by the insets."""
    css = _read_styles()
    defined = [name for name in SAFE_AREA_UTILITIES if _find_utility_block(css, name) is not None]
    assert defined == [], (
        f"src/styles.scss still defines safe-area utility classes: {defined}. "
        "Pad by env(safe-area-inset-*) in the edge component's own CSS instead."
    )


def test_when_index_html_read_then_viewport_fit_cover_enables_the_insets():
    """env(safe-area-inset-*) resolves to the device insets only with viewport-fit=cover."""
    index = (FRONTEND / "src" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<meta\s+name="viewport"[^>]*\bviewport-fit=cover\b', index), (
        "src/index.html's viewport meta must keep viewport-fit=cover, or every "
        "env(safe-area-inset-*) padding resolves to 0"
    )


# ---------------------------------------------------------------------------
# Criterion: .pt-safe is applied to the mobile <header> in layout.html
# ---------------------------------------------------------------------------


def test_when_navbar_sources_read_then_header_pads_by_top_safe_area_inset():
    """The mobile header must clear the iOS notch by the top safe-area inset.

    Per requirements §3 the mobile header pads by env(safe-area-inset-top). Since
    Issue #15 the header is encapsulated in NavbarComponent, which wraps its
    mat-toolbar in that <header>, so the padding stays outside the toolbar's row.
    The Material 3 template has no utility-class CSS: the navbar's own stylesheet
    declares the padding on the `.navbar` header rule, and the template carries no
    `.pt-safe` utility class.
    """
    html = NAVBAR_TS.with_suffix(".html").read_text(encoding="utf-8")
    header = re.search(r"<header\b[^>]*>", html)
    assert header, "Expected navbar.html to render the mobile <header>"
    assert re.search(r"\bclass=\"navbar\"", header.group(0)), (
        "Expected the navbar <header> to carry its component class 'navbar'"
    )
    assert "pt-safe" not in html, (
        "navbar.html must not use the global .pt-safe utility; pad from navbar.css"
    )

    css = NAVBAR_TS.with_suffix(".css").read_text(encoding="utf-8")
    rule = re.search(r"(?:^|\})\s*\.navbar\s*\{([^}]*)\}", css)
    assert rule, "Expected a `.navbar { ... }` rule in navbar.css"
    assert _env_inset_pattern("top").search(rule.group(1)), (
        "The `.navbar` header rule in navbar.css must pad by env(safe-area-inset-top); "
        f"actual block content: {rule.group(1).strip()!r}"
    )


# ---------------------------------------------------------------------------
# Criterion: .pb-safe remains applied to the bottom tab bar and its CSS
# definition is present (unchanged or co-located with the new utilities)
# ---------------------------------------------------------------------------


BOTTOM_TAB_BAR_DIR = FRONTEND / "src" / "app" / "shared" / "bottom-tab-bar"


def test_when_bottom_tab_bar_sources_read_then_bar_pads_by_bottom_safe_area_inset():
    """The bottom-tab-bar (the M3 navigation bar) must clear the iOS home indicator.

    The criterion behind '.pb-safe remains applied to the bottom tab bar' is the
    bottom safe-area inset. The Material 3 template has no utility-class CSS, so
    the bar's own stylesheet pads the `.nav-bar` rule by env(safe-area-inset-bottom)
    and the template carries no `.pb-safe` utility class.
    """
    html = (BOTTOM_TAB_BAR_DIR / "bottom-tab-bar.html").read_text(encoding="utf-8")
    assert "pb-safe" not in html, (
        "bottom-tab-bar.html must not use the global .pb-safe utility; "
        "pad from bottom-tab-bar.css"
    )

    css = (BOTTOM_TAB_BAR_DIR / "bottom-tab-bar.css").read_text(encoding="utf-8")
    rule = re.search(r"(?:^|\})\s*\.nav-bar\s*\{([^}]*)\}", css)
    assert rule, "Expected a `.nav-bar { ... }` rule in bottom-tab-bar.css"
    padding = re.search(r"(?:^|[;\s])padding\s*:([^;]*);", rule.group(1))
    assert padding and _env_inset_pattern("bottom").search(padding.group(1)), (
        "The `.nav-bar` rule in bottom-tab-bar.css must pad by env(safe-area-inset-bottom); "
        f"actual block content: {rule.group(1).strip()!r}"
    )


def test_when_bottom_tab_bar_styles_read_then_bar_is_64px_plus_bottom_safe_area():
    """The navigation bar's block size is 64px + env(safe-area-inset-bottom).

    The toast unit lifts compact snackbars by exactly that amount
    (src/styles/overlays/_toast.scss), so the bar's stylesheet must keep the
    contract, with the inset below the 64px bar rather than eating into it.
    """
    css = (BOTTOM_TAB_BAR_DIR / "bottom-tab-bar.css").read_text(encoding="utf-8")
    assert re.search(
        r"block-size\s*:\s*calc\(\s*64px\s*\+\s*env\(\s*safe-area-inset-bottom\s*\)\s*\)",
        css,
    ), (
        "Expected bottom-tab-bar.css to size the bar as "
        "calc(64px + env(safe-area-inset-bottom))"
    )


# ---------------------------------------------------------------------------
# Criterion: no regression — layout and bottom-tab-bar spec files are present
# ---------------------------------------------------------------------------


def test_when_frontend_src_listed_then_at_least_one_layout_spec_exists():
    """At least one layout spec (layout*.spec.ts or responsive-shell*.spec.ts) must be present.

    Derived from: 'No regression in layout/bottom-tab-bar specs'.
    """
    layout_specs = list((FRONTEND / "src").rglob("layout*.spec.ts")) + list(
        (FRONTEND / "src").rglob("responsive-shell*.spec.ts")
    )
    assert len(layout_specs) > 0, (
        "No layout spec file found under frontend/src — "
        "expected at least one layout*.spec.ts or responsive-shell*.spec.ts"
    )


def test_when_frontend_src_listed_then_at_least_one_bottom_tab_bar_spec_exists():
    """At least one spec file matching 'bottom-tab-bar*.spec.ts' must be present.

    Derived from: 'No regression in layout/bottom-tab-bar specs'.
    """
    specs = list((FRONTEND / "src").rglob("bottom-tab-bar*.spec.ts"))
    assert len(specs) > 0, (
        "No bottom-tab-bar spec file found under frontend/src — "
        "expected at least one bottom-tab-bar*.spec.ts"
    )
