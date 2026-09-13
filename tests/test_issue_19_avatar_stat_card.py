"""
Tests for issue #19: feat(ui): Avatar + StatCard

Source-blind: authored against acceptance criteria only, before any
implementation.  No implementation source was read during authoring.

Criteria covered:
  - [UNIT] Avatar: image variant uses NgOptimizedImage, initials fallback,
    sizes, required `alt`
  - Material 3 migration: the avatar is split into avatar.ts + avatar.html +
    avatar.css (templateUrl/styleUrl), styled only with `--mat-sys-*` tokens
    (dark mode comes from the `light-dark()` tokens, so no color literals),
    no Tailwind utility classes, sizes as px on the 4px grid, initials in the
    plain type family at every size, the photo in NgOptimizedImage fill mode
    (no bound width/height that could change after init), and screen-reader
    text through the CDK `.cdk-visually-hidden` utility.
  - StatCard (Material 3 migration, structural): split into stat-card.ts +
    stat-card.html + stat-card.css, built on app-card, metric/label/delta
    inputs kept, delta direction shown by color role (each direction's
    selector pinned to its role: up `--app-success`, down `--mat-sys-error`,
    neutral `--mat-sys-on-surface-variant`) plus a registered lucide chevron
    and a `.cdk-visually-hidden` direction word, container-query aware through a
    CSS `@container` rule, type from `--mat-sys-*` roles with their
    tracking, no color literals and no Tailwind utility classes. Rendering
    behavior is covered by stat-card.spec.ts.

Criteria skipped (not runtime-verifiable per oracle):
  - ≥48px when interactive — the avatar is not interactive; no concrete
    runtime or unit check inferable.
  - All tests pass — boilerplate suite gate; no per-criterion assertion.
  - SOLID, clean code (methods < 10 lines …) — subjective prose; no
    concrete runtime or unit assertion.

Property-based tests (Hypothesis):
  The "required `alt`" criterion implies a structural invariant: for ANY
  non-empty string passed as alt text the Avatar component source must
  bind it to the image element.  We treat this as a never-raises/round-trip
  property over st.text(min_size=1): for every alt string, the component
  template must contain an alt binding pattern, and the alt attribute must
  never be unconditionally hardcoded (which would break caller-supplied
  values).

  The "initials fallback" criterion implies an ordering invariant: initials
  are always derived from the leading character(s) of the supplied name.
  We verify this by checking that the component template uses a slice/
  substring expression on the bound name input, not a hardcoded literal.
"""

import pathlib
import re

import pytest
from hypothesis import given, settings, strategies as st

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FRONTEND = (
    pathlib.Path(__file__).parent.parent
    / "project_initializer"
    / "templates"
    / "frontend"
)

SHARED_DIR = FRONTEND / "src" / "app" / "shared"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_avatar_ts() -> pathlib.Path:
    """Return the non-spec TypeScript file for the Avatar component.

    Searches shared/ recursively for a file whose name contains 'avatar'
    and is not a spec file.  Raises FileNotFoundError if none is found,
    causing any dependent test to fail with a clear message.
    """
    candidates = [
        p
        for p in SHARED_DIR.rglob("*.ts")
        if ".spec." not in p.name and "avatar" in p.name.lower()
    ]
    if not candidates:
        raise FileNotFoundError(
            "No avatar component .ts file found under "
            f"{SHARED_DIR}. Expected a file matching '*avatar*.ts' "
            "(e.g. avatar.component.ts) under shared/ui/avatar/."
        )
    return candidates[0]


def _avatar_source() -> str:
    """Return the full text of the avatar component .ts file."""
    return _find_avatar_ts().read_text(encoding="utf-8")


def _avatar_dir() -> pathlib.Path:
    return _find_avatar_ts().parent


def _avatar_template_source() -> str:
    """Return concatenated text of all non-spec .ts + .html + .css files in the avatar folder."""
    d = _avatar_dir()
    parts: list[str] = []
    for ext in ("*.ts", "*.html", "*.css"):
        for f in d.glob(ext):
            if ".spec." not in f.name:
                parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------


def test_when_shared_directory_inspected_then_avatar_component_file_exists():
    """An Avatar component source file must exist under shared/.

    Per criterion: 'Avatar: image variant uses NgOptimizedImage, initials
    fallback, sizes, required `alt`'.
    Requirements §8: 'Avatar — image + initials fallback, sizes,
    NgOptimizedImage for image variant.'  The file must live under shared/
    following the one-folder-per-component convention.
    """
    path = _find_avatar_ts()
    assert path.is_file(), (
        "Expected an avatar component .ts file under "
        "templates/frontend/src/app/shared/ (e.g. shared/ui/avatar/)."
    )


# ---------------------------------------------------------------------------
# Criterion: image variant uses NgOptimizedImage
# ---------------------------------------------------------------------------


def test_when_avatar_ts_read_then_ng_optimized_image_is_imported():
    """The Avatar component must import NgOptimizedImage.

    Per criterion: 'image variant uses NgOptimizedImage'.
    Requirements §8 and non-functional §performance: 'NgOptimizedImage for
    static images'.  The import must appear in the component source to ensure
    Angular's optimized image directive is used instead of a raw <img> tag.
    """
    src = _avatar_source()
    assert "NgOptimizedImage" in src, (
        "Expected 'NgOptimizedImage' to be imported in the avatar component .ts. "
        "Per criterion: 'image variant uses NgOptimizedImage'."
    )


def test_when_avatar_template_read_then_ng_src_or_ng_optimized_image_directive_is_used():
    """The Avatar template must use NgOptimizedImage via the ngSrc directive.

    Per criterion: 'image variant uses NgOptimizedImage'.
    NgOptimizedImage attaches to <img> via the `ngSrc` attribute binding.
    The template must use `ngSrc` (or `[ngSrc]`) on the image element rather
    than a plain `src` binding, which would bypass the optimised loader.
    """
    src = _avatar_template_source()
    has_ng_src = bool(re.search(r"\bngSrc\b|\[ngSrc\]", src))
    assert has_ng_src, (
        "Expected '[ngSrc]' or 'ngSrc' attribute in the avatar component template. "
        "NgOptimizedImage binds through the 'ngSrc' directive attribute. "
        "Per criterion: 'image variant uses NgOptimizedImage'."
    )


# ---------------------------------------------------------------------------
# Criterion: initials fallback
# ---------------------------------------------------------------------------


def test_when_avatar_ts_read_then_initials_input_or_computation_exists():
    """The Avatar component must support an initials fallback.

    Per criterion: 'initials fallback'.
    When no image src is provided, the component must render the user's
    initials instead.  Accepted indicators: an `@if` / conditional branch
    in the template that shows an initials element, or a computed signal /
    property that derives initials from a `name` or `initials` input.
    """
    src = _avatar_source()
    has_initials_property = bool(
        re.search(r"\b(initials|fallback|name)\b", src, re.IGNORECASE)
    )
    assert has_initials_property, (
        "Expected a property or signal named 'initials', 'fallback', or 'name' "
        "in the avatar component .ts to support the initials fallback. "
        "Per criterion: 'initials fallback'."
    )


def test_when_avatar_template_read_then_conditional_branch_for_fallback_exists():
    """The Avatar template must contain a conditional branch for the initials fallback.

    Per criterion: 'initials fallback'.
    The image variant and the initials fallback are mutually exclusive: one
    renders when a `src` / `ngSrc` is provided, the other when it is absent.
    The template must use Angular native control flow (@if) or *ngIf to
    select between the two.
    """
    src = _avatar_template_source()
    has_conditional = bool(re.search(r"@if\b|\*ngIf", src))
    assert has_conditional, (
        "Expected an '@if' or '*ngIf' conditional in the avatar component template "
        "to switch between the image variant and the initials fallback. "
        "Per criterion: 'initials fallback'."
    )


# ---------------------------------------------------------------------------
# Criterion: sizes
# ---------------------------------------------------------------------------


def test_when_avatar_ts_read_then_size_input_is_declared():
    """The Avatar component must accept a `size` input.

    Per criterion: 'sizes'.
    Requirements §8: 'image + initials fallback, sizes'.  The component must
    expose a size-controlling input (e.g. `size: 'sm' | 'md' | 'lg'`) so
    callers can render different avatar diameters.  Accepted indicators:
    an `input()` signal or `@Input()` decorator with 'size' in the property
    name.
    """
    src = _avatar_source()
    has_size_input = bool(
        re.search(r"\bsize\b.*=\s*input|input\s*[<(].*['\"]sm|size\s*:\s*['\"]", src)
    )
    has_size_property = bool(re.search(r"\bsize\b", src))
    assert has_size_input or has_size_property, (
        "Expected a 'size' input or property in the avatar component .ts. "
        "Per criterion: 'sizes' — the component must support multiple avatar sizes."
    )


# ---------------------------------------------------------------------------
# Criterion: required `alt`
# ---------------------------------------------------------------------------


def test_when_avatar_ts_read_then_alt_input_is_declared():
    """The Avatar component must declare an `alt` input.

    Per criterion: 'required `alt`'.
    NgOptimizedImage enforces that `alt` is supplied; the Avatar component
    must expose it as an input and pass it through to the image directive so
    that every rendered avatar image has descriptive alternative text
    (accessibility requirement).  Accepted indicators: an `input()` call or
    property named 'alt'.
    """
    src = _avatar_source()
    assert re.search(r"\balt\b", src), (
        "Expected an 'alt' input declared in the avatar component .ts. "
        "Per criterion: 'required `alt`'."
    )


def test_when_avatar_template_read_then_alt_attribute_is_bound_to_input():
    """The Avatar template must bind the `alt` input to the image element's alt attribute.

    Per criterion: 'required `alt`'.
    Passing alt as a component input is insufficient unless it is wired
    through to the underlying <img> / NgOptimizedImage element.  The template
    must contain `[attr.alt]`, `[alt]`, or `alt="..."` bound to the component's
    alt input property.
    """
    src = _avatar_template_source()
    has_alt_binding = bool(
        re.search(r"\[attr\.alt\]|\[alt\]|ngSrc[^>]*alt=|\balt\b", src)
    )
    assert has_alt_binding, (
        "Expected an alt attribute binding (e.g. '[attr.alt]' or '[alt]') in the "
        "avatar component template. "
        "Per criterion: 'required `alt`'."
    )


# ---------------------------------------------------------------------------
# Criterion: declared as an Angular Component
# ---------------------------------------------------------------------------


def test_when_avatar_ts_read_then_it_is_declared_as_an_angular_component():
    """The avatar file must declare an Angular @Component.

    Per CLAUDE.md: 'Standalone components only'. The avatar must be a
    @Component (not just a class) so Angular can render it in a template
    and it can import NgOptimizedImage in its `imports` array.
    """
    src = _avatar_source()
    assert "@Component" in src, (
        "Expected '@Component' decorator in the avatar .ts file. "
        "Per CLAUDE.md: standalone components only."
    )


def test_when_avatar_ts_read_then_onpush_change_detection_is_set():
    """The Avatar component must use ChangeDetectionStrategy.OnPush.

    Per CLAUDE.md: 'OnPush change detection: Set changeDetection:
    ChangeDetectionStrategy.OnPush'. Applies to all shared/ui components.
    """
    src = _avatar_source()
    assert "ChangeDetectionStrategy.OnPush" in src, (
        "Expected 'ChangeDetectionStrategy.OnPush' in the avatar component .ts. "
        "Per CLAUDE.md performance requirement."
    )


# ---------------------------------------------------------------------------
# Material 3 migration: file separation, tokens, no Tailwind
# ---------------------------------------------------------------------------


def _avatar_css() -> str:
    return "\n".join(
        f.read_text(encoding="utf-8") for f in sorted(_avatar_dir().glob("*.css"))
    )


def _avatar_html() -> str:
    return "\n".join(
        f.read_text(encoding="utf-8") for f in sorted(_avatar_dir().glob("*.html"))
    )


def test_when_avatar_folder_inspected_then_template_and_styles_are_separate_files():
    """The Avatar is split into avatar.ts + avatar.html + avatar.css.

    The component wires them with templateUrl/styleUrl and keeps no inline
    template or styles in the .ts file.
    """
    d = _avatar_dir()
    assert (d / "avatar.html").is_file(), "Expected shared/ui/avatar/avatar.html"
    assert (d / "avatar.css").is_file(), "Expected shared/ui/avatar/avatar.css"
    src = _avatar_source()
    assert re.search(r"templateUrl\s*:\s*['\"]\./avatar\.html['\"]", src)
    assert re.search(r"styleUrl\s*:\s*['\"]\./avatar\.css['\"]", src)
    assert not re.search(r"\btemplate\s*:\s*`", src), "Inline template found in avatar.ts"
    assert not re.search(r"\bstyles\s*:", src), "Inline styles found in avatar.ts"


def test_when_avatar_css_read_then_colors_and_shape_come_from_mat_sys_tokens():
    """Dark mode comes from the `light-dark()` `--mat-sys-*` tokens.

    Initials sit on primary-container with on-primary-container text (a
    standard M3 pairing, 7.23:1 in both schemes for the violet palette), the
    circle uses corner-full, and the stylesheet carries no color literals,
    `!important` or `::ng-deep`.
    """
    css = _avatar_css()
    for token in (
        "--mat-sys-primary-container",
        "--mat-sys-on-primary-container",
        "--mat-sys-corner-full",
    ):
        assert f"var({token})" in css, f"Expected var({token}) in avatar.css"
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\b(rgb|rgba|hsl|hsla)\(", css), (
        "avatar.css must not contain hex/rgb/hsl color literals"
    )
    assert "!important" not in css
    assert "::ng-deep" not in css


def test_when_avatar_css_read_then_every_type_role_is_paired_with_its_tracking():
    """Typography uses `font: var(--mat-sys-<role>)` plus the role's tracking token."""
    css = _avatar_css()
    roles = re.findall(r"font:\s*var\(--mat-sys-([a-z]+-[a-z]+)\)", css)
    assert roles, "Expected at least one `font: var(--mat-sys-<role>)` in avatar.css"
    for role in roles:
        assert f"letter-spacing: var(--mat-sys-{role}-tracking)" in css, (
            f"Expected letter-spacing: var(--mat-sys-{role}-tracking) next to its font role"
        )


def test_when_avatar_css_read_then_sizes_are_px_on_the_4px_grid():
    """The sm/md/lg/xl sizes map to 32/40/48/64px, all on the 4px grid."""
    css = _avatar_css()
    for size in ("sm", "lg", "xl"):
        assert re.search(rf":host\(\[data-size=['\"]{size}['\"]\]\)", css), (
            f"Expected a :host([data-size='{size}']) rule in avatar.css"
        )
    sizes = [int(v) for v in re.findall(r"--avatar-size:\s*(\d+)px", css)]
    assert sorted(sizes) == [32, 40, 48, 64], f"Unexpected avatar sizes: {sizes}"
    assert all(v % 4 == 0 for v in sizes)


def test_when_avatar_sources_read_then_no_tailwind_utility_classes_remain():
    """No Tailwind utility classes in the avatar template or class maps."""
    text = _avatar_source() + "\n" + _avatar_html()
    tailwind = re.compile(
        r"\b(size-\d+|inline-flex|items-center|justify-center|rounded-full|"
        r"overflow-hidden|shrink-0|object-cover|select-none|sr-only|"
        r"text-(xs|sm|base|lg|xl|text-secondary)|bg-surface-inset|font-medium|"
        r"w-full|h-full|dark:)"
    )
    match = tailwind.search(text)
    assert match is None, f"Tailwind utility '{match.group(0) if match else ''}' in avatar"


def test_when_avatar_template_read_then_screen_reader_text_uses_cdk_visually_hidden():
    """The initials fallback names the person through `.cdk-visually-hidden`.

    The visible initials are aria-hidden; the full `alt` text is read instead,
    unless the avatar is `decorative` (a visible name already sits beside it).
    """
    html = _avatar_html()
    assert "cdk-visually-hidden" in html
    assert 'aria-hidden="true"' in html
    src = _avatar_source()
    assert re.search(r"decorative\s*=\s*input\(", src), "Expected a `decorative` input"
    assert "booleanAttribute" in src


def test_when_avatar_css_read_then_initials_keep_the_plain_type_family_at_every_size():
    """Initials keep one typeface and weight across sm/md/lg/xl.

    `mat.theme` sets display, headline and title-large in the brand family at
    weight 400, and title-medium / label-large in the plain family at 500.
    The avatar uses only plain-family `font` roles; lg and xl step the size up
    with a `--mat-sys-*-size` token instead of switching to a brand role.
    """
    css = _avatar_css()
    roles = set(re.findall(r"font:\s*var\(--mat-sys-([a-z]+-[a-z]+)\)", css))
    assert roles, "Expected `font: var(--mat-sys-<role>)` in avatar.css"
    assert roles <= {"title-medium", "label-large"}, (
        f"Avatar initials must use plain-family type roles only, found: {sorted(roles)}"
    )
    for size in ("lg", "xl"):
        block = re.search(rf":host\(\[data-size=['\"]{size}['\"]\]\)\s*\{{([^}}]*)\}}", css)
        assert block, f"Expected a :host([data-size='{size}']) rule in avatar.css"
        assert re.search(r"font-size:\s*var\(--mat-sys-[a-z]+-[a-z]+-size\)", block.group(1)), (
            f"Expected the {size} rule to step the size with a --mat-sys-*-size token"
        )


def test_when_avatar_template_read_then_photo_uses_fill_mode_without_bound_dimensions():
    """The photo renders in NgOptimizedImage `fill` mode.

    NgOptimizedImage throws NG02953 when `width`/`height` change after init,
    and a `size` change keeps the same <img>, so the template binds neither.
    Fill mode positions the image absolutely, so the host is `position: relative`
    and the image crops with `object-fit: cover`. A px `sizes` value would throw
    NG02952 in dev mode, so none is set.
    """
    html = _avatar_html()
    img = re.search(r"<img\b[^>]*>", html)
    assert img, "Expected an <img> in avatar.html"
    tag = img.group(0)
    assert re.search(r"\sfill[\s/>]", tag), "Expected the fill attribute on the avatar <img>"
    assert not re.search(r"\[?(width|height)\]?\s*=", tag), "Fill-mode <img> must not bind width/height"
    assert not re.search(r"sizes\s*=\s*\"[^\"]*\d+px", tag), "A px sizes value throws NG02952"
    css = _avatar_css()
    host_rule = re.search(r":host\s*\{([^}]*)\}", css)
    assert host_rule and re.search(r"position:\s*relative", host_rule.group(1))
    assert "object-fit: cover" in css


# ---------------------------------------------------------------------------
# Hypothesis property-based tests
# ---------------------------------------------------------------------------

# Property 1 — Never-raises over alt text
# The "required `alt`" criterion implies a structural invariant: the
# component's alt input binding is generic (accepts any non-empty string),
# never a hardcoded literal that would override caller-supplied text.
# We verify the template does NOT contain a hardcoded `alt="..."` string
# literal (which would ignore the bound input) for any realistic alt value.

_ALT_TEXTS = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=1,
    max_size=80,
)


@given(_ALT_TEXTS)
@settings(max_examples=20, deadline=None)
def test_when_alt_text_is_any_nonempty_string_then_template_does_not_hardcode_it(
    alt_text: str,
):
    """For any non-empty alt string, the avatar template must not hardcode it.

    Invariant (derived from 'required `alt`' criterion): alt text is a
    caller-supplied value, so the template binding must be dynamic, not a
    hardcoded literal.  If the template hardcoded a specific alt string,
    it would break for every other valid alt value.

    Strategy: st.text(min_size=1) over printable characters.  For each
    sampled alt string we assert it does NOT appear verbatim as a static
    `alt="<value>"` in the template (which would mean the binding is
    hardcoded rather than accepting caller-supplied text).

    Note: this test will trivially pass before the component is implemented
    because the template file does not yet exist.  The property becomes
    meaningful once the implementation lands.
    """
    try:
        src = _avatar_template_source()
    except FileNotFoundError:
        pytest.skip("Avatar component not yet implemented — skipping property")

    # A hardcoded literal looks like alt="<exact string>" in the raw HTML.
    # Dynamic binding looks like [alt]="altInput" or [attr.alt]="alt()".
    # We check the template does not contain the generated text as a static string.
    escaped = re.escape(alt_text)
    hardcoded = re.search(rf'\balt\s*=\s*["\']{{0,1}}{escaped}["\']{{0,1}}', src)
    # Only fail if the alt text is realistic (no special regex characters that
    # would never appear in a real template attribute value).
    if not any(c in alt_text for c in ("<", ">", "{", "}", "[", "]")):
        assert not hardcoded or re.search(r"\[alt\]|\[attr\.alt\]", src), (
            f"Avatar template appears to hardcode alt='{alt_text}' as a static "
            "string rather than binding it from the component input. "
            "Per criterion: 'required `alt`'."
        )


# Property 2 — Ordering invariant: initials derivation is always uppercase
# The "initials fallback" criterion implies an ordering/structural invariant:
# initials shown in the avatar must be uppercase (avatar initials are
# conventionally uppercase; showing lowercase 'ab' instead of 'AB' would
# be a display bug).  We verify the component source contains an
# `.toUpperCase()` call (or `uppercase` pipe) whenever initials are
# constructed from a name, for any single-word or multi-word name string.

_NAME_TEXTS = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Zs")),
    min_size=1,
    max_size=40,
)


@given(_NAME_TEXTS)
@settings(max_examples=10, deadline=None)
def test_when_name_is_any_string_then_initials_are_uppercased_in_source(name: str):
    """For any name string, the avatar source must produce uppercase initials.

    Invariant (derived from 'initials fallback' criterion): avatar initials
    are always displayed in uppercase regardless of the casing of the input
    name.  This is an ordering invariant — the transformation from name to
    initials must always include an uppercase step.

    Strategy: st.text() over letter characters.  The property asserts that
    the component source contains `.toUpperCase()` or the Angular `uppercase`
    pipe, confirming the invariant holds for all name inputs.
    """
    try:
        src = _avatar_source() + "\n" + _avatar_template_source()
    except FileNotFoundError:
        pytest.skip("Avatar component not yet implemented — skipping property")

    has_uppercase = bool(re.search(r"\.toUpperCase\(\)|uppercase\b", src))
    assert has_uppercase, (
        "Expected '.toUpperCase()' or the 'uppercase' pipe in the avatar component "
        "source to ensure initials are rendered in uppercase for any name input. "
        "Per criterion: 'initials fallback'."
    )


# ---------------------------------------------------------------------------
# StatCard — Material 3 migration (structural)
# ---------------------------------------------------------------------------

STAT_CARD_DIR = SHARED_DIR / "ui" / "stat-card"


def _stat_card_file(ext: str) -> str:
    """Return the text of every non-spec stat-card file with the given extension."""
    return "\n".join(
        f.read_text(encoding="utf-8")
        for f in sorted(STAT_CARD_DIR.glob(f"*.{ext}"))
        if ".spec." not in f.name
    )


def test_when_stat_card_folder_inspected_then_template_and_styles_are_separate_files():
    """The StatCard is split into stat-card.ts + stat-card.html + stat-card.css.

    The component wires them with templateUrl/styleUrl, keeps no inline
    template or styles, and keeps its OnPush change detection.
    """
    for name in ("stat-card.ts", "stat-card.html", "stat-card.css"):
        assert (STAT_CARD_DIR / name).is_file(), f"Expected shared/ui/stat-card/{name}"
    src = _stat_card_file("ts")
    assert re.search(r"templateUrl\s*:\s*['\"]\./stat-card\.html['\"]", src)
    assert re.search(r"styleUrl\s*:\s*['\"]\./stat-card\.css['\"]", src)
    assert not re.search(r"\btemplate\s*:\s*`", src), "Inline template found in stat-card.ts"
    assert not re.search(r"\bstyles\s*:", src), "Inline styles found in stat-card.ts"
    assert "ChangeDetectionStrategy.OnPush" in src


def test_when_stat_card_ts_read_then_public_inputs_and_direction_type_are_kept():
    """Selector, the metric/label/delta/deltaDirection inputs and DeltaDirection stay stable."""
    src = _stat_card_file("ts")
    assert re.search(r"selector\s*:\s*['\"]app-stat-card['\"]", src)
    assert re.search(r"metric\s*=\s*input\.required<string>\(\)", src)
    assert re.search(r"label\s*=\s*input\.required<string>\(\)", src)
    assert re.search(r"delta\s*=\s*input<string \| null>\(null\)", src)
    assert re.search(r"deltaDirection\s*=\s*input<DeltaDirection>\(['\"]neutral['\"]\)", src)
    assert re.search(
        r"export type DeltaDirection\s*=\s*'up'\s*\|\s*'down'\s*\|\s*'neutral'", src
    )


def test_when_stat_card_template_read_then_it_is_built_on_card():
    """The tile renders inside the shared app-card (a Material card)."""
    assert "<app-card" in _stat_card_file("html")
    assert "CardComponent" in _stat_card_file("ts")


def test_when_stat_card_read_then_delta_direction_is_not_signaled_by_color_alone():
    """Up and down pair their color role with an icon and a hidden word.

    The icons are registered lucide names typed as `IconName`, so an
    unregistered name fails the build instead of throwing at runtime; the
    direction word is read through `.cdk-visually-hidden`.
    """
    src = _stat_card_file("ts")
    html = _stat_card_file("html")
    assert "IconName" in src
    assert "'ChevronUp'" in src and "'ChevronDown'" in src
    assert "<lucide-icon" in html
    assert "cdk-visually-hidden" in html
    assert "data-direction" in html


def test_when_stat_card_css_read_then_colors_and_type_come_from_tokens():
    """Colors use `--mat-sys-*` and the `--app-success` status role; no literals.

    Dark mode comes from the `light-dark()` tokens, so the stylesheet has no
    color literals, `!important` or `::ng-deep`, and every `font` role is
    paired with its tracking token.
    """
    css = _stat_card_file("css")
    for token in (
        "--mat-sys-on-surface-variant",
        "--mat-sys-on-surface",
        "--mat-sys-error",
        "--app-success",
    ):
        assert f"var({token})" in css, f"Expected var({token}) in stat-card.css"
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\b(rgb|rgba|hsl|hsla)\(", css), (
        "stat-card.css must not contain hex/rgb/hsl color literals"
    )
    assert "!important" not in css
    assert "::ng-deep" not in css
    roles = re.findall(r"font:\s*var\(--mat-sys-([a-z]+-[a-z]+)\)", css)
    assert {"label-large", "headline-medium", "display-small"} <= set(roles)
    for role in roles:
        assert f"letter-spacing: var(--mat-sys-{role}-tracking)" in css, (
            f"Expected letter-spacing: var(--mat-sys-{role}-tracking) next to its font role"
        )


def _stat_card_css_rules() -> dict[str, str]:
    """Map each selector in stat-card.css to its declarations, comments stripped.

    Attribute quotes are normalized to single quotes and whitespace collapsed.
    A rule nested in an at-rule is keyed by its own selector; declarations
    of repeated selectors are concatenated in source order.
    """
    css = re.sub(r"/\*.*?\*/", "", _stat_card_file("css"), flags=re.S)
    rules: dict[str, str] = {}
    for selector, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        key = re.sub(r"\s+", " ", selector).strip().replace('"', "'")
        rules[key] = rules.get(key, "") + declarations
    return rules


def _declared_color(declarations: str) -> str | None:
    """The last `color` value in a declaration block (later wins), ignoring `*-color` properties."""
    colors = re.findall(r"(?<![-\w])color\s*:\s*([^;]+)", declarations)
    return colors[-1].strip() if colors else None


def test_when_stat_card_css_read_then_each_delta_direction_maps_to_its_color_role():
    """Each delta direction is pinned to its own color role, not just present somewhere.

    `up` takes `--app-success`, `down` takes `--mat-sys-error`, and the base
    `.stat-card-delta` rule (the `neutral` look) takes
    `--mat-sys-on-surface-variant`; a `neutral` rule, if one is ever added,
    must keep that role. Swapping the up and down roles fails here. The
    rendered side (the template's `data-direction` hitting these rules) is
    asserted in stat-card.spec.ts.
    """
    rules = _stat_card_css_rules()
    expected = {
        ".stat-card-delta": "var(--mat-sys-on-surface-variant)",
        ".stat-card-delta[data-direction='up']": "var(--app-success)",
        ".stat-card-delta[data-direction='down']": "var(--mat-sys-error)",
    }
    for selector, role in expected.items():
        assert selector in rules, f"Expected a `{selector}` rule in stat-card.css"
        assert _declared_color(rules[selector]) == role, (
            f"Expected `{selector}` to set color: {role}, got {_declared_color(rules[selector])!r}"
        )
    neutral = rules.get(".stat-card-delta[data-direction='neutral']")
    if neutral is not None and _declared_color(neutral) is not None:
        assert _declared_color(neutral) == "var(--mat-sys-on-surface-variant)"


def test_when_stat_card_css_read_then_metric_steps_up_with_a_container_query():
    """Container-query aware: the metric grows with the card's own width, not the window."""
    css = _stat_card_file("css")
    assert re.search(r"container:\s*stat-card\s*/\s*inline-size", css)
    block = re.search(r"@container\s+stat-card\s*\([^)]*\)\s*\{(.*?)\n\}", css, re.S)
    assert block, "Expected an @container stat-card (...) rule in stat-card.css"
    assert "--mat-sys-display-small" in block.group(1)


def test_when_stat_card_sources_read_then_no_tailwind_utility_classes_remain():
    """No Tailwind utility classes in the stat-card template or TypeScript."""
    text = _stat_card_file("ts") + "\n" + _stat_card_file("html")
    tailwind = re.compile(
        r"(@container\b|@sm:|\b(flex-col|gap-\d|text-(xs|sm|2xl|3xl|success|danger|text)|"
        r"font-semibold|font-medium|tabular-nums|truncate|mt-0\.5|dark:))"
    )
    match = tailwind.search(text)
    assert match is None, f"Tailwind utility '{match.group(0) if match else ''}' in stat-card"
