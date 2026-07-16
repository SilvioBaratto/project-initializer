"""Unit tests for scope-aware docker-compose transforms."""

import pytest

from project_initializer.cli import (
    copy_template,
    get_api_templates_dir,
    get_auth_overlay_dir,
    get_templates_dir,
)
from project_initializer.file_transforms import (
    filter_compose,
    generate_frontend_compose,
    strip_nginx_proxy_block,
)


def _api_compose(framework):
    return (get_api_templates_dir(framework) / "docker-compose.yml").read_text(
        encoding="utf-8"
    )


def _supabase_compose(framework):
    return (
        get_auth_overlay_dir("supabase", framework) / "docker-compose.yml"
    ).read_text(encoding="utf-8")


# --- filter_compose: fullstack is identity ---------------------------------


@pytest.mark.parametrize("framework", ["fastapi", "nestjs"])
def test_when_fullstack_scope_compose_is_returned_unchanged(framework):
    text = _api_compose(framework)
    assert filter_compose(text, "fullstack") == text


def test_when_supabase_compose_filtered_fullstack_it_is_unchanged():
    text = _supabase_compose("fastapi")
    assert filter_compose(text, "fullstack") == text


# --- filter_compose: api scope removes the frontend service ----------------


@pytest.mark.parametrize("framework", ["fastapi", "nestjs"])
def test_when_api_scope_frontend_service_is_removed(framework):
    result = filter_compose(_api_compose(framework), "api")
    assert "context: ./frontend" not in result
    assert "\n  frontend:\n" not in result


@pytest.mark.parametrize("framework", ["fastapi", "nestjs"])
def test_when_api_scope_db_api_adminer_are_retained(framework):
    result = filter_compose(_api_compose(framework), "api")
    assert "\n  api:\n" in result
    assert "\n  db:\n" in result
    assert "\n  adminer:\n" in result


@pytest.mark.parametrize("framework", ["fastapi", "nestjs"])
def test_when_api_scope_top_level_sections_are_kept(framework):
    result = filter_compose(_api_compose(framework), "api")
    assert "\nvolumes:\n" in result
    assert "  postgres_data:" in result
    assert "\nnetworks:\n" in result


@pytest.mark.parametrize("framework", ["fastapi", "nestjs"])
def test_when_supabase_api_scope_only_api_service_remains(framework):
    result = filter_compose(_supabase_compose(framework), "api")
    assert "\n  frontend:\n" not in result
    assert "\n  api:\n" in result
    # Supabase hosts the database, so these overlays ship no local db service.
    assert "\n  db:\n" not in result


def test_when_api_scope_no_dangling_frontend_anywhere():
    result = filter_compose(_api_compose("fastapi"), "api")
    assert "frontend" not in result


# --- generate_frontend_compose ---------------------------------------------


def test_when_frontend_compose_generated_it_has_only_frontend_service():
    text = generate_frontend_compose()
    assert "  frontend:" in text
    assert "\n  db:\n" not in text
    assert "\n  api:\n" not in text


def test_when_frontend_compose_generated_it_exposes_port_and_network():
    text = generate_frontend_compose()
    # Host port is parametrized via the compose-topology var, defaulting to 4200.
    assert '- "${FRONTEND_HOST_PORT:-4200}:80"' in text
    assert "context: ./frontend" in text
    assert "\nnetworks:\n" in text


def test_when_frontend_compose_generated_it_has_no_depends_on():
    assert "depends_on" not in generate_frontend_compose()


# --- cli wiring: scaffolded compose reflects scope -------------------------


def test_when_api_scope_scaffolded_compose_has_no_frontend_service(tmp_path):
    copy_template(tmp_path, "app", auth=None, framework="fastapi", scope="api")
    compose = (tmp_path / "docker-compose.yml").read_text(encoding="utf-8")
    assert "\n  frontend:\n" not in compose
    assert "\n  api:\n" in compose


def test_when_supabase_api_scope_scaffolded_compose_is_api_only(tmp_path):
    copy_template(tmp_path, "app", auth="supabase", framework="fastapi", scope="api")
    compose = (tmp_path / "docker-compose.yml").read_text(encoding="utf-8")
    assert "\n  frontend:\n" not in compose
    assert "\n  api:\n" in compose


def test_when_frontend_scope_a_frontend_only_compose_is_generated(tmp_path):
    copy_template(tmp_path, "app", auth=None, framework="fastapi", scope="frontend")
    compose = (tmp_path / "docker-compose.yml").read_text(encoding="utf-8")
    assert "  frontend:" in compose
    assert "\n  api:\n" not in compose


def test_when_fullstack_scope_scaffolded_compose_is_byte_identical(tmp_path):
    copy_template(tmp_path, "app", auth=None, framework="fastapi", scope="fullstack")
    scaffolded = (tmp_path / "docker-compose.yml").read_text(encoding="utf-8")
    assert scaffolded == _api_compose("fastapi")


# --- strip_nginx_proxy_block -----------------------------------------------


def _nginx_text():
    return (get_templates_dir() / "frontend" / "nginx.conf").read_text(encoding="utf-8")


def test_when_proxy_block_stripped_location_api_is_removed():
    result = strip_nginx_proxy_block(_nginx_text())
    assert "location /api/" not in result
    assert "proxy_pass" not in result


def test_when_proxy_block_stripped_health_and_root_locations_are_kept():
    result = strip_nginx_proxy_block(_nginx_text())
    assert "location /health" in result
    assert "location / {" in result


def test_when_proxy_block_stripped_braces_stay_balanced():
    result = strip_nginx_proxy_block(_nginx_text())
    assert result.count("{") == result.count("}")


def test_when_strip_applied_twice_result_is_unchanged():
    once = strip_nginx_proxy_block(_nginx_text())
    assert strip_nginx_proxy_block(once) == once


def test_when_no_proxy_block_present_text_is_returned_unchanged():
    text = "server {\n    location / {\n        try_files $uri /index.html;\n    }\n}\n"
    assert strip_nginx_proxy_block(text) == text


# --- cli wiring: scaffolded nginx.conf reflects scope ----------------------


def test_when_frontend_scope_scaffolded_nginx_has_no_api_proxy(tmp_path):
    copy_template(tmp_path, "app", auth=None, framework="fastapi", scope="frontend")
    nginx = (tmp_path / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    assert "location /api/" not in nginx
    assert "location /health" in nginx


def test_when_fullstack_scope_scaffolded_nginx_is_byte_identical(tmp_path):
    copy_template(tmp_path, "app", auth=None, framework="fastapi", scope="fullstack")
    scaffolded = (tmp_path / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    api_nginx = (
        get_api_templates_dir("fastapi") / "frontend" / "nginx.conf"
    ).read_text(encoding="utf-8")
    assert scaffolded == api_nginx
    assert "location /api/" in scaffolded
