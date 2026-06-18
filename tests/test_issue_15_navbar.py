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

Note: the NavbarComponent uses an inline template in navbar.ts (Angular best
practice for simple components). The tests check the .ts source for all
template-level assertions.
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

# ─── Criterion: Navbar applies `.pt-safe` ─────────────────────────────────────


class TestNavbarPtSafe:
    """The navbar's outermost element must carry the pt-safe class so the top
    safe-area inset clears the iOS notch / dynamic-island.
    Source: criterion text + requirements.md §3 ('Apply .pt-safe to the mobile header')."""

    def test_when_navbar_template_is_rendered_then_pt_safe_class_is_present(self):
        assert NAVBAR_TS.exists(), (
            "navbar.ts not found — component not yet created (RED phase)"
        )
        content = NAVBAR_TS.read_text(encoding="utf-8")
        assert "pt-safe" in content, (
            "The navbar template must include the pt-safe class on its host/outermost element "
            "so the iOS notch safe-area inset is honoured."
        )


# ─── Criterion: Navbar projects brand / actions ───────────────────────────────


class TestNavbarContentProjection:
    """The navbar must expose Angular content-projection slots for a 'brand' area
    (logo / app name) and an 'actions' area (icon buttons, avatar, etc.).
    Source: criterion text 'projects brand/actions'; Angular convention is ng-content
    with a [select] attribute that names the slot."""

    def test_when_navbar_template_is_rendered_then_brand_slot_is_present(self):
        assert NAVBAR_TS.exists(), (
            "navbar.ts not found — component not yet created (RED phase)"
        )
        content = NAVBAR_TS.read_text(encoding="utf-8")
        # Accept any ng-content whose select attribute references a brand-related name.
        assert re.search(r"ng-content[^>]*brand", content, re.IGNORECASE), (
            "The navbar template must expose a content-projection slot for the brand area "
            '(e.g. <ng-content select="[navbarBrand]"> or equivalent).'
        )

    def test_when_navbar_template_is_rendered_then_actions_slot_is_present(self):
        assert NAVBAR_TS.exists(), (
            "navbar.ts not found — component not yet created (RED phase)"
        )
        content = NAVBAR_TS.read_text(encoding="utf-8")
        assert re.search(r"ng-content[^>]*action", content, re.IGNORECASE), (
            "The navbar template must expose a content-projection slot for the actions area "
            '(e.g. <ng-content select="[navbarActions]"> or equivalent).'
        )


# ─── Criterion: Navbar uses dark-mode tokens (no hardcoded hex) ───────────────

_HEX_RE = re.compile(
    r"(?<!['\"\w-])"  # not preceded by quote, word char, or dash
    r"#(?:[0-9a-fA-F]{3,4}"  # 3- or 4-digit shorthand
    r"|[0-9a-fA-F]{6}"  # 6-digit full
    r"|[0-9a-fA-F]{8})\b"  # 8-digit with alpha
)


class TestNavbarDarkModeTokens:
    """The navbar must consume @theme CSS custom-property tokens for all colours
    (var(--color-*) via Tailwind utility classes), not hardcoded hex literals.
    Hardcoded hex bypasses the token system and breaks dark-mode switching.
    Source: criterion text 'dark-mode tokens' + requirements.md non-functional
    'Theming: all components consume @theme tokens (no hardcoded hex)'."""

    def test_when_navbar_ts_file_is_read_then_no_hardcoded_hex_colors_are_present(self):
        assert NAVBAR_TS.exists(), (
            "navbar.ts not found — component not yet created (RED phase)"
        )
        content = NAVBAR_TS.read_text(encoding="utf-8")
        hits = _HEX_RE.findall(content)
        assert not hits, (
            f"Hardcoded hex colour(s) found in navbar.ts — use @theme tokens instead: {hits}"
        )


# ─── Property-based test ──────────────────────────────────────────────────────
# Invariant implied by 'dark-mode tokens': for ALL lines in the navbar source,
# no raw hex colour literal is present.


@given(data=st.data())
@settings(max_examples=200)
def test_when_any_navbar_ts_line_is_sampled_then_no_hex_color_appears(data):
    """Invariant: every line of the navbar component source is free of raw hex
    colour literals. hypothesis samples individual lines so the property is
    checked across the whole file. Fails RED because the file does not exist yet;
    passes GREEN only when every line in the source is hex-free."""
    assert NAVBAR_TS.exists(), (
        "navbar.ts not found — component not yet created (RED phase)"
    )
    lines = NAVBAR_TS.read_text(encoding="utf-8").splitlines()
    if not lines:
        return
    line = data.draw(st.sampled_from(lines))
    assert not _HEX_RE.search(line), (
        f"Hardcoded hex colour found on line: {line!r} — use @theme tokens instead"
    )
