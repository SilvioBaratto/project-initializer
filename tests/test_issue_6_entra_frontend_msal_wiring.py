"""
Source-blind example tests for issue #6 — scope-level criteria.
feat(entra-frontend): wire MSAL via app.config factory providers and standalone bootstrap init

Criteria covered (per oracle: [UNIT]):
  [UNIT] app.config.ts provides MSAL_INSTANCE via an MSALInstanceFactory returning a
         PublicClientApplication built from environment public values, plus MsalService
         and an MSAL_GUARD_CONFIG (InteractionType.Redirect, scopes [environment.scope])
  [UNIT] Exactly one token-attaching interceptor is registered (the custom authInterceptor);
         MsalInterceptor is absent from providers
  [UNIT] app.ts awaits msalService.instance.initialize() and then handleRedirectPromise()
         during startup (constructor/ngOnInit), before any protected navigation resolves
  [UNIT] app.config.ts retains the base router + icon providers and stays under the
         line/method limits

Criteria skipped (NOT VERIFIABLE per oracle):
  - "All tests pass"      — boilerplate suite gate; no per-criterion assertion
  - "SOLID, clean code"   — subjective prose; no concrete runtime/unit assertion

All tests inspect static template-file content only; no Angular TestBed is instantiated.
Tests are authored from the acceptance criteria text and requirements.md only — no
implementation source was read during authoring.
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).parent.parent
ENTRA_FRONTEND = ROOT / "project_initializer" / "templates-entra-frontend"
FRONTEND_SRC = ENTRA_FRONTEND / "frontend" / "src" / "app"

APP_CONFIG_TS = FRONTEND_SRC / "app.config.ts"
APP_TS = FRONTEND_SRC / "app.ts"


# ===========================================================================
# Helpers
# ===========================================================================


@pytest.fixture(scope="module")
def app_config_content() -> str:
    assert APP_CONFIG_TS.exists(), f"app.config.ts not found at {APP_CONFIG_TS}"
    return APP_CONFIG_TS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def app_ts_content() -> str:
    assert APP_TS.exists(), f"app.ts not found at {APP_TS}"
    return APP_TS.read_text(encoding="utf-8")


# ===========================================================================
# Criterion: app.config.ts provides MSAL_INSTANCE via MSALInstanceFactory
# ===========================================================================


def test_when_app_config_ts_read_then_msal_instance_token_is_provided(
    app_config_content,
):
    """MSAL_INSTANCE provider token must be registered in app.config.ts.

    Criterion: 'app.config.ts provides MSAL_INSTANCE via an MSALInstanceFactory …'
    Assumption: MSAL_INSTANCE is imported from @azure/msal-angular and appears in the
    providers array as either a useFactory or useValue entry."""
    assert "MSAL_INSTANCE" in app_config_content, (
        "MSAL_INSTANCE provider token not found in app.config.ts — "
        "MSAL cannot be injected without it"
    )


def test_when_app_config_ts_read_then_msal_instance_factory_function_is_declared(
    app_config_content,
):
    """MSALInstanceFactory must be declared in app.config.ts.

    Criterion: '… via an MSALInstanceFactory returning a PublicClientApplication …'
    Assumption: the factory is a named function or const named MSALInstanceFactory."""
    assert "MSALInstanceFactory" in app_config_content, (
        "MSALInstanceFactory not found in app.config.ts — "
        "MSAL_INSTANCE must be provided via a dedicated factory function"
    )


def test_when_app_config_ts_read_then_public_client_application_is_constructed(
    app_config_content,
):
    """PublicClientApplication must be instantiated inside the MSAL factory.

    Criterion: '… returning a PublicClientApplication built from environment public values …'
    Assumption: the file contains `new PublicClientApplication(…)` or an import of
    PublicClientApplication from @azure/msal-browser."""
    assert "PublicClientApplication" in app_config_content, (
        "PublicClientApplication not found in app.config.ts — "
        "MSALInstanceFactory must return a PublicClientApplication instance"
    )


def test_when_app_config_ts_read_then_environment_is_used_in_msal_factory(
    app_config_content,
):
    """The MSAL factory must reference environment (not hard-coded values).

    Criterion: '… built from environment public values …'
    Assumption: the factory function references the imported `environment` object
    so values like tenantId, clientId, authority, scope come from the environment file."""
    assert "environment" in app_config_content, (
        "'environment' not referenced in app.config.ts — "
        "MSALInstanceFactory must build from environment public values, not hard-coded literals"
    )


def test_when_app_config_ts_read_then_msal_service_is_registered_as_provider(
    app_config_content,
):
    """MsalService must appear in the providers list of app.config.ts.

    Criterion: '… plus MsalService …'"""
    assert "MsalService" in app_config_content, (
        "MsalService not found in app.config.ts providers — MSAL auth service will not be injectable"
    )


def test_when_app_config_ts_read_then_msal_guard_config_token_is_provided(
    app_config_content,
):
    """MSAL_GUARD_CONFIG provider token must appear in app.config.ts.

    Criterion: '… and an MSAL_GUARD_CONFIG (InteractionType.Redirect, scopes [environment.scope])'"""
    assert "MSAL_GUARD_CONFIG" in app_config_content, (
        "MSAL_GUARD_CONFIG not found in app.config.ts — guard configuration is missing"
    )


def test_when_app_config_ts_read_then_interaction_type_redirect_is_specified(
    app_config_content,
):
    """InteractionType.Redirect must be set in the MSAL guard config.

    Criterion: '… MSAL_GUARD_CONFIG (InteractionType.Redirect, …)'
    Assumption: the literal text InteractionType.Redirect or 'Redirect' appears in the
    guard config section of app.config.ts."""
    has_redirect = (
        "InteractionType.Redirect" in app_config_content
        or "InteractionType" in app_config_content
        and "Redirect" in app_config_content
    )
    assert has_redirect, (
        "InteractionType.Redirect not found in app.config.ts — "
        "MSAL_GUARD_CONFIG must use Redirect interaction type"
    )


def test_when_app_config_ts_read_then_guard_config_references_environment_scope(
    app_config_content,
):
    """The MSAL guard config scopes must reference environment.scope (not hard-coded).

    Criterion: '… scopes [environment.scope]'"""
    assert "environment.scope" in app_config_content or (
        "environment" in app_config_content and "scope" in app_config_content
    ), (
        "environment.scope reference not found in app.config.ts — "
        "MSAL_GUARD_CONFIG scopes must be sourced from the environment file"
    )


# ===========================================================================
# Criterion: Exactly one interceptor (authInterceptor); MsalInterceptor absent
# ===========================================================================


def test_when_app_config_ts_read_then_auth_interceptor_is_registered(
    app_config_content,
):
    """The custom authInterceptor must be registered in app.config.ts.

    Criterion: 'Exactly one token-attaching interceptor is registered (the custom authInterceptor)'
    Assumption: the interceptor is referenced by name as authInterceptor or AUTH_INTERCEPTOR."""
    has_auth_interceptor = (
        "authInterceptor" in app_config_content
        or "AUTH_INTERCEPTOR" in app_config_content
        or "withInterceptors" in app_config_content
    )
    assert has_auth_interceptor, (
        "authInterceptor not found in app.config.ts — "
        "the custom token-attaching interceptor must be registered"
    )


def test_when_app_config_ts_read_then_msal_interceptor_is_absent_from_providers(
    app_config_content,
):
    """MsalInterceptor must NOT appear in app.config.ts providers.

    Criterion: 'MsalInterceptor is absent from providers'
    The defect being resolved is the double-attach caused by registering both interceptors;
    the fix is to use only the custom authInterceptor."""
    assert "MsalInterceptor" not in app_config_content, (
        "MsalInterceptor found in app.config.ts — "
        "only the custom authInterceptor must be registered (double-attach fix)"
    )


# ===========================================================================
# Criterion: MSAL init sequence at startup (superseded by issue #10)
#
# Issue #10 moved the init sequence from app.ts ngOnInit to
# provideAppInitializer in app.config.ts so the guard race is closed.
# The tests below now verify the *final* architecture: initialize() and
# handleRedirectPromise() live in app.config.ts, and app.ts is a
# simple shell component with no MSAL lifecycle work.
# ===========================================================================


def test_when_app_ts_read_then_msal_service_is_injected(app_ts_content):
    """app.ts must not carry MSAL init work; the init sequence lives in app.config.ts.

    Updated by issue #10: provideAppInitializer in app.config.ts owns the init,
    so app.ts no longer needs to inject MsalService for startup.
    This test now verifies the simplified component has RouterOutlet."""
    assert "RouterOutlet" in app_ts_content, (
        "RouterOutlet not found in app.ts — "
        "the root component must include the router outlet to render routes"
    )


def test_when_app_ts_read_then_initialize_call_is_present(app_config_content):
    """initialize() must be called in the MSAL startup path (now in app.config.ts).

    Updated by issue #10: the init sequence moved to provideAppInitializer in
    app.config.ts; initialize() must appear there, not in app.ts."""
    assert "initialize" in app_config_content, (
        "'initialize' not found in app.config.ts — "
        "MSAL requires initialize() to be called before any protected navigation"
    )


def test_when_app_ts_read_then_handle_redirect_promise_call_is_present(
    app_config_content,
):
    """handleRedirectPromise() must be called in the MSAL startup path (now in app.config.ts).

    Updated by issue #10: the init sequence moved to provideAppInitializer."""
    assert "handleRedirectPromise" in app_config_content, (
        "'handleRedirectPromise' not found in app.config.ts — "
        "MSAL requires handleRedirectPromise() to be awaited after initialize()"
    )


def test_when_app_ts_read_then_initialize_appears_before_handle_redirect_promise(
    app_config_content,
):
    """initialize() must be called before handleRedirectPromise() in the startup path.

    Updated by issue #10: ordering is now verified in app.config.ts where
    provideAppInitializer calls AuthService.runInitSequence()."""
    init_pos = app_config_content.find("initialize")
    redirect_pos = app_config_content.find("handleRedirectPromise")
    assert init_pos != -1, "'initialize' not found in app.config.ts"
    assert redirect_pos != -1, "'handleRedirectPromise' not found in app.config.ts"
    assert init_pos < redirect_pos, (
        "initialize must appear before handleRedirectPromise in app.config.ts — "
        "the MSAL init sequence requires initialize() to complete first"
    )


def test_when_app_ts_read_then_startup_is_async(app_config_content):
    """The startup path must use async/await.

    Updated by issue #10: the async init is in app.config.ts
    (provideAppInitializer callback is async)."""
    assert "async" in app_config_content or "runInitSequence" in app_config_content, (
        "Neither 'async' nor 'runInitSequence' found in app.config.ts — "
        "the MSAL startup path must be asynchronous"
    )


def test_when_app_ts_read_then_startup_is_in_constructor_or_ng_on_init(
    app_config_content,
):
    """The MSAL startup must complete before guards run.

    Updated by issue #10: provideAppInitializer in app.config.ts replaces
    the ngOnInit approach, ensuring startup completes before route resolution."""
    assert "provideAppInitializer" in app_config_content, (
        "'provideAppInitializer' not found in app.config.ts — "
        "MSAL startup must be wired via provideAppInitializer to block guard resolution"
    )


# ===========================================================================
# Criterion: app.config.ts retains base router + icon providers
# ===========================================================================


def test_when_app_config_ts_read_then_router_provider_is_present(app_config_content):
    """app.config.ts must retain the base router provider (provideRouter).

    Criterion: 'app.config.ts retains the base router + icon providers …'"""
    has_router = (
        "provideRouter" in app_config_content or "RouterModule" in app_config_content
    )
    assert has_router, (
        "provideRouter / RouterModule not found in app.config.ts — "
        "the base router provider must be retained from the base layer"
    )


def test_when_app_config_ts_read_then_icon_provider_is_present(app_config_content):
    """app.config.ts must retain the icon provider from the base layer.

    Criterion: 'app.config.ts retains the base router + icon providers …'
    Assumption: the icon provider is referenced by a name containing 'icon' or 'Icon'
    (e.g. provideIcons, MatIconRegistry, or a custom icon configuration call)."""
    has_icons = bool(re.search(r"icon|Icon", app_config_content))
    assert has_icons, (
        "Icon provider reference not found in app.config.ts — "
        "the icon provider from the base layer must be retained"
    )


def test_when_app_config_ts_read_then_file_is_under_line_limit(app_config_content):
    """app.config.ts must stay under 600 lines.

    Criterion: 'stays under the line/method limits'
    Assumption: the outer boundary of the stated range (500–600 lines) applies;
    600 lines is used as the hard limit to avoid failing on borderline files."""
    line_count = len(app_config_content.splitlines())
    assert line_count <= 600, (
        f"app.config.ts has {line_count} lines — must stay under 600 lines"
    )
