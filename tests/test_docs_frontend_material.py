"""Doc-drift guards for the frontend docs after the Material 3 migration.

The frontend template replaced Tailwind with Angular Material 3. The generated
root ``CLAUDE.md``, ``frontend/README.md`` and ``frontend/.claude/CLAUDE.md`` are
the only docs a scaffolded project gets, so these tests assert that:

1. **No generated doc mentions Tailwind or PostCSS** across the full flag and
   scope matrix, and neither do the repo's own ``CLAUDE.md`` / ``README.md``.
2. **The frontend guidance states the Material 3 conventions the template
   follows**, and each convention it names is cross-checked against the template
   file that implements it, so the doc cannot outlive the code.
"""

from pathlib import Path

import pytest

from project_initializer.docs_generator import (
    generate_api_claude,
    generate_api_readme,
    generate_frontend_claude,
    generate_frontend_readme,
    generate_root_claude,
    generate_root_readme,
)

REPO = Path(__file__).resolve().parent.parent
FRONTEND = REPO / "project_initializer" / "templates" / "frontend"

FRAMEWORKS = ["fastapi", "nestjs"]
AUTHS = [None, "token", "supabase", "entra"]
# (api, frontend) flags for the fullstack, api-only and frontend-only scopes.
SCOPES = [(True, True), (True, False), (False, True)]

_BANNED = ["tailwind", "postcss"]


def _generated_docs():
    """Every generated doc across framework x auth x scope, keyed by a readable name."""
    docs = {
        "frontend README": generate_frontend_readme(),
        "frontend CLAUDE": generate_frontend_claude(),
    }
    for framework in FRAMEWORKS:
        docs[f"{framework} api README"] = generate_api_readme(framework)
        for auth in AUTHS:
            docs[f"{framework}/{auth} api CLAUDE"] = generate_api_claude(framework, auth)
            for api, frontend in SCOPES:
                flags = dict(api=api, frontend=frontend)
                key = f"{framework}/{auth}/api={api}/frontend={frontend}"
                docs[f"{key} root README"] = generate_root_readme(framework, auth, **flags)
                docs[f"{key} root CLAUDE"] = generate_root_claude(framework, auth, **flags)
    return docs


def test_when_docs_generated_then_tailwind_and_postcss_are_never_mentioned():
    for name, doc in _generated_docs().items():
        lowered = doc.lower()
        for banned in _BANNED:
            assert banned not in lowered, f"{name} still mentions {banned!r}"


@pytest.mark.parametrize("path", ["CLAUDE.md", "README.md"])
def test_when_repo_docs_read_then_tailwind_is_not_mentioned(path):
    assert "tailwind" not in (REPO / path).read_text(encoding="utf-8").lower(), (
        f"{path} still describes Tailwind"
    )


@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize("api", [True, False])
def test_when_root_claude_generated_with_frontend_then_it_names_angular_material_3(
    framework, api
):
    doc = generate_root_claude(framework, None, api=api, frontend=True)
    section = doc.split("## Frontend Template (`frontend/`)", 1)
    assert len(section) == 2, "root CLAUDE.md must keep its Frontend Template section"
    assert "Angular Material 3" in section[1]


def test_when_frontend_readme_generated_then_it_names_angular_material_3():
    assert "Angular Material 3" in generate_frontend_readme()


# (fragment the frontend guidance must contain, template file, fragment that file must
# contain). A None template means the convention is a rule with nothing to point at.
_CONVENTIONS = [
    ("Angular Material 3", "package.json", '"@angular/material"'),
    ("`mat.theme()`", "src/styles.scss", "@include mat.theme("),
    ("`--mat-sys-*`", "src/styles.scss", "var(--mat-sys-surface)"),
    ("`--app-success`", "src/styles.scss", "success: mat."),
    ("`color-scheme`", "src/styles.scss", "color-scheme: light dark;"),
    ("`.light`", "src/styles.scss", ".light {"),
    ("`.dark`", "src/styles.scss", ".dark {"),
    ("`ThemeService`", "src/app/services/theme.ts", "export class ThemeService"),
    ("`src/styles/overlays/`", "src/styles.scss", "@use 'styles/overlays/"),
    ("`panelClass`", None, None),
    ("`.cdk-overlay-container`", None, None),
    ("`WindowSizeClassService`", "src/app/services/window-size-class.ts", "export class WindowSizeClassService"),
    ("(min-width: 600px)", "src/app/services/window-size-class.ts", "(min-width: 600px)"),
    ("(min-width: 840px)", "src/app/services/window-size-class.ts", "(min-width: 840px)"),
    ("(min-width: 1200px)", "src/app/services/window-size-class.ts", "(min-width: 1200px)"),
    ("(min-width: 1600px)", "src/app/services/window-size-class.ts", "(min-width: 1600px)"),
    ("CDK `Breakpoints` presets", None, None),
    ("`mat-sidenav`", "src/app/shared/layout/layout.html", "<mat-sidenav"),
    ("`app-bottom-tab-bar`", "src/app/shared/layout/layout.html", "<app-bottom-tab-bar"),
    ("`NAV_ITEMS`", "src/app/shared/nav-item.ts", "NAV_ITEMS"),
    ("no navigation drawer", None, None),
    # The size-class defaults of the docked rail.
    ("from 840px a toggle expands it", "src/app/shared/layout/layout.ts", "atLeast('expanded')"),
    ("from 1600px it starts expanded", "src/app/shared/layout/layout.ts", "'extraLarge'"),
    # The user's toggle overrides the size-class default; the doc names the storage key.
    (
        "`app-rail-expanded`",
        "src/app/shared/layout/layout.ts",
        "RAIL_EXPANDED_STORAGE_KEY = 'app-rail-expanded'",
    ),
    # A stored scheme paints from the first frame; ThemeService hands over from the inline value.
    ("reads the same `app-theme` key", "src/index.html", "localStorage.getItem('app-theme')"),
    ("removes that inline `color-scheme`", "src/app/services/theme.ts", "removeProperty('color-scheme')"),
    # Reduced motion also stops the router's view transitions.
    ("`::view-transition-*`", "src/styles.scss", "::view-transition-group(*)"),
    # CSP: the server swaps the nonce placeholder per response.
    ('`ngCspNonce="CSP_NONCE"`', "src/index.html", 'ngCspNonce="CSP_NONCE"'),
    # No global utility classes: edge components pad by the safe-area insets themselves.
    ("no global utility classes", None, None),
    ("`viewport-fit=cover`", "src/index.html", "viewport-fit=cover"),
    ("`templateUrl`", None, None),
    ("`styleUrl`", None, None),
    ("`<name>.css`", None, None),
    ("`src/app/icons.ts`", "src/app/icons.ts", "LUCIDE_ICONS"),
    ("`matButtonIcon`", None, None),
    ('`[size]="18"`', None, None),
    # Material's button icon margins target .mat-icon only (button.mjs, 21.2).
    ("`margin-inline: -8px 8px`", None, None),
    # lucide-angular 0.577 throws, rather than logs, for an unregistered name.
    ("has not been provided by any available icon providers", None, None),
    # mat-menu aliases panelClass to class, so the doc must steer menus to class.
    ("On `mat-menu`, use a static `class`", None, None),
    ("`.cdk-visually-hidden`", "src/styles.scss", "cdk.a11y-visually-hidden()"),
    ("48×48px", None, None),
    ("`TestbedHarnessEnvironment`", None, None),
    ("`@angular/build:unit-test`", "angular.json", '"@angular/build:unit-test"'),
    ("`src/test-providers.ts`", "src/test-providers.ts", "provideZonelessChangeDetection"),
]


@pytest.mark.parametrize(
    "doc_fragment, template, template_fragment",
    _CONVENTIONS,
    ids=[fragment for fragment, _, _ in _CONVENTIONS],
)
def test_when_frontend_claude_generated_then_material_convention_is_documented_and_real(
    doc_fragment, template, template_fragment
):
    assert doc_fragment in generate_frontend_claude(), (
        f"frontend/.claude/CLAUDE.md must document {doc_fragment!r}"
    )
    if template is not None:
        source = (FRONTEND / template).read_text(encoding="utf-8")
        assert template_fragment in source, (
            f"the doc names {doc_fragment!r}, but {template} no longer contains "
            f"{template_fragment!r}; update generate_frontend_claude() with the template"
        )


def test_when_frontend_claude_generated_then_overlay_partials_exist():
    """The overlay-partials directory the guidance points at holds real partials."""
    partials = sorted((FRONTEND / "src" / "styles" / "overlays").glob("_*.scss"))
    assert partials, "src/styles/overlays/ must contain the overlay partials"
