"""
Source-blind example tests for issue #22:
feat: add lazy-loaded pages/components demo catalog (light + dark)

Tests are authored from acceptance criteria only (Red phase of TDD).
All tests fail until the implementation is complete.

Criteria NOT tested here (per oracle classification):
  - "All tests pass" — boilerplate suite gate, no per-criterion assertion
  - "SOLID, clean code" — subjective prose, not runtime-verifiable
"""

import pathlib
import re

import pytest

TEMPLATES_ROOT = (
    pathlib.Path(__file__).parent.parent / "project_initializer" / "templates"
)
FRONTEND = TEMPLATES_ROOT / "frontend"

ROUTES_TS = FRONTEND / "src" / "app" / "app.routes.ts"
NAV_ITEM_TS = FRONTEND / "src" / "app" / "shared" / "nav-item.ts"
COMPONENTS_PAGE_DIR = FRONTEND / "src" / "app" / "pages" / "components"
COMPONENTS_TS = COMPONENTS_PAGE_DIR / "components.ts"
COMPONENTS_HTML = COMPONENTS_PAGE_DIR / "components.html"
COMPONENTS_CSS = COMPONENTS_PAGE_DIR / "components.css"
COMPONENTS_SPEC = COMPONENTS_PAGE_DIR / "components.spec.ts"
THEME_PREVIEW_TS = COMPONENTS_PAGE_DIR / "theme-preview.ts"
THEME_PREVIEW_HTML = COMPONENTS_PAGE_DIR / "theme-preview.html"
THEME_PREVIEW_CSS = COMPONENTS_PAGE_DIR / "theme-preview.css"

COMPONENT_GROUPS = ["Core", "Forms", "Navigation", "Overlays", "Data Display"]

# A class token that looks like a Tailwind utility (optionally behind a variant such as md: or dark:).
TAILWIND_CLASS = re.compile(
    r"^(?:[a-z0-9-]+:)*(?:flex|inline-flex|grid-cols-|block$|p[xytblrse]?-\d|m[xytblrse]?-(?:\d|auto)|"
    r"gap-|space-[xy]-|text-|bg-|border|rounded|shadow|ring-|font-|max-w-|min-h-|w-\d|h-\d|items-|"
    r"justify-|truncate|sr-only|animate-|transition|duration-|opacity-\d|divide-|tracking-|uppercase)"
)


# ---------------------------------------------------------------------------
# File-existence gate
# ---------------------------------------------------------------------------


def test_when_components_page_dir_inspected_then_ts_file_exists():
    assert COMPONENTS_TS.exists(), (
        "src/app/pages/components/components.ts must be created"
    )


def test_when_components_page_dir_inspected_then_html_file_exists():
    assert COMPONENTS_HTML.exists(), (
        "src/app/pages/components/components.html must be created"
    )


def test_when_components_page_dir_inspected_then_spec_file_exists():
    assert COMPONENTS_SPEC.exists(), (
        "src/app/pages/components/components.spec.ts must be created"
    )


# ---------------------------------------------------------------------------
# Criterion: /components is registered as a lazy loadComponent route
# under the layout children in app.routes.ts
# ---------------------------------------------------------------------------


def test_when_routes_file_inspected_then_components_path_is_declared():
    content = ROUTES_TS.read_text(encoding="utf-8")
    assert re.search(r"""path\s*:\s*['"]components['"]""", content), (
        "app.routes.ts must declare a route with path 'components'"
    )


def test_when_routes_file_inspected_then_components_route_uses_load_component():
    content = ROUTES_TS.read_text(encoding="utf-8")
    # The lazy import expression must reference the components page module
    assert re.search(r"pages/components/components", content), (
        "loadComponent must import from pages/components/components"
    )


def test_when_routes_file_inspected_then_components_route_is_after_layout_component():
    """
    Proxy for 'registered under the layout children': the components path must
    appear in the file after the LayoutComponent declaration, meaning it sits
    inside the children array of the layout shell route.
    """
    content = ROUTES_TS.read_text(encoding="utf-8")
    layout_idx = content.find("LayoutComponent")
    components_idx = max(
        content.find("'components'"),
        content.find('"components"'),
    )
    assert layout_idx != -1, "LayoutComponent must appear in app.routes.ts"
    assert components_idx != -1, "path 'components' must appear in app.routes.ts"
    assert layout_idx < components_idx, (
        "components route must appear after the LayoutComponent declaration "
        "— it must be a child route, not a top-level route"
    )


def test_when_routes_file_inspected_then_load_component_keyword_is_present():
    content = ROUTES_TS.read_text(encoding="utf-8")
    assert "loadComponent" in content, (
        "The components route must use loadComponent for lazy loading"
    )


# ---------------------------------------------------------------------------
# Criterion: The page renders every shared/ui/ component, grouped
# (Core, Forms, Navigation, Overlays, Data Display)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("group", COMPONENT_GROUPS)
def test_when_components_html_inspected_then_group_section_is_present(group):
    content = COMPONENTS_HTML.read_text(encoding="utf-8")
    assert group in content, (
        f"components.html must have a section for the '{group}' component group"
    )


# ---------------------------------------------------------------------------
# Criterion: Each component is shown in both a light region and a dark region
# (dark scoped via a `dark`-classed container, independent of the global theme toggle)
# ---------------------------------------------------------------------------


def test_when_components_html_inspected_then_dark_classed_container_is_present():
    """
    The dark region must be created by a container element carrying the CSS
    class 'dark'. The `.dark` rule in styles.scss sets `color-scheme: dark` on
    that subtree, so the `light-dark()` --mat-sys-* tokens inside it resolve to
    the dark scheme. This is independent of the global ThemeService toggle
    (which puts `.light` or `.dark` on <html>).

    The region lives in one place, app-theme-preview, and every group section
    that components.html mounts previews its demos through it.
    """
    content = COMPONENTS_HTML.read_text(encoding="utf-8")
    sections = sorted(set(re.findall(r"<app-([a-z-]+-section)\b", content)))
    assert len(sections) == len(COMPONENT_GROUPS), (
        "components.html must mount one section component per component group"
    )
    for name in sections:
        section_html = (COMPONENTS_PAGE_DIR / "sections" / f"{name}.html").read_text(encoding="utf-8")
        assert "<app-theme-preview>" in section_html, (
            f"{name}.html must preview its demos through app-theme-preview, "
            "which renders the light and the dark-classed region"
        )
    assert re.search(
        r'class=["\'][^"\']*\bdark\b[^"\']*["\']', THEME_PREVIEW_HTML.read_text(encoding="utf-8")
    ), "theme-preview.html must contain an element with CSS class 'dark' to scope the dark preview region"


def test_when_components_html_inspected_then_root_element_is_not_globally_dark():
    """
    The page must have a light region: the outermost rendered element must NOT
    carry the 'dark' class itself — otherwise the entire page would be dark and
    there would be no separate light region.
    The page host carries no classes at all; its margins live in components.css.
    """
    content = COMPONENTS_HTML.read_text(encoding="utf-8")
    first_tag = re.search(r"<[a-zA-Z][^>]*>", content)
    assert first_tag is not None, (
        "components.html must contain at least one HTML element"
    )
    first_tag_text = first_tag.group(0)
    assert not re.search(r'class=["\'][^"\']*\bdark\b[^"\']*["\']', first_tag_text), (
        "The page root element must not carry the 'dark' class — "
        "the light preview region must exist outside any dark-scoped container"
    )


# ---------------------------------------------------------------------------
# Criterion: Component is standalone, OnPush, and lazy-loaded
# ---------------------------------------------------------------------------


def test_when_components_ts_inspected_then_onpush_is_declared():
    content = COMPONENTS_TS.read_text(encoding="utf-8")
    assert "ChangeDetectionStrategy.OnPush" in content, (
        "ComponentsComponent must declare changeDetection: ChangeDetectionStrategy.OnPush"
    )


def test_when_components_ts_inspected_then_component_class_is_a_named_export():
    """loadComponent(() => import(...).then(m => m.ComponentsComponent)) requires a named export."""
    content = COMPONENTS_TS.read_text(encoding="utf-8")
    assert re.search(r"export\s+class\s+ComponentsComponent", content), (
        "ComponentsComponent must be a named export to be referenced by loadComponent"
    )


def test_when_components_page_inspected_then_template_and_styles_are_separate_files():
    """
    The page is split into components.ts + components.html + components.css,
    wired with templateUrl and styleUrl (no inline template or styles).
    """
    content = COMPONENTS_TS.read_text(encoding="utf-8")
    assert COMPONENTS_CSS.exists(), "src/app/pages/components/components.css must exist"
    assert re.search(r"templateUrl\s*:\s*['\"]\./components\.html['\"]", content), (
        "ComponentsComponent must use templateUrl: './components.html'"
    )
    assert re.search(r"styleUrl\s*:\s*['\"]\./components\.css['\"]", content), (
        "ComponentsComponent must use styleUrl: './components.css'"
    )
    assert not re.search(r"\b(template|styles)\s*:", content), (
        "ComponentsComponent must not declare an inline template or inline styles"
    )


def test_when_theme_preview_inspected_then_template_and_styles_are_separate_files():
    """ThemePreviewComponent is split into .ts + .html + .css like every component."""
    for path in (THEME_PREVIEW_TS, THEME_PREVIEW_HTML, THEME_PREVIEW_CSS):
        assert path.exists(), f"{path.name} must exist in src/app/pages/components/"
    content = THEME_PREVIEW_TS.read_text(encoding="utf-8")
    assert "ChangeDetectionStrategy.OnPush" in content
    assert re.search(r"templateUrl\s*:\s*['\"]\./theme-preview\.html['\"]", content)
    assert re.search(r"styleUrl\s*:\s*['\"]\./theme-preview\.css['\"]", content)
    assert not re.search(r"\b(template|styles)\s*:", content), (
        "ThemePreviewComponent must not declare an inline template or inline styles"
    )


def test_when_theme_preview_html_inspected_then_light_and_dark_regions_are_present():
    """Each demo is stamped into one `light`-classed and one `dark`-classed region."""
    content = THEME_PREVIEW_HTML.read_text(encoding="utf-8")
    assert re.search(r'class=["\'][^"\']*\blight\b[^"\']*["\']', content)
    assert re.search(r'class=["\'][^"\']*\bdark\b[^"\']*["\']', content)
    assert content.count("ngTemplateOutlet") == 2, (
        "theme-preview.html must stamp the projected template once per region"
    )


def test_when_region_styles_inspected_then_regions_paint_surface_tokens():
    """
    A region that forces a color scheme must paint its own ground: the preview
    regions take background --mat-sys-surface and color --mat-sys-on-surface,
    which resolve in the region's scheme. They are styled once, in
    theme-preview.css; the page stylesheet doesn't keep a second copy.
    """
    content = THEME_PREVIEW_CSS.read_text(encoding="utf-8")
    assert re.search(r"background(-color)?\s*:\s*var\(--mat-sys-surface\)", content), (
        "theme-preview.css must paint the preview region with var(--mat-sys-surface)"
    )
    assert re.search(r"(?<![-\w])color\s*:\s*var\(--mat-sys-on-surface\)", content), (
        "theme-preview.css must set the preview region text to var(--mat-sys-on-surface)"
    )
    assert ".preview-region" not in COMPONENTS_CSS.read_text(encoding="utf-8"), (
        "components.css must not duplicate the preview region rules of theme-preview.css"
    )


@pytest.mark.parametrize("path", [COMPONENTS_CSS, THEME_PREVIEW_CSS], ids=lambda p: p.name)
def test_when_catalog_styles_inspected_then_they_use_tokens_and_no_color_literals(path):
    """Colors come from --mat-sys-* tokens only: no hex/rgb/hsl literals, !important or ::ng-deep."""
    content = path.read_text(encoding="utf-8")
    assert "var(--mat-sys-" in content
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", content), f"{path.name} contains a hex color literal"
    assert not re.search(r"\b(rgb|rgba|hsl|hsla)\(", content), f"{path.name} contains a color function literal"
    assert "!important" not in content
    assert "::ng-deep" not in content


def test_when_components_css_inspected_then_page_margins_follow_m3_window_sizes():
    """M3 margins: 16px below 600px (compact), 24px from 600px (medium and up)."""
    content = COMPONENTS_CSS.read_text(encoding="utf-8")
    host_rule = re.search(r":host\s*\{([^}]*)\}", content)
    assert host_rule and "16px" in host_rule.group(1), "the page host must use 16px compact margins"
    medium = re.search(r"@media\s*\(min-width:\s*600px\)\s*\{\s*:host\s*\{([^}]*)\}", content)
    assert medium and "24px" in medium.group(1), "from 600px the page host must use 24px margins"


def test_when_region_styles_inspected_then_columns_switch_at_m3_breakpoint():
    """Light and dark regions sit side by side from the M3 expanded class (840px), never at 768px."""
    assert re.search(r"@media\s*\(min-width:\s*840px\)", THEME_PREVIEW_CSS.read_text(encoding="utf-8"))
    for path in (COMPONENTS_CSS, THEME_PREVIEW_CSS):
        assert "768px" not in path.read_text(encoding="utf-8"), f"{path.name} uses the non-M3 768px breakpoint"


@pytest.mark.parametrize("path", [COMPONENTS_HTML, THEME_PREVIEW_HTML], ids=lambda p: p.name)
def test_when_catalog_templates_inspected_then_no_tailwind_utility_classes_remain(path):
    """Styling comes from Material components and component CSS, not Tailwind utilities."""
    content = path.read_text(encoding="utf-8")
    tokens = [
        token
        for value in re.findall(r'\bclass=["\']([^"\']*)["\']', content)
        for token in value.split()
    ]
    offenders = [token for token in tokens if TAILWIND_CLASS.match(token)]
    assert not offenders, f"{path.name} still uses Tailwind utility classes: {offenders}"


def test_when_components_html_inspected_then_heading_outline_has_one_h1_and_group_h2s():
    """One h1 per routed view, and one h2 per component group (no skipped levels)."""
    content = COMPONENTS_HTML.read_text(encoding="utf-8")
    assert len(re.findall(r"<h1\b", content)) == 1, "components.html must have exactly one h1"
    assert len(re.findall(r"<h2\b", content)) == len(COMPONENT_GROUPS), (
        "components.html must have one h2 per component group"
    )


def test_when_components_ts_inspected_then_standalone_is_not_explicitly_set_to_false():
    """
    Angular 21 defaults standalone to true; the project convention is NOT to set
    standalone: true explicitly.  Verify standalone is not set to false.
    """
    content = COMPONENTS_TS.read_text(encoding="utf-8")
    assert "standalone: false" not in content, (
        "ComponentsComponent must not set standalone: false — "
        "Angular 21 components are standalone by default"
    )


# ---------------------------------------------------------------------------
# Criterion: Existing nav tests stay green —
# do NOT add the route to shared/nav-item.ts NAV_ITEMS
# ---------------------------------------------------------------------------


def test_when_nav_items_file_inspected_then_components_is_absent_from_nav_items():
    """
    Adding 'components' to NAV_ITEMS would break the sidebar/bottom-tab-bar/layout
    specs that assert the exact set of navigation items.
    """
    content = NAV_ITEM_TS.read_text(encoding="utf-8")
    nav_items_match = re.search(
        r"NAV_ITEMS\s*[=:][^;]+;",
        content,
        re.DOTALL,
    )
    if nav_items_match:
        block = nav_items_match.group(0)
        assert "components" not in block.lower(), (
            "NAV_ITEMS must not include the 'components' route path"
        )
    else:
        # If the regex didn't match, fall back to a full-file check
        # NAV_ITEMS is the only export; if 'components' appears at all it is a violation
        assert re.search(r"['\"]/components['\"]", content) is None, (
            "shared/nav-item.ts must not reference the /components route"
        )


# ---------------------------------------------------------------------------
# Criterion: components.spec.ts asserts both theme regions and a section
# per component group
# ---------------------------------------------------------------------------


def test_when_components_spec_inspected_then_dark_region_is_asserted():
    content = COMPONENTS_SPEC.read_text(encoding="utf-8")
    assert re.search(r"\bdark\b", content), (
        "components.spec.ts must include an assertion that verifies "
        "the dark theme region is rendered"
    )


@pytest.mark.parametrize("group", COMPONENT_GROUPS)
def test_when_components_spec_inspected_then_group_is_asserted(group):
    content = COMPONENTS_SPEC.read_text(encoding="utf-8")
    assert group in content, (
        f"components.spec.ts must include an assertion covering the '{group}' component group"
    )
