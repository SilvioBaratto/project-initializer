"""
Source-blind example tests for issue #8:
feat(entra-frontend): add auth route guards and the single custom token interceptor

Every test is derived from the acceptance criteria text and requirements.md only.
No implementation source was read during authoring (Red phase of TDD).

Criteria mapped (per oracle classification):
  [T2]   authGuard awaits initialization and redirects unauthenticated users to /login
         (with returnUrl); guestGuard redirects authenticated users to /
  [UNIT] A single custom authInterceptor attaches Authorization: Bearer <token> from
         AuthService, and no MsalInterceptor is registered anywhere in the overlay
  [UNIT] On 401 the interceptor delegates re-authentication to AuthService (MSAL
         interactive), not to any Supabase path
  [UNIT] app.routes.ts defines a login route (guarded by guestGuard) and protected
         routes under authGuard, with no forgot-password/update-password routes

Criteria skipped (NOT VERIFIABLE per oracle):
  - "All tests pass"     — boilerplate suite gate; no per-criterion assertion
  - "SOLID, clean code"  — subjective prose; no concrete runtime/unit assertion

Global criteria already covered by test_issue_6_entra_global_criteria.py and
test_issue_7_entra_auth_service.py are NOT re-tested here to avoid duplication.
"""

import re
from pathlib import Path

import pytest
from hypothesis import given, settings as hyp_settings, strategies as st

# ── Path constants ─────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
ENTRA_FRONTEND = ROOT / "project_initializer" / "templates-entra-frontend"
_FE_APP = ENTRA_FRONTEND / "frontend" / "src" / "app"

# Guard files — the criterion names the symbols authGuard and guestGuard.
# Angular 21 standalone: guards are typically functions in a dedicated file.
# Assumption: guards live in core/guards/ (mirrors the supabase overlay layout).
_GUARDS_CANDIDATES = [
    _FE_APP / "core" / "guards" / "auth.guard.ts",
    _FE_APP / "guards" / "auth.guard.ts",
]

# Interceptor — the criterion names a single custom authInterceptor.
# Assumption: the interceptor lives in core/interceptors/ (mirrors supabase layout).
_INTERCEPTOR_CANDIDATES = [
    _FE_APP / "core" / "interceptors" / "auth.interceptor.ts",
    _FE_APP / "interceptors" / "auth.interceptor.ts",
]

APP_ROUTES = _FE_APP / "app.routes.ts"
APP_CONFIG = _FE_APP / "app.config.ts"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _read(path: Path) -> str:
    """Read a template file; fail with a clear diagnostic if missing."""
    assert path.exists(), (
        f"Template file not found (implementation not yet written?): {path}"
    )
    return path.read_text(encoding="utf-8")


def _find_guard_file() -> Path | None:
    for candidate in _GUARDS_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _find_interceptor_file() -> Path | None:
    for candidate in _INTERCEPTOR_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


# ===========================================================================
# [T2] authGuard: awaits initialization, redirects unauthenticated → /login
# ===========================================================================


def test_when_guard_file_is_inspected_then_it_exists():
    """The auth guard file must exist in the entra frontend overlay.

    Criterion: 'authGuard awaits initialization and redirects unauthenticated
    users to /login (with returnUrl)'
    Assumption: the guard is implemented as a function in a file named auth.guard.ts
    under core/guards/ or guards/ (mirrors supabase overlay file layout 1:1)."""
    found = _find_guard_file()
    assert found is not None, f"auth.guard.ts not found; checked: {_GUARDS_CANDIDATES}"


def test_when_auth_guard_is_read_then_auth_guard_symbol_is_exported():
    """authGuard must be exported from the guard file.

    Criterion: 'authGuard awaits initialization …'
    Assumption: the exported symbol is named authGuard (camelCase function export,
    as per Angular 21 functional guard convention)."""
    path = _find_guard_file()
    assert path is not None, f"auth.guard.ts not found; checked: {_GUARDS_CANDIDATES}"
    content = _read(path)
    assert "authGuard" in content, "authGuard must be exported from the guard file"


def test_when_auth_guard_is_read_then_guest_guard_symbol_is_exported():
    """guestGuard must be exported from the same guard file (or a co-located file).

    Criterion: 'guestGuard redirects authenticated users to /'
    Assumption: guestGuard is defined in the same auth.guard.ts file as authGuard."""
    path = _find_guard_file()
    assert path is not None, f"auth.guard.ts not found; checked: {_GUARDS_CANDIDATES}"
    content = _read(path)
    assert "guestGuard" in content, (
        "guestGuard must be defined alongside authGuard — both guards must exist in the overlay"
    )


def test_when_auth_guard_is_read_then_wait_until_initialized_is_called():
    """authGuard must await AuthService initialization before making the auth decision.

    Criterion: 'authGuard awaits initialization …'
    Assumption: the guard calls waitUntilInitialized() (the AuthService method
    defined in issue #7 scope criterion #6) before checking isAuthenticated."""
    path = _find_guard_file()
    assert path is not None, f"auth.guard.ts not found; checked: {_GUARDS_CANDIDATES}"
    content = _read(path)
    assert "waitUntilInitialized" in content, (
        "authGuard must call waitUntilInitialized() to await MSAL init "
        "before evaluating the authentication state"
    )


def test_when_auth_guard_is_read_then_redirect_to_login_is_present():
    """authGuard must redirect unauthenticated users to /login.

    Criterion: '… redirects unauthenticated users to /login (with returnUrl)'"""
    path = _find_guard_file()
    assert path is not None, f"auth.guard.ts not found; checked: {_GUARDS_CANDIDATES}"
    content = _read(path)
    has_login_redirect = "/login" in content or "login" in content
    assert has_login_redirect, "authGuard must redirect unauthenticated users to /login"


def test_when_auth_guard_is_read_then_return_url_is_preserved_on_redirect():
    """authGuard must attach returnUrl as a query parameter on the login redirect.

    Criterion: '… redirects unauthenticated users to /login (with returnUrl)'
    The parenthetical '(with returnUrl)' is an explicit requirement: the original
    URL must be preserved so users land back after successful login."""
    path = _find_guard_file()
    assert path is not None, f"auth.guard.ts not found; checked: {_GUARDS_CANDIDATES}"
    content = _read(path)
    assert "returnUrl" in content, (
        "authGuard must set returnUrl as a query parameter on the /login redirect "
        "so users are returned to their original destination after authentication"
    )


def test_when_auth_guard_is_read_then_is_authenticated_is_checked():
    """authGuard must check isAuthenticated (the AuthService signal) to decide the outcome.

    Criterion: '… redirects unauthenticated users …' implies a check on the auth state.
    Assumption: the guard reads the isAuthenticated signal from AuthService."""
    path = _find_guard_file()
    assert path is not None, f"auth.guard.ts not found; checked: {_GUARDS_CANDIDATES}"
    content = _read(path)
    assert "isAuthenticated" in content, (
        "authGuard must check isAuthenticated (the AuthService signal) "
        "to decide whether to allow or redirect"
    )


def test_when_guest_guard_is_read_then_redirect_to_root_is_present():
    """guestGuard must redirect authenticated users to /.

    Criterion: 'guestGuard redirects authenticated users to /'"""
    path = _find_guard_file()
    assert path is not None, f"auth.guard.ts not found; checked: {_GUARDS_CANDIDATES}"
    content = _read(path)
    # The redirect target '/' must appear near guestGuard logic.
    # Assumption: the literal string '/' or createUrlTree(['/']) or router.navigate(['/'])
    # is used; we match any occurrence of the root route as a string literal or array element.
    has_root_redirect = bool(
        re.search(r"['\"/]\s*/\s*['\"]", content)
        or re.search(r"\[\s*['\"]\/['\"]", content)
        or "navigate(['/'])" in content
        or "createUrlTree(['/'])" in content
        or "'/'," in content
        or '"/",' in content
    )
    assert has_root_redirect, (
        "guestGuard must redirect authenticated users to '/' "
        "(root route, not /login or any other path)"
    )


def test_when_guest_guard_is_read_then_auth_service_is_used():
    """guestGuard must consult AuthService to determine the authenticated state.

    Criterion: 'guestGuard redirects authenticated users to /'
    The guard must read isAuthenticated or call AuthService, not duplicate logic."""
    path = _find_guard_file()
    assert path is not None, f"auth.guard.ts not found; checked: {_GUARDS_CANDIDATES}"
    content = _read(path)
    has_auth_service = "AuthService" in content or "authService" in content
    assert has_auth_service, (
        "guestGuard must use AuthService to determine whether the user is authenticated"
    )


# ===========================================================================
# [UNIT] Single custom authInterceptor attaches Bearer token; no MsalInterceptor
# ===========================================================================


def test_when_interceptor_file_is_inspected_then_it_exists():
    """The custom authInterceptor file must exist in the entra frontend overlay.

    Criterion: 'A single custom authInterceptor attaches Authorization: Bearer <token>
    from AuthService, and no MsalInterceptor is registered anywhere in the overlay'
    Assumption: the interceptor is in core/interceptors/auth.interceptor.ts."""
    found = _find_interceptor_file()
    assert found is not None, (
        f"auth.interceptor.ts not found; checked: {_INTERCEPTOR_CANDIDATES}"
    )


def test_when_auth_interceptor_is_read_then_auth_interceptor_symbol_is_exported():
    """authInterceptor must be exported from the interceptor file.

    Criterion: 'A single custom authInterceptor …'
    Assumption: the exported function is named authInterceptor (functional interceptor,
    Angular 21 convention)."""
    path = _find_interceptor_file()
    assert path is not None, (
        f"auth.interceptor.ts not found; checked: {_INTERCEPTOR_CANDIDATES}"
    )
    content = _read(path)
    assert "authInterceptor" in content, (
        "authInterceptor must be exported from the interceptor file"
    )


def test_when_auth_interceptor_is_read_then_authorization_bearer_header_is_set():
    """The interceptor must attach an Authorization: Bearer header to outgoing requests.

    Criterion: '… attaches Authorization: Bearer <token> from AuthService'
    Assumption: the header name 'Authorization' and value prefix 'Bearer' both appear
    in the interceptor source."""
    path = _find_interceptor_file()
    assert path is not None, (
        f"auth.interceptor.ts not found; checked: {_INTERCEPTOR_CANDIDATES}"
    )
    content = _read(path)
    assert "Authorization" in content, (
        "authInterceptor must set the Authorization header on each outgoing request"
    )
    assert "Bearer" in content, (
        "authInterceptor must use the Bearer scheme for the Authorization header value"
    )


def test_when_auth_interceptor_is_read_then_token_is_sourced_from_auth_service():
    """The Bearer token must be retrieved from AuthService, not hard-coded or from Supabase.

    Criterion: '… attaches Authorization: Bearer <token> from AuthService'"""
    path = _find_interceptor_file()
    assert path is not None, (
        f"auth.interceptor.ts not found; checked: {_INTERCEPTOR_CANDIDATES}"
    )
    content = _read(path)
    has_auth_service = "AuthService" in content or "authService" in content
    assert has_auth_service, (
        "authInterceptor must source the token from AuthService "
        "(getAccessToken() or equivalent), not from Supabase or a hard-coded value"
    )


def test_when_app_config_is_read_then_msal_interceptor_is_absent():
    """MsalInterceptor must not appear in app.config.ts (the overlay providers file).

    Criterion: '… no MsalInterceptor is registered anywhere in the overlay'
    The double-attach defect is resolved by wiring only the custom authInterceptor;
    registering MsalInterceptor in addition would reintroduce the defect."""
    content = _read(APP_CONFIG)
    assert "MsalInterceptor" not in content, (
        "MsalInterceptor must not be registered in app.config.ts — "
        "only the custom authInterceptor is allowed (double-attach fix)"
    )


def test_when_interceptor_file_is_read_then_msal_interceptor_is_not_imported():
    """MsalInterceptor must not be imported in auth.interceptor.ts either.

    Criterion: '… no MsalInterceptor is registered anywhere in the overlay'
    An import of MsalInterceptor inside the custom interceptor file would indicate
    delegation to MSAL's own interceptor, violating the exclusive-choice criterion."""
    path = _find_interceptor_file()
    assert path is not None, (
        f"auth.interceptor.ts not found; checked: {_INTERCEPTOR_CANDIDATES}"
    )
    content = _read(path)
    assert "MsalInterceptor" not in content, (
        "MsalInterceptor must not be imported or used inside auth.interceptor.ts — "
        "the custom interceptor must operate independently of MSAL's own interceptor"
    )


# Property: for any HTTP method token (get, post, put, delete), the interceptor
# source contains the cloning pattern — idempotent across HTTP method names.
# Criterion implies an invariant: the interceptor must attach the header to every
# outgoing request, regardless of HTTP method.  We test the presence of the cloning
# pattern (setHeaders / clone) as the structural invariant that enables per-request
# header injection.
@given(st.sampled_from(["get", "post", "put", "delete", "patch"]))
@hyp_settings(max_examples=5)
def test_when_interceptor_file_exists_then_request_cloning_pattern_is_present_for_all_methods(
    _http_method: str,
):
    """Invariant: the interceptor must clone the request to attach headers (all HTTP methods
    are covered by the same clone logic).  The presence of `clone` or `setHeaders` in the
    interceptor source is the structural invariant that guarantees this."""
    path = _find_interceptor_file()
    assert path is not None, (
        f"auth.interceptor.ts not found; checked: {_INTERCEPTOR_CANDIDATES}"
    )
    content = path.read_text(encoding="utf-8")
    has_clone_pattern = "clone" in content or "setHeaders" in content
    assert has_clone_pattern, (
        "authInterceptor must clone the HttpRequest to attach the Authorization header — "
        "HttpRequest objects are immutable and cannot be mutated directly"
    )


# ===========================================================================
# [UNIT] On 401 the interceptor delegates re-auth to AuthService (MSAL), not Supabase
# ===========================================================================


def test_when_auth_interceptor_is_read_then_401_response_is_handled():
    """The interceptor must handle 401 responses from the API.

    Criterion: 'On 401 the interceptor delegates re-authentication to AuthService
    (MSAL interactive), not to any Supabase path'"""
    path = _find_interceptor_file()
    assert path is not None, (
        f"auth.interceptor.ts not found; checked: {_INTERCEPTOR_CANDIDATES}"
    )
    content = _read(path)
    has_401_check = (
        "401" in content
        or "UNAUTHORIZED" in content
        or "status === 401" in content
        or re.search(r"status\s*===?\s*401", content) is not None
        or re.search(r"HttpStatusCode\.Unauthorized", content) is not None
    )
    assert has_401_check, (
        "authInterceptor must detect 401 responses and trigger re-authentication"
    )


def test_when_auth_interceptor_is_read_then_reauthentication_uses_msal_interactive():
    """On 401, re-authentication must be delegated to AuthService MSAL-interactive flow.

    Criterion: '… delegates re-authentication to AuthService (MSAL interactive) …'
    Assumption: the interceptor calls a method on AuthService (e.g. login(), or
    acquireTokenRedirect) — not a Supabase sign-in method."""
    path = _find_interceptor_file()
    assert path is not None, (
        f"auth.interceptor.ts not found; checked: {_INTERCEPTOR_CANDIDATES}"
    )
    content = _read(path)
    has_msal_reauth = (
        "AuthService" in content
        or "authService" in content
        or "login(" in content
        or "acquireTokenRedirect" in content
        or "loginRedirect" in content
    )
    assert has_msal_reauth, (
        "On 401, authInterceptor must delegate re-authentication to AuthService "
        "(MSAL interactive flow via login() or acquireTokenRedirect)"
    )


def test_when_auth_interceptor_is_read_then_supabase_is_not_referenced():
    """The interceptor must not reference Supabase at all.

    Criterion: '… not to any Supabase path'
    The entra interceptor must use the MSAL path exclusively; any Supabase reference
    would indicate a copy-paste error from the supabase overlay."""
    path = _find_interceptor_file()
    assert path is not None, (
        f"auth.interceptor.ts not found; checked: {_INTERCEPTOR_CANDIDATES}"
    )
    content = _read(path).lower()
    assert "supabase" not in content, (
        "authInterceptor must not reference Supabase — 401 handling must delegate "
        "exclusively to AuthService (MSAL interactive), not any Supabase sign-in path"
    )


# ===========================================================================
# [UNIT] app.routes.ts: login route under guestGuard; protected routes under
#        authGuard; no forgot-password / update-password routes
# ===========================================================================


def test_when_app_routes_ts_is_inspected_then_it_exists():
    """app.routes.ts must be present in the entra frontend overlay.

    Criterion: 'app.routes.ts defines a login route (guarded by guestGuard) and
    protected routes under authGuard …'"""
    assert APP_ROUTES.exists(), f"app.routes.ts not found at {APP_ROUTES}"


@pytest.fixture(scope="module")
def routes_content() -> str:
    assert APP_ROUTES.exists(), f"app.routes.ts not found at {APP_ROUTES}"
    return APP_ROUTES.read_text(encoding="utf-8")


def test_when_app_routes_ts_is_read_then_login_route_is_defined(routes_content):
    """A 'login' route must be declared in app.routes.ts.

    Criterion: 'app.routes.ts defines a login route …'
    Assumption: the route appears as path: 'login' (with single or double quotes)."""
    assert re.search(r"""path\s*:\s*['"]login['"]""", routes_content), (
        "app.routes.ts must define a route with path: 'login'"
    )


def test_when_app_routes_ts_is_read_then_login_route_is_guarded_by_guest_guard(
    routes_content,
):
    """The login route must be protected by guestGuard.

    Criterion: '… a login route (guarded by guestGuard) …'
    guestGuard prevents already-authenticated users from reaching /login."""
    assert "guestGuard" in routes_content, (
        "app.routes.ts must apply guestGuard to the login route"
    )


def test_when_app_routes_ts_is_read_then_protected_routes_are_guarded_by_auth_guard(
    routes_content,
):
    """Protected routes must be guarded by authGuard.

    Criterion: '… protected routes under authGuard …'
    Assumption: authGuard appears in the canActivate or canActivateChild configuration
    of at least one non-login route."""
    assert "authGuard" in routes_content, (
        "app.routes.ts must apply authGuard to protect routes requiring authentication"
    )


def test_when_app_routes_ts_is_read_then_forgot_password_route_is_absent(
    routes_content,
):
    """The forgot-password route must NOT exist in the entra overlay's routes.

    Criterion: '… with no forgot-password/update-password routes'
    Rationale: Entra uses MSAL (the IdP manages the password reset flow);
    including a forgot-password route from the supabase overlay is an error."""
    assert "forgot-password" not in routes_content, (
        "app.routes.ts must not define a forgot-password route — "
        "Entra delegates password management to the Microsoft identity platform"
    )


def test_when_app_routes_ts_is_read_then_update_password_route_is_absent(
    routes_content,
):
    """The update-password route must NOT exist in the entra overlay's routes.

    Criterion: '… with no forgot-password/update-password routes'"""
    assert "update-password" not in routes_content, (
        "app.routes.ts must not define an update-password route — "
        "Entra delegates password management to the Microsoft identity platform"
    )


def test_when_app_routes_ts_is_read_then_both_guard_symbols_are_imported(
    routes_content,
):
    """Both authGuard and guestGuard must be imported in app.routes.ts so they can be
    applied to routes.

    Criterion: combined reading of the login-guard and protected-route criteria."""
    assert "authGuard" in routes_content and "guestGuard" in routes_content, (
        "app.routes.ts must import and reference both authGuard and guestGuard"
    )


# Property: the login route must appear exactly once (idempotence / uniqueness invariant).
# Criterion implies: there is one login route. Duplicate login routes would break routing.
def test_when_app_routes_ts_is_read_then_login_route_appears_exactly_once(
    routes_content,
):
    """The login route must appear exactly once — no duplicate login route definitions.

    Criterion: 'app.routes.ts defines a login route …' (singular, not plural).
    Duplicate route entries cause the first match to win and the second to be silently
    ignored, which is a latent bug."""
    login_matches = len(re.findall(r"""path\s*:\s*['"]login['"]""", routes_content))
    assert login_matches == 1, (
        f"app.routes.ts defines the login route {login_matches} time(s); "
        "it must appear exactly once"
    )
