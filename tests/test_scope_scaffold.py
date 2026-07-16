"""End-to-end integration tests for scope x framework x auth scaffolding.

Drives ``copy_template`` directly into ``tmp_path`` and inspects the output
tree. Covers routing (#5), compose filtering (#6), and nginx stripping (#7).
Test data is read from the real template files so fixtures cannot drift.
"""

import hashlib
import re

import pytest

from project_initializer.cli import copy_template, get_api_templates_dir

FRAMEWORKS = ["fastapi", "nestjs"]
AUTHS = [None, "token", "supabase"]
ROOT_CONFIGS = [".env.example", ".gitignore", ".github", ".vscode", "CLAUDE.md"]

_SERVICE_RE = re.compile(r"^  ([a-z0-9_-]+):$")


def _scaffold(dest, scope, framework="fastapi", auth=None):
    copy_template(dest, "app", auth=auth, framework=framework, scope=scope)


def _compose_services(text):
    """Return the service names declared under ``services:`` (no PyYAML)."""
    services, in_services = [], False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line == "services:":
            in_services = True
            continue
        if in_services and line and not line[0].isspace():
            break
        match = _SERVICE_RE.match(line)
        if in_services and match:
            services.append(match.group(1))
    return services


def _tree_hashes(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# --- api scope --------------------------------------------------------------


@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize("auth", AUTHS)
def test_when_api_scope_api_and_env_exist_without_frontend(tmp_path, framework, auth):
    _scaffold(tmp_path, "api", framework, auth)
    assert (tmp_path / "api").exists()
    assert (tmp_path / ".env").exists()
    assert not (tmp_path / "frontend").exists()


@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize("auth", AUTHS)
def test_when_api_scope_compose_has_no_frontend_service(tmp_path, framework, auth):
    _scaffold(tmp_path, "api", framework, auth)
    services = _compose_services((tmp_path / "docker-compose.yml").read_text())
    assert "frontend" not in services
    assert "api" in services


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_when_api_scope_non_supabase_keeps_db_and_adminer(tmp_path, framework):
    _scaffold(tmp_path, "api", framework, None)
    services = _compose_services((tmp_path / "docker-compose.yml").read_text())
    assert "db" in services
    assert "adminer" in services


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_when_api_scope_supabase_has_no_db_or_adminer(tmp_path, framework):
    _scaffold(tmp_path, "api", framework, "supabase")
    services = _compose_services((tmp_path / "docker-compose.yml").read_text())
    assert "db" not in services
    assert "adminer" not in services
    assert "api" in services


# --- frontend scope ---------------------------------------------------------


def test_when_frontend_scope_no_api_dir_or_env(tmp_path):
    _scaffold(tmp_path, "frontend")
    assert not (tmp_path / "api").exists()
    assert not (tmp_path / "api" / ".env").exists()
    assert (tmp_path / "frontend").exists()


def test_when_frontend_scope_nginx_has_no_api_proxy(tmp_path):
    _scaffold(tmp_path, "frontend")
    nginx = (tmp_path / "frontend" / "nginx.conf").read_text()
    assert "location /api/" not in nginx


def test_when_frontend_scope_compose_has_no_backend_services(tmp_path):
    _scaffold(tmp_path, "frontend")
    compose = tmp_path / "docker-compose.yml"
    if not compose.exists():
        return
    services = _compose_services(compose.read_text())
    assert "db" not in services
    assert "adminer" not in services
    assert "api" not in services


# --- fullstack scope + byte-for-byte guarantee ------------------------------


@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize("auth", AUTHS)
def test_when_fullstack_scope_both_halves_present(tmp_path, framework, auth):
    _scaffold(tmp_path, "fullstack", framework, auth)
    assert (tmp_path / "api").exists()
    assert (tmp_path / "frontend").exists()
    assert (tmp_path / ".env").exists()


@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize("auth", AUTHS)
def test_when_fullstack_scaffolded_twice_trees_are_identical(tmp_path, framework, auth):
    first, second = tmp_path / "first", tmp_path / "second"
    _scaffold(first, "fullstack", framework, auth)
    _scaffold(second, "fullstack", framework, auth)
    assert _tree_hashes(first) == _tree_hashes(second)


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_when_fullstack_compose_matches_template_byte_for_byte(tmp_path, framework):
    _scaffold(tmp_path, "fullstack", framework, None)
    scaffolded = (tmp_path / "docker-compose.yml").read_text()
    template = (get_api_templates_dir(framework) / "docker-compose.yml").read_text()
    assert scaffolded == template


def test_when_fullstack_scope_nginx_keeps_api_proxy(tmp_path):
    _scaffold(tmp_path, "fullstack")
    assert "location /api/" in (tmp_path / "frontend" / "nginx.conf").read_text()


# --- root configs present in every scope ------------------------------------


@pytest.mark.parametrize(
    "scope,framework,auth",
    [
        ("fullstack", "fastapi", None),
        ("api", "fastapi", None),
        ("frontend", "fastapi", None),
    ],
)
@pytest.mark.parametrize("config", ROOT_CONFIGS)
def test_when_any_scope_root_config_is_present(
    tmp_path, scope, framework, auth, config
):
    _scaffold(tmp_path, scope, framework, auth)
    assert (tmp_path / config).exists()


# --- no orphan directory for the skipped half -------------------------------


def test_when_api_scope_no_orphan_frontend_dir(tmp_path):
    _scaffold(tmp_path, "api")
    assert "frontend" not in {p.name for p in tmp_path.iterdir()}


def test_when_frontend_scope_no_orphan_api_dir(tmp_path):
    _scaffold(tmp_path, "frontend")
    assert "api" not in {p.name for p in tmp_path.iterdir()}
