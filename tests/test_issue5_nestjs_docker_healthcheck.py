"""
Source-blind example tests for issue #5 acceptance criteria (UNIT-verifiable scope criteria).

These tests parse the docker-compose YAML files as data; they never import production source.
All assertions are derived from the acceptance criteria text only.

Criteria under test:
  [UNIT] The `api` service in both templates-api-nestjs/docker-compose.yml and
         templates-supabase-nestjs/docker-compose.yml declares a `healthcheck` that probes
         http://localhost:8000/api/v1/health/liveness with a `start_period` covering migration time.
  [UNIT] The `frontend` service `depends_on` the `api` service with `condition: service_healthy`.
"""

import pathlib
import re

import pytest
import yaml
from hypothesis import given, strategies as st

REPO_ROOT = pathlib.Path(__file__).parent.parent

COMPOSE_FILES = [
    REPO_ROOT / "project_initializer" / "templates-api-nestjs" / "docker-compose.yml",
    REPO_ROOT
    / "project_initializer"
    / "templates-supabase-nestjs"
    / "docker-compose.yml",
]


def load_compose(path: pathlib.Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Healthcheck — api service
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("compose_path", COMPOSE_FILES, ids=lambda p: p.parent.name)
def test_when_api_service_is_read_then_healthcheck_key_is_present(compose_path):
    """Criterion: api service declares a healthcheck."""
    compose = load_compose(compose_path)
    assert "healthcheck" in compose["services"]["api"], (
        f"'healthcheck' key missing from 'api' service in {compose_path}"
    )


@pytest.mark.parametrize("compose_path", COMPOSE_FILES, ids=lambda p: p.parent.name)
def test_when_api_healthcheck_is_read_then_it_probes_liveness_endpoint(compose_path):
    """Criterion: healthcheck probes http://localhost:8000/api/v1/health/liveness."""
    compose = load_compose(compose_path)
    healthcheck = compose["services"]["api"]["healthcheck"]

    # The test field may be a list ["CMD", ...] or ["CMD-SHELL", "..."] or a string.
    test_value = healthcheck.get("test", "")
    if isinstance(test_value, list):
        test_str = " ".join(str(t) for t in test_value)
    else:
        test_str = str(test_value)

    assert "http://localhost:8000/api/v1/health/liveness" in test_str, (
        f"Expected liveness URL in healthcheck.test but got: {test_str!r} in {compose_path}"
    )


@pytest.mark.parametrize("compose_path", COMPOSE_FILES, ids=lambda p: p.parent.name)
def test_when_api_healthcheck_is_read_then_start_period_is_declared(compose_path):
    """Criterion: healthcheck declares a start_period to cover migration time."""
    compose = load_compose(compose_path)
    healthcheck = compose["services"]["api"]["healthcheck"]

    assert "start_period" in healthcheck, (
        f"'start_period' missing from api healthcheck in {compose_path}"
    )


@pytest.mark.parametrize("compose_path", COMPOSE_FILES, ids=lambda p: p.parent.name)
def test_when_api_healthcheck_start_period_is_read_then_it_covers_migration_time(
    compose_path,
):
    """Criterion: start_period is long enough to cover migration time (>= 30s assumed minimum).

    Assumption: 'covering migration time' means at least 30 s, the smallest value that
    meaningfully accommodates Prisma migration on a cold Docker volume.
    """
    compose = load_compose(compose_path)
    start_period_raw = compose["services"]["api"]["healthcheck"]["start_period"]

    # Docker Compose accepts '30s', '1m', '1m30s' etc.
    seconds = _parse_duration_to_seconds(str(start_period_raw))

    assert seconds >= 30, (
        f"start_period {start_period_raw!r} ({seconds}s) < 30s in {compose_path}; "
        "must cover migration time"
    )


# ---------------------------------------------------------------------------
# frontend depends_on api with condition: service_healthy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("compose_path", COMPOSE_FILES, ids=lambda p: p.parent.name)
def test_when_frontend_service_is_read_then_depends_on_api_is_declared(compose_path):
    """Criterion: frontend service depends_on the api service."""
    compose = load_compose(compose_path)
    services = compose.get("services", {})

    if "frontend" not in services:
        pytest.skip(f"No 'frontend' service in {compose_path} (api-scope compose?)")

    depends = services["frontend"].get("depends_on", {})

    # depends_on may be a list of service names or a dict with conditions.
    if isinstance(depends, list):
        assert "api" in depends, (
            f"frontend.depends_on does not list 'api' in {compose_path}"
        )
    else:
        assert "api" in depends, (
            f"frontend.depends_on does not include 'api' in {compose_path}"
        )


@pytest.mark.parametrize("compose_path", COMPOSE_FILES, ids=lambda p: p.parent.name)
def test_when_frontend_depends_on_api_is_read_then_condition_is_service_healthy(
    compose_path,
):
    """Criterion: frontend depends_on api with condition: service_healthy."""
    compose = load_compose(compose_path)
    services = compose.get("services", {})

    if "frontend" not in services:
        pytest.skip(f"No 'frontend' service in {compose_path} (api-scope compose?)")

    depends = services["frontend"].get("depends_on", {})

    assert isinstance(depends, dict), (
        f"frontend.depends_on must be a mapping (not a list) to carry conditions in {compose_path}"
    )
    assert "api" in depends, (
        f"frontend.depends_on does not include 'api' in {compose_path}"
    )
    condition = depends["api"].get("condition", "")
    assert condition == "service_healthy", (
        f"frontend.depends_on.api.condition is {condition!r}, expected 'service_healthy' in {compose_path}"
    )


# ---------------------------------------------------------------------------
# Property: the liveness URL path is stable across any future compose variants
# (invariant: any compose file we generate that has an api healthcheck must
#  contain that exact URL — round-trip structural invariant over the string)
# ---------------------------------------------------------------------------


@given(st.sampled_from(COMPOSE_FILES))
def test_when_any_compose_file_has_api_healthcheck_then_liveness_url_is_always_present(
    compose_path,
):
    """Property: for every compose file in the set, if api has a healthcheck, its test contains the liveness URL."""
    compose = load_compose(compose_path)
    api_service = compose.get("services", {}).get("api", {})
    if "healthcheck" not in api_service:
        return  # not yet implemented — will fail parametrized tests above
    test_value = api_service["healthcheck"].get("test", "")
    if isinstance(test_value, list):
        test_str = " ".join(str(t) for t in test_value)
    else:
        test_str = str(test_value)
    assert "http://localhost:8000/api/v1/health/liveness" in test_str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_duration_to_seconds(value: str) -> float:
    """Convert a Docker duration string like '30s', '1m', '1m30s' to total seconds."""
    total = 0.0
    for amount, unit in re.findall(r"(\d+(?:\.\d+)?)([smh])", value):
        n = float(amount)
        if unit == "s":
            total += n
        elif unit == "m":
            total += n * 60
        elif unit == "h":
            total += n * 3600
    if total == 0.0 and re.match(r"^\d+$", value.strip()):
        # bare integer treated as seconds
        total = float(value.strip())
    return total
