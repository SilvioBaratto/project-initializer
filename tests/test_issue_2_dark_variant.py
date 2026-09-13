"""
Tests for issue #2: dark mode driven by the ThemeService class on <html>.

History: issue #2 wired Tailwind's `dark:` variant to the `.dark` class with
`@custom-variant`. The Material 3 migration replaced Tailwind: `mat.theme()` in
src/styles.scss emits every `--mat-sys-*` token as `light-dark()`, and the CSS
`color-scheme` property picks the side. These tests keep the original intent on
that mechanism:
  - src/styles.scss sets `color-scheme: light dark` on `html` and includes
    `mat.theme(...)` there, so every token follows the OS by default
  - `.dark` and `.light` are bare class rules that each set `color-scheme`, so the
    class ThemeService puts on <html> pins the scheme for the whole document and a
    nested `.light` / `.dark` region re-scopes only its subtree (the successor of
    the `.dark *` descendant clause and the `.light` exclusion)
  - Criterion 3: when OS prefers dark and theme is 'system', ThemeService applies
    `.dark`; theme.ts toggles both classes and theme.spec.ts covers the
    system + OS-prefers-dark path and both class applications
  - No redundant `@media (prefers-color-scheme: dark)` block duplicates the tokens,
    and no Tailwind residue (styles.css, `@import 'tailwindcss'`, `@custom-variant`)
  - Existing theme / layout / sidebar spec files are not removed (no regression)

Criteria skipped (not runtime-verifiable per oracle):
  - "All tests pass" — boilerplate suite gate; no per-criterion assertion
  - SOLID / clean-code prose — subjective; no concrete runtime assertion
"""

import json
import pathlib
import re

FRONTEND = (
    pathlib.Path(__file__).parent.parent
    / "project_initializer"
    / "templates"
    / "frontend"
)

STYLES_SCSS = FRONTEND / "src" / "styles.scss"
LEGACY_STYLES_CSS = FRONTEND / "src" / "styles.css"
THEME_TS = FRONTEND / "src" / "app" / "services" / "theme.ts"
THEME_SPEC = FRONTEND / "src" / "app" / "services" / "theme.spec.ts"
INDEX_HTML = FRONTEND / "src" / "index.html"


def _read_styles() -> str:
    return STYLES_SCSS.read_text(encoding="utf-8")


def _rule_body(css: str, selector: str) -> str | None:
    """Return the body of the top-level rule whose selector is exactly *selector*.

    The selector must start a line (so `html {` does not match `html,\\nbody {`)
    and the body is found by brace matching, which copes with nested Sass blocks
    and `#{...}` interpolation.
    """
    match = re.search(rf"^{re.escape(selector)}\s*\{{", css, re.MULTILINE)
    if match is None:
        return None
    depth = 1
    for index in range(match.end(), len(css)):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
            if depth == 0:
                return css[match.end() : index]
    return None


def _declares_color_scheme(body: str | None, value: str) -> bool:
    return body is not None and re.search(
        rf"(^|[;{{\s])color-scheme\s*:\s*{value}\s*;", body
    ) is not None


# ---------------------------------------------------------------------------
# Criterion: the theme is emitted on html with color-scheme: light dark
# ---------------------------------------------------------------------------


def test_when_styles_scss_read_then_html_sets_color_scheme_light_dark():
    """`html { color-scheme: light dark; }` lets the light-dark() tokens follow the OS."""
    body = _rule_body(_read_styles(), "html")
    assert body is not None, "Expected a top-level `html { ... }` rule in src/styles.scss"
    assert _declares_color_scheme(body, r"light\s+dark"), (
        "The html rule in src/styles.scss must declare `color-scheme: light dark;`"
    )


def test_when_styles_scss_read_then_html_includes_mat_theme():
    """The M3 theme is applied on html through Angular Material's `mat.theme()` mixin."""
    css = _read_styles()
    assert re.search(r"""@use\s+['"]@angular/material['"]\s+as\s+mat\s*;""", css), (
        "src/styles.scss must `@use '@angular/material' as mat;`"
    )
    body = _rule_body(css, "html")
    assert body is not None and "@include mat.theme(" in body, (
        "The html rule in src/styles.scss must `@include mat.theme(...)`"
    )


# ---------------------------------------------------------------------------
# Criterion: .dark / .light pin the scheme on <html> and on nested regions
# ---------------------------------------------------------------------------


def test_when_styles_scss_read_then_dark_class_sets_dark_color_scheme():
    """A bare `.dark` rule sets `color-scheme: dark` (on <html> or any subtree)."""
    assert _declares_color_scheme(_rule_body(_read_styles(), ".dark"), "dark"), (
        "src/styles.scss must define `.dark { color-scheme: dark; }`"
    )


def test_when_styles_scss_read_then_light_class_sets_light_color_scheme():
    """A bare `.light` rule sets `color-scheme: light`, re-asserting light under a global `.dark`."""
    assert _declares_color_scheme(_rule_body(_read_styles(), ".light"), "light"), (
        "src/styles.scss must define `.light { color-scheme: light; }`"
    )


def test_when_styles_scss_read_then_no_media_query_duplicates_the_dark_tokens():
    """The OS preference is honoured by `color-scheme: light dark` plus ThemeService.

    `mat.theme()` already emits light-dark() values, so a
    `@media (prefers-color-scheme: dark)` block would only duplicate (and fight)
    the class the service applies.
    """
    assert "prefers-color-scheme" not in _read_styles(), (
        "src/styles.scss must not add a prefers-color-scheme media query"
    )


# ---------------------------------------------------------------------------
# Criterion 3: when OS prefers dark and theme='system', ThemeService applies
# .dark — theme.ts toggles both classes and theme.spec.ts covers the paths.
# ---------------------------------------------------------------------------


def test_when_theme_service_read_then_it_toggles_both_scheme_classes_on_the_root():
    """ThemeService keeps exactly one of `.dark` / `.light` on document.documentElement."""
    source = THEME_TS.read_text(encoding="utf-8")
    assert "document.documentElement" in source, (
        "ThemeService must apply the scheme class to document.documentElement"
    )
    for class_name in ("dark", "light"):
        assert re.search(rf"classList\.toggle\(\s*['\"]{class_name}['\"]", source), (
            f"ThemeService must toggle the '{class_name}' class on the root element"
        )


def test_when_index_html_read_then_a_stored_scheme_is_pinned_before_angular_boots():
    """A stored Light or Dark choice paints from the first frame, not after bootstrap.

    ThemeService applies its class from an effect after bootstrap, and the inlined
    critical CSS has no `.light` / `.dark` rule, so a head script in index.html reads
    ThemeService's own storage key and pins the scheme as an inline `color-scheme`.
    ThemeService must remove that inline value, or it would override every later switch.
    """
    theme_ts = THEME_TS.read_text(encoding="utf-8")
    key = re.search(r"const STORAGE_KEY = '([^']+)'", theme_ts)
    assert key is not None, "theme.ts must declare its localStorage key as STORAGE_KEY"

    head = INDEX_HTML.read_text(encoding="utf-8").split("</head>", 1)[0]
    script = "\n".join(re.findall(r"<script>(.*?)</script>", head, re.DOTALL))
    assert f"localStorage.getItem('{key.group(1)}')" in script, (
        "index.html's head script must read ThemeService's storage key"
    )
    assert "style.colorScheme" in script, (
        "index.html's head script must pin the stored scheme as an inline color-scheme"
    )
    assert re.search(r"style\.removeProperty\(\s*'color-scheme'\s*\)", theme_ts), (
        "ThemeService must remove the inline color-scheme when it applies the class"
    )


def test_when_system_mode_and_os_prefers_dark_then_theme_spec_covers_class_toggle():
    """theme.spec.ts must cover the system-mode isDark path AND both class applications.

    The spec strings asserted on correspond to test names in theme.spec.ts:
      - "when theme is system and OS prefers dark, true is returned" (isDark computed)
      - "when isDark is true, the dark class is present on documentElement"
      - "when isDark is false, the light class forces the light color-scheme"
    """
    theme_spec = THEME_SPEC.read_text(encoding="utf-8")

    assert "system" in theme_spec and "prefers dark" in theme_spec, (
        "theme.spec.ts must cover the 'system mode + OS prefers dark → isDark=true' path"
    )
    assert "dark class" in theme_spec and "classList.contains('dark')" in theme_spec, (
        "theme.spec.ts must assert the dark class on documentElement"
    )
    assert "light class" in theme_spec and "classList.contains('light')" in theme_spec, (
        "theme.spec.ts must assert the light class on documentElement"
    )


# ---------------------------------------------------------------------------
# Criterion: no Tailwind dark variant remains
# ---------------------------------------------------------------------------


def test_when_global_styles_listed_then_tailwind_dark_variant_is_gone():
    """styles.css (Tailwind entry) is gone; styles.scss has no Tailwind import or custom variant."""
    assert not LEGACY_STYLES_CSS.exists(), (
        "src/styles.css must be removed; src/styles.scss is the global stylesheet"
    )
    css = _read_styles()
    assert "tailwindcss" not in css, "src/styles.scss must not import tailwindcss"
    assert "@custom-variant" not in css, "src/styles.scss must not declare @custom-variant"


def test_when_angular_json_read_then_the_global_stylesheet_is_styles_scss():
    """Every build target's global styles list src/styles.scss, never the legacy styles.css."""
    angular = json.loads((FRONTEND / "angular.json").read_text(encoding="utf-8"))
    for name, project in angular["projects"].items():
        styles = project["architect"]["build"]["options"].get("styles", [])
        assert "src/styles.scss" in styles, (
            f"[{name}] build options must list src/styles.scss, got {styles!r}"
        )
        assert "src/styles.css" not in styles, (
            f"[{name}] build options still list src/styles.css"
        )


# ---------------------------------------------------------------------------
# Criterion: no regression — existing theme / layout / sidebar spec files present
# ---------------------------------------------------------------------------


def test_when_frontend_src_listed_then_at_least_one_layout_spec_exists():
    """At least one spec file matching 'layout*.spec.ts' or 'responsive-shell*.spec.ts'
    must be present under frontend/src.

    Derived from: 'No regression in theme/layout/sidebar behavior or their existing specs'.
    The requirements explicitly name 'responsive-shell.integration.spec.ts' as the
    canonical layout integration spec (requirements.md §9).
    """
    layout_specs = list((FRONTEND / "src").rglob("layout*.spec.ts")) + list(
        (FRONTEND / "src").rglob("responsive-shell*.spec.ts")
    )
    assert len(layout_specs) > 0, (
        "No layout spec file found under frontend/src — "
        "expected at least one layout*.spec.ts or responsive-shell*.spec.ts"
    )


def test_when_frontend_src_listed_then_at_least_one_sidebar_spec_exists():
    """At least one spec file matching 'sidebar*.spec.ts' must be present.

    Derived from: 'No regression in theme/layout/sidebar behavior or their existing specs'.
    """
    sidebar_specs = list((FRONTEND / "src").rglob("sidebar*.spec.ts"))
    assert len(sidebar_specs) > 0, (
        "No sidebar spec file found under frontend/src — "
        "expected at least one sidebar*.spec.ts"
    )


def test_when_frontend_src_listed_then_at_least_one_theme_spec_exists():
    """At least one spec file matching 'theme*.spec.ts' must be present.

    Derived from: 'No regression in theme/layout/sidebar behavior or their existing specs'.
    The requirements reference 'services/theme.ts' as the ThemeService source
    (requirements.md §2); its companion spec must not be deleted.
    """
    theme_specs = list((FRONTEND / "src").rglob("theme*.spec.ts"))
    assert len(theme_specs) > 0, (
        "No theme spec file found under frontend/src — "
        "expected at least one theme*.spec.ts"
    )
