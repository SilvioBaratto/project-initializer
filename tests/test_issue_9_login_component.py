"""
Source-blind tests for issue #9 — criteria 6, 7, and 8 (no-forbidden-files sub-criterion):

  Criterion 6 [T3 — file-content check only]:
    login.ts/login.html/login.css render a single accessible "Sign in with Microsoft"
    button that calls AuthService.login() (MSAL redirect); no email/password/signup/
    forgot-password UI remains.

  Criterion 7 [UNIT]:
    Login component uses OnPush, signals for isLoading/errorMessage, and inject();
    button has an accessible label and disabled/loading state.

  Criterion 8 (no-forbidden-files) [UNIT]:
    No forgot-password/* or update-password/* files exist anywhere in
    templates-entra-frontend/.

Tests are authored from the acceptance criteria only; no implementation source was read.
T3 criteria are verified by inspecting overlay template file contents (the only observable
output available without running a browser).  Assumption: 'accessible label' means the
button element has either [attr.aria-label] binding or an aria-label attribute, or the
button text itself is "Sign in with Microsoft".
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


def _find(root: Path, *globs: str) -> list[Path]:
    results: list[Path] = []
    for g in globs:
        results.extend(root.rglob(g))
    return results


def _require_overlay(test_func_name: str):
    if not _FRONTEND_OVERLAY.is_dir():
        pytest.fail(
            f"templates-entra-frontend/ does not exist yet (Red phase expected); "
            f"failing {test_func_name}"
        )


# ---------------------------------------------------------------------------
# Criterion 6a — login.ts exists
# ---------------------------------------------------------------------------


def test_when_frontend_overlay_present_then_login_ts_exists():
    """templates-entra-frontend/ must contain a login.ts file."""
    _require_overlay("test_when_frontend_overlay_present_then_login_ts_exists")
    files = _find(_FRONTEND_OVERLAY, "login.ts", "login.component.ts")
    assert files, (
        "templates-entra-frontend/ must contain login.ts or login.component.ts"
    )


# ---------------------------------------------------------------------------
# Criterion 6b — login.html contains "Sign in with Microsoft"
# ---------------------------------------------------------------------------


def test_when_login_html_present_then_sign_in_with_microsoft_text_appears():
    """login.html must contain the text 'Sign in with Microsoft' (button label)."""
    _require_overlay(
        "test_when_login_html_present_then_sign_in_with_microsoft_text_appears"
    )
    files = _find(_FRONTEND_OVERLAY, "login.html", "login.component.html")
    assert files, (
        "templates-entra-frontend/ must contain login.html or login.component.html"
    )
    content = "\n".join(_read(f) for f in files)
    assert "Sign in with Microsoft" in content, (
        "login.html must contain the 'Sign in with Microsoft' button text"
    )


# ---------------------------------------------------------------------------
# Criterion 6c — login.html calls AuthService.login() (MSAL redirect)
# ---------------------------------------------------------------------------


def test_when_login_ts_present_then_auth_service_login_is_called():
    """login.ts must invoke AuthService.login() to trigger the MSAL redirect flow."""
    _require_overlay("test_when_login_ts_present_then_auth_service_login_is_called")
    files = _find(_FRONTEND_OVERLAY, "login.ts", "login.component.ts")
    assert files, "login.ts must exist"
    content = "\n".join(_read(f) for f in files)
    assert "login()" in content or "this.authService.login" in content, (
        "login.ts must call AuthService.login() to trigger MSAL redirect"
    )


# ---------------------------------------------------------------------------
# Criterion 6d — login.html has no email/password/signup/forgot-password fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "forbidden_pattern",
    [
        r'type=["\']email["\']',
        r'type=["\']password["\']',
        r"signup",
        r"sign-up",
        r"forgot.password",
        r"forgot_password",
        r"register",
    ],
)
def test_when_login_html_present_then_forbidden_ui_pattern_is_absent(forbidden_pattern):
    """login.html must contain no email/password/signup/forgot-password UI elements."""
    _require_overlay(
        f"test_when_login_html_present_then_forbidden_ui_pattern_{forbidden_pattern}_is_absent"
    )
    files = _find(_FRONTEND_OVERLAY, "login.html", "login.component.html")
    if not files:
        pytest.fail("login.html not found in templates-entra-frontend/")
    content = "\n".join(_read(f) for f in files)
    match = re.search(forbidden_pattern, content, re.IGNORECASE)
    assert not match, (
        f"login.html must not contain '{forbidden_pattern}'; found: {match.group() if match else ''}"
    )


# ---------------------------------------------------------------------------
# Criterion 7a — login.ts uses OnPush change detection
# ---------------------------------------------------------------------------


def test_when_login_ts_present_then_onpush_change_detection_is_set():
    """login.ts must set changeDetection: ChangeDetectionStrategy.OnPush."""
    _require_overlay("test_when_login_ts_present_then_onpush_change_detection_is_set")
    files = _find(_FRONTEND_OVERLAY, "login.ts", "login.component.ts")
    assert files, "login.ts must exist"
    content = "\n".join(_read(f) for f in files)
    assert "OnPush" in content, (
        "login.ts must declare changeDetection: ChangeDetectionStrategy.OnPush"
    )


# ---------------------------------------------------------------------------
# Criterion 7b — login.ts uses signals for isLoading and errorMessage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("signal_name", ["isLoading", "errorMessage"])
def test_when_login_ts_present_then_signal_is_declared(signal_name):
    """login.ts must declare a signal() for each reactive state field."""
    _require_overlay(
        f"test_when_login_ts_present_then_{signal_name}_signal_is_declared"
    )
    files = _find(_FRONTEND_OVERLAY, "login.ts", "login.component.ts")
    assert files, "login.ts must exist"
    content = "\n".join(_read(f) for f in files)
    assert signal_name in content, (
        f"login.ts must declare '{signal_name}' as a signal() field"
    )
    # The signal() call must be present alongside the field name
    assert "signal(" in content, (
        "login.ts must use signal() from @angular/core for reactive state"
    )


# ---------------------------------------------------------------------------
# Criterion 7c — login.ts uses inject() instead of constructor injection
# ---------------------------------------------------------------------------


def test_when_login_ts_present_then_inject_function_is_used():
    """login.ts must use inject() from @angular/core, not constructor injection."""
    _require_overlay("test_when_login_ts_present_then_inject_function_is_used")
    files = _find(_FRONTEND_OVERLAY, "login.ts", "login.component.ts")
    assert files, "login.ts must exist"
    content = "\n".join(_read(f) for f in files)
    assert "inject(" in content, (
        "login.ts must use the inject() function for dependency injection"
    )


# ---------------------------------------------------------------------------
# Criterion 7d — login.html button has an accessible label
# ---------------------------------------------------------------------------


def test_when_login_html_present_then_button_has_accessible_label():
    """
    The 'Sign in with Microsoft' button must have an accessible label.
    Assumption: the button text 'Sign in with Microsoft' alone satisfies the accessible
    label requirement; an explicit aria-label attribute is also acceptable.
    """
    _require_overlay("test_when_login_html_present_then_button_has_accessible_label")
    files = _find(_FRONTEND_OVERLAY, "login.html", "login.component.html")
    assert files, "login.html must exist"
    content = "\n".join(_read(f) for f in files)
    has_text_label = "Sign in with Microsoft" in content
    has_aria_label = "aria-label" in content
    assert has_text_label or has_aria_label, (
        "The sign-in button must have an accessible label "
        "(visible text 'Sign in with Microsoft' or aria-label attribute)"
    )


# ---------------------------------------------------------------------------
# Criterion 7e — login.html button has a disabled/loading binding
# ---------------------------------------------------------------------------


def test_when_login_html_present_then_button_has_disabled_binding():
    """The sign-in button must have a [disabled] or [attr.disabled] binding."""
    _require_overlay("test_when_login_html_present_then_button_has_disabled_binding")
    files = _find(_FRONTEND_OVERLAY, "login.html", "login.component.html")
    assert files, "login.html must exist"
    content = "\n".join(_read(f) for f in files)
    assert re.search(r"\[disabled\]|\[attr\.disabled\]", content), (
        "The sign-in button in login.html must have a [disabled] binding for loading state"
    )


# ---------------------------------------------------------------------------
# Criterion 8 (no-forbidden-files) — forgot-password and update-password absent
# ---------------------------------------------------------------------------


def test_when_frontend_overlay_present_then_no_forgot_password_files_exist():
    """templates-entra-frontend/ must contain no forgot-password/* files."""
    _require_overlay(
        "test_when_frontend_overlay_present_then_no_forgot_password_files_exist"
    )
    matches = list(_FRONTEND_OVERLAY.rglob("*forgot*password*")) + list(
        _FRONTEND_OVERLAY.rglob("*forgot-password*")
    )
    assert not matches, (
        f"templates-entra-frontend/ must not contain forgot-password files; found: {matches}"
    )


def test_when_frontend_overlay_present_then_no_update_password_files_exist():
    """templates-entra-frontend/ must contain no update-password/* files."""
    _require_overlay(
        "test_when_frontend_overlay_present_then_no_update_password_files_exist"
    )
    matches = list(_FRONTEND_OVERLAY.rglob("*update*password*")) + list(
        _FRONTEND_OVERLAY.rglob("*update-password*")
    )
    assert not matches, (
        f"templates-entra-frontend/ must not contain update-password files; found: {matches}"
    )


# ---------------------------------------------------------------------------
# Criterion (sidebar): sidebar.ts onLogout calls AuthService.logout()
# T3 criterion — verified by file content inspection
# ---------------------------------------------------------------------------


def test_when_sidebar_ts_present_then_on_logout_calls_auth_service_logout():
    """sidebar.ts must call AuthService.logout() from its onLogout() method."""
    _require_overlay(
        "test_when_sidebar_ts_present_then_on_logout_calls_auth_service_logout"
    )
    files = _find(_FRONTEND_OVERLAY, "sidebar.ts", "sidebar.component.ts")
    assert files, (
        "templates-entra-frontend/ must contain sidebar.ts or sidebar.component.ts"
    )
    content = "\n".join(_read(f) for f in files)
    assert "onLogout" in content, "sidebar.ts must define an onLogout() method"
    assert "logout()" in content or "authService.logout" in content, (
        "sidebar.ts onLogout() must call AuthService.logout() for MSAL sign-out"
    )
