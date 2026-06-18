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
COMPONENTS_SPEC = COMPONENTS_PAGE_DIR / "components.spec.ts"

COMPONENT_GROUPS = ["Core", "Forms", "Navigation", "Overlays", "Data Display"]


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
    class 'dark', matching the @custom-variant dark (&:where(.dark, .dark *))
    declaration in styles.css.  This is independent of the global ThemeService
    toggle (which sets 'dark' on a document-level ancestor).
    """
    content = COMPONENTS_HTML.read_text(encoding="utf-8")
    assert re.search(r'class=["\'][^"\']*\bdark\b[^"\']*["\']', content), (
        "components.html must contain at least one element with CSS class 'dark' "
        "to scope the dark preview region"
    )


def test_when_components_html_inspected_then_root_element_is_not_globally_dark():
    """
    The page must have a light region: the outermost rendered element must NOT
    carry the 'dark' class itself — otherwise the entire page would be dark and
    there would be no separate light region.
    Per implementation notes the host class is 'block p-6 md:p-8'.
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
