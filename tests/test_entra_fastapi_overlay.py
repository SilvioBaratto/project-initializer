"""
Source-blind example tests for issue #3:
feat(entra): add templates-entra-fastapi backend overlay with in-process v2 JWT validation

Tests are derived from acceptance criteria only. The overlay replaces the auth
seam of the base layer: ``api/auth_deps.py`` (the dependency), ``infrastructure/
auth_settings.py`` (the settings) and a new ``infrastructure/auth/entra.py`` (the
verifier). Everything else, such as ``deps.py``, ``settings.py`` and the auth
route, is inherited from the base layer and never forked.
"""

import ast
import re
import tomllib
from pathlib import Path

import pytest

from tests.fastapi_entra_sources import (
    auth_failure_statuses_are_wired,
    base_handlers_text,
    entra_auth_deps_text,
    entra_auth_settings_text,
    entra_verifier_text,
    generated_entra_env_example,
)

# ---------------------------------------------------------------------------
# Paths — all computed from repo root.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_PACKAGE_ROOT = _REPO_ROOT / "project_initializer"
_CLI_PY = _PACKAGE_ROOT / "cli.py"
_OVERLAY_ROOT = _PACKAGE_ROOT / "templates-entra-fastapi"
_API_ROOT = _OVERLAY_ROOT / "api"
_PYPROJECT_TOML = _API_ROOT / "pyproject.toml"
_BASE_APP_ROOT = _PACKAGE_ROOT / "templates-api-fastapi" / "api" / "app"
_BASE_SETTINGS_PY = _BASE_APP_ROOT / "infrastructure" / "settings.py"
_BASE_AUTH_PY = _BASE_APP_ROOT / "api" / "v1" / "endpoints" / "auth.py"
_BASE_PAGINATION_PY = _BASE_APP_ROOT / "api" / "pagination.py"

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
    """'entra' must appear as a quoted string inside AUTH_MODES so argparse accepts --auth entra.

    Validates project_initializer/cli.py.
    """
    content = _CLI_PY.read_text(encoding="utf-8")
    assert '"entra"' in content or "'entra'" in content, (
        "'entra' not found in cli.py — --auth entra will be rejected by argparse"
    )


# ===========================================================================
# Criterion: templates-entra-fastapi/ ships the seam, the settings and the verifier
# ===========================================================================


@pytest.mark.parametrize(
    "relative_path",
    [
        "api/app/api/auth_deps.py",
        "api/app/infrastructure/auth_settings.py",
        "api/app/infrastructure/auth/entra.py",
        "api/pyproject.toml",
        "api/tests/auth_test_env.py",
        "api/tests/entra_tokens.py",
        "api/tests/integration/test_auth.py",
    ],
)
def test_when_overlay_is_present_then_required_file_exists(relative_path: str):
    """The overlay ships the seam, the settings, the verifier and its own tests.

    Validates project_initializer/templates-entra-fastapi/api (seam, settings, verifier, pyproject.toml and test helpers).
    """
    assert (_OVERLAY_ROOT / relative_path).exists(), (
        f"Required overlay file missing: {relative_path}"
    )


@pytest.mark.parametrize(
    "relative_path",
    [
        "api/app/api/deps.py",
        "api/app/api/v1/router.py",
        "api/app/api/v1/endpoints/auth.py",
        "api/app/infrastructure/settings.py",
        "api/.env.example",
    ],
)
def test_when_overlay_is_present_then_a_base_file_is_not_forked(relative_path: str):
    """A layer overwrites by path, so a copy of a base file silently forks it.

    The overlay replaces only the auth seam; ``deps.py``, the router, the auth
    route and ``settings.py`` come from the base layer, and the CLI generates
    ``.env.example``.

    Validates project_initializer/templates-entra-fastapi/api (absence of forked base files).
    """
    assert not (_OVERLAY_ROOT / relative_path).exists(), (
        f"{relative_path} must not be shipped by the entra overlay"
    )


# ===========================================================================
# Criterion: pyproject.toml declares PyJWT[crypto] and httpx; no supabase
# ===========================================================================


def _dependency_names(entries: list[str]) -> set[str]:
    """Return the lower-cased distribution names of PEP 508 requirement strings."""
    return {
        re.split(r"[\[=<>!~;\s]", entry, maxsplit=1)[0].lower() for entry in entries
    }


class TestPyprojectDependencies:
    """Dependency declarations of the entra overlay."""

    @pytest.fixture(scope="class")
    @classmethod
    def manifest(cls) -> dict:
        """Parsed pyproject.toml of the overlay."""
        with _PYPROJECT_TOML.open("rb") as handle:
            return tomllib.load(handle)

    def test_when_dependencies_are_read_then_pyjwt_crypto_is_declared(
        self, manifest: dict
    ):
        """PyJWT with the crypto extra verifies RS256 signatures.

        Validates project_initializer/templates-entra-fastapi/api/pyproject.toml.
        """
        runtime = [entry.lower() for entry in manifest["project"]["dependencies"]]
        assert any(entry.startswith("pyjwt[crypto]") for entry in runtime), (
            "PyJWT[crypto] must be declared in pyproject.toml for in-process JWKS validation"
        )

    def test_when_dependencies_are_read_then_pyjwt_is_pinned_to_the_audited_release(
        self, manifest: dict
    ):
        """PyJWT stays on 2.15.1: a failed key-set reload there keeps the cached keys.

        Validates project_initializer/templates-entra-fastapi/api/pyproject.toml.
        """
        assert "PyJWT[crypto]==2.15.1" in manifest["project"]["dependencies"]

    def test_when_dependencies_are_read_then_httpx_is_declared(self, manifest: dict):
        """httpx is the HTTP client the template and its tests rely on.

        Validates project_initializer/templates-entra-fastapi/api/pyproject.toml.
        """
        assert "httpx" in _dependency_names(manifest["project"]["dependencies"])

    def test_when_dependencies_are_read_then_supabase_is_absent(self, manifest: dict):
        """The entra variant must not pull in the Supabase client.

        Validates project_initializer/templates-entra-fastapi/api/pyproject.toml.
        """
        declared = (
            manifest["project"]["dependencies"]
            + manifest["project"]["optional-dependencies"]["dev"]
        )
        assert not any("supabase" in name for name in _dependency_names(declared)), (
            "supabase must not appear in pyproject.toml — entra overlay uses PyJWT, not supabase-py"
        )


# ===========================================================================
# Criterion: no client secret appears anywhere in the overlay
# ===========================================================================

_CLIENT_SECRET_RE = re.compile(r"client[_-]?secret", re.IGNORECASE)

_CLIENT_SECRET_SOURCES = {
    "auth_settings.py": entra_auth_settings_text,
    "auth_deps.py": entra_auth_deps_text,
    "entra.py": entra_verifier_text,
    "generated .env.example": generated_entra_env_example,
    "pyproject.toml": lambda: _PYPROJECT_TOML.read_text(encoding="utf-8"),
    "base auth.py": lambda: _BASE_AUTH_PY.read_text(encoding="utf-8"),
}


@pytest.mark.parametrize("source_name", list(_CLIENT_SECRET_SOURCES))
def test_when_overlay_file_is_read_then_no_client_secret_appears(source_name: str):
    """Validation is signature-only; no client secret is ever needed or permitted.

    Validates project_initializer/templates-entra-fastapi/api sources, the generated .env.example (project_initializer/env_generator.py generate_env()) and project_initializer/templates-api-fastapi/api/app/api/v1/endpoints/auth.py.
    """
    content = _CLIENT_SECRET_SOURCES[source_name]()
    match = _CLIENT_SECRET_RE.search(content)
    assert match is None, (
        f"Client secret pattern '{match.group()}' found in {source_name}"
    )


# ===========================================================================
# Criterion: the generated .env.example and the settings retain the local
# Docker DATABASE_URL
# ===========================================================================


class TestLocalDockerDatabase:
    """The entra variant uses the local Docker database, not a hosted one."""

    def test_when_env_example_is_read_then_database_url_key_is_present(self):
        """The generated example names the database URL.

        Validates project_initializer/env_generator.py generate_env() (fastapi, entra, use_placeholders=True).
        """
        assert "DATABASE_URL" in generated_entra_env_example()

    def test_when_env_example_is_read_then_supabase_pooler_host_is_absent(self):
        """The generated example points at no Supabase host.

        Validates project_initializer/env_generator.py generate_env() (fastapi, entra, use_placeholders=True).
        """
        assert "supabase.co" not in generated_entra_env_example(), (
            "Entra overlay must use the local Docker DB, not the Supabase pooler URL"
        )

    def test_when_base_settings_are_read_then_database_url_field_is_declared(self):
        """The base settings own the database URL the overlay inherits.

        Validates project_initializer/templates-api-fastapi/api/app/infrastructure/settings.py.
        """
        source = _BASE_SETTINGS_PY.read_text(encoding="utf-8")
        assert "DATABASE_URL" in source or "database_url" in source

    @pytest.mark.parametrize(
        "source_reader", [entra_auth_settings_text, entra_auth_deps_text]
    )
    def test_when_entra_auth_files_are_read_then_supabase_settings_are_absent(
        self, source_reader
    ):
        """Neither entra auth module declares a Supabase setting.

        Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth_settings.py and project_initializer/templates-entra-fastapi/api/app/api/auth_deps.py.
        """
        source = source_reader()
        assert "supabase_url" not in source, (
            "the entra overlay must not declare supabase_url — it keeps the local Docker DB"
        )
        assert "supabase_publishable_key" not in source


# ===========================================================================
# Criterion: the auth seam keeps the names every route and the role guard import
# ===========================================================================

_SEAM_SYMBOLS = ["get_current_user", "get_token_verifier", "CurrentUser"]


@pytest.mark.parametrize("symbol", _SEAM_SYMBOLS)
def test_when_auth_deps_is_parsed_then_seam_symbol_is_defined(symbol: str):
    """The seam module must define every name the base routes import from it.

    ``get_optional_user``, ``get_user_id``, ``DBSession`` and the per-process rate
    limiter no longer exist: routes depend on ``CurrentUser`` only, sessions come
    from ``get_db``, and the limiter is a middleware.

    Validates project_initializer/templates-entra-fastapi/api/app/api/auth_deps.py.
    """
    names = _top_level_names(entra_auth_deps_text())
    assert symbol in names, (
        f"'{symbol}' not found as a top-level name in auth_deps.py — "
        "the auth seam surface is broken"
    )


@pytest.mark.parametrize("symbol", ["PaginationParams", "Pagination"])
def test_when_base_pagination_is_parsed_then_pagination_symbol_is_defined(symbol: str):
    """Pagination moved out of the overlay's dependencies into the base ``pagination.py``.

    Validates project_initializer/templates-api-fastapi/api/app/api/pagination.py.
    """
    names = _top_level_names(_BASE_PAGINATION_PY.read_text(encoding="utf-8"))
    assert symbol in names


# ===========================================================================
# Criterion: auth_settings.py declares the required Entra-specific settings fields
# ===========================================================================


@pytest.mark.parametrize(
    "field_name",
    [
        "entra_tenant_id",
        "entra_api_client_id",
        "entra_api_audience",
        "entra_api_scope",
        "entra_authority",
        "entra_jwks_timeout",
        "entra_jwks_refresh_cooldown",
    ],
)
def test_when_auth_settings_is_read_then_entra_field_is_declared(field_name: str):
    """auth_settings.py must expose each ENTRA_* env var as a Pydantic field or property.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth_settings.py.
    """
    source = entra_auth_settings_text().lower()
    assert field_name in source, (
        f"Entra setting '{field_name}' not found in auth_settings.py"
    )


def test_when_auth_settings_is_read_then_the_spa_client_id_is_not_a_backend_setting():
    """The API validates tokens; the SPA registration's id is a frontend value only.

    ``ENTRA_SPA_CLIENT_ID`` stays in the generated ``.env`` for the frontend
    build, and the settings ignore unknown variables, so the API never reads it.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth_settings.py and project_initializer/env_generator.py generate_env().
    """
    assert "entra_spa_client_id" not in entra_auth_settings_text().lower()
    assert "ENTRA_SPA_CLIENT_ID" in generated_entra_env_example()


@pytest.mark.parametrize("field_name", ["entra_tenant_id", "entra_api_client_id"])
def test_when_auth_settings_is_read_then_the_identifier_is_validated_as_a_guid(
    field_name: str,
):
    """Tenant and client ids must be GUIDs, stored lowercase, or the app refuses to start.

    A domain-style tenant or ``common`` never equals the ``tid`` claim, so every
    token would be refused; the issuer and tenant checks compare lowercase text.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth_settings.py.
    """
    source = entra_auth_settings_text()
    assert f'"{field_name}"' in source
    assert "UUID(" in source
    assert "must be a GUID" in source
    assert "return str(parsed)" in source


def test_when_auth_settings_is_read_then_the_scope_is_normalised_and_never_empty():
    """The scope is stored as its bare name and an empty one is refused.

    ``scp`` carries bare names, so ``api://<id>/access_as_user`` has to reduce to
    ``access_as_user``; a scope that reduces to nothing would disable the check.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth_settings.py and project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    source = entra_auth_settings_text()
    assert "def normalize_scope" in source
    assert "rsplit(SCOPE_SEPARATOR, 1)[-1]" in source
    assert "entra_api_scope: ScopeName" in source
    assert "ENTRA_API_SCOPE must be one scope name" in source
    assert "normalize_scope(required_scope)" in entra_verifier_text()
    assert "a non-empty required scope is needed" in entra_verifier_text()


def test_when_auth_settings_is_read_then_the_refresh_cooldown_is_bounded():
    """ENTRA_JWKS_REFRESH_COOLDOWN is positive and capped, so reloads stay rate limited.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth_settings.py.
    """
    source = entra_auth_settings_text()
    assert "DEFAULT_JWKS_REFRESH_COOLDOWN_SECONDS = 30.0" in source
    assert "entra_jwks_refresh_cooldown: float = Field(" in source
    assert "gt=0" in source
    assert "le=MAX_JWKS_REFRESH_COOLDOWN_SECONDS" in source


def test_when_the_verifier_is_read_then_the_cooldown_setting_reaches_the_resolver():
    """from_settings hands the cooldown to the resolver that wraps the key client.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    source = entra_verifier_text()
    assert "CooldownSigningKeyResolver(" in source
    assert (
        "refresh_cooldown_seconds=auth_settings.entra_jwks_refresh_cooldown" in source
    )


def test_when_the_generated_env_is_read_then_the_entra_settings_are_present():
    """The generated example names the identifiers the API needs, and no more.

    Validates project_initializer/env_generator.py generate_env() (fastapi, entra, use_placeholders=True).
    """
    env_example = generated_entra_env_example()
    for key in (
        "ENTRA_TENANT_ID",
        "ENTRA_API_CLIENT_ID",
        "ENTRA_API_AUDIENCE",
        "ENTRA_API_SCOPE",
    ):
        assert f"{key}=" in env_example


# ===========================================================================
# Criterion: the principal's email comes from the email claim alone
# ===========================================================================


def test_when_verifier_is_read_then_email_comes_from_the_email_claim_only():
    """``preferred_username`` is a mutable sign-in name, never promoted to ``email``.

    Code that links or authorises accounts by email would otherwise trust a value
    the user can change.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    source = entra_verifier_text()
    assert 'email=_text_claim(claims, "email")' in source
    assert "username=preferred_username" in source
    assert re.search(r"email=[^\n]*preferred_username", source) is None
    assert "or preferred_username" not in source


# ===========================================================================
# Criterion: PyJWKClient is used; no hard-coded key-refresh schedule
# ===========================================================================


def test_when_verifier_is_read_then_pyjwkclient_is_used():
    """In-process JWKS auto-refresh requires PyJWKClient from PyJWT.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    assert "PyJWKClient" in entra_verifier_text(), (
        "PyJWKClient not found in entra.py — JWKS key resolution requires it"
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
@pytest.mark.parametrize("source_reader", [entra_verifier_text, entra_auth_deps_text])
def test_when_verifier_files_are_read_then_no_hardcoded_refresh_schedule_appears(
    scheduling_pattern: str, source_reader
):
    """Auto-refresh must rely on PyJWKClient's built-in caching, not an explicit scheduler.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py and project_initializer/templates-entra-fastapi/api/app/api/auth_deps.py.
    """
    assert scheduling_pattern not in source_reader(), (
        f"Hard-coded refresh pattern '{scheduling_pattern}' found in the entra auth code"
    )


# ===========================================================================
# Criterion: authentication failures return 401; scope failure returns 403
# (Static structure check — full runtime validation is in the overlay test suite)
# ===========================================================================


def test_when_verifier_is_read_then_authentication_failure_is_answered_with_401():
    """The verifier raises AuthenticationError and handlers.py maps it to HTTP 401.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py and project_initializer/templates-api-fastapi/api/app/api/handlers.py.
    """
    unauthorized, _ = auth_failure_statuses_are_wired()
    assert unauthorized, (
        "authentication failures must raise AuthenticationError, mapped to HTTP_401_UNAUTHORIZED"
    )


def test_when_verifier_is_read_then_insufficient_scope_is_answered_with_403():
    """The verifier raises AuthorizationError and handlers.py maps it to HTTP 403.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py and project_initializer/templates-api-fastapi/api/app/api/handlers.py.
    """
    _, forbidden = auth_failure_statuses_are_wired()
    assert forbidden, (
        "insufficient scope must raise AuthorizationError, mapped to HTTP_403_FORBIDDEN, not 401"
    )


def test_when_verifier_is_read_then_scp_claim_is_checked():
    """Scope enforcement must read the 'scp' claim (Entra v2 scope claim name).

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    source = entra_verifier_text()
    assert '"scp"' in source or "'scp'" in source, (
        "'scp' claim not referenced in entra.py — scope enforcement requires it"
    )


def test_when_verifier_is_read_then_tid_claim_is_checked():
    """Tenant pinning must verify the 'tid' claim to prevent cross-tenant token reuse.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py.
    """
    source = entra_verifier_text()
    assert '"tid"' in source or "'tid'" in source, (
        "'tid' claim not referenced in entra.py — tenant pinning requires it"
    )


def test_when_handlers_are_read_then_service_outage_is_answered_with_503():
    """A signing-key outage raises ExternalServiceError, which the handlers answer with 503.

    Validates project_initializer/templates-entra-fastapi/api/app/infrastructure/auth/entra.py and project_initializer/templates-api-fastapi/api/app/api/handlers.py.
    """
    assert "ExternalServiceError" in entra_verifier_text()
    assert "HTTP_503_SERVICE_UNAVAILABLE" in base_handlers_text()


# ===========================================================================
# Criterion: the base auth route exposes GET /auth/me returning the current user
# ===========================================================================


def test_when_base_auth_route_is_read_then_get_me_route_is_declared():
    """The auth router must register the '/me' path for GET requests.

    Validates project_initializer/templates-api-fastapi/api/app/api/v1/endpoints/auth.py.
    """
    source = _BASE_AUTH_PY.read_text(encoding="utf-8")
    assert '"/me"' in source or "'/me'" in source, (
        "Route '/me' not found in auth.py — GET /auth/me must be exposed"
    )


def test_when_base_auth_route_is_read_then_current_user_dependency_is_used():
    """The /auth/me handler must use CurrentUser so the entra seam decides who the caller is.

    Validates project_initializer/templates-api-fastapi/api/app/api/v1/endpoints/auth.py.
    """
    source = _BASE_AUTH_PY.read_text(encoding="utf-8")
    assert "CurrentUser" in source, (
        "CurrentUser not referenced in auth.py — /auth/me must return the current user"
    )
