"""
Source-blind example tests for issue #3:
feat(entra): add templates-entra-fastapi backend overlay with in-process v2 JWT validation

Tests are derived from acceptance criteria only; no implementation source was read.
Expected to FAIL before the overlay is created and PASS once all files are in place.
"""

import ast
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths — all computed from repo root; nothing under src/ or the overlay is
# opened to derive test logic.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_CLI_PY = _REPO_ROOT / "project_initializer" / "cli.py"
_OVERLAY_ROOT = _REPO_ROOT / "project_initializer" / "templates-entra-fastapi"
_API_ROOT = _OVERLAY_ROOT / "api"
_APP_ROOT = _API_ROOT / "app"
_CONFIG_PY = _APP_ROOT / "infrastructure/settings.py"
_DEPENDENCIES_PY = _APP_ROOT / "api/deps.py"
_REQUIREMENTS_TXT = _API_ROOT / "requirements.txt"
_ENV_EXAMPLE = _API_ROOT / ".env.example"
_AUTH_PY = _APP_ROOT / "api" / "v1" / "endpoints" / "auth.py"

# ---------------------------------------------------------------------------
# Helper — AST-level name extraction; never imports or executes the module
# ---------------------------------------------------------------------------


def _top_level_names(source: str) -> set[str]:
    """Return every name defined or assigned at module level via AST walk."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


# ===========================================================================
# Criterion: --auth entra is available as a fourth auth mode
# ===========================================================================


def test_when_cli_py_is_read_then_entra_is_in_auth_modes():
    """'entra' must appear as a quoted string inside AUTH_MODES so argparse accepts --auth entra."""
    content = _CLI_PY.read_text(encoding="utf-8")
    assert '"entra"' in content or "'entra'" in content, (
        "'entra' not found in cli.py — --auth entra will be rejected by argparse"
    )


# ===========================================================================
# Criterion: templates-entra-fastapi/ ships all required files
# ===========================================================================


@pytest.mark.parametrize(
    "relative_path",
    [
        "api/app/infrastructure/settings.py",
        "api/app/api/deps.py",
        "api/requirements.txt",
        "api/.env.example",
        "api/app/api/v1/endpoints/auth.py",
    ],
)
def test_when_overlay_is_present_then_required_file_exists(relative_path: str):
    assert (_OVERLAY_ROOT / relative_path).exists(), (
        f"Required overlay file missing: {relative_path}"
    )


# ===========================================================================
# Criterion: requirements.txt declares PyJWT[crypto] and httpx; no supabase
# ===========================================================================


class TestRequirementsTxt:
    @pytest.fixture(scope="class")
    def content(self) -> str:
        return _REQUIREMENTS_TXT.read_text(encoding="utf-8")

    def test_when_requirements_are_read_then_pyjwt_crypto_is_declared(
        self, content: str
    ):
        assert "pyjwt[crypto]" in content.lower(), (
            "PyJWT[crypto] must be declared in requirements.txt for in-process JWKS validation"
        )

    def test_when_requirements_are_read_then_httpx_is_declared(self, content: str):
        assert "httpx" in content.lower()

    def test_when_requirements_are_read_then_supabase_is_absent(self, content: str):
        assert "supabase" not in content.lower(), (
            "supabase must not appear in requirements.txt — entra overlay uses PyJWT, not supabase-py"
        )


# ===========================================================================
# Criterion: no client secret appears anywhere in the overlay
# ===========================================================================

_CLIENT_SECRET_RE = re.compile(r"client[_-]?secret", re.IGNORECASE)


@pytest.mark.parametrize(
    "file_path",
    [_CONFIG_PY, _DEPENDENCIES_PY, _ENV_EXAMPLE, _REQUIREMENTS_TXT, _AUTH_PY],
    ids=lambda p: p.name,
)
def test_when_overlay_file_is_read_then_no_client_secret_appears(file_path: Path):
    """Validation is signature-only; no client secret is ever needed or permitted."""
    content = file_path.read_text(encoding="utf-8")
    match = _CLIENT_SECRET_RE.search(content)
    assert match is None, (
        f"Client secret pattern '{match.group()}' found in {file_path.name}"
    )


# ===========================================================================
# Criterion: config.py and .env.example retain the local Docker DATABASE_URL
# ===========================================================================


class TestLocalDockerDatabase:
    def test_when_env_example_is_read_then_database_url_key_is_present(self):
        content = _ENV_EXAMPLE.read_text(encoding="utf-8")
        assert "DATABASE_URL" in content

    def test_when_env_example_is_read_then_supabase_pooler_host_is_absent(self):
        content = _ENV_EXAMPLE.read_text(encoding="utf-8")
        assert "supabase.co" not in content, (
            "Entra overlay must use the local Docker DB, not the Supabase pooler URL"
        )

    def test_when_config_py_is_read_then_database_url_field_is_declared(self):
        source = _CONFIG_PY.read_text(encoding="utf-8")
        assert "DATABASE_URL" in source or "database_url" in source

    def test_when_config_py_is_read_then_supabase_url_field_is_absent(self):
        source = _CONFIG_PY.read_text(encoding="utf-8")
        assert "supabase_url" not in source, (
            "config.py must not declare supabase_url — entra keeps the local Docker DB"
        )

    def test_when_config_py_is_read_then_supabase_publishable_key_field_is_absent(self):
        source = _CONFIG_PY.read_text(encoding="utf-8")
        assert "supabase_publishable_key" not in source


# ===========================================================================
# Criterion: supabase public surface preserved with identical exported names
# ===========================================================================

_REQUIRED_SYMBOLS = [
    "get_current_user",
    "get_optional_user",
    "get_user_id",
    "CurrentUser",
    "OptionalUser",
    "UserId",
    "DBSession",
    "RateLimiter",
    "get_rate_limiter",
    "PaginationParams",
    "Pagination",
]


@pytest.mark.parametrize("symbol", _REQUIRED_SYMBOLS)
def test_when_dependencies_py_is_parsed_then_required_symbol_is_defined(symbol: str):
    """Every name from the supabase surface must be present at module level in dependencies.py."""
    source = _DEPENDENCIES_PY.read_text(encoding="utf-8")
    names = _top_level_names(source)
    assert symbol in names, (
        f"'{symbol}' not found as a top-level name in dependencies.py — "
        "supabase public surface parity is broken"
    )


# ===========================================================================
# Criterion: config.py declares the required Entra-specific settings fields
# ===========================================================================


@pytest.mark.parametrize(
    "field_name",
    [
        "entra_tenant_id",
        "entra_api_client_id",
        "entra_api_audience",
        "entra_api_scope",
        "entra_spa_client_id",
    ],
)
def test_when_config_py_is_read_then_entra_field_is_declared(field_name: str):
    """config.py must expose each ENTRA_* env var as a Pydantic field or property."""
    source = _CONFIG_PY.read_text(encoding="utf-8").lower()
    assert field_name in source, f"Entra setting '{field_name}' not found in config.py"


# ===========================================================================
# Criterion: PyJWKClient is used; no hard-coded key-refresh schedule
# ===========================================================================


def test_when_dependencies_py_is_read_then_pyjwkclient_is_used():
    """In-process JWKS auto-refresh requires PyJWKClient from PyJWT."""
    source = _DEPENDENCIES_PY.read_text(encoding="utf-8")
    assert "PyJWKClient" in source, (
        "PyJWKClient not found in dependencies.py — JWKS key resolution requires it"
    )


@pytest.mark.parametrize(
    "scheduling_pattern",
    [
        "time.sleep",
        "threading.Timer",
        "asyncio.sleep",
        "schedule.every",
        "APScheduler",
    ],
)
def test_when_dependencies_py_is_read_then_no_hardcoded_refresh_schedule_appears(
    scheduling_pattern: str,
):
    """Auto-refresh must rely on PyJWKClient's built-in caching, not an explicit scheduler."""
    source = _DEPENDENCIES_PY.read_text(encoding="utf-8")
    assert scheduling_pattern not in source, (
        f"Hard-coded refresh pattern '{scheduling_pattern}' found in dependencies.py"
    )


# ===========================================================================
# Criterion: authentication failures return 401; scope failure returns 403
# (Static structure check — full runtime validation is in the overlay test suite)
# ===========================================================================


def test_when_dependencies_py_is_read_then_http_401_is_referenced():
    source = _DEPENDENCIES_PY.read_text(encoding="utf-8")
    assert "401" in source or "HTTP_401_UNAUTHORIZED" in source, (
        "No HTTP 401 reference found — authentication failures must return 401"
    )


def test_when_dependencies_py_is_read_then_http_403_is_referenced():
    source = _DEPENDENCIES_PY.read_text(encoding="utf-8")
    assert "403" in source or "HTTP_403_FORBIDDEN" in source, (
        "No HTTP 403 reference found — insufficient scope must return 403, not 401"
    )


def test_when_dependencies_py_is_read_then_scp_claim_is_checked():
    """Scope enforcement must read the 'scp' claim (Entra v2 scope claim name)."""
    source = _DEPENDENCIES_PY.read_text(encoding="utf-8")
    assert '"scp"' in source or "'scp'" in source, (
        "'scp' claim not referenced in dependencies.py — scope enforcement requires it"
    )


def test_when_dependencies_py_is_read_then_tid_claim_is_checked():
    """Tenant pinning must verify the 'tid' claim to prevent cross-tenant token reuse."""
    source = _DEPENDENCIES_PY.read_text(encoding="utf-8")
    assert '"tid"' in source or "'tid'" in source, (
        "'tid' claim not referenced in dependencies.py — tenant pinning requires it"
    )


# ===========================================================================
# Criterion: api/app/api/v1/endpoints/auth.py exposes GET /auth/me returning CurrentUser
# ===========================================================================


def test_when_auth_py_is_read_then_get_me_route_is_declared():
    """The auth router must register the '/me' path for GET requests."""
    source = _AUTH_PY.read_text(encoding="utf-8")
    assert '"/me"' in source or "'/me'" in source, (
        "Route '/me' not found in auth.py — GET /auth/me must be exposed"
    )


def test_when_auth_py_is_read_then_current_user_dependency_is_used():
    """The /auth/me handler must use CurrentUser so the return type is declared in the spec."""
    source = _AUTH_PY.read_text(encoding="utf-8")
    assert "CurrentUser" in source, (
        "CurrentUser not referenced in auth.py — /auth/me must return CurrentUser"
    )
