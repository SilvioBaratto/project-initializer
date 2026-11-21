"""Runtime defaults of the generated ``.env`` and ``.env.example``.

``BAML_LOG`` keeps the BAML runtime from printing prompts and replies, which carry
user content. ``NODE_ENV`` of the NestJS file has to match the image the compose
file starts: the dev target installs devDependencies, so a ``development`` value is
only safe there. The production image sets its own ``NODE_ENV`` and never receives
the generated file.
"""

import re
from pathlib import Path

import pytest

from project_initializer.env_generator import generate_env, parse_env

_PACKAGE = Path(__file__).resolve().parent.parent / "project_initializer"
_NESTJS_API = _PACKAGE / "templates-api-nestjs" / "api"
_NESTJS_COMPOSE = _PACKAGE / "templates-api-nestjs" / "docker-compose.yml"
_SUPABASE_NESTJS_COMPOSE = _PACKAGE / "templates-supabase-nestjs" / "docker-compose.yml"

_FRAMEWORKS = ("fastapi", "nestjs")
_AUTH_MODES = (None, "token", "supabase", "entra")
_QUIET_BAML_LEVELS = frozenset({"off", "error"})


def _setting(content: str, key: str) -> str | None:
    """Read one ``KEY=VALUE`` setting of rendered ``.env`` text; None when absent."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            name, _, value = stripped.partition("=")
            if name == key:
                return value.strip('"')
    return None


def _stage(dockerfile: str, name: str) -> str:
    """Return the text of one ``FROM ... AS <name>`` stage."""
    stages = re.split(r"^(?=FROM )", dockerfile, flags=re.M)
    (stage,) = [text for text in stages if re.match(rf"FROM .* AS {name}\b", text)]
    return stage


@pytest.mark.parametrize("framework", _FRAMEWORKS)
@pytest.mark.parametrize("auth", _AUTH_MODES)
def test_when_env_is_generated_then_baml_logging_is_off(framework, auth):
    """The generated ``.env`` silences BAML, whose INFO and WARN logs hold the prompt.

    Validates project_initializer/env_generator.py generate_env().
    """
    content = generate_env(framework, auth)

    assert _setting(content, "BAML_LOG") == "off"


@pytest.mark.parametrize("framework", _FRAMEWORKS)
@pytest.mark.parametrize("auth", _AUTH_MODES)
def test_when_env_example_is_generated_then_baml_logging_is_off(framework, auth):
    """The committed example carries the same quiet default as the ``.env``.

    Validates project_initializer/env_generator.py generate_env(use_placeholders=True).
    """
    content = generate_env(framework, auth, use_placeholders=True)

    assert _setting(content, "BAML_LOG") == "off"


def test_when_the_defaults_file_is_read_then_it_names_baml_log_off():
    """env_defaults.env is where the value comes from; the generator only falls back to it.

    Validates project_initializer/env_defaults.env.
    """
    defaults = parse_env(_PACKAGE / "env_defaults.env")

    assert defaults["BAML_LOG"] == "off"


def test_when_the_root_env_chooses_a_baml_level_then_it_is_kept():
    """An operator who sets BAML_LOG on purpose keeps the choice; only the default is off.

    Validates project_initializer/env_generator.py generate_env().
    """
    content = generate_env("fastapi", None, {"BAML_LOG": "error"})

    assert _setting(content, "BAML_LOG") == "error"
    assert _setting(content, "BAML_LOG") in _QUIET_BAML_LEVELS


def test_when_the_root_env_lacks_baml_log_then_the_fallback_is_off():
    """A root .env written before BAML_LOG existed still yields a quiet scaffold.

    Validates project_initializer/env_generator.py generate_env().
    """
    content = generate_env("nestjs", "token", {})

    assert _setting(content, "BAML_LOG") == "off"


def test_when_fastapi_env_is_generated_then_it_has_no_node_env():
    """NODE_ENV is a NestJS variable; FastAPI selects its mode with ENVIRONMENT.

    Validates project_initializer/env_generator.py generate_env().
    """
    content = generate_env("fastapi", None)

    assert _setting(content, "NODE_ENV") is None
    assert _setting(content, "ENVIRONMENT") == "development"


@pytest.mark.parametrize("compose", [_NESTJS_COMPOSE, _SUPABASE_NESTJS_COMPOSE])
def test_when_nestjs_compose_is_read_then_it_runs_the_dev_target_with_the_env_file(
    compose: Path,
):
    """Compose starts the ``dev`` stage, which installs devDependencies, and feeds it ``.env``.

    That pairing is what makes ``NODE_ENV=development`` (pino-pretty, a
    devDependency) safe in the generated file.

    Validates project_initializer/templates-{api,supabase}-nestjs/docker-compose.yml.
    """
    text = compose.read_text(encoding="utf-8")

    assert re.search(r"^\s+target: dev$", text, re.M)
    assert re.search(r"^\s+- \.env$", text, re.M)


def test_when_the_nestjs_dockerfile_is_read_then_only_the_dev_stage_has_dev_dependencies():
    """The dev stage installs everything; the production stage omits devDependencies.

    The production stage fixes ``NODE_ENV=production`` itself, so a ``development``
    in the generated ``.env`` can only reach it if somebody hands the file over.

    Validates project_initializer/templates-api-nestjs/api/Dockerfile.
    """
    dockerfile = (_NESTJS_API / "Dockerfile").read_text(encoding="utf-8")
    dev = _stage(dockerfile, "dev")
    runtime = dockerfile[dockerfile.rindex("FROM node:") :]

    assert "--omit=dev" not in dev
    assert "npm ci" in dev
    assert "npm ci --omit=dev" in runtime
    assert re.search(r"^ENV NODE_ENV=production\b", runtime, re.M)


def test_when_the_nestjs_dockerignore_is_read_then_the_env_file_stays_out_of_the_image():
    """``.env`` is excluded, so a built image never holds the generated NODE_ENV.

    Validates project_initializer/templates-api-nestjs/api/.dockerignore.
    """
    ignored = (_NESTJS_API / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".env" in ignored
    assert ".env.*" in ignored


def test_when_nestjs_env_is_generated_then_node_env_is_development_with_a_warning():
    """The dev compose target needs ``development``; the comment keeps it off production images.

    Validates project_initializer/env_generator.py generate_env().
    """
    content = generate_env("nestjs", None)
    lines = content.splitlines()
    node_env_index = lines.index("NODE_ENV=development")

    assert "production image" in lines[node_env_index - 1]
    assert "never hand it this file" in lines[node_env_index - 1]
