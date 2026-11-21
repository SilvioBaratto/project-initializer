"""Dependency pins of the FastAPI templates.

Three layers ship a ``requirements.txt`` (the base, supabase and entra); the token
overlay ships none and inherits the base. One Dockerfile layer installs whichever
file the layers merge to, so a dependency that no code imports is attack surface
every scaffold carries.
"""

import re
from pathlib import Path

import pytest

_PACKAGE = Path(__file__).resolve().parent.parent / "project_initializer"
_REQUIREMENT_FILES = {
    "base": _PACKAGE / "templates-api-fastapi" / "api" / "requirements.txt",
    "supabase": _PACKAGE / "templates-supabase-fastapi" / "api" / "requirements.txt",
    "entra": _PACKAGE / "templates-entra-fastapi" / "api" / "requirements.txt",
}

# Neither library is imported by any FastAPI template: the health endpoints read
# no host metrics and there is no Prometheus exposition.
_UNUSED_DEPENDENCIES = ("psutil", "prometheus-client", "prometheus_client")

_REQUIREMENT_LINE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?P<extras>\[[^\]]*\])?(?P<spec>.*)$"
)


def _requirement_lines(variant: str) -> list[str]:
    text = _REQUIREMENT_FILES[variant].read_text(encoding="utf-8")
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _requirement_names(variant: str) -> set[str]:
    names: set[str] = set()
    for line in _requirement_lines(variant):
        match = _REQUIREMENT_LINE.match(line)
        assert match is not None, f"{variant}: unparsable requirement {line!r}"
        names.add(match.group("name").lower())
    return names


@pytest.mark.parametrize("variant", sorted(_REQUIREMENT_FILES))
def test_when_requirements_are_read_then_every_dependency_is_pinned_exactly(
    variant: str,
):
    """Every line pins one version with ``==``, so two scaffolds install the same set.

    Validates project_initializer/templates-{api,supabase,entra}-fastapi/api/requirements.txt.
    """
    for line in _requirement_lines(variant):
        match = _REQUIREMENT_LINE.match(line)
        assert match is not None, f"{variant}: unparsable requirement {line!r}"
        assert match.group("spec").startswith("=="), (
            f"{variant}: {match.group('name')} is not pinned with =="
        )


@pytest.mark.parametrize("variant", sorted(_REQUIREMENT_FILES))
@pytest.mark.parametrize("dependency", _UNUSED_DEPENDENCIES)
def test_when_requirements_are_read_then_an_unused_monitoring_library_is_absent(
    variant: str, dependency: str
):
    """psutil and prometheus-client are not declared by any FastAPI variant.

    Validates project_initializer/templates-{api,supabase,entra}-fastapi/api/requirements.txt.
    """
    assert dependency not in _requirement_names(variant), (
        f"{variant} still declares {dependency}"
    )


def test_when_the_entra_requirements_are_read_then_pyjwt_is_on_the_audited_release():
    """PyJWT stays on 2.15.1, where a failed key-set reload keeps the cached keys.

    The unknown-kid cooldown relies on that to keep known users signed in while
    Entra's key endpoint is down.

    Validates project_initializer/templates-entra-fastapi/api/requirements.txt.
    """
    assert "PyJWT[crypto]==2.15.1" in _requirement_lines("entra")


def test_when_the_base_requirements_are_read_then_the_token_stack_is_pinned():
    """The token overlay ships no requirements and inherits these two pins.

    Validates project_initializer/templates-api-fastapi/api/requirements.txt.
    """
    lines = _requirement_lines("base")
    assert "python-jose[cryptography]==3.5.0" in lines
    assert any(line.startswith("bcrypt==") for line in lines)
    assert "passlib" not in _requirement_names("base")


def test_when_the_token_overlay_is_listed_then_it_ships_no_requirements_file():
    """The token layer inherits the base file; a copy would fork the pins.

    Validates project_initializer/templates-token-fastapi/api/ (absence of requirements.txt).
    """
    token_api = _PACKAGE / "templates-token-fastapi" / "api"
    assert not (token_api / "requirements.txt").exists()
