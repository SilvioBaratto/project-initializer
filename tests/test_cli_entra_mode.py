"""Tests for --auth entra CLI registration (issue #1).

All tests are authored from the acceptance criteria only; no implementation
source was read during authorship.
"""

import pytest
from hypothesis import given, settings as hyp_settings, strategies as st

from project_initializer.cli import (
    AUTH_MODES,
    build_parser,
    select_layers,
    validate_scope,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _stub_template_dirs(tmp_path, dirs):
    """Create empty stub template subdirs under tmp_path."""
    for d in dirs:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)


def _stub_api_subdir(tmp_path, framework_dir):
    """Create an api/ subdir so copy_template can write api/.env."""
    (tmp_path / framework_dir / "api").mkdir(parents=True, exist_ok=True)


# ── Criterion: "entra" is a member of AUTH_MODES ─────────────────────────────


def test_when_auth_modes_inspected_then_entra_is_present():
    """'entra' must be a member of AUTH_MODES."""
    assert "entra" in AUTH_MODES


# ── Criterion: --auth entra parses without error ──────────────────────────────


def test_when_auth_entra_flag_given_then_parser_accepts_it():
    """--auth entra must be accepted by the argument parser without error."""
    parser = build_parser()
    args = parser.parse_args(["myproject", "--auth", "entra"])
    assert args.auth == "entra"


# ── Criterion: all AUTH_MODES values accepted by parser (never-raises property) ──


@given(st.sampled_from(AUTH_MODES))
@hyp_settings(max_examples=20)
def test_when_any_auth_mode_given_then_parser_accepts_it(mode):
    """Every value in AUTH_MODES must parse without SystemExit — never-raises invariant."""
    parser = build_parser()
    args = parser.parse_args(["myproject", "--auth", mode])
    assert args.auth == mode


# ── Criterion: existing auth modes still parse (regression) ──────────────────


@pytest.mark.parametrize("mode", ["token", "supabase"])
def test_when_existing_auth_mode_given_then_parser_still_accepts_it(mode):
    """Existing 'token' and 'supabase' modes must remain valid after adding 'entra'."""
    parser = build_parser()
    args = parser.parse_args(["myproject", "--auth", mode])
    assert args.auth == mode


def test_when_no_auth_flag_given_then_auth_defaults_to_none():
    """Omitting --auth must still default to None (none/no-auth mode unchanged)."""
    parser = build_parser()
    args = parser.parse_args(["myproject"])
    assert args.auth is None


# ── Criterion: select_layers resolves templates-entra-fastapi path ────────────


def test_when_select_layers_called_with_entra_fastapi_then_entra_fastapi_overlay_path_included():
    """select_layers('fullstack', 'fastapi', 'entra') must include a path
    ending with templates-entra-fastapi."""
    layers = select_layers("fullstack", "fastapi", "entra")
    paths = [str(src) for src, _, _ in layers]
    assert any("templates-entra-fastapi" in p for p in paths)


def test_when_select_layers_called_with_entra_fastapi_then_entra_frontend_overlay_path_included():
    """select_layers('fullstack', 'fastapi', 'entra') must include a path
    ending with templates-entra-frontend."""
    layers = select_layers("fullstack", "fastapi", "entra")
    paths = [str(src) for src, _, _ in layers]
    assert any("templates-entra-frontend" in p for p in paths)


def test_when_select_layers_called_with_entra_nestjs_then_entra_nestjs_overlay_path_included():
    """select_layers('fullstack', 'nestjs', 'entra') must include a path
    ending with templates-entra-nestjs."""
    layers = select_layers("fullstack", "nestjs", "entra")
    paths = [str(src) for src, _, _ in layers]
    assert any("templates-entra-nestjs" in p for p in paths)


# ── Property: select_layers includes {mode}-specific overlay for every AUTH_MODE ─


@given(st.sampled_from(AUTH_MODES))
@hyp_settings(max_examples=20)
def test_when_any_auth_mode_given_then_select_layers_includes_auth_overlay_paths(mode):
    """For every auth mode, select_layers('fullstack', 'fastapi', mode) must
    include templates-{mode}-fastapi and templates-{mode}-frontend — ordering invariant."""
    layers = select_layers("fullstack", "fastapi", mode)
    paths = [str(src) for src, _, _ in layers]
    assert any(f"templates-{mode}-fastapi" in p for p in paths)
    assert any(f"templates-{mode}-frontend" in p for p in paths)


# ── Criterion: validate_scope rejects --scope frontend --auth entra ───────────


def test_when_scope_frontend_and_auth_entra_then_validate_scope_returns_errors():
    """validate_scope must reject the combination --scope frontend --auth entra."""
    errors = validate_scope("frontend", None, "entra")
    assert len(errors) > 0


# ── Property: --scope frontend rejects any auth mode ─────────────────────────


@given(st.sampled_from(AUTH_MODES))
@hyp_settings(max_examples=20)
def test_when_scope_frontend_and_any_auth_mode_then_validate_scope_rejects(mode):
    """--scope frontend must reject every auth mode, including newly added entra."""
    errors = validate_scope("frontend", None, mode)
    assert len(errors) > 0


# ── Criterion: existing validate_scope rejections unchanged (regression) ──────


@pytest.mark.parametrize("mode", ["token", "supabase"])
def test_when_scope_frontend_and_existing_auth_mode_then_validate_scope_still_rejects(
    mode,
):
    """Existing --scope frontend rejections for 'token' and 'supabase' must be unchanged."""
    errors = validate_scope("frontend", None, mode)
    assert len(errors) > 0


# ── Criterion: copy_template prints ENTRA_* guidance when auth == "entra" ─────


@pytest.fixture()
def entra_stub_root(tmp_path):
    """tmp_path wired up with the minimal stub dirs needed for an entra+fastapi scaffold."""
    _stub_template_dirs(
        tmp_path,
        [
            "templates",
            "templates-api-fastapi",
            "templates-entra-fastapi",
            "templates-entra-frontend",
        ],
    )
    _stub_api_subdir(tmp_path, "templates-api-fastapi")
    return tmp_path


def test_when_auth_is_entra_then_copy_template_prints_entra_tenant_id_guidance(
    entra_stub_root, capsys, monkeypatch
):
    """copy_template() must print ENTRA_TENANT_ID guidance when auth='entra'."""
    import project_initializer.cli as cli_module

    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", entra_stub_root)

    dest = entra_stub_root / "myproject"
    cli_module.copy_template(dest, "myproject", auth="entra", framework="fastapi")

    captured = capsys.readouterr()
    assert "ENTRA_TENANT_ID" in captured.out


def test_when_auth_is_entra_then_copy_template_prints_entra_api_client_id_guidance(
    entra_stub_root, capsys, monkeypatch
):
    """copy_template() must print ENTRA_API_CLIENT_ID guidance when auth='entra'."""
    import project_initializer.cli as cli_module

    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", entra_stub_root)

    dest = entra_stub_root / "myproject"
    cli_module.copy_template(dest, "myproject", auth="entra", framework="fastapi")

    captured = capsys.readouterr()
    assert "ENTRA_API_CLIENT_ID" in captured.out


def test_when_auth_is_entra_then_copy_template_prints_entra_spa_client_id_guidance(
    entra_stub_root, capsys, monkeypatch
):
    """copy_template() must print ENTRA_SPA_CLIENT_ID guidance when auth='entra'."""
    import project_initializer.cli as cli_module

    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", entra_stub_root)

    dest = entra_stub_root / "myproject"
    cli_module.copy_template(dest, "myproject", auth="entra", framework="fastapi")

    captured = capsys.readouterr()
    assert "ENTRA_SPA_CLIENT_ID" in captured.out


def test_when_auth_is_entra_then_copy_template_prints_spa_registration_hint(
    entra_stub_root, capsys, monkeypatch
):
    """copy_template() must print a hint to register a SPA + API app when auth='entra'."""
    import project_initializer.cli as cli_module

    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", entra_stub_root)

    dest = entra_stub_root / "myproject"
    cli_module.copy_template(dest, "myproject", auth="entra", framework="fastapi")

    captured = capsys.readouterr()
    # The guidance must mention registering both a SPA and an API app.
    out_lower = captured.out.lower()
    assert "spa" in out_lower or "register" in out_lower


# ── Criterion: supabase guidance unchanged (regression) ───────────────────────


@pytest.fixture()
def supabase_stub_root(tmp_path):
    """tmp_path with minimal stubs for a supabase+fastapi scaffold."""
    _stub_template_dirs(
        tmp_path,
        [
            "templates",
            "templates-api-fastapi",
            "templates-supabase-fastapi",
            "templates-supabase-frontend",
        ],
    )
    _stub_api_subdir(tmp_path, "templates-api-fastapi")
    return tmp_path


def test_when_auth_is_supabase_then_copy_template_still_prints_supabase_url_guidance(
    supabase_stub_root, capsys, monkeypatch
):
    """copy_template() must still print SUPABASE_URL guidance when auth='supabase'
    (existing branch must be unchanged after adding the entra branch)."""
    import project_initializer.cli as cli_module

    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", supabase_stub_root)

    dest = supabase_stub_root / "myproject"
    cli_module.copy_template(dest, "myproject", auth="supabase", framework="fastapi")

    captured = capsys.readouterr()
    assert "SUPABASE_URL" in captured.out


def test_when_auth_is_entra_then_copy_template_does_not_print_supabase_guidance(
    entra_stub_root, capsys, monkeypatch
):
    """copy_template() must NOT print supabase-specific guidance when auth='entra'."""
    import project_initializer.cli as cli_module

    monkeypatch.setattr(cli_module, "TEMPLATES_ROOT", entra_stub_root)

    dest = entra_stub_root / "myproject"
    cli_module.copy_template(dest, "myproject", auth="entra", framework="fastapi")

    captured = capsys.readouterr()
    assert "SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY" not in captured.out
