"""
Tests for issue #24: cross-browser/device QA report for shared UI parity.

Verifiable criteria (oracle: UNIT):
  1. The report has a results matrix (browser x device) covering notch clearance,
     dvh full-height under toolbar show/hide, sticky-footer + safe-area, dark-mode
     toggle, and focus traps.
  2. A pytest asserts the report scaffolds and contains each required validation
     heading.

Material 3 migration: the template no longer uses Tailwind, so the report must
describe the mechanisms it actually ships (the `color-scheme` classes that pick
the `--mat-sys-*` token values, Material dialogs, side sheets and the compact actions
bottom sheet for focus traps, the 600px navigation bar / rail switch) instead of `dark:*` or
`h-dvh` utilities, while keeping the browser x form-factor matrix.

Skipped (oracle: NOT VERIFIABLE):
  - "ships in the frontend template documenting iOS Safari + Chrome + Edge" —
    file presence is side-checked here, but documentation quality is subjective.
  - Real-device iOS testing attestation — prose claim, not machine-checkable.
  - All tests pass — suite gate, not a per-criterion assertion.
  - SOLID / clean-code — subjective.

Design note: the criterion 1 and 2 assertions are derived from the criterion
text alone; the Material 3 assertions follow the migrated template.
"""

import pathlib

import pytest

FRONTEND_TEMPLATE = (
    pathlib.Path(__file__).parent.parent
    / "project_initializer"
    / "templates"
    / "frontend"
)
QA_REPORT_PATH = FRONTEND_TEMPLATE / "QA_REPORT.md"

# Criterion text: "iOS Safari + Chrome + Edge on both mobile and desktop"
REQUIRED_BROWSERS = ["iOS Safari", "Chrome", "Edge"]
REQUIRED_FORM_FACTORS = ["mobile", "desktop"]

# Criterion text: "notch clearance, dvh full-height under toolbar show/hide,
# sticky-footer + safe-area, dark-mode toggle, and focus traps"
REQUIRED_TOPICS = [
    "notch",
    "dvh",
    "sticky-footer",
    "safe-area",
    "dark-mode",
    "focus trap",
]

# Tailwind vocabulary the report used before the Material 3 migration.
TAILWIND_RESIDUE = ["tailwind", "h-dvh", "dark:", "@custom-variant"]


@pytest.fixture(scope="module")
def report() -> str:
    """
    Criterion 2: 'a pytest asserts the report scaffolds'.
    Interpreted as: the markdown file must exist at the template path so that
    the scaffolding step copies it into every generated project.
    """
    assert QA_REPORT_PATH.exists(), (
        f"QA_REPORT.md not found at expected path {QA_REPORT_PATH}. "
        "The implementation must place the QA report in the frontend template."
    )
    return QA_REPORT_PATH.read_text(encoding="utf-8")


def _section(report: str, heading_keyword: str) -> list[str]:
    """Lines under the first heading containing *heading_keyword*, up to the next heading or rule."""
    lines = report.splitlines()
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if line.lstrip().startswith("#") and heading_keyword.lower() in line.lower()
        ),
        None,
    )
    assert start is not None, f"No heading containing {heading_keyword!r} in QA report"
    section = []
    for line in lines[start + 1 :]:
        if line.lstrip().startswith("#") or line.strip() == "---":
            break
        section.append(line)
    return section


# ---------------------------------------------------------------------------
# Criterion 1 – results matrix covers required browsers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("browser", REQUIRED_BROWSERS)
def test_when_matrix_is_read_then_required_browser_is_listed(report, browser):
    assert browser in report, f"Browser '{browser}' not found in QA report matrix"


# ---------------------------------------------------------------------------
# Criterion 1 – results matrix covers both form factors (mobile / desktop)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("form_factor", REQUIRED_FORM_FACTORS)
def test_when_matrix_is_read_then_form_factor_is_listed(report, form_factor):
    assert form_factor in report.lower(), (
        f"Form factor '{form_factor}' not found in QA report"
    )


# ---------------------------------------------------------------------------
# Criterion 1 – results matrix covers all five required validation topics
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topic", REQUIRED_TOPICS)
def test_when_matrix_is_read_then_required_topic_is_present(report, topic):
    assert topic.lower() in report.lower(), (
        f"Required matrix topic '{topic}' not found in QA report"
    )


# ---------------------------------------------------------------------------
# Criterion 1 – every browser section is a Mobile x Desktop table with a row
# for every required topic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("browser", REQUIRED_BROWSERS)
def test_when_browser_section_is_read_then_matrix_has_form_factor_columns_and_topic_rows(
    report, browser
):
    rows = [line for line in _section(report, browser) if line.lstrip().startswith("|")]
    assert len(rows) >= 3, f"[{browser}] expected a markdown table with a header and rows"
    header = [cell.strip().lower() for cell in rows[0].strip().strip("|").split("|")]
    for form_factor in REQUIRED_FORM_FACTORS:
        assert form_factor in header, (
            f"[{browser}] matrix header must have a '{form_factor}' column, got {header}"
        )
    body = "\n".join(rows[2:]).lower()
    for topic in REQUIRED_TOPICS:
        assert topic in body, f"[{browser}] matrix has no row for '{topic}'"


# ---------------------------------------------------------------------------
# Criterion 2 – each required topic must appear as a section heading
# The criterion says "contains each required validation heading"; in Markdown
# a heading is a line whose first non-whitespace characters are '#' signs.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("heading_keyword", REQUIRED_TOPICS)
def test_when_report_is_read_then_each_required_validation_heading_is_present(
    report, heading_keyword
):
    heading_lines = [
        line for line in report.splitlines() if line.lstrip().startswith("#")
    ]
    heading_text = "\n".join(heading_lines).lower()
    assert heading_keyword.lower() in heading_text, (
        f"Required validation heading for '{heading_keyword}' not found. "
        f"Headings present: {heading_lines}"
    )


# ---------------------------------------------------------------------------
# Material 3 migration – the report describes what the template ships
# ---------------------------------------------------------------------------


def test_when_report_is_read_then_no_tailwind_vocabulary_remains(report):
    lowered = report.lower()
    found = [term for term in TAILWIND_RESIDUE if term in lowered]
    assert found == [], f"QA report still refers to Tailwind: {found}"


def test_when_dark_mode_section_is_read_then_it_describes_the_color_scheme_classes(report):
    """ThemeService's `.light` / `.dark` classes set `color-scheme`, which picks the token values."""
    section = "\n".join(_section(report, "dark-mode toggle"))
    for fragment in ("ThemeService", ".light", ".dark", "color-scheme", "--mat-sys-"):
        assert fragment in section, (
            f"Dark-mode toggle section must mention {fragment!r}"
        )
    assert "cdk-overlay-container" in section, (
        "Dark-mode toggle section must cover Material overlay panels"
    )


def test_when_focus_trap_section_is_read_then_every_modal_surface_the_shell_renders_is_covered(
    report,
):
    """Dialogs and side sheets (MatDialog) and the compact actions sheet (MatBottomSheet) trap focus.

    The shell has no modal rail: `mat-sidenav` renders only from 600px, docked in `side`
    mode, so the report must not ask testers to check one.
    """
    section = "\n".join(_section(report, "focus trap"))
    for fragment in ("MatDialog", "MatBottomSheet", "Escape"):
        assert fragment in section, f"Focus trap section must cover {fragment!r}"
    assert "modal rail" not in report.lower(), "QA report still lists a modal rail"
    layout_html = (FRONTEND_TEMPLATE / "src" / "app" / "shared" / "layout" / "layout.html").read_text(
        encoding="utf-8"
    )
    assert 'mode="side"' in layout_html and 'mode="over"' not in layout_html, (
        "layout.html gained a modal sidenav: cover it in the focus trap section"
    )


def test_when_report_is_read_then_the_m3_navigation_breakpoints_are_validated(report):
    """The navigation bar / rail switch is checked on both sides of each M3 boundary."""
    section = "\n".join(_section(report, "600px"))
    for boundary in ("599/600px", "839/840px", "1199/1200px", "1599/1600px"):
        assert boundary in section, (
            f"Navigation breakpoint section must list the {boundary} boundary"
        )
