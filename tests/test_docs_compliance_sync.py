"""Doc-drift guard for the behaviour that the backend compliance rework added.

The generated docs and the repo docs must describe the templates as they are: the
FastAPI middleware order and catch-all, the database error classification, the
migration safety net, the coverage gate, the container start-up and, per auth
variant, the rules each overlay enforces, the database TLS rule, the SIGHUP log-level
reload and the audit actions; and on the NestJS side the platform settings, the backup
schema, roles (RBAC) and the audit trail. Three kinds of assertion live here:

* statements the docs must make (``_FASTAPI_ALL``, ``_FASTAPI_BY_AUTH``, ...);
* stale statements the docs must no longer make (``_STALE_FASTAPI``);
* settings and values the docs name, cross-checked against the template source,
  so a renamed variable or a changed limit fails here instead of silently
  leaving the docs wrong.
"""

import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from project_initializer.docs_generator import (
    generate_api_claude,
    generate_api_readme,
    generate_root_claude,
    generate_root_readme,
)
from project_initializer.env_generator import generate_env, parse_env

_REPO = Path(__file__).resolve().parent.parent
_PACKAGE = _REPO / "project_initializer"
_FASTAPI_BASE = _PACKAGE / "templates-api-fastapi" / "api"
_NESTJS_BASE = _PACKAGE / "templates-api-nestjs" / "api"
_FASTAPI_TOKEN = _PACKAGE / "templates-token-fastapi" / "api"

AUTHS = [None, "token", "supabase", "entra"]

_FASTAPI_ALL = [
    "`UnhandledErrorMiddleware`",
    "CORS, request logging, security headers, `UnhandledErrorMiddleware`, rate limiting",
    "matched route template",
    "`NulFreeStr`",
    "`additional_databases`",
    "`DATABASE_ERROR`",
    "`flush_or_conflict`",
    "register_shutdown_hook",
    "register_readiness_probe",
    "`audit.action`",
    "logger `app.audit`",
    "pins that logger to INFO",
    "`DATABASE_ECHO`",
    "`*` is refused in `staging` and `production`",
    "`--no-access-log`",
    "`set_log_level(",
    "`hide_input_in_errors`",
    "--rev-id",
    "preserve_and_drop_column",
    'config.attributes["embedded"]',
    "`migration_backup.<table>__rollback_<UTC YYYYmmddHHMMSSffffff>`",
    "`pytest.ini` enforces a coverage gate",
    "`--no-cov`",
    "`ErrorEnvelope`",
    "Item ids are UUIDs",
    "`DB_WAIT_TIMEOUT_SECONDS`",
    "`FORWARDED_ALLOW_IPS`",
    "`idx_items_created_at`",
    "`DatabaseOperationError`",
    "deadlock",
    "does not trip the breaker",
    "without a vote",
    "**Database TLS.**",
    "refuses to start unless the database connection is TLS-protected",
    "`DATABASE_URL` and, when set, `DIRECT_DATABASE_URL`",
    "`require`, `verify-ca` or `verify-full`",
    "which wins over the URL",
    "`DATABASE_SSL_MODE=disable` is refused even beside `sslmode=require`",
    "`development` and `test` are exempt, and so is a SQLite URL",
    "`DATABASE_ALLOW_INSECURE_TRANSPORT=true` (default `false`)",
    "`ENVIRONMENT=production docker compose up` needs that opt-out",
    "never the URL, which holds the password",
    "**SIGHUP reloads `LOG_LEVEL`.**",
    "`reload_log_level_on_sighup`",
    "`docker kill --signal=HUP <container>`",
    "wins over the one in the process environment",
    "the environment is the fallback when the file has none",
    "`log_level.reload_rejected`",
    "`log_level.reloaded`",
    "`log_level.reload_failed`",
    "never the text",
    "nothing but the level changes",
    "restored on shutdown",
    "a terminal hang-up also sends SIGHUP",
    "a reload re-applies the start-up value",
    "`item.create`, `item.update` and `item.delete` as background tasks",
]

_FASTAPI_BY_AUTH = {
    "token": [
        "`user.register`",
        "`user.login`",
        "`resource_id` and `actor_id` are the user id",
        "carry no email or username",
        "`AccessTokenDTO` that gained `user_id`",
        "`TokenResponse` does not expose it",
        "Emails are stored and matched in lower case",
        "A blank `username` means none",
        "`RegistrationService`",
        "`app/application/services/registration.py`",
        "answer **503** before they look at the credentials",
        "`Cache-Control: no-store`",
        "`auth.validate_rejected`",
        "At every stage a non-empty secret must meet its minimum",
    ],
    "supabase": [
        "the role `anonymous`",
        "`sb_secret_`",
        "a 200 whose body is not a user",
        "`0003_enable_row_level_security.py`",
        "`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`",
        "`sslmode=require` in both URLs",
        "already meets the database TLS rule",
    ],
    "entra": [
        "`ENTRA_JWKS_REFRESH_COOLDOWN`",
        "`2.15.1`",
        "`CooldownSigningKeyResolver`",
        "must be GUIDs written with hyphens",
        "`email` comes from the `email` claim alone",
        "it becomes `username` and is never promoted to `email`",
        "no usable key",
    ],
}

_STALE_FASTAPI = [
    "coverage is reported, not gated",
    "Coverage of `app/` is reported on every run",
    "no threshold is enforced",
    "Add `--cov-fail-under=75`",
    "any outward import",
    "nothing wires the",
    "unwired",
    "call `await dispose_async_engine()` when the lifespan",
    "`<table>__rollback_<UTC YYYYmmddHHMMSS>`",
]

_NESTJS_ALL = [
    "`TRUST_PROXY_HOPS`",
    "512 KiB",
    "**413**",
    "`Malformed JSON request body`",
    "`HealthCheckExceptionFilter`",
    "`P2010`",
    "`P2024` and `P2037`",
    "`stripSslParameters`",
    "`DB_POOL_MAX`",
    "`API_DOCS_ENABLED`",
    "`DB_WAIT_TIMEOUT_SECONDS`",
    "`prisma.config.ts`",
    "`@ZodResponse`",
    "`Too many requests`",
    "`migration_backup.",
    "microsecond",
    "`NODE_ENV=development`",
    "`NODE_ENV=production`",
    "**Database TLS.**",
    "every `sslmode` parameter in it is `require`, `verify-ca` or `verify-full`",
    "spelled exactly in lower case",
    "`DB_ALLOW_INSECURE_TRANSPORT=true` (a boolean, default `false`)",
    "names neither the URL nor the host",
    "`DIRECT_URL` is not checked",
    "**Log level reload.**",
    "`src/config/log-level-reload.ts`",
    "`kill -HUP <pid>`",
    "`docker kill --signal=HUP <container>`",
    "`../.env` and then `.env`",
    "without touching `process.env`",
    "A value you exported that differs from what the file held at start-up wins",
    "otherwise the edited file wins",
    "one warning that names only the accepted set",
    "Nothing is installed on Windows",
    "a terminal hang-up also sends `SIGHUP`",
    "a reload re-applies the start-up value",
    "## Roles (RBAC)",
    "`@Roles(...roles)`",
    "`RolesGuard`",
    "`[ThrottlerGuard, ...AUTH_GUARDS, RolesGuard]`",
    "A route without `@Roles` passes this guard",
    "compared exactly, case included",
    "answer **403**",
    "`Insufficient permissions`",
    "never lists the required roles",
    "A `@Roles` on the handler replaces one on the controller",
    "`Request rejected by roles guard`",
    "No sample route uses it",
    "## Audit trail",
    "`AuditLogger`",
    "`record(action, resourceId, actorId)`",
    "`event: 'audit.action'`",
    "pinned to `info`",
    "`LOG_LEVEL=warn`, `error` or `silent`",
    "`item.create`, `item.update` and `item.delete`",
    "after the repository call succeeded",
    "`create(item, actorId)`, `update(id, changes, actorId)` and `remove(id, actorId)`",
    "`auditActorIdOf(user)`",
    "the constant `anonymous`",
    "Never an email, a username or a token",
    "`RolesGuard` (enforces `@Roles`), the last global guard",
]

_NESTJS_ROLE_SOURCES = {
    None: "every `@Roles` route is denied",
    "token": "`@Roles('service')` is the only role a token caller can satisfy",
    "supabase": "A route that needs a signed-in person lists `authenticated`",
    "entra": "A token without that claim has no role",
}

_STALE_NESTJS = [
    "❌ RBAC / CASL",
    "5. ZodValidationPipe (global)",
]

_NESTJS_BY_AUTH = {
    "token": ["`token68`", "at least 32 characters"],
    "supabase": [
        "the role `anonymous`",
        "`SUPABASE_AUTH_TIMEOUT_MS`",
        "must use https",
        "a 429",
        "HTML5 email grammar",
        "`_prisma_migrations`",
    ],
    "entra": [
        "24 hours",
        "30-second clock tolerance",
        "`exp` and `iat`",
        "must be GUIDs and are lowercased",
        "`api://<client id>/`",
        "HTML5 email grammar",
    ],
}


_DOCUMENTED_SETTINGS = {
    (_FASTAPI_BASE, "entrypoint.sh"): ["DB_WAIT_TIMEOUT_SECONDS"],
    (_FASTAPI_BASE, "app/api/middleware/rate_limiting.py"): ["FORWARDED_ALLOW_IPS"],
    (_FASTAPI_BASE, "app/infrastructure/settings.py"): [
        "DATABASE_ECHO",
        "CORS_ORIGINS",
        "hide_input_in_errors",
        "DATABASE_SSL_MODE",
        "DATABASE_ALLOW_INSECURE_TRANSPORT=true",
        "DIRECT_DATABASE_URL",
    ],
    (_FASTAPI_BASE, "app/infrastructure/log_level.py"): [
        "LOG_LEVEL",
        "SIGHUP",
        "log_level.reloaded",
        "log_level.reload_rejected",
        "log_level.reload_failed",
    ],
    (_FASTAPI_BASE, "app/api/v1/endpoints/items.py"): [
        "item.create",
        "item.update",
        "item.delete",
    ],
    (_FASTAPI_TOKEN, "app/api/v1/endpoints/auth.py"): [
        "user.register",
        "user.login",
    ],
    (_NESTJS_BASE, "entrypoint.sh"): ["DB_WAIT_TIMEOUT_SECONDS"],
    (_NESTJS_BASE, "src/config/env.base.ts"): [
        "TRUST_PROXY_HOPS",
        "API_DOCS_ENABLED",
        "DB_POOL_MAX",
        "DB_ALLOW_INSECURE_TRANSPORT",
    ],
    (_NESTJS_BASE, "src/config/log-level-reload.ts"): ["SIGHUP", "LOG_LEVEL"],
    (_NESTJS_BASE, "src/common/auth/roles.guard.ts"): [
        "Request rejected by roles guard"
    ],
    (_NESTJS_BASE, "src/common/auth/auth-messages.ts"): ["Insufficient permissions"],
    (_NESTJS_BASE, "src/common/audit/audit-logger.ts"): [
        "audit.action",
        "anonymous",
    ],
    (_NESTJS_BASE, "src/modules/items/item.constants.ts"): [
        "item.create",
        "item.update",
        "item.delete",
    ],
}


def _source(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _fastapi_claude(auth, async_db=False) -> str:
    return generate_api_claude("fastapi", auth, async_db=async_db)


@pytest.mark.parametrize("auth", AUTHS)
@pytest.mark.parametrize("statement", _FASTAPI_ALL)
def test_when_fastapi_api_claude_is_generated_then_it_makes_the_statement(
    auth, statement
):
    """Every FastAPI variant documents the shared behaviour of the base template.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    assert statement in _fastapi_claude(auth)


@pytest.mark.parametrize(("auth", "statements"), list(_FASTAPI_BY_AUTH.items()))
def test_when_fastapi_api_claude_is_generated_then_the_overlay_rules_are_documented(
    auth, statements
):
    """The overlay's own rules appear in its docs.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = _fastapi_claude(auth)
    missing = [statement for statement in statements if statement not in doc]
    assert missing == []


@pytest.mark.parametrize("auth", AUTHS)
def test_when_fastapi_api_claude_is_generated_then_other_overlays_are_not_described(
    auth,
):
    """A variant documents its own overlay only, so no variant mentions another's rules.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = _fastapi_claude(auth)
    for other, statements in _FASTAPI_BY_AUTH.items():
        if other == auth:
            continue
        leaked = [
            statement
            for statement in statements
            if statement in doc and statement != "`0003_enable_row_level_security.py`"
        ]
        assert leaked == [], f"{auth or 'none'} docs describe the {other} overlay"


@pytest.mark.parametrize("auth", AUTHS)
@pytest.mark.parametrize("async_db", [False, True])
@pytest.mark.parametrize("stale", _STALE_FASTAPI)
def test_when_fastapi_api_claude_is_generated_then_stale_statements_are_gone(
    auth, async_db, stale
):
    """Statements that stopped being true must not survive in the generated docs.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    assert stale not in _fastapi_claude(auth, async_db)


def test_when_the_async_overlay_is_scaffolded_then_its_lifecycle_wiring_is_documented():
    """Importing the async module registers the shutdown hook and the readiness probe.

    Validates project_initializer/docs_generator.py generate_api_claude() with async_db=True.
    """
    doc = _fastapi_claude(None, async_db=True)

    assert "registers its engine disposal as a shutdown hook" in doc
    assert "`run_shutdown_hooks`" in doc
    assert "`additional_databases`" in doc


@pytest.mark.parametrize("auth", AUTHS)
def test_when_the_fastapi_readmes_are_generated_then_the_gate_and_container_are_described(
    auth,
):
    """The quick-start docs state the coverage gate, `--no-cov`, and the container start-up.

    Validates project_initializer/docs_generator.py generate_api_readme(), generate_root_readme() and generate_root_claude().
    """
    api_readme = generate_api_readme("fastapi", auth=auth)
    root_readme = generate_root_readme("fastapi", auth)
    root_claude = generate_root_claude("fastapi", auth)

    assert "75% branch coverage" in api_readme
    assert "--no-cov" in api_readme
    assert "--rev-id" in api_readme
    assert "`DB_WAIT_TIMEOUT_SECONDS`" in root_readme
    assert "`--no-access-log`" in root_readme
    assert "allowlist" in root_claude
    assert "importlib.import_module" in root_claude
    assert "the catch-all" in root_claude


@pytest.mark.parametrize("auth", AUTHS)
@pytest.mark.parametrize("statement", _NESTJS_ALL)
def test_when_nestjs_api_claude_is_generated_then_it_makes_the_statement(
    auth, statement
):
    """Every NestJS variant documents the platform behaviour of the base template.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    assert statement in generate_api_claude("nestjs", auth)


@pytest.mark.parametrize(("auth", "statements"), list(_NESTJS_BY_AUTH.items()))
def test_when_nestjs_api_claude_is_generated_then_the_overlay_rules_are_documented(
    auth, statements
):
    """The overlay's own rules appear in its docs.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = generate_api_claude("nestjs", auth)
    missing = [statement for statement in statements if statement not in doc]
    assert missing == []


@pytest.mark.parametrize("auth", AUTHS)
@pytest.mark.parametrize("stale", _STALE_NESTJS)
def test_when_nestjs_api_claude_is_generated_then_stale_statements_are_gone(
    auth, stale
):
    """RBAC is no longer a non-goal and the guard order lists the roles guard.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    assert stale not in generate_api_claude("nestjs", auth)


@pytest.mark.parametrize(("auth", "statement"), list(_NESTJS_ROLE_SOURCES.items()))
def test_when_nestjs_api_claude_is_generated_then_the_role_source_is_the_variants_own(
    auth, statement
):
    """Each variant says where its callers' roles come from, and no other variant says it.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    assert statement in generate_api_claude("nestjs", auth)
    for other in AUTHS:
        if other != auth:
            assert statement not in generate_api_claude("nestjs", other), (
                f"{other or 'none'} docs describe the roles of {auth or 'none'}"
            )


@pytest.mark.parametrize("auth", AUTHS)
def test_when_the_nestjs_root_docs_are_generated_then_tls_reload_roles_and_audit_appear(
    auth,
):
    """The root README and CLAUDE.md name the production TLS rule, SIGHUP, roles and the audit trail.

    Validates project_initializer/docs_generator.py generate_root_readme(), generate_root_claude() and generate_api_readme().
    """
    readme = generate_root_readme("nestjs", auth)
    claude = generate_root_claude("nestjs", auth)
    api_readme = generate_api_readme("nestjs", auth=auth)

    assert "`DB_ALLOW_INSECURE_TRANSPORT=true`" in readme
    assert "`require`, `verify-ca` or `verify-full`" in readme
    assert "`NODE_ENV=development` and is unaffected" in readme
    assert "`kill -HUP <pid>`" in readme
    assert "a container reads no `.env` file" in readme
    assert "`@Roles` and `RolesGuard`" in claude
    assert "`AuditLogger`" in claude
    assert "log-level-reload.ts (SIGHUP)" in api_readme
    assert "audit/ (AuditLogger)" in api_readme


@pytest.mark.parametrize("auth", AUTHS)
def test_when_the_nestjs_api_claude_is_generated_then_the_guard_order_matches_the_module(
    auth,
):
    """The documented middleware stack names the roles guard as the last global guard.

    Validates project_initializer/docs_generator.py generate_api_claude().
    """
    doc = generate_api_claude("nestjs", auth)

    assert doc.index("4. Access-token guard") < doc.index("5. `RolesGuard`")
    assert doc.index("5. `RolesGuard`") < doc.index("6. ZodValidationPipe")


@pytest.mark.parametrize("auth", AUTHS)
def test_when_the_fastapi_root_docs_are_generated_then_tls_and_reload_are_described(
    auth,
):
    """Both root docs and the api README carry the database TLS rule and the SIGHUP reload.

    Validates project_initializer/docs_generator.py generate_root_readme(), generate_root_claude() and generate_api_readme().
    """
    readme = generate_root_readme("fastapi", auth)
    claude = generate_root_claude("fastapi", auth)
    api_readme = generate_api_readme("fastapi", auth=auth)

    assert "refuses a database connection that is not TLS-protected" in readme
    assert "`DIRECT_DATABASE_URL`" in readme
    assert "`kill -HUP <pid>`" in readme
    assert "`docker kill --signal=HUP <container>` in Docker" in readme
    assert "a reload re-applies the start-up value" in readme
    assert "`log_level.py` (SIGHUP reloads `LOG_LEVEL`)" in claude
    assert "log_level (SIGHUP reloads LOG_LEVEL)" in api_readme


def test_when_the_fastapi_root_readme_is_generated_then_the_tls_hint_fits_the_database():
    """Supabase hosts the database, so it never mentions the compose `db`; the others do.

    Validates project_initializer/docs_generator.py generate_root_readme().
    """
    supabase = generate_root_readme("fastapi", "supabase")
    for auth in (None, "token", "entra"):
        readme = generate_root_readme("fastapi", auth)
        assert "`ENVIRONMENT=production docker compose up` needs" in readme
        assert "`DATABASE_ALLOW_INSECURE_TRANSPORT=true`" in readme
        assert "already meets the rule" not in readme

    assert "so it already meets the rule" in supabase
    assert "`DATABASE_SSL_MODE=require` and `sslmode=require` in both URLs" in supabase
    assert "docker compose up` needs" not in supabase


def test_when_the_token_root_claude_is_generated_then_the_audit_actions_appear():
    """Only the token variant documents the registration and login audit actions.

    Validates project_initializer/docs_generator.py generate_root_claude().
    """
    assert "`user.register` and `user.login`" in generate_root_claude(
        "fastapi", "token"
    )
    for auth in (None, "supabase", "entra"):
        assert "user.register" not in generate_root_claude("fastapi", auth)


@pytest.mark.parametrize("auth", AUTHS)
def test_when_the_nestjs_root_readme_is_generated_then_proxy_and_wait_are_described(
    auth,
):
    """The root README names the proxy-hop setting, the body limit and the start-up wait.

    Validates project_initializer/docs_generator.py generate_root_readme().
    """
    readme = generate_root_readme("nestjs", auth)

    assert "`TRUST_PROXY_HOPS`" in readme
    assert "413" in readme
    assert "`DB_WAIT_TIMEOUT_SECONDS`" in readme
    assert "`NODE_ENV=development`" in readme


def test_when_the_docs_name_a_setting_then_the_templates_read_it():
    """Each variable the docs introduce exists in the code that reads it.

    Validates project_initializer/templates-{api-fastapi,token-fastapi,api-nestjs}/api sources (entrypoint.sh, settings.py, env.base.ts and the other files it lists).
    """
    missing = [
        f"{root.name}/{relative}: {name}"
        for (root, relative), names in _DOCUMENTED_SETTINGS.items()
        for name in names
        if name not in _source(root, relative)
    ]

    assert missing == []


def test_when_the_docs_name_the_tls_modes_then_the_templates_accept_exactly_those():
    """Both stacks accept require, verify-ca and verify-full, and the opt-outs default to off.

    Validates project_initializer/templates-api-fastapi/api/app/infrastructure/settings.py and project_initializer/templates-api-nestjs/api/src/config/env.base.ts.
    """
    accepted = {"require", "verify-ca", "verify-full"}
    fastapi = _source(_FASTAPI_BASE, "app/infrastructure/settings.py")
    nestjs = _source(_NESTJS_BASE, "src/config/env.base.ts")

    fastapi_modes = re.search(
        r"ENCRYPTED_SSL_MODES = frozenset\(\{(.*?)\}\)", fastapi, re.S
    )
    nestjs_modes = re.search(
        r"ENCRYPTED_DATABASE_SSLMODES[^=]*= new Set\(\[(.*?)\]\)", nestjs, re.S
    )

    assert fastapi_modes is not None and nestjs_modes is not None
    assert set(re.findall(r"[\"']([a-z-]+)[\"']", fastapi_modes.group(1))) == accepted
    assert set(re.findall(r"[\"']([a-z-]+)[\"']", nestjs_modes.group(1))) == accepted
    assert 'FILE_BACKENDS = frozenset({"sqlite"})' in fastapi
    assert "database_allow_insecure_transport: bool = False" in fastapi
    assert "return self.is_production or self.is_staging" in fastapi
    assert "DB_ALLOW_INSECURE_TRANSPORT: false," in nestjs
    assert "env.NODE_ENV !== PRODUCTION_NODE_ENV" in nestjs


def test_when_the_docs_describe_the_guard_order_then_the_root_module_registers_it_that_way():
    """RolesGuard comes after the rate limiter and the authentication guards.

    Validates project_initializer/templates-api-nestjs/api/src/app.module.ts.
    """
    module = _source(_NESTJS_BASE, "src/app.module.ts")

    assert (
        module.index("useClass: ThrottlerGuard")
        < module.index("...AUTH_GUARDS")
        < module.index("useClass: RolesGuard")
    )


def test_when_the_docs_name_the_items_service_signatures_then_they_match_the_template():
    """The audit actor is the last argument of every state-changing method.

    Validates project_initializer/templates-api-nestjs/api/src/modules/items/items.service.ts.
    """
    service = _source(_NESTJS_BASE, "src/modules/items/items.service.ts")

    for signature in (
        "create(item: NewItem, actorId: string)",
        "update(id: string, changes: ItemChanges, actorId: string)",
        "remove(id: string, actorId: string)",
    ):
        assert signature in service


def test_when_the_docs_say_user_id_stays_internal_then_the_response_schema_omits_it():
    """AccessTokenDTO carries user_id for the audit record; TokenResponse never exposes it.

    Validates project_initializer/templates-token-fastapi/api/app/application/dto/user.py and project_initializer/templates-token-fastapi/api/app/api/schemas/auth.py.
    """
    dto = _source(_FASTAPI_TOKEN, "app/application/dto/user.py")
    schemas = _source(_FASTAPI_TOKEN, "app/api/schemas/auth.py")
    token_response = schemas.split("class TokenResponse", 1)[1].split("\nclass ", 1)[0]

    assert "user_id: str" in dto.split("class AccessTokenDTO", 1)[1]
    assert "user_id" not in token_response


@pytest.mark.parametrize("framework", ["fastapi", "nestjs"])
@pytest.mark.parametrize("auth", AUTHS)
def test_when_the_env_is_generated_then_neither_tls_opt_out_is_set(framework, auth):
    """The opt-outs are the operator's explicit choice, so no generated file turns one on.

    Validates project_initializer/env_generator.py generate_env().
    """
    for content in (
        generate_env(framework, auth),
        generate_env(framework, auth, use_placeholders=True),
    ):
        assert "ALLOW_INSECURE_TRANSPORT" not in content


def test_when_the_supabase_env_is_generated_then_it_meets_each_stacks_tls_rule(
    tmp_path,
):
    """The docs promise that the generated Supabase files pass the production TLS check.

    Validates project_initializer/env_generator.py generate_env().
    """
    accepted = {"require", "verify-ca", "verify-full"}
    fastapi_path, nestjs_path = tmp_path / "fastapi.env", tmp_path / "nestjs.env"
    generate_env("fastapi", "supabase", dest=str(fastapi_path))
    generate_env("nestjs", "supabase", dest=str(nestjs_path))
    fastapi, nestjs = parse_env(fastapi_path), parse_env(nestjs_path)

    assert fastapi["DATABASE_SSL_MODE"] in accepted
    for key in ("DATABASE_URL", "DIRECT_DATABASE_URL"):
        assert parse_qs(urlparse(fastapi[key]).query)["sslmode"] == ["require"]
    assert parse_qs(urlparse(nestjs["DATABASE_URL"]).query)["sslmode"] == ["require"]


def test_when_the_docs_name_a_limit_then_it_matches_the_template():
    """The numbers in the docs are the numbers in the code.

    Validates project_initializer/templates-{api-nestjs,entra-nestjs,supabase-nestjs,entra-fastapi}/api limit constants (http-limits.ts, auth.service.ts, supabase-client.provider.ts, auth_settings.py).
    """
    body_limit = re.search(
        r"MAX_REQUEST_BODY_KILOBYTES = (\d+)",
        _source(_NESTJS_BASE, "src/config/http-limits.ts"),
    )
    entra = _source(
        _PACKAGE / "templates-entra-nestjs" / "api", "src/modules/auth/auth.service.ts"
    )
    supabase = _source(
        _PACKAGE / "templates-supabase-nestjs" / "api",
        "src/modules/auth/supabase-client.provider.ts",
    )
    fastapi_entra = _source(
        _PACKAGE / "templates-entra-fastapi" / "api",
        "app/infrastructure/auth_settings.py",
    )

    assert body_limit is not None and body_limit.group(1) == "512"
    assert "CLOCK_TOLERANCE_SECONDS = 30" in entra
    assert "JWKS_CACHE_MAX_AGE_MS = 24 * MILLISECONDS_PER_HOUR" in entra
    assert "SUPABASE_AUTH_TIMEOUT_MS = 5_000" in supabase
    assert "DEFAULT_JWKS_REFRESH_COOLDOWN_SECONDS = 30.0" in fastapi_entra
    assert "MAX_JWKS_REFRESH_COOLDOWN_SECONDS = 3600.0" in fastapi_entra


@pytest.mark.parametrize("name", ["CLAUDE.md", "README.md", "CONTRIBUTING.md"])
def test_when_the_repo_docs_are_read_then_stale_statements_are_gone(name):
    """The repo-level docs no longer carry the claims the rework made false.

    Validates CLAUDE.md, README.md and CONTRIBUTING.md.
    """
    text = (_REPO / name).read_text(encoding="utf-8")

    for stale in (
        "all 6 variants",
        "any outward import",
        "unwired",
        "(not gated)",
        "reported, not gated",
        "working dev defaults",
    ):
        assert stale not in text, f"{name} still says {stale!r}"


def test_when_the_changelog_is_read_then_the_breaking_changes_are_listed():
    """[Unreleased] lists every change a client or an operator must act on.

    Validates CHANGELOG.md [Unreleased].
    """
    changelog = (_REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = changelog.split("## [0.4.1]")[0]

    for keyword in (
        "audit log line changed",
        "`additional_databases`",
        "item ids must be UUIDs",
        "`email` comes from the `email` claim only",
        "Entra ids must be GUIDs in FastAPI too",
        "`anonymous`",
        "413",
        "`TRUST_PROXY_HOPS` defaults to 1",
        "`--no-access-log`",
        "`DB_WAIT_TIMEOUT_SECONDS`",
        "`migration_backup`",
    ):
        assert keyword in unreleased, f"CHANGELOG [Unreleased] lacks {keyword!r}"
    assert "## [0.4.1] - 2026-09-14" in changelog


def _unreleased_section(heading: str) -> str:
    """Return the text of one ``### <heading>`` block of the [Unreleased] changelog."""
    changelog = (_REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = changelog.split("## [Unreleased]", 1)[1].split("## [0.4.1]", 1)[0]
    (block,) = [
        block
        for block in re.split(r"^### ", unreleased, flags=re.M)
        if block.startswith(heading)
    ]
    return block


@pytest.mark.parametrize(
    ("heading", "statements"),
    [
        (
            "Breaking changes",
            [
                "`ENVIRONMENT=staging` and `production` refuse a database connection that is not TLS-protected",
                "`DATABASE_ALLOW_INSECURE_TRANSPORT=true`",
                "`DIRECT_DATABASE_URL`",
                "`NODE_ENV=production` refuses a `DATABASE_URL`",
                "`DB_ALLOW_INSECURE_TRANSPORT=true`",
                "`ItemsService.create`, `update` and `remove` take the actor id",
                "`create(item, actorId)`, `update(id, changes, actorId)`, `remove(id, actorId)`",
                "`AccessTokenDTO` gained a required `user_id`",
                "`TokenResponse` does not expose it",
            ],
        ),
        (
            "Security",
            [
                "TLS-protected in deployed environments",
                "Role-based access control in NestJS",
                "`@Roles(...roles)`",
                "`[ThrottlerGuard, ...AUTH_GUARDS, RolesGuard]`",
                "fail closed",
                "Audit trails name an actor by opaque id",
            ],
        ),
        (
            "Changed",
            [
                "SIGHUP now drives it",
                "NestJS `ItemsService` records its changes",
                "`AuthService.authenticate` returns an `AccessTokenDTO` that carries `user_id`",
            ],
        ),
        (
            "Added",
            [
                "SIGHUP reloads `LOG_LEVEL` in both stacks",
                "`log_level.reload_rejected`",
                "`log_level.reloaded`",
                "`log_level.reload_failed`",
                "`docker kill --signal=HUP <container>`",
                "A terminal hang-up also sends SIGHUP",
                "re-applies the start-up value",
                "NestJS `@Roles(...roles)` and `RolesGuard`",
                "NestJS `AuditLogger`",
                "`audit.action`",
                "`user.register` and `user.login`",
            ],
        ),
    ],
)
def test_when_the_changelog_is_read_then_each_entry_sits_under_its_heading(
    heading, statements
):
    """Operators find the TLS refusal, the opt-outs, the signature change and the new features.

    Validates CHANGELOG.md [Unreleased] headings.
    """
    section = _unreleased_section(heading)
    missing = [statement for statement in statements if statement not in section]

    assert missing == []


@pytest.mark.parametrize(
    ("name", "statements"),
    [
        (
            "README.md",
            [
                "refuses a database connection that is not TLS-protected",
                "`DATABASE_ALLOW_INSECURE_TRANSPORT=true`",
                "`DB_ALLOW_INSECURE_TRANSPORT=true`",
                "`kill -HUP <pid>`",
                "`@Roles(...)` and the global",
                "`user.register`",
            ],
        ),
        (
            "CLAUDE.md",
            [
                "`DATABASE_ALLOW_INSECURE_TRANSPORT=true`",
                "`DB_ALLOW_INSECURE_TRANSPORT=true`",
                "`app/infrastructure/log_level.py`",
                "`log_level.reload_rejected`",
                "`user.register` and `user.login`",
                "`AccessTokenDTO` gained `user_id`",
                "`[ThrottlerGuard, ...AUTH_GUARDS, RolesGuard]`",
                "every `@Roles` route is denied (fail closed)",
                "`AuditLogger.record(action, resourceId, actorId)`",
                "`src/config/log-level-reload.ts`",
                "`DIRECT_URL` is not checked",
                "a terminal hang-up also sends SIGHUP",
            ],
        ),
    ],
)
def test_when_the_repo_docs_are_read_then_they_describe_the_new_behaviour(
    name, statements
):
    """The repo-level docs carry the database TLS rule, the reload, roles and the audit trail.

    Validates README.md and CLAUDE.md.
    """
    text = (_REPO / name).read_text(encoding="utf-8")
    missing = [statement for statement in statements if statement not in text]

    assert missing == []
