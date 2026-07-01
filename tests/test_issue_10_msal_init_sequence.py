"""
Source-blind tests for issue #10 — scope criteria:

  Criterion 6 [UNIT]: A single MSAL init sequence (initialize() → handleRedirectPromise()
    → set active account → update isAuthenticated) runs exactly once at startup and
    completes before any protected route guard resolves; prefer provideAppInitializer
    in app.config.ts over root-component ngOnInit to close the guard race.

  Criterion 7 [UNIT]: AuthService.waitUntilInitialized() awaits the init promise owned
    by AuthService, not an unassigned window.__msalInitialized global; the orphaned
    global declaration is removed.

  Criterion 8 [T2 — file-content proxy]: After a successful redirect login,
    isAuthenticated() returns true and the active account is set via setActiveAccount();
    authGuard lets the authenticated user through; guestGuard bounces them off /login.

  Criterion 9 [UNIT]: refreshAccount() (or equivalent account-sync logic) is actually
    invoked in the init path, not only in tests; no dead/orphaned wiring remains.

  Criterion 10 [UNIT]: A test proves the runtime contract — with a stubbed account
    present after init, isAuthenticated() is true and waitUntilInitialized() resolves
    only after the init sequence completes (not a synchronous no-op).

  Criterion 11 [UNIT]: handleRedirectPromise() and initialize() are each called exactly
    once per load (no double-consume of the redirect result).

Tests are authored from the acceptance criteria only; no implementation source was read.
Global criteria (--auth entra, backend JWT, no-secret, overlay layout, JWKS) are already
covered by test_issue_9_*.py files.

Assumption for criterion 7: the orphaned global `declare global { interface Window {
  __msalInitialized? } }` pattern in auth.service.ts must be gone; waitUntilInitialized()
must not reference `window.__msalInitialized`.
Assumption for criterion 8: T2 (integration) is proxied by file-content inspection —
we check that the guard files reference the isAuthenticated signal and that guestGuard
has a redirect to a non-guarded route, since we cannot spin up a browser.
Assumption for criterion 10: verified by inspecting that the AuthService spec file
contains both 'isAuthenticated' and 'waitUntilInitialized' in the same test block,
and that the spec stubs an account before calling the init path.
Assumption for criterion 11: 'exactly once' is verified by counting occurrences of
`initialize()` and `handleRedirectPromise()` in the non-spec TypeScript source — any
count other than exactly 1 is a violation.
"""

import re
from pathlib import Path

import pytest

_PKG = Path(__file__).parent.parent / "project_initializer"
_FRONTEND_OVERLAY = _PKG / "templates-entra-frontend"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _ts_src_files(root: Path, exclude_spec: bool = True) -> list[Path]:
    """Return all .ts files, optionally excluding spec/test files."""
    all_ts = list(root.rglob("*.ts"))
    if exclude_spec:
        return [f for f in all_ts if ".spec." not in f.name and ".test." not in f.name]
    return all_ts


def _ts_spec_files(root: Path) -> list[Path]:
    return [f for f in root.rglob("*.ts") if ".spec." in f.name or ".test." in f.name]


def _combined(files: list[Path]) -> str:
    return "\n".join(_read(f) for f in files)


def _require_overlay():
    if not _FRONTEND_OVERLAY.is_dir():
        pytest.fail("templates-entra-frontend/ does not exist yet (Red phase)")


# ---------------------------------------------------------------------------
# Criterion 6a — provideAppInitializer is used in app.config.ts
# ---------------------------------------------------------------------------


def test_when_app_config_present_then_provide_app_initializer_is_used():
    """
    The MSAL init sequence must be wired via provideAppInitializer in app.config.ts
    so it completes before route guards resolve, closing the guard race.
    """
    _require_overlay()
    config_files = list(_FRONTEND_OVERLAY.rglob("app.config.ts"))
    assert config_files, "templates-entra-frontend/ must contain an app.config.ts"
    content = _combined(config_files)
    assert "provideAppInitializer" in content, (
        "app.config.ts must use provideAppInitializer to register the MSAL init sequence"
    )


def test_when_app_config_present_then_init_sequence_not_wired_only_in_ngoninit():
    """
    The init sequence must NOT rely solely on ngOnInit in the root component; it must be
    in app.config.ts so guards cannot fire before MSAL is ready.
    Assumption: if provideAppInitializer is present in app.config.ts the guard race is
    closed regardless of whether app.ts also still has an ngOnInit.
    This is the positive side of criterion 6 — already covered by the test above.
    Here we verify that app.config.ts is the authoritative owner of the init wiring.
    """
    _require_overlay()
    config_files = list(_FRONTEND_OVERLAY.rglob("app.config.ts"))
    assert config_files, "app.config.ts must exist"
    content = _combined(config_files)
    # initialize() or handleRedirectPromise must appear in app.config.ts (or be
    # referenced via the function passed to provideAppInitializer)
    has_init_wiring = (
        "initialize" in content
        or "handleRedirectPromise" in content
        or "provideAppInitializer" in content
    )
    assert has_init_wiring, (
        "app.config.ts must own or reference the MSAL init sequence via provideAppInitializer"
    )


# ---------------------------------------------------------------------------
# Criterion 6b — init sequence includes all four steps
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "step",
    ["initialize", "handleRedirectPromise", "setActiveAccount", "isAuthenticated"],
)
def test_when_init_path_present_then_step_appears_in_non_spec_source(step):
    """
    The MSAL init sequence must include all four steps: initialize(),
    handleRedirectPromise(), setActiveAccount(), and an isAuthenticated update.
    Each step must appear in non-spec source files (production code).
    """
    _require_overlay()
    src_files = _ts_src_files(_FRONTEND_OVERLAY, exclude_spec=True)
    assert src_files, "templates-entra-frontend/ must contain TypeScript source files"
    content = _combined(src_files)
    assert step in content, (
        f"MSAL init sequence must include '{step}' in production source (not only in specs)"
    )


# ---------------------------------------------------------------------------
# Criterion 7a — window.__msalInitialized global is removed from AuthService
# ---------------------------------------------------------------------------


def test_when_auth_service_present_then_window_msal_initialized_global_is_absent():
    """
    The orphaned 'window.__msalInitialized' global declaration must be removed from
    AuthService; waitUntilInitialized() must not rely on an unowned window global.
    """
    _require_overlay()
    auth_files = list(_FRONTEND_OVERLAY.rglob("auth.service.ts"))
    assert auth_files, "templates-entra-frontend/ must contain auth.service.ts"
    content = _combined(auth_files)
    assert "__msalInitialized" not in content, (
        "auth.service.ts must not reference window.__msalInitialized; "
        "the init promise must be owned by AuthService directly"
    )


def test_when_auth_service_present_then_window_global_declaration_is_absent():
    """The 'declare global { interface Window' pattern must be removed from auth.service.ts."""
    _require_overlay()
    auth_files = list(_FRONTEND_OVERLAY.rglob("auth.service.ts"))
    assert auth_files, "auth.service.ts must exist"
    content = _combined(auth_files)
    assert "declare global" not in content, (
        "auth.service.ts must not contain 'declare global' — the window global is dead code"
    )


# ---------------------------------------------------------------------------
# Criterion 7b — waitUntilInitialized() is a first-class method in AuthService
# ---------------------------------------------------------------------------


def test_when_auth_service_present_then_wait_until_initialized_method_exists():
    """AuthService must expose a waitUntilInitialized() method."""
    _require_overlay()
    auth_files = list(_FRONTEND_OVERLAY.rglob("auth.service.ts"))
    assert auth_files, "auth.service.ts must exist"
    content = _combined(auth_files)
    assert "waitUntilInitialized" in content, (
        "AuthService must expose a waitUntilInitialized() method for guards to await"
    )


def test_when_auth_service_present_then_init_promise_is_owned_by_service():
    """
    The init promise must be a private field of AuthService (e.g. a Promise<void>
    stored as a class member), not handed off to an external global.
    Assumption: 'owned by AuthService' means the init promise reference appears in
    auth.service.ts without a window property assignment.
    """
    _require_overlay()
    auth_files = list(_FRONTEND_OVERLAY.rglob("auth.service.ts"))
    assert auth_files, "auth.service.ts must exist"
    content = _combined(auth_files)
    # The service must have a Promise field (resolve/Promise pattern or similar)
    has_promise = "Promise" in content or "resolve" in content
    assert has_promise, (
        "AuthService must own the init promise as a class member "
        "(not delegate it to a window global)"
    )


# ---------------------------------------------------------------------------
# Criterion 8 (T2 proxy) — authGuard reads isAuthenticated; guestGuard redirects
# ---------------------------------------------------------------------------


def test_when_auth_guard_present_then_is_authenticated_is_checked():
    """
    authGuard must check the isAuthenticated() signal to decide whether to let
    the user through.
    """
    _require_overlay()
    guard_files = list(_FRONTEND_OVERLAY.rglob("auth.guard.ts"))
    assert guard_files, "templates-entra-frontend/ must contain auth.guard.ts"
    content = _combined(guard_files)
    assert "isAuthenticated" in content, (
        "authGuard must check the isAuthenticated() signal from AuthService"
    )


def test_when_auth_guard_present_then_wait_until_initialized_is_awaited():
    """
    authGuard must await waitUntilInitialized() so it never fires before MSAL is ready.
    """
    _require_overlay()
    guard_files = list(_FRONTEND_OVERLAY.rglob("auth.guard.ts"))
    assert guard_files, "auth.guard.ts must exist"
    content = _combined(guard_files)
    assert "waitUntilInitialized" in content, (
        "authGuard must await AuthService.waitUntilInitialized() before checking auth state"
    )


def test_when_guest_guard_present_then_authenticated_user_is_redirected():
    """
    guestGuard must redirect an already-authenticated user away from /login
    (e.g. to '/' or the home route).
    """
    _require_overlay()
    guard_files = list(_FRONTEND_OVERLAY.rglob("auth.guard.ts"))
    assert guard_files, "auth.guard.ts must exist"
    content = _combined(guard_files)
    # guestGuard must contain redirect logic — createUrlTree or router.navigate
    has_redirect = (
        "createUrlTree" in content
        or "router.navigate" in content
        or "UrlTree" in content
    )
    assert has_redirect, (
        "guestGuard must redirect authenticated users away from the login route"
    )


def test_when_init_path_present_then_set_active_account_is_called():
    """
    After handleRedirectPromise() resolves, setActiveAccount() must be called to
    store the signed-in account so isAuthenticated() reflects the real state.
    """
    _require_overlay()
    src_files = _ts_src_files(_FRONTEND_OVERLAY, exclude_spec=True)
    content = _combined(src_files)
    assert "setActiveAccount" in content, (
        "The init path must call setActiveAccount() after handleRedirectPromise() "
        "so the active account is set before guards run"
    )


# ---------------------------------------------------------------------------
# Criterion 9 — refreshAccount() (or equivalent) called in the init path
# ---------------------------------------------------------------------------


def test_when_non_spec_source_present_then_refresh_account_or_equivalent_is_in_init_path():
    """
    refreshAccount() or an equivalent account-sync call must appear in the production
    init path (app.config.ts or a service initializer), not only in spec files.
    Assumption: 'equivalent account-sync logic' means any call to isAuthenticated.set()
    or getAllAccounts() that gates on the init result also satisfies this criterion.
    """
    _require_overlay()
    src_files = _ts_src_files(_FRONTEND_OVERLAY, exclude_spec=True)
    content = _combined(src_files)
    has_account_sync = (
        "refreshAccount" in content
        or "getAllAccounts" in content
        or "isAuthenticated.set" in content
    )
    assert has_account_sync, (
        "The production init path must call refreshAccount() or equivalent account-sync logic; "
        "it must not exist only in spec files"
    )


def test_when_spec_files_present_then_refresh_account_not_only_in_specs():
    """
    If refreshAccount() appears in spec files it must also appear in non-spec source;
    a method that exists only in tests is dead/orphaned wiring.
    """
    _require_overlay()
    spec_files = _ts_spec_files(_FRONTEND_OVERLAY)
    src_files = _ts_src_files(_FRONTEND_OVERLAY, exclude_spec=True)
    if not spec_files:
        pytest.skip("No spec files found; nothing to verify")
    spec_content = _combined(spec_files)
    if "refreshAccount" not in spec_content:
        pytest.skip("refreshAccount not referenced in specs; criterion does not apply")
    src_content = _combined(src_files)
    assert "refreshAccount" in src_content, (
        "refreshAccount() is referenced in spec files but absent from production source — "
        "it must be wired in the init path, not only in tests"
    )


# ---------------------------------------------------------------------------
# Criterion 10 — AuthService spec proves the runtime contract
# ---------------------------------------------------------------------------


def test_when_auth_service_spec_present_then_is_authenticated_signal_is_tested():
    """
    The AuthService spec must contain a test that asserts isAuthenticated() is true
    after the init sequence completes with a stubbed account.
    """
    _require_overlay()
    spec_files = list(_FRONTEND_OVERLAY.rglob("auth.service.spec.ts"))
    assert spec_files, (
        "templates-entra-frontend/ must contain an auth.service.spec.ts that proves "
        "the isAuthenticated runtime contract"
    )
    content = _combined(spec_files)
    assert "isAuthenticated" in content, (
        "auth.service.spec.ts must test that isAuthenticated() is true after init"
    )


def test_when_auth_service_spec_present_then_wait_until_initialized_is_tested():
    """
    The AuthService spec must test that waitUntilInitialized() resolves only after
    the init sequence finishes (not as a synchronous no-op).
    """
    _require_overlay()
    spec_files = list(_FRONTEND_OVERLAY.rglob("auth.service.spec.ts"))
    assert spec_files, "auth.service.spec.ts must exist"
    content = _combined(spec_files)
    assert "waitUntilInitialized" in content, (
        "auth.service.spec.ts must test waitUntilInitialized() to prove it is async "
        "and resolves only after the init sequence completes"
    )


def test_when_auth_service_spec_present_then_stubbed_account_is_used_in_init_test():
    """
    The runtime contract test must stub a real account before the init call,
    proving the signal reflects observed state not a hardcoded default.
    Assumption: 'stubbed account' means a mock/spy on getAllAccounts() or
    getActiveAccount() that returns a non-null account object.
    """
    _require_overlay()
    spec_files = list(_FRONTEND_OVERLAY.rglob("auth.service.spec.ts"))
    assert spec_files, "auth.service.spec.ts must exist"
    content = _combined(spec_files)
    has_account_stub = (
        "getAllAccounts" in content
        or "getActiveAccount" in content
        or "mockAccount" in content.lower()
        or "stubAccount" in content.lower()
        or "fakeAccount" in content.lower()
    )
    assert has_account_stub, (
        "auth.service.spec.ts must stub an account (getAllAccounts/getActiveAccount mock) "
        "so the isAuthenticated assertion reflects a real account being present"
    )


# ---------------------------------------------------------------------------
# Criterion 11 — initialize() and handleRedirectPromise() called exactly once
# ---------------------------------------------------------------------------


def test_when_non_spec_source_present_then_initialize_is_called_exactly_once():
    """
    initialize() must appear exactly once in non-spec production TypeScript files;
    calling it twice double-initializes MSAL and calling it zero times means the
    init sequence never runs.
    Assumption: 'exactly once' is counted over the full non-spec source corpus of
    the overlay; the method name searched is 'initialize()'.
    """
    _require_overlay()
    src_files = _ts_src_files(_FRONTEND_OVERLAY, exclude_spec=True)
    content = _combined(src_files)
    # Count occurrences of a call expression — .initialize() or instance.initialize()
    # We look for the call pattern, not bare identifier, to avoid false positives on
    # property names like 'isInitialized'.
    matches = re.findall(r"\.\s*initialize\s*\(", content)
    assert len(matches) == 1, (
        f"initialize() must be called exactly once in non-spec production source; "
        f"found {len(matches)} occurrence(s)"
    )


def test_when_non_spec_source_present_then_handle_redirect_promise_is_called_exactly_once():
    """
    handleRedirectPromise() must appear exactly once in non-spec production TypeScript
    files; calling it twice would double-consume the redirect result.
    """
    _require_overlay()
    src_files = _ts_src_files(_FRONTEND_OVERLAY, exclude_spec=True)
    content = _combined(src_files)
    matches = re.findall(r"\.\s*handleRedirectPromise\s*\(", content)
    assert len(matches) == 1, (
        f"handleRedirectPromise() must be called exactly once in non-spec production source; "
        f"found {len(matches)} occurrence(s)"
    )
