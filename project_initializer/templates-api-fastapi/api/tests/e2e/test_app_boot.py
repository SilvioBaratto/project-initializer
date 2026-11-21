"""End-to-end smoke tests: the application boots, serves and follows its docs policy."""

import logging
import signal
from http import HTTPStatus
from typing import Any

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import main as main_module
from app.api.docs import (
    DOCS_CONTENT_SECURITY_POLICY,
    OPENAPI_PATH,
    REDOC_JS_URL,
    REDOC_PATH,
    SWAGGER_PATH,
    SWAGGER_UI_JS_URL,
)
from app.api.headers import REQUEST_ID_HEADER
from app.api.middleware.security import API_CONTENT_SECURITY_POLICY
from app.infrastructure import log_level as log_level_module
from app.infrastructure.circuit_breaker import CircuitState
from app.infrastructure.health import DatabaseHealth, DatabaseStatus
from app.infrastructure.settings import settings

pytestmark = pytest.mark.e2e

STARTUP_LOGGER = "app.main"
API_PREFIX = settings.api_v1_str
DOCS_ROUTES = (SWAGGER_PATH, REDOC_PATH, OPENAPI_PATH)
EXPECTED_ROUTES = [
    pytest.param("GET", "/", id="root"),
    pytest.param("GET", "/health", id="liveness"),
    pytest.param("GET", "/health/ready", id="readiness"),
    pytest.param("GET", f"{API_PREFIX}/auth/me", id="current-user"),
    pytest.param("GET", f"{API_PREFIX}/items", id="items-list"),
    pytest.param("POST", f"{API_PREFIX}/items", id="items-create"),
    pytest.param("GET", f"{API_PREFIX}/items/{{item_id}}", id="items-get"),
    pytest.param("PUT", f"{API_PREFIX}/items/{{item_id}}", id="items-update"),
    pytest.param("DELETE", f"{API_PREFIX}/items/{{item_id}}", id="items-delete"),
    pytest.param("POST", f"{API_PREFIX}/chat/", id="chat"),
    pytest.param("POST", f"{API_PREFIX}/chat/stream", id="chat-stream"),
    pytest.param("GET", f"{API_PREFIX}/test/ping", id="ping"),
]
# (environment, api_docs_enabled override, whether the docs are served)
DOCS_POLICY = [
    pytest.param("development", None, True, id="development-default"),
    pytest.param("test", None, True, id="test-default"),
    pytest.param("staging", None, True, id="staging-default"),
    pytest.param("production", None, False, id="production-default"),
    pytest.param("production", True, True, id="production-opted-in"),
    pytest.param("development", False, False, id="development-opted-out"),
    pytest.param("staging", False, False, id="staging-opted-out"),
]


def served_routes(application: FastAPI) -> set[tuple[str, str]]:
    """The (method, path) pairs of every route the application registers."""
    return {
        (method, route.path)
        for route in application.routes
        for method in getattr(route, "methods", ())
    }


@pytest.fixture
def lifecycle_calls(monkeypatch) -> list[str]:
    """Replace the startup and shutdown hooks of ``app.main`` with recorders.

    The real hooks would reach the database named in the developer's ``.env``.
    """
    calls: list[str] = []

    def probe(_manager) -> DatabaseHealth:
        """Report a reachable database."""
        calls.append("probe")
        return DatabaseHealth(DatabaseStatus.UP, CircuitState.CLOSED)

    async def run_hooks() -> None:
        """Record that the registered shutdown hooks ran."""
        calls.append("hooks")

    monkeypatch.setattr(main_module, "init_db", lambda: calls.append("init"))
    monkeypatch.setattr(main_module, "close_db", lambda: calls.append("close"))
    monkeypatch.setattr(main_module, "run_shutdown_hooks", run_hooks)
    monkeypatch.setattr(main_module, "probe_database", probe)
    return calls


def test_when_the_module_is_imported_then_a_configured_application_exists():
    """when app.main is imported, the application carries the configured identity.

    Validates app.main.create_application().
    """
    assert isinstance(main_module.app, FastAPI)
    assert main_module.app.title == settings.project_name
    assert main_module.app.version == settings.version


@pytest.mark.parametrize(("method", "path"), EXPECTED_ROUTES)
def test_when_the_application_is_built_then_each_expected_route_is_registered(
    method, path
):
    """when the application is built, every public route is mounted.

    Validates app.main.create_application().
    """
    assert (method, path) in served_routes(main_module.app)


def test_when_the_shared_client_is_used_then_the_real_lifespan_never_runs(
    client, monkeypatch
):
    """when requests go through the shared client, no startup hook is executed.

    The hooks would otherwise connect to the developer's configured database.

    Validates tests.conftest.client().
    """

    def fail_if_called() -> None:
        """Fail the test when startup touches the database."""
        raise AssertionError("the lifespan must not run in the shared client")

    monkeypatch.setattr(main_module, "init_db", fail_if_called)

    assert client.get("/health").status_code == HTTPStatus.OK


def test_when_the_lifespan_runs_then_it_initialises_probes_and_releases_in_order(
    build_app, lifecycle_calls
):
    """when the app starts and stops, each step runs once and the hooks precede close.

    The optional components' shutdown hooks run before the synchronous engine is
    disposed.

    Validates app.main.lifespan().
    """
    with TestClient(build_app()) as running:
        assert running.get("/health").status_code == HTTPStatus.OK
        assert lifecycle_calls == ["init", "probe"]

    assert lifecycle_calls == ["init", "probe", "hooks", "close"]


def test_when_the_database_is_down_at_startup_then_the_application_still_starts(
    build_app, lifecycle_calls, monkeypatch, caplog
):
    """when the startup probe finds the database down, the app still starts.

    A warning is logged.

    Readiness reports the outage; the liveness probe keeps the process alive.

    Validates app.main.lifespan().
    """
    monkeypatch.setattr(
        main_module,
        "probe_database",
        lambda _manager: DatabaseHealth(DatabaseStatus.DOWN, CircuitState.OPEN),
    )

    with (
        caplog.at_level(logging.WARNING, logger=STARTUP_LOGGER),
        TestClient(build_app()) as running,
    ):
        assert running.get("/health").status_code == HTTPStatus.OK

    assert "app.startup_database_unavailable" in caplog.text


async def test_when_the_application_body_fails_then_the_engine_is_still_disposed(
    build_app, lifecycle_calls
):
    """when an exception reaches the lifespan, it propagates after the shutdown work.

    A second yield in the generator would replace it with a RuntimeError.

    Validates app.main.lifespan().
    """
    with pytest.raises(ValueError, match="boom"):
        async with main_module.lifespan(build_app()):
            raise ValueError("boom")

    assert lifecycle_calls == ["init", "probe", "hooks", "close"]


@pytest.mark.usefixtures("ignored_sighup")
async def test_when_sighup_arrives_while_serving_then_the_log_level_is_reloaded(
    build_app, lifecycle_calls, monkeypatch, tmp_path, restored_root_level
):
    """when the process gets SIGHUP, it re-reads LOG_LEVEL and drops the handler at shutdown.

    The lifespan runs on the main thread here, which is where a signal handler
    can be installed; under the ``TestClient`` it runs on a worker thread.

    Validates app.main.lifespan().
    """
    env_file = tmp_path / ".env"
    env_file.write_text("LOG_LEVEL=debug\n", encoding="utf-8")
    monkeypatch.setattr(log_level_module, "locate_project_dotenv", lambda: env_file)
    application = build_app()
    assert logging.getLogger().level == logging.WARNING

    async with main_module.lifespan(application):
        assert signal.getsignal(signal.SIGHUP) is not signal.SIG_IGN
        signal.raise_signal(signal.SIGHUP)
        assert logging.getLogger().level == logging.DEBUG

    assert signal.getsignal(signal.SIGHUP) is signal.SIG_IGN


@pytest.mark.parametrize(("environment", "override", "served"), DOCS_POLICY)
def test_when_settings_decide_the_docs_then_all_three_routes_follow_them(
    build_app, environment, override, served
):
    """when docs are enabled, /docs, /redoc and /openapi.json answer; otherwise all 404.

    The OpenAPI schema is hidden together with the pages, so a production
    deployment does not publish its own route map.

    Validates app.main.create_application().
    """
    application = build_app(environment=environment, api_docs_enabled=override)
    client = TestClient(application)

    statuses = {route: client.get(route).status_code for route in DOCS_ROUTES}

    assert statuses == dict.fromkeys(DOCS_ROUTES, 200 if served else 404)
    assert (application.openapi_url is not None) is served


def test_when_the_docs_are_served_then_pages_use_pinned_assets_and_the_docs_policy(
    build_app,
):
    """when docs are on, the pages reference the pinned CDN files and get the docs CSP.

    Validates app.api.docs.register_docs_routes().
    """
    client = TestClient(build_app(environment="test", api_docs_enabled=True))

    swagger = client.get(SWAGGER_PATH)
    redoc = client.get(REDOC_PATH)

    assert SWAGGER_UI_JS_URL in swagger.text
    assert REDOC_JS_URL in redoc.text
    assert swagger.headers["Content-Security-Policy"] == DOCS_CONTENT_SECURITY_POLICY
    assert redoc.headers["Content-Security-Policy"] == DOCS_CONTENT_SECURITY_POLICY


def test_when_the_docs_are_served_then_the_api_routes_keep_the_strict_policy(
    build_app, api_prefix
):
    """when docs are on, API responses still get the default-src 'none' policy.

    Validates app.api.middleware.security.SecurityHeadersMiddleware.
    """
    client = TestClient(build_app(environment="test", api_docs_enabled=True))

    response = client.get(f"{api_prefix}/test/ping")

    assert response.headers["Content-Security-Policy"] == API_CONTENT_SECURITY_POLICY


def test_when_the_docs_are_hidden_then_a_404_does_not_get_the_docs_policy(build_app):
    """when docs are off, the docs paths answer 404 under the strict policy.

    Validates app.main.create_application().
    """
    client = TestClient(build_app(environment="production"))

    response = client.get(SWAGGER_PATH)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.headers["Content-Security-Policy"] == API_CONTENT_SECURITY_POLICY


@pytest.mark.parametrize(
    "environment", ["development", "test", "staging", "production"]
)
def test_when_the_application_boots_in_any_environment_then_the_root_answers(
    build_app, environment
):
    """when the app is built for each environment, / answers 200 with a request id.

    Validates app.main.create_application().
    """
    response = TestClient(build_app(environment=environment)).get("/")

    assert response.status_code == HTTPStatus.OK
    assert response.headers[REQUEST_ID_HEADER]


def test_when_the_development_server_starts_then_uvicorn_gets_no_access_log(
    monkeypatch,
):
    """when the app is run directly, uvicorn starts with its access log switched off.

    The structured http.request record replaces it; uvicorn's line carries the
    client address and the raw query string.

    Validates app.main.run_development_server().
    """
    started_with: dict[str, Any] = {}
    monkeypatch.setattr(
        uvicorn, "run", lambda target, **options: started_with.update(options)
    )

    main_module.run_development_server()

    assert started_with["access_log"] is False
    assert started_with["host"] == main_module.DEV_SERVER_HOST
    assert started_with["port"] == main_module.DEV_SERVER_PORT
