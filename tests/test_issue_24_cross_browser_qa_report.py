"""
Tests for issue #24: cross-browser/device QA report for shared UI parity.

Verifiable criteria (oracle: UNIT):
  1. The report has a results matrix (browser x device) covering notch clearance,
     dvh full-height under toolbar show/hide, sticky-footer + safe-area, dark-mode
     toggle, and focus traps.
  2. A pytest asserts the report scaffolds and contains each required validation
     heading.

Skipped (oracle: NOT VERIFIABLE):
  - "ships in the frontend template documenting iOS Safari + Chrome + Edge" —
    file presence is side-checked here, but documentation quality is subjective.
  - Real-device iOS testing attestation — prose claim, not machine-checkable.
  - All tests pass — suite gate, not a per-criterion assertion.
  - SOLID / clean-code — subjective.

Design note: all assertions are derived from the criterion text alone.
No implementation source was read when authoring these tests.
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
