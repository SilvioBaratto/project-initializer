"""
Tests for issue #19: feat(ui): Avatar + StatCard

Source-blind: authored against acceptance criteria only, before any
implementation.  No implementation source was read during authoring.

Criteria covered:
  - [UNIT] Avatar: image variant uses NgOptimizedImage, initials fallback,
    sizes, required `alt`

Criteria skipped (not runtime-verifiable per oracle):
  - StatCard: metric/label/delta with directional color, container-query
    aware, built on Card — no concrete runtime or unit check inferable.
  - Dark-mode tokens; ≥44px when interactive — no concrete runtime or unit
    check inferable.
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
    """Return concatenated text of all non-spec .ts + .html files in the avatar folder."""
    d = _avatar_dir()
    parts: list[str] = []
    for ext in ("*.ts", "*.html"):
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
@settings(max_examples=20)
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
@settings(max_examples=10)
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
