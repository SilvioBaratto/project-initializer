"""
Tests for issue #5: feat(ui): core layout primitives — Container, Grid, Stack, Card.

Source-blind: authored against acceptance criteria only, before any implementation.

Criteria covered:
  - [UNIT] Container, Grid, Stack, Card exist under shared/ui/, each standalone +
    OnPush + signal-based
  - [T3 → static proxy] All consume @theme tokens (no hardcoded hex) — the
    runtime light/dark rendering check is browser-tier; this layer verifies the
    contract statically (no hex literals in source files)
  - [UNIT] Grid offers responsive cols (1 / 2 / 3 cells per row on the M3
    4 / 8 / 12-column grid, breakpoints 600px / 1200px) + gap input and a
    native CSS container-query (@container) option
  - [UNIT] Container applies the safe-area insets (.px-safe intent) on top of
    the M3 window margins (16px, 24px from 600px), split into .ts/.html/.css
  - [UNIT] Card renders <mat-card> and projects [slot-header] / default /
    [slot-footer] into mat-card-header / mat-card-content / mat-card-footer,
    split into .ts/.html/.css, with padding and appearance inputs and
    --mat-sys-* tokens only (static check here; card.spec.ts checks the
    projection at runtime)

Criteria skipped (not runtime-verifiable per oracle):
  - All tests pass — boilerplate suite gate; no per-criterion assertion
  - SOLID / clean code (methods < 10 lines …) — subjective prose; no concrete
    runtime or unit assertion

No Hypothesis property-based tests: none of the verifiable criteria imply a
parametric invariant over a varying input domain. Every assertion targets a
static property of template source files, not a function applied to an input
that must hold for all members of a domain.
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

COMPONENTS = ["container", "grid", "stack", "card"]

# Matches bare hex colour literals: #rgb #rgba #rrggbb #rrggbbaa.
# Excludes CSS id selectors (#id-name) and Angular template expressions.
# The negative look-behind for word chars / & prevents false-positives on
# things like &nbsp;, #someId, or template variable references.
_HEX_COLOR_RE = re.compile(
    r"(?<![&\w])#([0-9A-Fa-f]{8}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{3})\b"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _component_dir(name: str) -> pathlib.Path:
    return UI_ROOT / name


def _ts_file(name: str) -> pathlib.Path:
    """Return the primary (non-spec) TypeScript file for a component."""
    comp_dir = _component_dir(name)
    candidates = {f.name: f for f in comp_dir.glob("*.ts") if ".spec." not in f.name}
    if not candidates:
        raise FileNotFoundError(f"No non-spec .ts file found in {comp_dir}")
    # Prefer the file named after the component (grid.ts, grid.component.ts). Match the whole
    # file name, not a substring, and never rely on glob order, which differs between filesystems.
    for primary in (f"{name}.ts", f"{name}.component.ts"):
        if primary in candidates:
            return candidates[primary]
    return candidates[sorted(candidates)[0]]


def _full_source(name: str) -> str:
    """Return the concatenated source of .ts + any .html and .css file(s) in the component dir."""
    comp_dir = _component_dir(name)
    ts_text = _ts_file(name).read_text(encoding="utf-8")
    html_text = "".join(f.read_text(encoding="utf-8") for f in comp_dir.glob("*.html"))
    css_text = "".join(f.read_text(encoding="utf-8") for f in comp_dir.glob("*.css"))
    return ts_text + "\n" + html_text + "\n" + css_text


# ---------------------------------------------------------------------------
# Criterion: Container, Grid, Stack, Card exist under shared/ui/,
#            each standalone + OnPush + signal-based
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("component", COMPONENTS)
def test_when_ui_directory_inspected_then_component_folder_exists(component):
    """shared/ui/<component>/ must be a directory.

    Per criterion: 'Container, Grid, Stack, Card exist under shared/ui/'.
    """
    comp_dir = _component_dir(component)
    assert comp_dir.is_dir(), (
        f"Expected shared/ui/{component}/ to exist as a directory under "
        f"templates/frontend/src/app/shared/ui/"
    )


@pytest.mark.parametrize("component", COMPONENTS)
def test_when_component_folder_inspected_then_typescript_source_file_exists(component):
    """Each component folder must contain at least one non-spec .ts source file.

    Per criterion: one folder per component (.ts + inline or .html template).
    """
    comp_dir = _component_dir(component)
    non_spec_ts = [f for f in comp_dir.glob("*.ts") if ".spec." not in f.name]
    assert non_spec_ts, (
        f"Expected at least one .ts source file (not .spec.ts) in "
        f"shared/ui/{component}/"
    )


@pytest.mark.parametrize("component", COMPONENTS)
def test_when_component_ts_read_then_onpush_change_detection_is_set(component):
    """Each component must declare ChangeDetectionStrategy.OnPush.

    Per criterion: 'each standalone + OnPush + signal-based'.
    CLAUDE.md: 'OnPush change detection: Set changeDetection:
    ChangeDetectionStrategy.OnPush'.
    """
    ts = _ts_file(component).read_text(encoding="utf-8")
    assert "ChangeDetectionStrategy.OnPush" in ts, (
        f"Expected 'ChangeDetectionStrategy.OnPush' in shared/ui/{component}/ .ts file"
    )


@pytest.mark.parametrize("component", COMPONENTS)
def test_when_component_ts_read_then_standalone_is_not_opted_out(component):
    """Each component must not opt out of standalone mode.

    Per criterion: 'each standalone'.
    CLAUDE.md: Angular 21 components are standalone by default — do NOT set
    standalone: true (redundant), but MUST NOT set standalone: false (opts out).
    """
    ts = _ts_file(component).read_text(encoding="utf-8")
    assert "standalone: false" not in ts, (
        f"shared/ui/{component}/ .ts file must not contain 'standalone: false' "
        f"(that would opt the component out of standalone mode)"
    )


@pytest.mark.parametrize("component", COMPONENTS)
def test_when_component_ts_read_then_signal_input_function_is_used(component):
    """Each component must use Angular's signal input() function.

    Per criterion: 'signal-based'.
    CLAUDE.md: 'Signals for state: Use signal(), computed(), input(), output()'.
    Interpretation: at least one call to input() appears in the component .ts,
    indicating signal-based inputs rather than @Input() decorators.
    """
    ts = _ts_file(component).read_text(encoding="utf-8")
    assert "input(" in ts, (
        f"Expected 'input(' (Angular signals input function) in "
        f"shared/ui/{component}/ .ts file. Per criterion: components must be "
        f"signal-based."
    )


# ---------------------------------------------------------------------------
# Criterion: All consume @theme tokens — no hardcoded hex colours
#
# Note: The oracle classifies this as [T3] (browser rendering of light + dark).
# The static layer — "no hardcoded hex" — is directly derivable from the
# criterion text and testable at file level without a browser.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("component", COMPONENTS)
def test_when_component_source_inspected_then_no_hardcoded_hex_colors_found(component):
    """Component files must contain no hardcoded hex colour literals.

    Per criterion: 'All consume @theme tokens (no hardcoded hex)'.
    Interpretation: neither the .ts nor the .html source of a component may
    contain bare CSS hex literals such as #fff, #ffffff, #rrggbb, or #rrggbbaa.
    All colours must come from @theme CSS custom-property tokens.

    This is the static, file-level layer of the T3 criterion; the browser
    rendering in light and dark is a separate T3-tier concern.
    """
    combined = _full_source(component)
    matches = _HEX_COLOR_RE.findall(combined)
    assert not matches, (
        f"Found hardcoded hex color value(s) in shared/ui/{component}/: "
        f"{['#' + m for m in matches]!r}. "
        f"Replace with @theme tokens (e.g. var(--color-primary)) to satisfy "
        f"the 'no hardcoded hex' acceptance criterion."
    )


# ---------------------------------------------------------------------------
# Criterion: Grid — responsive cols (1 / 2 / 3 cells per row on the M3
#            4 / 8 / 12-column grid) + gap input + container-query option
# ---------------------------------------------------------------------------


def _grid_css() -> str:
    return (_component_dir("grid") / "grid.css").read_text(encoding="utf-8")


def _css_block_after(css: str, at_rule: str) -> str:
    """Return the text of the first block opened by `at_rule` (up to its matching brace)."""
    start = css.find(at_rule)
    assert start != -1, f"Expected '{at_rule}' in grid.css"
    depth = 0
    for i in range(css.index("{", start), len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[start : i + 1]
    raise AssertionError(f"Unbalanced block after '{at_rule}' in grid.css")


def test_when_grid_folder_inspected_then_ts_html_css_are_wired_by_url():
    """Grid is split into grid.ts + grid.html + grid.css, wired with
    templateUrl / styleUrl (no inline template or styles)."""
    comp_dir = _component_dir("grid")
    for ext in ("ts", "html", "css"):
        assert (comp_dir / f"grid.{ext}").is_file(), f"Expected shared/ui/grid/grid.{ext} to exist"
    ts = _ts_file("grid").read_text(encoding="utf-8")
    assert "selector: 'app-grid'" in ts, "Grid selector must stay 'app-grid'"
    assert "templateUrl: './grid.html'" in ts, "Grid must use templateUrl: './grid.html'"
    assert "styleUrl: './grid.css'" in ts, "Grid must use styleUrl: './grid.css'"
    assert "template:" not in ts and "styles:" not in ts, (
        "Grid must not declare an inline template or inline styles"
    )


def test_when_grid_source_read_then_base_column_class_is_present():
    """Below 600px (M3 compact) the grid lays out on 4 columns with a 16px gutter,
    and every cell spans 4 columns, so a row holds one cell (mobile-first base).

    Per criterion: 'Grid offers responsive cols (1 / md:2 / lg:3)', now expressed
    on the Material 3 column grid (layout/breakpoints.md:9: 4 / 8 / 12 columns).
    """
    css = _grid_css()
    base = css[: css.find("@media")]
    assert "display: grid" in base, "Expected the grid cells to use display: grid"
    assert "--app-grid-columns: 4;" in base, "Expected 4 columns as the compact base"
    assert "--app-grid-cell-span: 4;" in base, "Expected each cell to span 4 columns"
    assert "repeat(var(--app-grid-columns), minmax(0, 1fr))" in base, (
        "Expected grid-template-columns to repeat the M3 column count"
    )
    assert "gap: 16px;" in base, "Expected a 16px compact gutter"
    assert re.search(
        r":where\(\.app-grid > \.app-grid__cells\) > \*\s*\{[^}]*"
        r"grid-column: span var\(--app-grid-cell-span\);",
        base,
    ), (
        "Expected the default cell span in a zero-specificity :where() rule, so a "
        "cell's own grid-column rule or --app-grid-cell-span always wins"
    )


def test_when_grid_source_read_then_medium_breakpoint_column_class_is_present():
    """From 600px (M3 medium) the grid uses 8 columns and a 24px gutter, so
    4-column cells sit two per row. Replaces md:grid-cols-2 (768px)."""
    css = _grid_css()
    block = _css_block_after(css, "@media (min-width: 600px)")
    assert "--app-grid-columns: 8;" in block, "Expected 8 columns from 600px"
    assert "gap: 24px;" in block, "Expected a 24px gutter from 600px"
    assert "768px" not in css and "1024px" not in css, (
        "grid.css must use M3 breakpoints (600/840/1200px), not Tailwind's 768px/1024px"
    )


def test_when_grid_source_read_then_large_breakpoint_column_class_is_present():
    """From 1200px (M3 large) the grid uses 12 columns, so 4-column cells sit
    three per row. Replaces lg:grid-cols-3 (1024px)."""
    block = _css_block_after(_grid_css(), "@media (min-width: 1200px)")
    assert "--app-grid-columns: 12;" in block, "Expected 12 columns from 1200px"


def test_when_grid_css_read_then_no_tailwind_or_color_literals_remain():
    """Grid styling is plain CSS: no Tailwind utility classes in any grid source,
    no color literals, no !important and no ::ng-deep."""
    combined = _full_source("grid")
    assert not re.search(r"\b(?:grid-cols-\d|md:|lg:|gap-\d)", combined), (
        "Grid sources must not contain Tailwind grid utility classes"
    )
    css = _grid_css()
    assert not _CARD_COLOR_LITERAL_RE.search(css), "grid.css must not contain color literals"
    assert "!important" not in css, "grid.css must not use !important"
    assert "::ng-deep" not in css, "grid.css must not use ::ng-deep"


def test_when_grid_ts_read_then_gap_signal_input_is_declared():
    """Grid component must expose a signal input named 'gap'.

    Per criterion: 'Grid offers responsive cols ... + gap input'.
    Interpretation: the Grid .ts file declares a property named 'gap' whose
    value is an Angular signals input() call (e.g. `readonly gap = input(4)` or
    `readonly gap = input<number>(4)`).
    """
    ts = _ts_file("grid").read_text(encoding="utf-8")
    has_gap_input = bool(re.search(r"\bgap\s*=\s*input[<(]", ts))
    assert has_gap_input, (
        "Expected a signal input named 'gap' in the Grid component .ts file, "
        "e.g. `readonly gap = input(4)` or `readonly gap = input<number>(4)`. "
        "Per criterion: 'Grid offers ... + gap input'."
    )


def test_when_grid_source_read_then_container_query_option_is_present():
    """Grid offers a native CSS container-query option.

    Per criterion: 'Grid offers ... a container-query (@container) option'.
    The Grid .ts declares a `containerQuery` signal input that toggles a host
    class; grid.css makes that host an inline-size query container and repeats
    the M3 column steps in @container rules at the same 600px / 1200px literals
    as the window media queries (8 columns from 600px, 12 from 1200px).
    The host must be display: block: a custom element is inline by default, and
    inline-size containment has no effect on an inline box.
    """
    ts = _ts_file("grid").read_text(encoding="utf-8")
    assert re.search(r"\bcontainerQuery\s*=\s*input[<(]", ts), (
        "Expected a signal input named 'containerQuery' in the Grid .ts file"
    )
    css = _grid_css()
    assert "container-type: inline-size" in css, (
        "Expected grid.css to establish an inline-size query container"
    )
    assert re.search(r"\.app-grid\s*\{[^}]*display: block;", css), (
        "Expected the app-grid host to be display: block, or the inline-size "
        "container never applies and the @container rules never match"
    )
    medium = _css_block_after(css, "@container (min-width: 600px)")
    assert "--app-grid-columns: 8;" in medium, "Expected 8 columns from a 600px container"
    large = _css_block_after(css, "@container (min-width: 1200px)")
    assert "--app-grid-columns: 12;" in large, "Expected 12 columns from a 1200px container"


# ---------------------------------------------------------------------------
# Criterion: Container applies the safe-area insets (the .px-safe intent)
# ---------------------------------------------------------------------------

_CONTAINER_TAILWIND_RE = re.compile(
    r"\b(?:px-safe|mx-auto|w-full|max-w-\w+|px-\d|p[xytblr]?-\d)\b|\b(?:sm|md|lg|xl|dark):"
)


def _container_css() -> str:
    return (_component_dir("container") / "container.css").read_text(encoding="utf-8")


def test_when_container_folder_inspected_then_ts_html_css_are_wired_by_url():
    """Container is split into container.ts + container.html + container.css,
    wired with templateUrl / styleUrl (no inline template or styles), and keeps
    its `app-container` selector and `size` signal input."""
    comp_dir = _component_dir("container")
    for ext in ("ts", "html", "css"):
        assert (comp_dir / f"container.{ext}").is_file(), (
            f"Expected shared/ui/container/container.{ext} to exist"
        )
    ts = _ts_file("container").read_text(encoding="utf-8")
    assert "selector: 'app-container'" in ts, "Container selector must stay 'app-container'"
    assert "templateUrl: './container.html'" in ts, "Container must use templateUrl"
    assert "styleUrl: './container.css'" in ts, "Container must use styleUrl"
    assert "template:" not in ts and "styles:" not in ts, (
        "Container must not declare an inline template or inline styles"
    )
    assert re.search(r"\bsize\s*=\s*input[<(]", ts), "Container must declare a `size` input()"


def test_when_container_css_read_then_safe_area_insets_pad_both_sides():
    """Container pads its content by the device safe-area insets.

    Per criterion: 'Container applies .px-safe' — the global .px-safe utility
    maps the horizontal padding to env(safe-area-inset-left) /
    env(safe-area-inset-right). The Material 3 container folds those insets
    into its own padding (window margin + inset) in container.css instead of
    stacking a competing global class on the host.
    """
    css = _container_css()
    assert "env(safe-area-inset-left" in css, (
        "Expected container.css to pad the left side by env(safe-area-inset-left)"
    )
    assert "env(safe-area-inset-right" in css, (
        "Expected container.css to pad the right side by env(safe-area-inset-right)"
    )


def test_when_container_css_read_then_m3_window_margins_are_applied():
    """Container applies the M3 window margins: 16px below 600px and 24px from
    the 600px medium breakpoint (never the Tailwind 768px md breakpoint)."""
    css = _container_css()
    assert "16px" in css, "Expected the 16px compact window margin in container.css"
    media = re.search(r"@media\s*\(\s*min-width:\s*600px\s*\)\s*\{(?P<body>.*?)\}\s*\}", css, re.S)
    assert media and "24px" in media.group("body"), (
        "Expected a @media (min-width: 600px) block setting the 24px window margin"
    )
    assert "768px" not in css, "container.css must use M3 breakpoints, not 768px"


def test_when_container_source_read_then_no_tailwind_or_color_literals_remain():
    """Container styling is plain CSS: no Tailwind utility classes in any file,
    and no color literals, !important or ::ng-deep in container.css."""
    combined = _full_source("container")
    leftovers = _CONTAINER_TAILWIND_RE.findall(combined)
    assert not leftovers, f"Tailwind utility residue in shared/ui/container/: {leftovers!r}"
    css = _container_css()
    assert not _CARD_COLOR_LITERAL_RE.search(css), "container.css must not contain color literals"
    assert "!important" not in css, "container.css must not use !important"
    assert "::ng-deep" not in css, "container.css must not use ::ng-deep"


# ---------------------------------------------------------------------------
# Criterion: Card — Angular Material 3 card with header / default / footer slots
# ---------------------------------------------------------------------------

_CARD_COLOR_LITERAL_RE = re.compile(
    r"(?<![&\w])#[0-9A-Fa-f]{3,8}\b|\b(?:rgba?|hsla?)\(", re.IGNORECASE
)


def test_when_card_folder_inspected_then_ts_html_css_are_wired_by_url():
    """Card is split into card.ts + card.html + card.css, wired with
    templateUrl / styleUrl (no inline template or styles)."""
    comp_dir = _component_dir("card")
    for ext in ("ts", "html", "css"):
        assert (comp_dir / f"card.{ext}").is_file(), (
            f"Expected shared/ui/card/card.{ext} to exist"
        )
    ts = _ts_file("card").read_text(encoding="utf-8")
    assert "templateUrl: './card.html'" in ts, "Card must use templateUrl: './card.html'"
    assert "styleUrl: './card.css'" in ts, "Card must use styleUrl: './card.css'"
    assert "template:" not in ts and "styles:" not in ts, (
        "Card must not declare an inline template or inline styles"
    )


def test_when_card_template_read_then_mat_card_hosts_header_body_and_footer_slots():
    """Card renders an Angular Material <mat-card> and projects the three slots
    ([slot-header], default, [slot-footer]) into its header, content and footer
    sections — the public projection API consumers rely on."""
    html = (_component_dir("card") / "card.html").read_text(encoding="utf-8")
    ts = _ts_file("card").read_text(encoding="utf-8")
    assert "selector: 'app-card'" in ts, "Card selector must stay 'app-card'"
    assert "MatCardModule" in ts, "Card must import MatCardModule"
    for tag in ("<mat-card", "<mat-card-header", "<mat-card-content", "<mat-card-footer"):
        assert tag in html, f"Expected {tag} in card.html"
    assert 'select="[slot-header]"' in html, "Card must project [slot-header]"
    assert 'select="[slot-footer]"' in html, "Card must project [slot-footer]"
    assert re.search(r"<ng-content\s*/>|<ng-content>\s*</ng-content>", html), (
        "Card must project default content with an unselected <ng-content>"
    )


def test_when_card_ts_read_then_padding_and_appearance_inputs_are_declared():
    """Card keeps its `padding` signal input and exposes the M3 card type
    through an `appearance` signal input."""
    ts = _ts_file("card").read_text(encoding="utf-8")
    assert re.search(r"\bpadding\s*=\s*input[<(]", ts), "Card must declare a `padding` input()"
    assert re.search(r"\bappearance\s*=\s*input[<(]", ts), "Card must declare an `appearance` input()"


def test_when_card_css_read_then_colors_and_type_come_from_material_tokens():
    """Card styling uses --mat-sys-* tokens only: no color literals,
    no !important and no ::ng-deep (light and dark resolve from the theme)."""
    css = (_component_dir("card") / "card.css").read_text(encoding="utf-8")
    assert "var(--mat-sys-" in css, "Expected card.css to use --mat-sys-* tokens"
    assert not _CARD_COLOR_LITERAL_RE.search(css), "card.css must not contain color literals"
    assert "!important" not in css, "card.css must not use !important"
    assert "::ng-deep" not in css, "card.css must not use ::ng-deep"


# ---------------------------------------------------------------------------
# Criterion: Stack — plain flex primitive whose inputs map to rules in stack.css
# ---------------------------------------------------------------------------

# Tailwind flex utilities the pre-migration Stack computed into a class string.
_STACK_TAILWIND_RE = re.compile(
    r"\b(?:flex-(?:row|col|wrap|nowrap)|items-(?:start|center|end|stretch|baseline)"
    r"|justify-(?:start|center|end|between|around|evenly)|gap-\d+)\b"
)


def _stack_file(ext: str) -> str:
    return (_component_dir("stack") / f"stack.{ext}").read_text(encoding="utf-8")


def test_when_stack_folder_inspected_then_ts_html_css_are_wired_by_url():
    """Stack is split into stack.ts + stack.html + stack.css, wired with
    templateUrl / styleUrl (no inline template or styles), and keeps its
    `app-stack` selector and direction / gap / wrap / align signal inputs
    (plus the M3 migration's `justify` input)."""
    comp_dir = _component_dir("stack")
    for ext in ("ts", "html", "css"):
        assert (comp_dir / f"stack.{ext}").is_file(), f"Expected shared/ui/stack/stack.{ext} to exist"
    ts = _stack_file("ts")
    assert "selector: 'app-stack'" in ts, "Stack selector must stay 'app-stack'"
    assert "templateUrl: './stack.html'" in ts, "Stack must use templateUrl: './stack.html'"
    assert "styleUrl: './stack.css'" in ts, "Stack must use styleUrl: './stack.css'"
    assert "template:" not in ts and "styles:" not in ts, (
        "Stack must not declare an inline template or inline styles"
    )
    for name in ("direction", "gap", "wrap", "align", "justify"):
        assert re.search(rf"\b{name}\s*=\s*input[<(]", ts), f"Stack must declare a `{name}` input()"


def test_when_stack_css_read_then_inputs_map_to_flex_rules_on_the_host():
    """The host itself is the flex container, and stack.css maps every input:
    direction / wrap / align / justify through host data attributes, and the
    gap through the --app-stack-gap custom property, which the component sets
    in whole 4px steps (the M3 4px spacing grid)."""
    css = _stack_file("css")
    host = re.search(r":host\s*\{(?P<body>[^}]*)\}", css)
    assert host, "Expected a :host rule in stack.css"
    assert "display: flex;" in host.group("body"), "Expected the host to be the flex container"
    assert "gap: var(--app-stack-gap" in host.group("body"), (
        "Expected the host gap to read the --app-stack-gap custom property"
    )
    assert re.search(r":host\(\[data-direction='row'\]\)\s*\{[^}]*flex-direction: row;", css), (
        "Expected data-direction='row' to lay items out in a row"
    )
    assert re.search(r":host\(\[data-wrap='wrap'\]\)\s*\{[^}]*flex-wrap: wrap;", css), (
        "Expected data-wrap='wrap' to wrap items"
    )
    for align in ("start", "center", "end", "stretch", "baseline"):
        assert re.search(rf":host\(\[data-align='{align}'\]\)\s*\{{[^}}]*align-items: {align};", css), (
            f"Expected data-align='{align}' to map to align-items: {align}"
        )
    for justify in ("start", "center", "end", "space-between", "space-around", "space-evenly"):
        assert re.search(
            rf":host\(\[data-justify='{justify}'\]\)\s*\{{[^}}]*justify-content: {justify};", css
        ), f"Expected data-justify='{justify}' to map to justify-content: {justify}"
    ts = _stack_file("ts")
    assert "'[style.--app-stack-gap]'" in ts, "Expected the host to bind --app-stack-gap"
    assert re.search(r"\bSTACK_GAP_STEP_PX\s*=\s*4;", ts), "Expected gap steps of 4px (M3 grid)"


def test_when_stack_source_read_then_no_tailwind_or_color_literals_remain():
    """Stack styling is plain CSS: no Tailwind flex utility classes in the .ts or
    .html (the computed class string is gone), and stack.css has no color
    literals, !important or ::ng-deep."""
    markup = _stack_file("ts") + "\n" + _stack_file("html")
    leftovers = _STACK_TAILWIND_RE.findall(markup)
    assert not leftovers, f"Tailwind utility residue in shared/ui/stack/: {leftovers!r}"
    css = _stack_file("css")
    assert not _CARD_COLOR_LITERAL_RE.search(css), "stack.css must not contain color literals"
    assert "!important" not in css, "stack.css must not use !important"
    assert "::ng-deep" not in css, "stack.css must not use ::ng-deep"
