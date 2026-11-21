"""Keeps the AI framework and its queue infrastructure out of the scaffolder.

The templates and the generators ship no BAML, no LLM provider setting, no chatbot and
no Redis-backed job queue. These guards read the real ``project_initializer/`` tree and
fresh scaffolds, so a re-introduced file name, dependency, environment key or compose
service fails here and names the leftover.
"""

import re
from collections.abc import Iterator
from functools import cache
from pathlib import Path

import pytest
import yaml

from project_initializer.cli import copy_template

_PACKAGE = Path(__file__).resolve().parent.parent / "project_initializer"

_FORBIDDEN_NAME_PARTS = ("baml", "chatbot")
_FORBIDDEN_TEXT = (
    "baml",
    "boundaryml",
    "azure_openai",
    "anthropic_api_key",
    "openai_api_key",
    "ollama",
    "bullmq",
    "bull-board",
    "ioredis",
)

# package-lock.json holds base64 integrity hashes, in which a short term can occur by
# chance; the dependency names they pin are checked through package.json instead.
_SKIPPED_FILE_NAMES = frozenset({"package-lock.json"})

_BINARY_SNIFF_BYTES = 8192
_ENV_KEY = re.compile(r"^\s*([A-Za-z0-9_]+)\s*=", re.MULTILINE)
_REMOVED_ENV_KEY = re.compile(r"^(REDIS_|QUEUE_MONITOR|BAML_LOG$)")

_VARIANTS = [
    pytest.param("nestjs", None, id="nestjs"),
    pytest.param("nestjs", "supabase", id="nestjs-supabase"),
    pytest.param("fastapi", None, id="fastapi"),
    pytest.param("fastapi", "supabase", id="fastapi-supabase"),
]


@cache
def _text_files() -> tuple[tuple[Path, str], ...]:
    """Every text file of the package with its lower-cased content, read once."""
    files = []
    for path in sorted(_PACKAGE.rglob("*")):
        if not path.is_file() or path.name in _SKIPPED_FILE_NAMES:
            continue
        content = path.read_bytes()
        if b"\0" not in content[:_BINARY_SNIFF_BYTES]:
            files.append((path, content.decode("utf-8", errors="replace").lower()))
    return tuple(files)


def _lines_naming(term: str) -> Iterator[str]:
    for path, text in _text_files():
        for number, line in enumerate(text.splitlines(), start=1):
            if term in line:
                yield f"{path.relative_to(_PACKAGE)}:{number}"


def test_when_the_package_tree_is_listed_then_no_name_mentions_the_ai_framework():
    """No file or directory under the package is named after BAML or a chatbot.

    Validates project_initializer/ file and directory names.
    """
    offenders = [
        str(path.relative_to(_PACKAGE))
        for path in _PACKAGE.rglob("*")
        if any(part in path.name.lower() for part in _FORBIDDEN_NAME_PARTS)
    ]

    assert offenders == []


@pytest.mark.parametrize("term", _FORBIDDEN_TEXT)
def test_when_the_package_files_are_read_then_none_mentions_the_term(term):
    """No template or generator file names an AI framework, an LLM provider or the job queue stack.

    Validates the text files of project_initializer/ (templates, generators and defaults).
    """
    assert list(_lines_naming(term)) == []


@pytest.mark.parametrize(("framework", "auth"), _VARIANTS)
def test_when_a_project_is_scaffolded_then_compose_has_no_redis(
    tmp_path, framework, auth
):
    """The compose file declares no redis service and no service waits for one.

    Validates project_initializer/templates-{api,supabase}-{fastapi,nestjs}/docker-compose.yml.
    """
    copy_template(tmp_path, "app", auth=auth, framework=framework)

    compose = yaml.safe_load((tmp_path / "docker-compose.yml").read_text("utf-8"))

    assert "api" in compose["services"]
    assert "redis" not in compose["services"]
    for name, service in compose["services"].items():
        assert "redis" not in service.get("depends_on", {}), name


@pytest.mark.parametrize(("framework", "auth"), _VARIANTS)
def test_when_a_project_is_scaffolded_then_env_files_have_no_queue_or_log_keys(
    tmp_path, framework, auth
):
    """No generated env file sets a Redis, queue dashboard or BAML logging key.

    Validates project_initializer/env_generator.py generate_env() and the .env.example templates.
    """
    copy_template(tmp_path, "app", auth=auth, framework=framework)

    env_files = [path for path in tmp_path.rglob(".env*") if path.is_file()]
    offenders = [
        f"{path.relative_to(tmp_path)}: {key}"
        for path in env_files
        for key in _ENV_KEY.findall(path.read_text("utf-8"))
        if _REMOVED_ENV_KEY.match(key)
    ]

    assert {path.name for path in env_files} >= {".env", ".env.example"}
    assert offenders == []
