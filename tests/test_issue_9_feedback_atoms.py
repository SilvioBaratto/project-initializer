"""
Tests for issue #9: feat(ui): feedback atoms — Badge, Spinner, Skeleton, Alert.

Source-blind: authored against acceptance criteria only, before any implementation.

Criteria covered:
  - [UNIT] Spinner: `role="status"` + sr-only label, reduced-motion safe
  - [UNIT] Skeleton uses `.animate-shimmer`, no layout shift
  - [UNIT] Alert: `role="alert"`, variant (info/success/warning/danger) via tokens

Criteria skipped (not runtime-verifiable per oracle):
  - Badge variants via tokens, dark-mode aware — NOT VERIFIABLE: browser-tier
    rendering concern; no static or unit-level observable signal differentiating
    dark-mode token application from the source alone.
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


def test_when_spinner_source_read_then_role_status_is_present():
    """Spinner template must declare role="status".

    Per criterion: 'Spinner: `role="status"`'.
    WAI-ARIA: role="status" is a live region that announces asynchronous status
    messages to screen readers without interrupting the user.
    """
    src = _read_dir(SPINNER_DIR)
    assert 'role="status"' in src or "role='status'" in src, (
        'Expected role="status" in the Spinner component source (.ts or .html). '
        "Per criterion: 'Spinner: `role=\"status\"` + sr-only label'."
    )


def test_when_spinner_source_read_then_sr_only_label_is_present():
    """Spinner template must contain a screen-reader-only label.

    Per criterion: 'Spinner: role="status" + sr-only label'.
    The label must be visually hidden but announced by assistive technology.
    Accepted forms: the Tailwind `sr-only` utility class, or an `aria-label`
    attribute on the status element.
    """
    src = _read_dir(SPINNER_DIR)
    has_sr_only = "sr-only" in src
    has_aria_label = bool(re.search(r"aria-label\s*=", src))
    assert has_sr_only or has_aria_label, (
        "Expected 'sr-only' class or an 'aria-label' attribute in the Spinner "
        "component source. Per criterion: 'Spinner: role=\"status\" + sr-only label'."
    )


def test_when_spinner_source_read_then_animate_spin_is_referenced():
    """Spinner template must reference the animate-spin Tailwind utility.

    Requirements §7: 'Spinner — `animate-spin`'. The spinning animation must be
    applied via Tailwind's built-in animate-spin class rather than custom CSS,
    so the component is consistent with the design system.
    """
    src = _read_dir(SPINNER_DIR)
    assert "animate-spin" in src, (
        "Expected 'animate-spin' in the Spinner component source. "
        "Requirements §7: 'Spinner — animate-spin, role=\"status\" + sr-only label'."
    )


def test_when_spinner_source_read_then_reduced_motion_is_handled():
    """Spinner must handle reduced-motion preference.

    Per criterion: 'Spinner: role="status" + sr-only label, reduced-motion safe'.
    Reduced-motion safety means the animation must be suppressed or replaced when
    the user has requested reduced motion. Accepted forms:
      - A `prefers-reduced-motion` media query or Tailwind `motion-reduce:` utility
        in the component source, template, or a companion CSS file in the directory.
      - A `motion-safe:` / `motion-reduce:` Tailwind prefix applied to the spin class.
    """
    src = _read_dir(SPINNER_DIR)
    # Also check any companion CSS / SCSS files in the spinner directory
    extra_css = "".join(
        f.read_text(encoding="utf-8") for f in SPINNER_DIR.glob("*.css")
    ) + "".join(f.read_text(encoding="utf-8") for f in SPINNER_DIR.glob("*.scss"))
    combined = src + extra_css

    has_reduced_motion = (
        "prefers-reduced-motion" in combined
        or "motion-reduce:" in combined
        or "motion-safe:" in combined
    )
    assert has_reduced_motion, (
        "Expected a reduced-motion guard in the Spinner component. Accepted: "
        "'prefers-reduced-motion' media query, Tailwind 'motion-reduce:' prefix, "
        "or 'motion-safe:' prefix. "
        "Per criterion: 'Spinner: role=\"status\" + sr-only label, reduced-motion safe'."
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


# ===========================================================================
# Skeleton
# ===========================================================================
# Criterion: Skeleton uses `.animate-shimmer`, no layout shift
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


def test_when_skeleton_source_read_then_animate_shimmer_class_is_referenced():
    """Skeleton component must reference the .animate-shimmer class.

    Per criterion: 'Skeleton uses .animate-shimmer'.
    Requirements §7 (current state): 'Shimmer/fade/slide keyframes in @layer
    utilities'. The Skeleton component must apply the existing .animate-shimmer
    utility rather than reimplementing a custom animation.
    """
    src = _read_dir(SKELETON_DIR)
    assert "animate-shimmer" in src, (
        "Expected 'animate-shimmer' in the Skeleton component source (.ts or .html). "
        "Per criterion: 'Skeleton uses .animate-shimmer'."
    )


def test_when_skeleton_source_read_then_explicit_dimensions_are_declared():
    """Skeleton must set explicit width/height so it does not cause layout shift.

    Per criterion: 'Skeleton uses .animate-shimmer, no layout shift'.
    A skeleton placeholder that does not declare dimensions causes cumulative
    layout shift (CLS) when content loads. The component must expose width/height
    inputs (or apply a fixed-size utility) so the reserved space equals the
    eventual content size. Accepted indicators: a signal input named 'width' or
    'height', a class like 'w-full'/'h-4', or an explicit inline-style binding.
    """
    src = _read_dir(SKELETON_DIR)
    has_size_input = bool(re.search(r"\b(width|height)\s*=\s*input[<(]", src))
    has_size_class = bool(
        re.search(
            r"(w-\w+|h-\w+|width|height)",
            src,
        )
    )
    assert has_size_input or has_size_class, (
        "Expected explicit size handling in the Skeleton component: a signal input "
        "named 'width'/'height', or a Tailwind size class (w-*, h-*) / width/height "
        "style binding. Per criterion: 'Skeleton uses .animate-shimmer, no layout shift'."
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


def test_when_alert_source_read_then_role_alert_is_present():
    """Alert template must declare role="alert".

    Per criterion: 'Alert: `role="alert"`'.
    WAI-ARIA: role="alert" is an assertive live region; it interrupts the user
    to announce urgent messages (e.g. validation errors). Required for the alert
    to be announced by screen readers without the user having to seek it out.
    """
    src = _read_dir(ALERT_DIR)
    assert 'role="alert"' in src or "role='alert'" in src, (
        'Expected role="alert" in the Alert component source (.ts or .html). '
        "Per criterion: 'Alert: `role=\"alert\"`, variant (info/success/warning/danger)'."
    )


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
    The variant names must appear in the .ts (type union, string literal, or
    class-map) or in the .html template as CSS-class references.
    """
    combined = _read_dir(ALERT_DIR)
    assert variant in combined, (
        f"Expected the variant value '{variant}' in the Alert component source "
        f"(.ts or .html). Per criterion: 'variant (info/success/warning/danger)'."
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
