"""
Tests for issue #5: feat(ui): core layout primitives — Container, Grid, Stack, Card.

Source-blind: authored against acceptance criteria only, before any implementation.

Criteria covered:
  - [UNIT] Container, Grid, Stack, Card exist under shared/ui/, each standalone +
    OnPush + signal-based
  - [T3 → static proxy] All consume @theme tokens (no hardcoded hex) — the
    runtime light/dark rendering check is browser-tier; this layer verifies the
    contract statically (no hex literals in source files)
  - [UNIT] Grid offers responsive cols (1 / md:2 / lg:3) + gap input and a
    container-query (@container) option
  - [UNIT] Container applies .px-safe

Criteria skipped (not runtime-verifiable per oracle):
  - Card projects header / default / footer content via ng-content slots —
    NOT VERIFIABLE: Angular content projection is a runtime structural concern
    with no testable static or unit-level signal
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
    candidates = [f for f in comp_dir.glob("*.ts") if ".spec." not in f.name]
    if not candidates:
        raise FileNotFoundError(f"No non-spec .ts file found in {comp_dir}")
    # Prefer the file whose name matches the component (e.g. grid.ts, grid.component.ts)
    primary = [f for f in candidates if name in f.name]
    return (primary or candidates)[0]


def _full_source(name: str) -> str:
    """Return the concatenated source of .ts + any .html file(s) in the component dir."""
    comp_dir = _component_dir(name)
    ts_text = _ts_file(name).read_text(encoding="utf-8")
    html_text = "".join(f.read_text(encoding="utf-8") for f in comp_dir.glob("*.html"))
    return ts_text + "\n" + html_text


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
# Criterion: Grid — responsive cols (1 / md:2 / lg:3) + gap input +
#            container-query (@container) option
# ---------------------------------------------------------------------------


def test_when_grid_source_read_then_base_column_class_is_present():
    """Grid component must apply grid-cols-1 as the base (mobile-first) column class.

    Per criterion: 'Grid offers responsive cols (1 / md:2 / lg:3)'.
    The mobile-first baseline is 1 column.
    """
    combined = _full_source("grid")
    assert "grid-cols-1" in combined, (
        "Expected 'grid-cols-1' in the Grid component source (base mobile-first "
        "column class)"
    )


def test_when_grid_source_read_then_medium_breakpoint_column_class_is_present():
    """Grid component must apply md:grid-cols-2 at the medium breakpoint.

    Per criterion: 'Grid offers responsive cols (1 / md:2 / lg:3)'.
    """
    combined = _full_source("grid")
    assert "md:grid-cols-2" in combined, (
        "Expected 'md:grid-cols-2' in the Grid component source (medium breakpoint)"
    )


def test_when_grid_source_read_then_large_breakpoint_column_class_is_present():
    """Grid component must apply lg:grid-cols-3 at the large breakpoint.

    Per criterion: 'Grid offers responsive cols (1 / md:2 / lg:3)'.
    """
    combined = _full_source("grid")
    assert "lg:grid-cols-3" in combined, (
        "Expected 'lg:grid-cols-3' in the Grid component source (large breakpoint)"
    )


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
    """Grid component source must reference @container for container-query support.

    Per criterion: 'Grid offers ... a container-query (@container) option'.
    Satisfied if '@container' appears in the grid .ts or .html — either as the
    Tailwind CSS class ('class=\"@container\"') that establishes a containment
    context, or as container-query variant prefixes (e.g. '@md:grid-cols-2').
    """
    combined = _full_source("grid")
    has_container = "@container" in combined or bool(
        re.search(r"@\w+:grid-cols-", combined)
    )
    assert has_container, (
        "Expected '@container' (Tailwind containment-context class) or container-"
        "query column variants (e.g. @md:grid-cols-2) in the Grid component source. "
        "Per criterion: 'Grid offers ... a container-query (@container) option'."
    )


# ---------------------------------------------------------------------------
# Criterion: Container applies .px-safe
# ---------------------------------------------------------------------------


def test_when_container_source_read_then_px_safe_class_is_applied():
    """Container component must apply the px-safe utility class.

    Per criterion: 'Container applies .px-safe'.
    .px-safe maps padding-inline to env(safe-area-inset-left) /
    env(safe-area-inset-right) (requirements §3 — full safe-area inset set).
    The class must appear in the Container component's .html template or .ts
    inline template string.
    """
    combined = _full_source("container")
    assert "px-safe" in combined, (
        "Expected 'px-safe' to appear in the Container component source "
        "(template or .ts inline template). Per criterion: 'Container applies "
        ".px-safe'."
    )
