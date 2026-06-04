"""Integration tests for scope-aware copy_template routing + the file hook."""

import pytest

from project_initializer.cli import _copy_file, copy_template


# --- _copy_file: the per-file copy-or-transform contract -------------------


def test_when_no_transform_binary_file_is_copied_byte_for_byte(tmp_path):
    src = tmp_path / "favicon.ico"
    src.write_bytes(b"\x00\x01\xff\xfe binary \x00")
    dst = tmp_path / "out.ico"
    _copy_file(src, dst, None)
    assert dst.read_bytes() == src.read_bytes()


def test_when_transform_returns_none_file_falls_through_to_copy2(tmp_path):
    src = tmp_path / "favicon.ico"
    src.write_bytes(b"\x00\x01\xff\xfe")
    dst = tmp_path / "out.ico"
    _copy_file(src, dst, lambda path: None)
    assert dst.read_bytes() == src.read_bytes()


def test_when_transform_returns_text_transformed_content_is_written(tmp_path):
    src = tmp_path / "docker-compose.yml"
    src.write_text("services:\n  frontend:\n", encoding="utf-8")
    dst = tmp_path / "out.yml"
    _copy_file(src, dst, lambda path: "transformed")
    assert dst.read_text(encoding="utf-8") == "transformed"


# --- copy_template: scope-aware output tree --------------------------------


def test_when_api_scope_api_dir_and_env_exist_and_frontend_is_absent(tmp_path):
    copy_template(tmp_path, "app", auth=None, framework="fastapi", scope="api")
    assert (tmp_path / "api").exists()
    assert (tmp_path / "api" / ".env").exists()
    assert (tmp_path / "docker-compose.yml").exists()
    assert not (tmp_path / "frontend").exists()


def test_when_api_scope_root_configs_are_kept(tmp_path):
    copy_template(tmp_path, "app", auth=None, framework="fastapi", scope="api")
    assert (tmp_path / ".gitignore").exists()
    assert (tmp_path / ".env.example").exists()


def test_when_frontend_scope_frontend_exists_and_api_is_absent(tmp_path):
    copy_template(tmp_path, "app", auth=None, framework="fastapi", scope="frontend")
    assert (tmp_path / "frontend").exists()
    assert not (tmp_path / "api").exists()


def test_when_frontend_scope_no_api_env_is_generated(tmp_path):
    copy_template(tmp_path, "app", auth=None, framework="fastapi", scope="frontend")
    assert not (tmp_path / "api").exists()
    assert not (tmp_path / "api" / ".env").exists()


@pytest.mark.parametrize("framework", ["fastapi", "nestjs"])
def test_when_fullstack_scope_both_halves_are_present(tmp_path, framework):
    copy_template(tmp_path, "app", auth=None, framework=framework, scope="fullstack")
    assert (tmp_path / "api").exists()
    assert (tmp_path / "frontend").exists()
    assert (tmp_path / "api" / ".env").exists()


def test_when_scope_defaults_to_fullstack_both_halves_present(tmp_path):
    copy_template(tmp_path, "app", auth=None, framework="fastapi")
    assert (tmp_path / "api").exists()
    assert (tmp_path / "frontend").exists()


def test_when_api_scope_no_orphan_frontend_dir_is_left(tmp_path):
    copy_template(tmp_path, "app", auth=None, framework="fastapi", scope="api")
    assert "frontend" not in {p.name for p in tmp_path.iterdir()}
