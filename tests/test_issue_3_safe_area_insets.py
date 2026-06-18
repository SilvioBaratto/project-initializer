"""
Tests for issue #3: feat(frontend): complete safe-area inset utilities and apply to chrome.

Source-blind: authored against acceptance criteria only, before any implementation.
Criteria covered (UNIT-verifiable):
  - .pt-safe, .pl-safe, .pr-safe, and combined .px-safe are defined and mapped to
    the matching env(safe-area-inset-*) values in src/styles.css
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

STYLES_CSS = FRONTEND / "src" / "styles.css"
LAYOUT_HTML = FRONTEND / "src" / "app" / "shared" / "layout" / "layout.html"
NAVBAR_TS = FRONTEND / "src" / "app" / "shared" / "ui" / "navbar" / "navbar.ts"


def _read_styles() -> str:
    return STYLES_CSS.read_text(encoding="utf-8")


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
# Criterion: .pt-safe, .pl-safe, .pr-safe, .px-safe are defined in styles.css
# ---------------------------------------------------------------------------


def test_when_styles_css_read_then_pt_safe_class_is_defined():
    """.pt-safe must be defined as a CSS utility class in src/styles.css."""
    block = _find_utility_block(_read_styles(), ".pt-safe")
    assert block is not None, (
        "Expected '.pt-safe { ... }' to be defined in src/styles.css"
    )


def test_when_styles_css_read_then_pl_safe_class_is_defined():
    """.pl-safe must be defined as a CSS utility class in src/styles.css."""
    block = _find_utility_block(_read_styles(), ".pl-safe")
    assert block is not None, (
        "Expected '.pl-safe { ... }' to be defined in src/styles.css"
    )


def test_when_styles_css_read_then_pr_safe_class_is_defined():
    """.pr-safe must be defined as a CSS utility class in src/styles.css."""
    block = _find_utility_block(_read_styles(), ".pr-safe")
    assert block is not None, (
        "Expected '.pr-safe { ... }' to be defined in src/styles.css"
    )


def test_when_styles_css_read_then_px_safe_class_is_defined():
    """.px-safe must be defined as a CSS utility class in src/styles.css."""
    block = _find_utility_block(_read_styles(), ".px-safe")
    assert block is not None, (
        "Expected '.px-safe { ... }' to be defined in src/styles.css"
    )


# ---------------------------------------------------------------------------
# Criterion: each utility maps to the correct env(safe-area-inset-*) value
# ---------------------------------------------------------------------------


def test_when_pt_safe_block_read_then_it_maps_to_env_safe_area_inset_top():
    """.pt-safe must reference env(safe-area-inset-top) in its property value."""
    css = _read_styles()
    block = _find_utility_block(css, ".pt-safe")
    assert block is not None, ".pt-safe rule not found"
    assert _env_inset_pattern("top").search(block), (
        ".pt-safe must map to env(safe-area-inset-top); "
        f"actual block content: {block.strip()!r}"
    )


def test_when_pl_safe_block_read_then_it_maps_to_env_safe_area_inset_left():
    """.pl-safe must reference env(safe-area-inset-left) in its property value."""
    css = _read_styles()
    block = _find_utility_block(css, ".pl-safe")
    assert block is not None, ".pl-safe rule not found"
    assert _env_inset_pattern("left").search(block), (
        ".pl-safe must map to env(safe-area-inset-left); "
        f"actual block content: {block.strip()!r}"
    )


def test_when_pr_safe_block_read_then_it_maps_to_env_safe_area_inset_right():
    """.pr-safe must reference env(safe-area-inset-right) in its property value."""
    css = _read_styles()
    block = _find_utility_block(css, ".pr-safe")
    assert block is not None, ".pr-safe rule not found"
    assert _env_inset_pattern("right").search(block), (
        ".pr-safe must map to env(safe-area-inset-right); "
        f"actual block content: {block.strip()!r}"
    )


# ---------------------------------------------------------------------------
# Criterion: .px-safe applies BOTH left AND right insets
# ---------------------------------------------------------------------------


def test_when_px_safe_block_read_then_it_maps_to_env_safe_area_inset_left():
    """.px-safe must reference env(safe-area-inset-left) (it covers both horizontal sides)."""
    css = _read_styles()
    block = _find_utility_block(css, ".px-safe")
    assert block is not None, ".px-safe rule not found"
    assert _env_inset_pattern("left").search(block), (
        ".px-safe must reference env(safe-area-inset-left); "
        f"actual block content: {block.strip()!r}"
    )


def test_when_px_safe_block_read_then_it_maps_to_env_safe_area_inset_right():
    """.px-safe must reference env(safe-area-inset-right) (it covers both horizontal sides)."""
    css = _read_styles()
    block = _find_utility_block(css, ".px-safe")
    assert block is not None, ".px-safe rule not found"
    assert _env_inset_pattern("right").search(block), (
        ".px-safe must reference env(safe-area-inset-right); "
        f"actual block content: {block.strip()!r}"
    )


# ---------------------------------------------------------------------------
# Criterion: .pt-safe is applied to the mobile <header> in layout.html
# ---------------------------------------------------------------------------


def test_when_layout_html_read_then_header_element_has_pt_safe_class():
    """The mobile header must carry the class 'pt-safe' to clear the iOS notch.

    Per requirements §3: '.pt-safe' must be applied to the mobile header.
    Accepted in either layout.html (inline header) or the NavbarComponent's
    inline template in navbar.ts (when the header is extracted into a component).
    """
    layout = _read_layout()
    # Match any <header ...> that includes pt-safe in its class attribute.
    # Handles both class="... pt-safe ..." and [class]="'... pt-safe ...'".
    pattern = re.compile(r"<header\b[^>]*\bpt-safe\b", re.DOTALL)
    if pattern.search(layout):
        return  # Criterion satisfied by inline header in layout.html

    # Since Issue #15, the header is encapsulated in NavbarComponent.
    # Check the navbar component source for pt-safe on the <header> element.
    if NAVBAR_TS.exists():
        navbar_src = NAVBAR_TS.read_text(encoding="utf-8")
        assert pattern.search(navbar_src), (
            "Expected a <header> element with class 'pt-safe' in the NavbarComponent "
            "template (navbar.ts); none found. The mobile header must carry .pt-safe "
            "to clear the iOS notch."
        )
    else:
        assert False, (
            "Expected a <header> element with class 'pt-safe' in layout.html "
            "(or in the NavbarComponent's navbar.ts); none found. "
            "The mobile header must carry .pt-safe to clear the iOS notch."
        )


# ---------------------------------------------------------------------------
# Criterion: .pb-safe remains applied to the bottom tab bar and its CSS
# definition is present (unchanged or co-located with the new utilities)
# ---------------------------------------------------------------------------


def test_when_styles_css_read_then_pb_safe_class_is_still_defined():
    """.pb-safe must still be defined in src/styles.css (the pre-existing utility must not be removed).

    Per the criteria: '.pb-safe remains applied to the bottom tab bar and its
    definition is unchanged (or cleanly co-located with the new utilities)'.
    """
    block = _find_utility_block(_read_styles(), ".pb-safe")
    assert block is not None, (
        "Expected '.pb-safe { ... }' to remain defined in src/styles.css; it was removed."
    )


def test_when_pb_safe_block_read_then_it_maps_to_env_safe_area_inset_bottom():
    """.pb-safe must reference env(safe-area-inset-bottom) — the pre-existing mapping must not change."""
    css = _read_styles()
    block = _find_utility_block(css, ".pb-safe")
    assert block is not None, ".pb-safe rule not found"
    assert _env_inset_pattern("bottom").search(block), (
        ".pb-safe must map to env(safe-area-inset-bottom); "
        f"actual block content: {block.strip()!r}"
    )


def test_when_bottom_tab_bar_template_read_then_pb_safe_class_is_present():
    """The bottom-tab-bar template must carry the class 'pb-safe'.

    Per the criteria: '.pb-safe remains applied to the bottom tab bar'.
    Searches for pb-safe in any template file under the bottom-tab-bar directory.
    """
    bottom_tab_bar_dir = FRONTEND / "src" / "app" / "shared" / "bottom-tab-bar"
    # Collect all HTML/TS template files inside the component folder.
    templates = list(bottom_tab_bar_dir.rglob("*.html")) + list(
        bottom_tab_bar_dir.rglob("*.ts")
    )
    assert templates, (
        f"No files found under {bottom_tab_bar_dir} — "
        "expected at least one bottom-tab-bar component file"
    )
    found = any("pb-safe" in t.read_text(encoding="utf-8") for t in templates)
    assert found, (
        "Expected 'pb-safe' to appear in the bottom-tab-bar component template/source; "
        "it must remain applied to the bottom tab bar."
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
