"""
Tests for issue #2: feat(frontend): wire dark: variant via @custom-variant on the .dark class.

Source-blind: authored against acceptance criteria only, before any implementation.
Criteria covered (UNIT-verifiable):
  - @custom-variant dark (&:where(.dark, .dark *)); is declared in src/styles.css
    immediately after @import 'tailwindcss';
  - The dark: variant selector includes .dark * so it activates when .dark is on
    an ancestor (the ThemeService toggle on <html>)
  - Criterion 3 (corrected per issue comment): when OS prefers dark and theme is
    'system', ThemeService applies .dark so dark: utilities resolve — verified by
    checking that theme.spec.ts covers the isDark+class-application path.
  - Existing theme / layout / sidebar spec files are not removed (no regression)

Criteria skipped (not runtime-verifiable per oracle):
  - "All tests pass" — boilerplate suite gate; no per-criterion assertion
  - SOLID / clean-code prose — subjective; no concrete runtime assertion

Note on criterion 3: The issue comment clarifies that @custom-variant fully redefines
the dark: variant, so Tailwind no longer emits @media (prefers-color-scheme: dark) for
dark: utilities. OS preference is honored through ThemeService: isDark = theme==='dark'
|| (theme==='system' && osPrefersDark), which toggles .dark on <html>. No redundant
@media block should be added to styles.css.
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

_CUSTOM_VARIANT_DECL = "@custom-variant dark (&:where(.dark, .dark *));"

# @import may use single or double quotes — accept both.
_IMPORT_PATTERN = re.compile(r"""@import\s+['"]tailwindcss['"];""")


def _read_styles() -> str:
    return STYLES_CSS.read_text(encoding="utf-8")


def _styles_lines() -> list[str]:
    return _read_styles().splitlines()


# ---------------------------------------------------------------------------
# Criterion: @custom-variant dark declaration is present in src/styles.css
# ---------------------------------------------------------------------------


def test_when_styles_css_read_then_custom_variant_dark_declaration_is_present():
    """styles.css must contain the exact string '@custom-variant dark (&:where(.dark, .dark *));'."""
    assert _CUSTOM_VARIANT_DECL in _read_styles(), (
        f"Expected '{_CUSTOM_VARIANT_DECL}' in src/styles.css"
    )


# ---------------------------------------------------------------------------
# Criterion: @custom-variant is immediately after @import 'tailwindcss';
# ---------------------------------------------------------------------------


def test_when_styles_css_read_then_custom_variant_immediately_follows_tailwindcss_import():
    """The first non-blank line after '@import \"tailwindcss\";' must be the @custom-variant declaration.

    'Immediately after' is interpreted as: no non-blank content may appear between
    the @import line and the @custom-variant line.  Blank lines are ignored.
    """
    lines = _styles_lines()

    import_index = next(
        (i for i, line in enumerate(lines) if _IMPORT_PATTERN.match(line.strip())),
        None,
    )
    assert import_index is not None, (
        "@import 'tailwindcss'; (or with double quotes) not found in src/styles.css"
    )

    first_non_blank_after = next(
        (line.strip() for line in lines[import_index + 1 :] if line.strip()),
        None,
    )
    assert first_non_blank_after == _CUSTOM_VARIANT_DECL, (
        f"Expected first non-blank line after @import 'tailwindcss'; to be "
        f"'{_CUSTOM_VARIANT_DECL}', got {first_non_blank_after!r}"
    )


# ---------------------------------------------------------------------------
# Criterion: dark: utility activates when .dark is on an ancestor
# (the where() clause must contain '.dark *' — the descendant wildcard)
# ---------------------------------------------------------------------------


def test_when_custom_variant_selector_read_then_dot_dark_star_descendant_is_included():
    """The @custom-variant selector must include '.dark *' so that dark: utilities
    resolve on elements that are *descendants* of .dark, not only on .dark itself.

    This is required because ThemeService toggles .dark on <html>, not on every
    individual element.  Without '.dark *' the variant would never fire on children.
    """
    assert ".dark *" in _read_styles(), (
        "src/styles.css @custom-variant selector must include '.dark *' "
        "to activate dark: utilities on descendants of the .dark class"
    )


# ---------------------------------------------------------------------------
# Criterion 3 (corrected): when OS prefers dark and theme='system',
# ThemeService applies .dark so dark: utilities resolve — verified by
# confirming the ThemeService spec covers both isDark (system+OS) and
# _applyClass (class toggle) paths.
# ---------------------------------------------------------------------------


def test_when_system_mode_and_os_prefers_dark_then_theme_spec_covers_class_toggle():
    """theme.spec.ts must cover both the system-mode isDark path AND the class-application path.

    Per the issue comment: @custom-variant fully redefines dark:, so Tailwind no longer
    emits @media (prefers-color-scheme: dark) for dark: utilities. OS preference is
    honored by ThemeService toggling .dark on <html>. This test verifies the spec file
    contains the test cases that prove that path works.

    The two spec strings we assert on correspond to actual test names in theme.spec.ts:
      - "when theme is system and OS prefers dark, true is returned" (isDark computed)
      - "when isDark is true, the dark class is present on documentElement" (class toggle)
    """
    theme_spec = (FRONTEND / "src" / "app" / "services" / "theme.spec.ts").read_text(
        encoding="utf-8"
    )

    assert (
        "system" in theme_spec
        and "osPrefer" in theme_spec
        or ("system" in theme_spec and "prefers dark" in theme_spec)
    ), "theme.spec.ts must cover the 'system mode + OS prefers dark → isDark=true' path"

    assert (
        "dark class" in theme_spec
        or "classList" in theme_spec
        or "_applyClass" in theme_spec
    ), (
        "theme.spec.ts must cover the class-application (_applyClass / classList.toggle) path"
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
