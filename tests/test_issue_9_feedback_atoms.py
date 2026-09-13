"""
Tests for issue #9: feat(ui): feedback atoms — Badge, Spinner, Skeleton, Alert.

Source-blind: authored against acceptance criteria only, before any implementation.

Criteria covered:
  - [UNIT] Spinner: `role="status"` + sr-only label, reduced-motion safe
  - [UNIT] Skeleton shimmer, no layout shift — since the Material 3 migration the
    shimmer is a skeleton.css @keyframes animation on --mat-sys-surface-container-*
    tokens (off under prefers-reduced-motion), sized by width/height inputs with a
    per-shape CSS default, split into .ts/.html/.css with an aria-hidden placeholder
  - [UNIT] Alert: live region (`role="alert"` for danger, `role="status"` otherwise),
    variant (info/success/warning/danger) via --app-* / --mat-sys-* container tokens,
    separate .ts/.html/.css, leading icon, labelled matIconButton dismiss

  - [UNIT] Badge variants via tokens, dark-mode aware — since the Material 3
    migration each variant is a --mat-sys-* / --app-* container token pair in
    badge.css (tokens emit light-dark(), so dark mode follows); checked
    statically, plus the .ts/.html/.css split and a status icon per status variant

Criteria skipped (not runtime-verifiable per oracle):
  - All tests pass — boilerplate suite gate; no per-criterion assertion.
  - SOLID, clean code (methods < 10 lines …) — subjective prose; no concrete
    runtime or unit assertion.

Hypothesis / property-based tests:
  No invariant-implying criteria survive to this tier. The verifiable criteria
  target static structural properties of the component source (presence of
  ARIA attributes, CSS class references, signal declarations). These are
  existence checks over a fixed file set, not parametric transforms whose
  output must satisfy a law for all members of a varying input domain.
  Therefore no @given properties are emitted.
"""

import pathlib
import re

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FRONTEND = (
    pathlib.Path(__file__).parent.parent
    / "project_initializer"
    / "templates"
    / "frontend"
)

UI_ROOT = FRONTEND / "src" / "app" / "shared" / "ui"

SPINNER_DIR = UI_ROOT / "spinner"
SKELETON_DIR = UI_ROOT / "skeleton"
ALERT_DIR = UI_ROOT / "alert"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_dir(component_dir: pathlib.Path) -> str:
    """Return concatenated source of all .ts + .html files in a component dir."""
    parts: list[str] = []
    for ext in ("*.ts", "*.html"):
        for f in component_dir.glob(ext):
            if ".spec." not in f.name:
                parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _primary_ts(component_dir: pathlib.Path) -> pathlib.Path:
    """Return the primary (non-spec) TypeScript file for a component."""
    candidates = [f for f in component_dir.glob("*.ts") if ".spec." not in f.name]
    if not candidates:
        raise FileNotFoundError(f"No non-spec .ts file found in {component_dir}")
    name = component_dir.name  # e.g. "spinner"
    preferred = [f for f in candidates if name in f.name]
    return (preferred or candidates)[0]


# ===========================================================================
# Spinner
# ===========================================================================
# Criterion: Spinner: `role="status"` + sr-only label, reduced-motion safe
# ===========================================================================


def test_when_ui_directory_inspected_then_spinner_folder_exists():
    """shared/ui/spinner/ must be a directory.

    Per criterion: 'Spinner: role="status" + sr-only label, reduced-motion safe'.
    Requirements §7 specifies a Spinner component under shared/ui/.
    """
    assert SPINNER_DIR.is_dir(), (
        "Expected shared/ui/spinner/ to exist as a directory under "
        "templates/frontend/src/app/shared/ui/"
    )


def test_when_spinner_folder_inspected_then_typescript_source_file_exists():
    """Spinner folder must contain at least one non-spec .ts source file.

    Per requirements §7 pattern: 'one folder per component (.ts + template + .spec.ts)'.
    """
    non_spec = [f for f in SPINNER_DIR.glob("*.ts") if ".spec." not in f.name]
    assert non_spec, (
        "Expected at least one .ts source file (not .spec.ts) in shared/ui/spinner/"
    )


def _spinner_sources() -> str:
    """Return the Spinner's non-spec .ts + .html + .css sources, concatenated."""
    parts: list[str] = []
    for ext in ("*.ts", "*.html", "*.css"):
        for f in sorted(SPINNER_DIR.glob(ext)):
            if ".spec." not in f.name:
                parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _spinner_css() -> str:
    return (SPINNER_DIR / "spinner.css").read_text(encoding="utf-8")


def test_when_spinner_source_read_then_role_status_is_present():
    """Spinner template must declare role="status".

    Per criterion: 'Spinner: `role="status"`'.
    WAI-ARIA: role="status" is a live region that announces asynchronous status
    messages to screen readers without interrupting the user.
    """
    src = _spinner_sources()
    assert 'role="status"' in src or "role='status'" in src, (
        'Expected role="status" in the Spinner component source (.ts, .html or .css). '
        "Per criterion: 'Spinner: `role=\"status\"` + sr-only label'."
    )


def test_when_spinner_source_read_then_sr_only_label_is_present():
    """Spinner template must contain a screen-reader-only label.

    Per criterion: 'Spinner: role="status" + sr-only label'.
    The label must be visually hidden but announced by assistive technology.
    Since the Material 3 migration there is no Tailwind `sr-only`: the accepted
    forms are the CDK `cdk-visually-hidden` class (defined globally in
    styles.scss) on label text, or an `aria-label` attribute.
    """
    src = _spinner_sources()
    has_visually_hidden = "cdk-visually-hidden" in src
    has_aria_label = bool(re.search(r"aria-label\s*=", src))
    assert has_visually_hidden or has_aria_label, (
        "Expected a 'cdk-visually-hidden' label or an 'aria-label' attribute in the "
        "Spinner component source. Per criterion: 'Spinner: role=\"status\" + sr-only label'."
    )
    assert "sr-only" not in src, "The Tailwind sr-only utility no longer exists; use cdk-visually-hidden"


def test_when_spinner_source_read_then_indeterminate_material_spinner_is_used():
    """Spinner animates through Angular Material's circular progress indicator.

    Replaces the Tailwind `animate-spin` check: the spinning indicator is now an
    indeterminate `<mat-progress-spinner>` (MatProgressSpinnerModule), whose
    animation Material ships, and it is decorative because the label names the state.
    """
    ts = (SPINNER_DIR / "spinner.ts").read_text(encoding="utf-8")
    html = (SPINNER_DIR / "spinner.html").read_text(encoding="utf-8")
    assert "MatProgressSpinnerModule" in ts, "Expected MatProgressSpinnerModule in spinner.ts imports"
    match = re.search(r"<mat-progress-spinner\b([^>]*)>", html)
    assert match, "Expected a <mat-progress-spinner> in spinner.html"
    attrs = match.group(1)
    assert 'mode="indeterminate"' in attrs, "The spinner must be indeterminate"
    assert "[diameter]" in attrs, "The diameter must be bound from the size API"
    assert 'aria-hidden="true"' in attrs, "The indicator must be decorative next to the label"
    assert "animate-spin" not in ts + html, "The Tailwind animate-spin utility must be gone"


def test_when_spinner_source_read_then_reduced_motion_is_handled():
    """Spinner must stay reduced-motion safe.

    Per criterion: 'Spinner: role="status" + sr-only label, reduced-motion safe'.
    Reduced-motion safety means the indicator never freezes into a static arc that
    no longer reads as "in progress". Angular Material keeps an indeterminate
    mat-progress-spinner turning at 1.25x its duration under the preference, and the
    global reduced-motion rule in styles.scss exempts Material's progress indicators.
    So spinner.css needs no reduced-motion override, and must not reveal a label the
    consumer kept screen-reader-only.
    """
    css = _spinner_css()
    assert "prefers-reduced-motion" not in css, (
        "spinner.css must not override reduced motion: Material slows the indicator "
        "instead of stopping it, so revealing the label would only shift the layout."
    )
    styles = (FRONTEND / "src" / "styles.scss").read_text(encoding="utf-8")
    assert re.search(r":not\([^)]*\.mat-mdc-progress-spinner \*", styles), (
        "Expected the global reduced-motion rule in styles.scss to exempt "
        "mat-progress-spinner, so the indicator keeps turning."
    )


def test_when_spinner_ts_read_then_onpush_change_detection_is_set():
    """Spinner component must declare ChangeDetectionStrategy.OnPush.

    CLAUDE.md: 'OnPush change detection: Set changeDetection:
    ChangeDetectionStrategy.OnPush'. Applies to all shared/ui components.
    """
    ts = _primary_ts(SPINNER_DIR).read_text(encoding="utf-8")
    assert "ChangeDetectionStrategy.OnPush" in ts, (
        "Expected 'ChangeDetectionStrategy.OnPush' in shared/ui/spinner/ .ts file."
    )


def test_when_spinner_ts_read_then_standalone_is_not_opted_out():
    """Spinner component must not opt out of standalone mode.

    CLAUDE.md: Angular 21 components are standalone by default — must NOT set
    standalone: false.
    """
    ts = _primary_ts(SPINNER_DIR).read_text(encoding="utf-8")
    assert "standalone: false" not in ts, (
        "shared/ui/spinner/ .ts file must not contain 'standalone: false'."
    )


def test_when_spinner_folder_inspected_then_ts_html_and_css_files_exist():
    """Spinner is split into spinner.ts + spinner.html + spinner.css, wired by URL."""
    for name in ("spinner.ts", "spinner.html", "spinner.css"):
        assert (SPINNER_DIR / name).is_file(), f"Expected shared/ui/spinner/{name}"
    ts = (SPINNER_DIR / "spinner.ts").read_text(encoding="utf-8")
    assert "templateUrl: './spinner.html'" in ts
    assert "styleUrl: './spinner.css'" in ts
    assert not re.search(r"\btemplate:\s*`", ts), "Spinner must not use an inline template"
    assert not re.search(r"\bstyles:\s*[\[`]", ts), "Spinner must not use inline styles"


def test_when_spinner_ts_read_then_selector_and_label_input_are_kept():
    """Public API: app-spinner selector and the `label` signal input with its default."""
    ts = (SPINNER_DIR / "spinner.ts").read_text(encoding="utf-8")
    assert "selector: 'app-spinner'" in ts
    assert re.search(r"\blabel\s*=\s*input\('Loading…'\)", ts)
    assert "standalone:" not in ts


def test_when_spinner_css_read_then_label_type_and_color_come_from_tokens():
    """The label uses M3 type and color tokens; no color literals or overrides."""
    css = _spinner_css()
    for token in (
        "var(--mat-sys-body-medium)",
        "var(--mat-sys-body-medium-tracking)",
        "var(--mat-sys-on-surface-variant)",
    ):
        assert token in css, f"Expected {token} in spinner.css"
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", css)
    assert "!important" not in css
    assert "::ng-deep" not in css


def test_when_spinner_source_read_then_no_tailwind_utility_classes_remain():
    """No Tailwind utilities remain in spinner.ts, spinner.html or spinner.css."""
    assert not re.search(
        r"\b(motion-safe:|motion-reduce:|animate-spin|sr-only|inline-flex|text-(xs|sm|base)|[hw]-[0-9])",
        (SPINNER_DIR / "spinner.ts").read_text(encoding="utf-8")
        + (SPINNER_DIR / "spinner.html").read_text(encoding="utf-8"),
    )


# ===========================================================================
# Skeleton
# ===========================================================================
# Criterion: Skeleton shimmer (skeleton.css keyframes on tokens), no layout shift
# ===========================================================================


def test_when_ui_directory_inspected_then_skeleton_folder_exists():
    """shared/ui/skeleton/ must be a directory.

    Per criterion: 'Skeleton uses .animate-shimmer, no layout shift'.
    Requirements §7: 'Skeleton — promote the existing .animate-shimmer into a
    reusable Skeleton component (line/block/avatar shapes).'
    """
    assert SKELETON_DIR.is_dir(), (
        "Expected shared/ui/skeleton/ to exist as a directory under "
        "templates/frontend/src/app/shared/ui/"
    )


def test_when_skeleton_folder_inspected_then_typescript_source_file_exists():
    """Skeleton folder must contain at least one non-spec .ts source file."""
    non_spec = [f for f in SKELETON_DIR.glob("*.ts") if ".spec." not in f.name]
    assert non_spec, (
        "Expected at least one .ts source file (not .spec.ts) in shared/ui/skeleton/"
    )


def _skeleton_css() -> str:
    return (SKELETON_DIR / "skeleton.css").read_text(encoding="utf-8")


def test_when_skeleton_folder_inspected_then_ts_html_css_are_split_and_wired():
    """Skeleton is split into skeleton.ts + skeleton.html + skeleton.css, wired by URL."""
    for name in ("skeleton.ts", "skeleton.html", "skeleton.css"):
        assert (SKELETON_DIR / name).is_file(), f"Expected shared/ui/skeleton/{name}"
    ts = (SKELETON_DIR / "skeleton.ts").read_text(encoding="utf-8")
    assert "templateUrl: './skeleton.html'" in ts, "Expected templateUrl: './skeleton.html'"
    assert "styleUrl: './skeleton.css'" in ts, "Expected styleUrl: './skeleton.css'"
    assert not re.search(r"\btemplate\s*:", ts), "skeleton.ts must not inline a template"
    assert not re.search(r"\bstyles\s*:", ts), "skeleton.ts must not inline styles"


def test_when_skeleton_css_read_then_shimmer_keyframes_animate_the_placeholder():
    """The shimmer is a CSS animation defined in skeleton.css on surface tokens.

    Per criterion: 'Skeleton shimmer' (formerly the global Tailwind
    .animate-shimmer utility, removed with Tailwind). skeleton.css must define
    @keyframes, apply them with `animation:`, and paint the gradient from
    --mat-sys-surface-container-high toward --mat-sys-surface-container-highest.
    """
    css = _skeleton_css()
    keyframes = re.search(r"@keyframes\s+([\w-]+)", css)
    assert keyframes, "Expected an @keyframes shimmer animation in skeleton.css"
    name = keyframes.group(1)
    assert re.search(rf"animation:\s*{re.escape(name)}\b", css), (
        f"Expected skeleton.css to apply the '{name}' keyframes with `animation:`"
    )
    assert "var(--mat-sys-surface-container-high)" in css
    assert "var(--mat-sys-surface-container-highest)" in css


def test_when_skeleton_css_read_then_reduced_motion_turns_the_shimmer_off():
    """prefers-reduced-motion must stop the shimmer (animation: none) in skeleton.css."""
    css = _skeleton_css()
    block = re.search(
        r"@media[^{]*prefers-reduced-motion:\s*reduce[^{]*\{([\s\S]*?\}\s*)\}", css
    )
    assert block, "Expected a prefers-reduced-motion: reduce media query in skeleton.css"
    assert re.search(r"animation:\s*none", block.group(1)), (
        "Expected `animation: none` inside the reduced-motion media query"
    )


def test_when_skeleton_css_read_then_it_uses_tokens_and_no_color_literals():
    """Shapes take --mat-sys-corner-* tokens; no color literals, !important or ::ng-deep."""
    css = _skeleton_css()
    for token in (
        "var(--mat-sys-corner-extra-small)",
        "var(--mat-sys-corner-medium)",
        "var(--mat-sys-corner-full)",
    ):
        assert token in css, f"Expected {token} in skeleton.css"
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", css), (
        "skeleton.css must not contain color literals; use --mat-sys-* tokens."
    )
    assert "!important" not in css, "skeleton.css must not use !important"
    assert "::ng-deep" not in css, "skeleton.css must not use ::ng-deep"


def test_when_skeleton_template_read_then_placeholder_is_hidden_from_screen_readers():
    """The placeholder is decorative: skeleton.html marks it aria-hidden="true"."""
    html = (SKELETON_DIR / "skeleton.html").read_text(encoding="utf-8")
    assert 'aria-hidden="true"' in html, 'Expected aria-hidden="true" in skeleton.html'


def test_when_skeleton_source_read_then_explicit_dimensions_are_declared():
    """Skeleton must reserve explicit width/height so it does not cause layout shift.

    Per criterion: 'no layout shift'. A placeholder that does not declare
    dimensions causes cumulative layout shift (CLS) when content loads. The
    component exposes `width`/`height` signal inputs (CSS lengths). skeleton.html
    binds the placeholder's [style.inline-size]/[style.block-size] to computed()
    signals derived from them; the block size skips the avatar, so an avatar keeps
    one diameter and stays a circle. skeleton.css gives every shape a default
    px block size.
    """
    src = _read_dir(SKELETON_DIR)
    assert re.search(r"\bwidth\s*=\s*input[<(]", src), "Expected a `width` signal input"
    assert re.search(r"\bheight\s*=\s*input[<(]", src), "Expected a `height` signal input"

    html = (SKELETON_DIR / "skeleton.html").read_text(encoding="utf-8")
    ts = (SKELETON_DIR / "skeleton.ts").read_text(encoding="utf-8")
    inline = re.search(r"\[style\.inline-size\]\s*=\s*\"(\w+)\(\)\"", html)
    block = re.search(r"\[style\.block-size\]\s*=\s*\"(\w+)\(\)\"", html)
    assert inline, "Expected skeleton.html to bind the placeholder's [style.inline-size]"
    assert block, "Expected skeleton.html to bind the placeholder's [style.block-size]"

    def computed_body(name: str) -> str:
        found = re.search(rf"\b{name}\s*=\s*computed\(([\s\S]*?)\);", ts)
        assert found, f"Expected `{name}` to be a computed() signal in skeleton.ts"
        return found.group(1)

    assert "this.width()" in computed_body(inline.group(1)), (
        "Expected the placeholder's inline size to come from width()"
    )
    block_body = computed_body(block.group(1))
    assert "this.height()" in block_body, (
        "Expected the placeholder's block size to come from height()"
    )
    assert "'avatar'" in block_body, (
        "Expected the block size to skip the avatar so it keeps one diameter"
    )
    css = _skeleton_css()
    assert re.search(r"block-size:\s*\d+px", css), (
        "Expected skeleton.css to give the placeholder a default px block-size"
    )


def test_when_skeleton_ts_read_then_onpush_change_detection_is_set():
    """Skeleton component must declare ChangeDetectionStrategy.OnPush."""
    ts = _primary_ts(SKELETON_DIR).read_text(encoding="utf-8")
    assert "ChangeDetectionStrategy.OnPush" in ts, (
        "Expected 'ChangeDetectionStrategy.OnPush' in shared/ui/skeleton/ .ts file."
    )


def test_when_skeleton_ts_read_then_standalone_is_not_opted_out():
    """Skeleton component must not opt out of standalone mode."""
    ts = _primary_ts(SKELETON_DIR).read_text(encoding="utf-8")
    assert "standalone: false" not in ts, (
        "shared/ui/skeleton/ .ts file must not contain 'standalone: false'."
    )


# ===========================================================================
# Badge
# ===========================================================================
# Criterion: Badge variants via tokens, dark-mode aware. After the Material 3
# migration the variants live in badge.css as --mat-sys-* / --app-* token
# pairs (emitted as light-dark(), so dark mode follows), which is statically
# checkable.
# ===========================================================================

BADGE_DIR = UI_ROOT / "badge"

BADGE_VARIANT_TOKENS = {
    "primary": ("--mat-sys-primary-container", "--mat-sys-on-primary-container"),
    "info": ("--app-info-container", "--app-on-info-container"),
    "success": ("--app-success-container", "--app-on-success-container"),
    "warning": ("--app-warning-container", "--app-on-warning-container"),
    "danger": ("--mat-sys-error-container", "--mat-sys-on-error-container"),
}


def _badge_css() -> str:
    return (BADGE_DIR / "badge.css").read_text(encoding="utf-8")


def test_when_badge_folder_inspected_then_ts_html_and_css_files_exist():
    """Badge is split into badge.ts + badge.html + badge.css, wired by URL."""
    for name in ("badge.ts", "badge.html", "badge.css"):
        assert (BADGE_DIR / name).is_file(), f"Expected shared/ui/badge/{name}"
    ts = (BADGE_DIR / "badge.ts").read_text(encoding="utf-8")
    assert "templateUrl: './badge.html'" in ts
    assert "styleUrl: './badge.css'" in ts
    assert not re.search(r"\btemplate:\s*`", ts), "Badge must not use an inline template"
    assert not re.search(r"\bstyles:\s*[\[`]", ts), "Badge must not use inline styles"


def test_when_badge_ts_read_then_selector_variant_input_and_onpush_are_kept():
    """Public API: app-badge selector, `variant` signal input, OnPush, standalone."""
    ts = (BADGE_DIR / "badge.ts").read_text(encoding="utf-8")
    assert "selector: 'app-badge'" in ts
    assert re.search(r"\bvariant\s*=\s*input<BadgeVariant>\(", ts)
    assert "ChangeDetectionStrategy.OnPush" in ts
    assert "standalone:" not in ts
    for variant in ("default", "primary", "info", "success", "warning", "danger"):
        assert f"'{variant}'" in ts, f"BadgeVariant must still include '{variant}'"


@pytest.mark.parametrize("variant", sorted(BADGE_VARIANT_TOKENS))
def test_when_badge_css_read_then_variant_uses_container_token_pair(variant):
    """Each variant paints a container / on-container token pair (dark-mode aware)."""
    css = _badge_css()
    match = re.search(
        r":host\(\[data-variant=['\"]?" + variant + r"['\"]?\]\)\s*\{([^}]*)\}", css
    )
    assert match, f"Expected a :host([data-variant='{variant}']) rule in badge.css"
    container, on_container = BADGE_VARIANT_TOKENS[variant]
    assert f"var({container})" in match.group(1)
    assert f"var({on_container})" in match.group(1)


def test_when_badge_css_read_then_type_and_shape_come_from_tokens():
    """Label type, pill shape and the neutral default all come from --mat-sys-* tokens."""
    css = _badge_css()
    for token in (
        "var(--mat-sys-label-medium)",
        "var(--mat-sys-label-medium-tracking)",
        "var(--mat-sys-corner-full)",
        "var(--mat-sys-surface-container-highest)",
        "var(--mat-sys-on-surface-variant)",
    ):
        assert token in css, f"Expected {token} in badge.css"


def test_when_badge_css_read_then_no_color_literals_important_or_ng_deep():
    """Replaces the old `dark:`/utility checks: tokens only, no literals or overrides."""
    css = _badge_css()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", css)
    assert "!important" not in css
    assert "::ng-deep" not in css


def test_when_badge_source_read_then_no_tailwind_utility_classes_remain():
    """The Tailwind class map is gone from badge.ts and badge.html."""
    src = "\n".join(
        (BADGE_DIR / name).read_text(encoding="utf-8") for name in ("badge.ts", "badge.html")
    )
    assert not re.search(
        r"\b(inline-flex|items-center|rounded-full|px-2|py-0\.5|text-xs|font-medium|bg-|text-(primary|info|success|warning|danger|secondary))\b",
        src,
    )


@pytest.mark.parametrize(
    ("variant", "icon"),
    [
        ("info", "info"),
        ("success", "circle-check-big"),
        ("warning", "triangle-alert"),
        ("danger", "circle-alert"),
    ],
)
def test_when_badge_ts_read_then_status_variants_have_an_icon_not_color_alone(variant, icon):
    """Each status variant maps to its own leading icon, so status never rests on color.

    Matches the variant-to-icon entry, not the bare icon name: 'info' alone also
    appears in the BadgeVariant union and would pass with the icon removed.
    """
    ts = (BADGE_DIR / "badge.ts").read_text(encoding="utf-8")
    assert re.search(rf"\b{variant}:\s*'{icon}'", ts), (
        f"Expected badge.ts to map the {variant} variant to the {icon} icon"
    )


def test_when_badge_css_read_then_label_wraps_without_collapsing_min_content():
    """Long labels wrap at 200% text, but short words stay whole in a tight flex row.

    overflow-wrap: anywhere adds its break points to min-content, so a badge in a
    nowrap row could shrink to one glyph; break-word keeps min-content at word width.
    """
    css = _badge_css()
    match = re.search(r"\.label\s*\{([^}]*)\}", css)
    assert match, "Expected a .label rule in badge.css"
    assert re.search(r"overflow-wrap:\s*break-word", match.group(1))
    assert "anywhere" not in match.group(1)
    assert not re.search(r"(?<![-\w])(block-size|height)\s*:", css), (
        "No fixed height: text must not clip"
    )


# ===========================================================================
# Alert
# ===========================================================================
# Criterion: Alert: `role="alert"`, variant (info/success/warning/danger) via tokens
# ===========================================================================


def test_when_ui_directory_inspected_then_alert_folder_exists():
    """shared/ui/alert/ must be a directory.

    Per criterion: 'Alert: role="alert", variant (info/success/warning/danger) via tokens'.
    Requirements §7: 'Alert — semantic color tokens (danger/success/warning/info),
    role="alert" for errors.'
    """
    assert ALERT_DIR.is_dir(), (
        "Expected shared/ui/alert/ to exist as a directory under "
        "templates/frontend/src/app/shared/ui/"
    )


def test_when_alert_folder_inspected_then_typescript_source_file_exists():
    """Alert folder must contain at least one non-spec .ts source file."""
    non_spec = [f for f in ALERT_DIR.glob("*.ts") if ".spec." not in f.name]
    assert non_spec, (
        "Expected at least one .ts source file (not .spec.ts) in shared/ui/alert/"
    )


def _read_alert_sources() -> str:
    """Return the Alert component's .ts + .html + .css sources (specs excluded)."""
    parts: list[str] = []
    for ext in ("*.ts", "*.html", "*.css"):
        for f in sorted(ALERT_DIR.glob(ext)):
            if ".spec." not in f.name:
                parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_when_alert_folder_inspected_then_template_and_stylesheet_are_separate_files():
    """Alert must be split into alert.ts + alert.html + alert.css.

    The .ts wires them with templateUrl/styleUrl and carries no inline
    template or styles.
    """
    ts = (ALERT_DIR / "alert.ts").read_text(encoding="utf-8")
    assert (ALERT_DIR / "alert.html").is_file(), "Expected shared/ui/alert/alert.html"
    assert (ALERT_DIR / "alert.css").is_file(), "Expected shared/ui/alert/alert.css"
    assert "templateUrl: './alert.html'" in ts, "Expected templateUrl: './alert.html'"
    assert "styleUrl: './alert.css'" in ts, "Expected styleUrl: './alert.css'"
    assert not re.search(r"\btemplate\s*:", ts), "alert.ts must not use an inline template"
    assert not re.search(r"\bstyles\s*:", ts), "alert.ts must not use inline styles"


def test_when_alert_source_read_then_live_region_role_is_alert_for_danger_and_status_otherwise():
    """Alert's message must be a live region: role="alert" for danger, role="status" otherwise.

    Per criterion: 'Alert: `role="alert"`'. Material 3 has no alert component; the
    banner pattern is a persistent, non-blocking status built with role="status"
    (material-3-angular mapping §6). role="alert" is an assertive live region that
    interrupts the user, so it is reserved for the danger variant.
    """
    ts = (ALERT_DIR / "alert.ts").read_text(encoding="utf-8")
    html = (ALERT_DIR / "alert.html").read_text(encoding="utf-8")
    assert re.search(r"danger:\s*\{[^}]*role:\s*'alert'", ts), (
        "Expected the danger variant to map to role 'alert' in shared/ui/alert/alert.ts."
    )
    for variant in ("info", "success", "warning"):
        assert re.search(rf"{variant}:\s*\{{[^}}]*role:\s*'status'", ts), (
            f"Expected the {variant} variant to map to role 'status' in shared/ui/alert/alert.ts."
        )
    assert re.search(r'\[attr\.role\]="role\(\)"', html), (
        "Expected the message region in alert.html to bind [attr.role]=\"role()\"."
    )


def test_when_alert_source_read_then_each_variant_has_a_leading_icon():
    """Color is never the only signal: every variant maps to its own lucide icon."""
    ts = (ALERT_DIR / "alert.ts").read_text(encoding="utf-8")
    html = (ALERT_DIR / "alert.html").read_text(encoding="utf-8")
    icons = re.findall(r"icon:\s*'(\w+)'", ts)
    assert len(icons) == 4 and len(set(icons)) == 4, (
        f"Expected four distinct variant icons in alert.ts, found {icons}."
    )
    assert re.search(r'<lucide-icon\s+class="alert-icon"', html), (
        "Expected a leading <lucide-icon class=\"alert-icon\"> in alert.html."
    )


def test_when_alert_css_read_then_variants_use_status_container_tokens():
    """Variants paint M3 / --app-* container roles with their on-container content roles.

    info/success/warning use the app status roles; danger uses --mat-sys-error-container.
    The stylesheet holds no color literals, !important or ::ng-deep.
    """
    css = (ALERT_DIR / "alert.css").read_text(encoding="utf-8")
    for status in ("info", "success", "warning"):
        assert f"var(--app-{status}-container)" in css, f"Missing --app-{status}-container"
        assert f"var(--app-on-{status}-container)" in css, f"Missing --app-on-{status}-container"
    assert "var(--mat-sys-error-container)" in css, "Missing --mat-sys-error-container"
    assert "var(--mat-sys-on-error-container)" in css, "Missing --mat-sys-on-error-container"
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", css), (
        "alert.css must not contain color literals; use --mat-sys-* / --app-* tokens."
    )
    assert "!important" not in css, "alert.css must not use !important"
    assert "::ng-deep" not in css, "alert.css must not use ::ng-deep"


def test_when_alert_template_read_then_dismiss_is_a_labelled_material_icon_button():
    """The optional dismiss control is a matIconButton (48px touch target) with an aria-label."""
    html = (ALERT_DIR / "alert.html").read_text(encoding="utf-8")
    assert "matIconButton" in html, "Expected the dismiss control to be a matIconButton."
    assert 'type="button"' in html, "Expected the dismiss control to be type=\"button\"."
    assert '[attr.aria-label]="dismissLabel()"' in html, (
        "Expected the dismiss button to take its accessible name from dismissLabel()."
    )


def test_when_alert_source_read_then_no_tailwind_utility_classes_remain():
    """Alert template and TypeScript carry no Tailwind utility classes."""
    tailwind = re.compile(
        r"\b(flex|inline-flex|grid-cols|items-|justify-|gap-[0-9]|p[xytblr]?-[0-9]|"
        r"m[xytblr]?-[0-9]|w-[0-9]|h-[0-9]|min-h-|max-w-|text-(xs|sm|base|lg|xl|[0-9])|"
        r"font-(medium|semibold|bold|display|sans|mono)|bg-|border-|rounded|shadow|ring-|"
        r"dark:|md:|lg:|sm:|xl:|hover:|focus:|animate-|sr-only|truncate|space-[xy]-|"
        r"divide-|opacity-[0-9]|transition-|duration-)"
    )
    for name in ("alert.ts", "alert.html"):
        src = (ALERT_DIR / name).read_text(encoding="utf-8")
        match = tailwind.search(src)
        assert match is None, f"Tailwind residue {match.group(0)!r} in shared/ui/alert/{name}"


def test_when_alert_ts_read_then_variant_signal_input_is_declared():
    """Alert must declare a signal input named 'variant'.

    Per criterion: 'Alert: role="alert", variant (info/success/warning/danger) via tokens'.
    CLAUDE.md: 'Signals for state: Use signal(), computed(), input(), output()'.
    """
    ts = _primary_ts(ALERT_DIR).read_text(encoding="utf-8")
    assert re.search(r"\bvariant\s*=\s*input[<(]", ts), (
        "Expected a signal input named 'variant' in shared/ui/alert/ .ts, "
        "e.g. `readonly variant = input('info')`. "
        "Per criterion: 'Alert: role=\"alert\", variant (info/success/warning/danger)'."
    )


@pytest.mark.parametrize("variant", ["info", "success", "warning", "danger"])
def test_when_alert_source_read_then_variant_value_is_referenced(variant):
    """Each of the four Alert variant values must appear in the component source.

    Per criterion: 'Alert: role="alert", variant (info/success/warning/danger)'.
    The variant names must appear in the .ts (type union or variant map), the
    .html template, or the .css as variant selectors.
    """
    combined = _read_alert_sources()
    assert variant in combined, (
        f"Expected the variant value '{variant}' in the Alert component source "
        f"(.ts, .html or .css). Per criterion: 'variant (info/success/warning/danger)'."
    )


def test_when_alert_ts_read_then_onpush_change_detection_is_set():
    """Alert component must declare ChangeDetectionStrategy.OnPush."""
    ts = _primary_ts(ALERT_DIR).read_text(encoding="utf-8")
    assert "ChangeDetectionStrategy.OnPush" in ts, (
        "Expected 'ChangeDetectionStrategy.OnPush' in shared/ui/alert/ .ts file."
    )


def test_when_alert_ts_read_then_standalone_is_not_opted_out():
    """Alert component must not opt out of standalone mode."""
    ts = _primary_ts(ALERT_DIR).read_text(encoding="utf-8")
    assert "standalone: false" not in ts, (
        "shared/ui/alert/ .ts file must not contain 'standalone: false'."
    )
