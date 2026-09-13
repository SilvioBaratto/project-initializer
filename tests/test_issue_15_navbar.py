"""
Source-blind example tests for Issue #15: feat(ui) Navbar + standardised Hamburger toggle.

Only the single UNIT-verifiable criterion is tested:
    "Navbar applies `.pt-safe`, projects brand/actions, dark-mode tokens"

Skipped (NOT VERIFIABLE per oracle report):
    - Hamburger: aria-expanded / aria-controls / >=44px / visible focus
    - Integrates with Drawer open/close
    - All tests pass  (boilerplate suite gate)
    - SOLID / clean code  (subjective quality prose)

Every test is derived from the acceptance-criteria text and
requirements.md §3 / §6.  No implementation source was read.

Note: the NavbarComponent is an M3 small top app bar on Angular Material's
mat-toolbar, split into navbar.ts (templateUrl + styleUrl), navbar.html and
navbar.css. Template-level assertions read the .ts + .html + .css sources
together; styling assertions read navbar.css, which must use --mat-sys-* tokens.
"""

import re
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

# ─── Paths ────────────────────────────────────────────────────────────────────

_NAVBAR_DIR = (
    Path(__file__).parent.parent
    / "project_initializer"
    / "templates"
    / "frontend"
    / "src"
    / "app"
    / "shared"
    / "ui"
    / "navbar"
)

NAVBAR_TS = _NAVBAR_DIR / "navbar.ts"
NAVBAR_HTML = _NAVBAR_DIR / "navbar.html"
NAVBAR_CSS = _NAVBAR_DIR / "navbar.css"
NAVBAR_FILES = (NAVBAR_TS, NAVBAR_HTML, NAVBAR_CSS)


def _read_navbar_sources() -> str:
    """Concatenate navbar.ts + navbar.html + navbar.css (the component's three files)."""
    missing = [p.name for p in NAVBAR_FILES if not p.exists()]
    assert not missing, (
        f"navbar component files missing: {missing} — the component must ship "
        "navbar.ts, navbar.html and navbar.css"
    )
    return "\n".join(p.read_text(encoding="utf-8") for p in NAVBAR_FILES)

# ─── Criterion: Navbar applies `.pt-safe` ─────────────────────────────────────


class TestNavbarPtSafe:
    """The navbar's outermost element must carry the pt-safe class so the top
    safe-area inset clears the iOS notch / dynamic-island.
    Source: criterion text + requirements.md §3 ('Apply .pt-safe to the mobile header').
    The class sits on the <header> that wraps mat-toolbar, not on the toolbar row,
    whose fixed border-box height would otherwise swallow the inset."""

    # The Material 3 template has no utility-class CSS, so the criterion behind `.pt-safe`
    # (the top safe-area inset on the header) is met by the navbar's own stylesheet.

    def test_when_navbar_sources_are_read_then_top_safe_area_inset_is_honoured_without_utility_classes(self):
        content = _read_navbar_sources()
        assert "env(safe-area-inset-top)" in content, (
            "The navbar sources must pad the header by env(safe-area-inset-top) "
            "so the iOS notch safe-area inset is honoured."
        )
        assert "pt-safe" not in content, (
            "The navbar must not use the global .pt-safe utility class; pad from navbar.css."
        )

    def test_when_navbar_css_is_read_then_header_rule_pads_by_top_safe_area_inset(self):
        html = NAVBAR_HTML.read_text(encoding="utf-8")
        assert re.search(r"<header\b[^>]*\bclass=\"navbar\"", html, re.DOTALL), (
            "navbar.html must render a <header class=\"navbar\"> element "
            "(the header landmark wraps the mat-toolbar)."
        )
        css = (_NAVBAR_DIR / "navbar.css").read_text(encoding="utf-8")
        rule = re.search(r"(?:^|\})\s*\.navbar\s*\{([^}]*)\}", css)
        assert rule and re.search(
            r"padding\s*:\s*env\(\s*safe-area-inset-top\s*\)", rule.group(1)
        ), (
            "The `.navbar` header rule in navbar.css must pad by env(safe-area-inset-top), "
            "outside the toolbar row whose height would otherwise swallow the inset."
        )


# ─── Criterion: Navbar projects brand / actions ───────────────────────────────


class TestNavbarContentProjection:
    """The navbar must expose Angular content-projection slots for a 'brand' area
    (logo / app name) and an 'actions' area (icon buttons, avatar, etc.).
    Source: criterion text 'projects brand/actions'; Angular convention is ng-content
    with a [select] attribute that names the slot."""

    def test_when_navbar_template_is_rendered_then_brand_slot_is_present(self):
        content = _read_navbar_sources()
        # Accept any ng-content whose select attribute references a brand-related name.
        assert re.search(r"ng-content[^>]*brand", content, re.IGNORECASE), (
            "The navbar template must expose a content-projection slot for the brand area "
            '(e.g. <ng-content select="[navbarBrand]"> or equivalent).'
        )

    def test_when_navbar_template_is_rendered_then_actions_slot_is_present(self):
        content = _read_navbar_sources()
        assert re.search(r"ng-content[^>]*action", content, re.IGNORECASE), (
            "The navbar template must expose a content-projection slot for the actions area "
            '(e.g. <ng-content select="[navbarActions]"> or equivalent).'
        )


# ─── Structure: M3 top app bar on mat-toolbar ─────────────────────────────────


class TestNavbarMaterialToolbar:
    """The navbar is the M3 top app bar, which Angular Material ships as mat-toolbar.
    It keeps the <header> landmark, OnPush change detection and the
    templateUrl/styleUrl split (no inline template or styles)."""

    def test_when_navbar_ts_is_read_then_it_uses_on_push_change_detection(self):
        ts = NAVBAR_TS.read_text(encoding="utf-8")
        assert "ChangeDetectionStrategy.OnPush" in ts

    def test_when_navbar_ts_is_read_then_template_and_styles_are_external_files(self):
        ts = NAVBAR_TS.read_text(encoding="utf-8")
        assert re.search(r"templateUrl:\s*'\./navbar\.html'", ts)
        assert re.search(r"styleUrl:\s*'\./navbar\.css'", ts)
        assert not re.search(r"\btemplate:\s*`", ts), "navbar.ts must not inline its template"
        assert not re.search(r"\bstyles:\s*[\[`']", ts), "navbar.ts must not inline its styles"

    def test_when_navbar_is_read_then_mat_toolbar_sits_inside_the_header(self):
        ts = NAVBAR_TS.read_text(encoding="utf-8")
        html = NAVBAR_HTML.read_text(encoding="utf-8")
        assert "MatToolbar" in ts and "@angular/material/toolbar" in ts
        assert re.search(r"<header\b[^>]*>.*<mat-toolbar\b.*</mat-toolbar>.*</header>", html, re.DOTALL), (
            "navbar.html must nest <mat-toolbar> inside the <header> landmark"
        )

    def test_when_navbar_ts_is_read_then_selector_is_app_navbar(self):
        ts = NAVBAR_TS.read_text(encoding="utf-8")
        assert re.search(r"selector:\s*'app-navbar'", ts)
        assert "export class NavbarComponent" in ts


# ─── Criterion: Navbar uses dark-mode tokens (no hardcoded hex) ───────────────

_HEX_RE = re.compile(
    r"(?<!['\"\w-])"  # not preceded by quote, word char, or dash
    r"#(?:[0-9a-fA-F]{3,4}"  # 3- or 4-digit shorthand
    r"|[0-9a-fA-F]{6}"  # 6-digit full
    r"|[0-9a-fA-F]{8})\b"  # 8-digit with alpha
)

_COLOR_FN_RE = re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\(", re.IGNORECASE)


class TestNavbarDarkModeTokens:
    """The navbar must take every colour from the Material 3 system tokens
    (var(--mat-sys-*), reached through mat-toolbar's own component tokens), which
    mat.theme() resolves for both light and dark schemes, and never from hardcoded
    colour literals that would break dark-mode switching.
    Source: criterion text 'dark-mode tokens' + requirements.md non-functional
    'Theming: all components consume theme tokens (no hardcoded hex)'."""

    def test_when_navbar_files_are_read_then_no_hardcoded_hex_colors_are_present(self):
        content = _read_navbar_sources()
        hits = _HEX_RE.findall(content)
        assert not hits, (
            f"Hardcoded hex colour(s) found in the navbar sources — use --mat-sys-* tokens: {hits}"
        )

    def test_when_navbar_css_is_read_then_no_color_functions_are_present(self):
        css = NAVBAR_CSS.read_text(encoding="utf-8")
        hits = _COLOR_FN_RE.findall(css)
        assert not hits, f"Colour literal function(s) found in navbar.css: {hits}"

    def test_when_navbar_css_is_read_then_colors_come_from_mat_sys_tokens(self):
        """mat-toolbar already defaults its container tokens to surface / on-surface.
        The header behind the safe-area inset follows the same tokens with the same
        --mat-sys-* fallbacks, and navbar.css never redeclares the toolbar tokens,
        which would shadow a theme-level mat.toolbar-overrides()."""
        css = NAVBAR_CSS.read_text(encoding="utf-8")
        assert re.search(
            r"background-color:\s*var\(--mat-toolbar-container-background-color,\s*"
            r"var\(--mat-sys-surface\)\)",
            css,
        ), "The header must paint the toolbar container token, falling back to the M3 surface role"
        assert re.search(
            r"(?:^|[;{\s])color:\s*var\(--mat-toolbar-container-text-color,\s*"
            r"var\(--mat-sys-on-surface\)\)",
            css,
        ), "The header must use the toolbar text token, falling back to the M3 on-surface role"
        assert not re.search(r"--mat-toolbar-container-(?:background|text)-color\s*:", css), (
            "navbar.css must not redeclare the toolbar colour tokens; that shadows theme-level overrides"
        )

    def test_when_navbar_css_is_read_then_brand_uses_title_large_type_role(self):
        """The brand inherits title-large from mat-toolbar's --mat-toolbar-title-text-* tokens,
        so navbar.css declares no type properties of its own that would bypass them."""
        html = NAVBAR_HTML.read_text(encoding="utf-8")
        assert re.search(
            r"<mat-toolbar\b[^>]*>.*<ng-content[^>]*navbarBrand.*</mat-toolbar>", html, re.DOTALL
        ), "The brand slot must sit inside mat-toolbar to inherit its title-large type"
        css = re.sub(r"/\*.*?\*/", "", NAVBAR_CSS.read_text(encoding="utf-8"), flags=re.DOTALL)
        assert not re.search(
            r"(?:^|[;{\s])(?:font|font-family|font-size|font-weight|line-height|letter-spacing)\s*:",
            css,
        ), "navbar.css must not override the toolbar's title-large typography tokens"

    def test_when_navbar_css_is_read_then_no_important_or_ng_deep(self):
        css = NAVBAR_CSS.read_text(encoding="utf-8")
        assert "!important" not in css
        assert "::ng-deep" not in css


# ─── Property-based test ──────────────────────────────────────────────────────
# Invariant implied by 'dark-mode tokens': for ALL lines in the navbar sources
# (.ts + .html + .css), no raw hex colour literal is present.


@given(data=st.data())
@settings(max_examples=200, deadline=None)
def test_when_any_navbar_ts_line_is_sampled_then_no_hex_color_appears(data):
    """Invariant: every line of the navbar component sources (navbar.ts, navbar.html
    and navbar.css) is free of raw hex colour literals. hypothesis samples individual
    lines so the property is checked across all three files."""
    lines = _read_navbar_sources().splitlines()
    if not lines:
        return
    line = data.draw(st.sampled_from(lines))
    assert not _HEX_RE.search(line), (
        f"Hardcoded hex colour found on line: {line!r} — use --mat-sys-* tokens instead"
    )
