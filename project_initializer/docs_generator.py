"""Generate the per-project README.md and CLAUDE.md files for a scaffold.

Like ``env_generator`` and the compose transforms, the docs a generated project
ships are BUILT from the chosen flags rather than copied from static overlay
files (which had to be maintained in N places and drifted — the hexagonal
refactor is what exposed that). Six documents are produced:

    <root>/README.md               — human quick-start for the whole project
    <root>/CLAUDE.md               — repo-level AI-assistant guidance
    <root>/api/README.md           — backend quick-start
    <root>/api/.claude/CLAUDE.md    — deep backend architecture guide
    <root>/frontend/README.md       — Angular quick-start
    <root>/frontend/.claude/CLAUDE.md — Angular best-practices guidance

Each document is assembled from a base plus per-flag sections
(framework / auth / scope), so a NestJS project never mentions SQLAlchemy, a
no-auth project never documents Entra, etc.

Pure string assembly — stdlib only, no I/O (``cli.py`` writes the results).
"""

from __future__ import annotations

_LICENSE = "MIT"

# The NestJS production-readiness checklist is static, framework-fixed reference
# content (9 concern sections + legend + global-criteria table + filter-DI note),
# appended verbatim to the generated api/.claude/CLAUDE.md so the depth the
# static doc carried is preserved. It is written for every auth variant at once:
# the guard rows say what an auth variant registers, and the no-auth variant
# registers none.
_NESTJS_READINESS_CHECKLIST = """\
## Request pipeline

### Middleware Stack

1. Helmet (security headers) and CORS, applied by `configureApp` in `src/app.setup.ts`
2. nestjs-pino HTTP logging (request-id correlation via `x-request-id`)
3. Throttler (rate limiting), the first global guard
4. Access-token guard (auth variants only), registered through `src/app.auth.ts`
5. `RolesGuard` (enforces `@Roles`), the last global guard, so it sees the verified identity
6. ZodValidationPipe (global)
7. ZodSerializerInterceptor (global)
8. HttpExceptionFilter + PrismaClientExceptionFilter (global), registered by `configureApp`

## Production-readiness acceptance checklist

> **Research provenance:** deep research — 110 agents, 28 primary sources, 24 claims at 3-0 adversarial verification against official NestJS docs (https://docs.nestjs.com/). Statuses reflect **verified current state** of this template.
>
> **Legend:** ✅ done in template · ⚠️ partial / worth hardening · ❌ gap / not present (non-goal)

### 1. Core building blocks & DI

- ✅ `@Module()` with providers/controllers/imports/exports — feature modules under `src/modules/*`
- ✅ `PrismaModule` is **not** `@Global()`: a module that needs the database imports it (it exports `PrismaService`, `DATABASE_CIRCUIT_BREAKER` and `DATABASE_HEALTH_PORT`); never re-register `PrismaService` in another `providers:` array
- ✅ Services depend on port tokens (`ITEM_REPOSITORY`, `DATABASE_HEALTH_PORT`, `ACCESS_TOKEN_VERIFIER`) that a module binds with `{ provide, useClass }`; tests swap in fakes
- ✅ Type-based constructor injection; default singleton scope (use REQUEST only when strictly needed)
- Citations: `/modules`, `/providers`, `/fundamentals/injection-scopes`

### 2. Controllers & routing

- ✅ `@Controller('prefix')` + HTTP-method decorators; request-data decorators (`@Body/@Query/@Param`) over raw `@Req()`; ids and path parameters are validated by Zod param DTOs (`UuidParamDto`)
- ✅ `app.setGlobalPrefix('api/v1')` in `configureApp` (`src/app.setup.ts`), called by `main.ts`; controllers declare no prefix
- ⚠️ URI/header versioning (`VersioningType`) — static `api/v1` prefix is sufficient for a single version (non-goal)
- Citations: `/controllers`, `/techniques/versioning`

### 3. DTOs, validation & serialization

- ✅ Zod schemas via `nestjs-zod` as DTOs (not erased interfaces)
- ✅ `ZodValidationPipe` registered as `APP_PIPE` — strips unknown fields from all incoming bodies
- ✅ `ZodSerializerInterceptor` registered as `APP_INTERCEPTOR`; response schemas whitelist fields so Prisma rows cannot leak secret columns; handlers declare them with `@ZodResponse`
- ⚠️ Built-in transform pipes — Zod coercion covers primitive coercion; no `ParseIntPipe` needed
- Citations: `/pipes`, `/techniques/validation`, `/techniques/serialization`

### 4. Request pipeline — pipes, guards, interceptors, filters, middleware

- ✅ Global Zod pipe, the access-token guard (auth variants), `ZodSerializerInterceptor`
- ✅ `HttpExceptionFilter` + `PrismaClientExceptionFilter` registered via `useGlobalFilters()` inside `configureApp` (`src/app.setup.ts`), which both `main.ts` and the e2e harness (`test/support/create-e2e-app.ts`) call, so a test exercises the same error handling a client gets
- ✅ Error bodies share one shape (`statusCode`, `error`, `message`, `path`, `timestamp`, `requestId`, and `errors` for validation failures); an unexpected error is answered with a fixed generic 500 and every 5xx is logged once; an oversized body is a 413, malformed JSON a 400 with a fixed message, and the health controller answers an unhealthy probe with the Terminus result
- ✅ nestjs-pino request logging; `@CurrentUser()`, `@Public()` custom decorators
- ⚠️ **Filter DI caveat:** filters registered via `useGlobalFilters()` in `configureApp` (called from `main.ts`) live outside the Nest DI container and cannot inject providers. The current filters are dependency-free (`new`-instantiated there) — **no change is required today**.

  If a filter gains a DI dependency (e.g. a logger service), move it to a module provider instead:

  ```typescript
  // app.module.ts — use when a filter needs DI (e.g. an injected LoggerService)
  import { APP_FILTER } from '@nestjs/core';
  import { MyLoggedFilter } from './common/filters/my-logged.filter';

  @Module({
    providers: [
      { provide: APP_FILTER, useClass: MyLoggedFilter },
    ],
  })
  export class AppModule {}
  ```

  Keep dependency-free filters in `configureApp` via `useGlobalFilters()` — switching them to `APP_FILTER` without a real DI need adds unnecessary indirection. Order matters there: Nest tries global filters from the last registered to the first, so the catch-all stays first in the call.

- Citations: `/pipes`, `/guards`, `/interceptors`, `/exception-filters`, `/middleware`, `/custom-decorators`

### 5. Authentication & authorization

- ✅ Auth variants (token, supabase, entra): `src/app.auth.ts` registers the shared `AccessTokenGuard` as `APP_GUARD`; the variant's `AuthService` is bound to `ACCESS_TOKEN_VERIFIER` in its `auth.module.ts`. The no-auth variant leaves `AUTH_GUARDS` empty, so every route is public
- ✅ `@Public()` opt-out via `Reflector.getAllAndOverride` — the guard honors it
- ✅ A rejected request writes one warn line (status, method, path, request id) and never the token or the caller's email
- ✅ Role-based access control: `@Roles(...roles)` and the global `RolesGuard` (`src/common/auth/roles.*`), registered last as `[ThrottlerGuard, ...AUTH_GUARDS, RolesGuard]`; a route without `@Roles` passes, otherwise the caller needs one of the roles, and no identity, an empty `@Roles()` or a mismatch is a 403 with a generic message (see "Roles (RBAC)"). No sample route uses it, and the no-auth variant denies every `@Roles` route
- ❌ CASL / attribute-based rules — non-goal (add only when fine-grained authz is needed); token mode is for service-to-service callers
- Citations: `/security/authentication`, `/security/authorization`, `/guards`

### 6. Security hardening

- ✅ Helmet (`app.use(helmet())`) — `configureApp` in `src/app.setup.ts`
- ✅ CORS restricted to `CORS_ORIGINS` env (not `*`), credentials/methods/headers configured — `configureApp`
- ✅ Rate limiting: `ThrottlerModule` 100 req/60s + global `ThrottlerGuard` listed before the auth guard, so failed credentials still count; the client address honours `TRUST_PROXY_HOPS` (default 1) — `app.module.ts`, `src/config/rate-limit.ts`
- ✅ Secrets via `@nestjs/config` with `ConfigModule.forRoot({ isGlobal: true })`; generated secrets are written to the root `.env` only
- ❌ CSRF — non-goal (bearer-token APIs are largely CSRF-immune; add `csurf` only if cookie auth is introduced)
- Citations: `/security/helmet`, `/security/rate-limiting`, `/security/csrf`

### 7. Operational concerns

- ✅ Env validation: `src/config/env.base.ts` — `createEnvValidator()` throws on missing or malformed `DATABASE_URL`/`DIRECT_URL` and every other shared key, naming the key but never its value; each variant's `src/config/env.validation.ts` extends `baseEnvSchema`; wired via `ConfigModule.forRoot({ validate })`
- ✅ Structured logging: `nestjs-pino` with `x-request-id` correlation (a valid incoming id is kept, otherwise a UUID is generated), `authorization` and `cookie` redacted, and the request line limited to id, method and path (no query string, headers or client address) — `src/config/logger.config.ts`
- ✅ Audit trail: `AuditLogger.record(action, resourceId, actorId)` (`src/common/audit`) writes one `audit.action` line through a pino child pinned to `info`, so `LOG_LEVEL` cannot silence it; the items service records `item.create`, `item.update` and `item.delete` with the caller's opaque id or `anonymous`, never an email or a username
- ✅ Runtime log level: `SIGHUP` reloads `LOG_LEVEL` (`src/config/log-level-reload.ts`), see "Configuration"
- ✅ Health checks: `@nestjs/terminus` liveness + readiness probes (DB with circuit state, disk, memory) — `src/modules/health/health.controller.ts`
- ✅ OpenAPI/Swagger at `/docs` (off in production unless `API_DOCS_ENABLED=true`) with a bearer requirement in auth variants and `cleanupOpenApiDoc` — `setupOpenApi` in `src/app.setup.ts`
- ✅ Graceful shutdown: `app.enableShutdownHooks()` in `configureApp` + Prisma `$disconnect` on `onModuleDestroy`; a start-up failure logs one fatal line and exits with code 1, forced after 10 seconds when closing hangs
- Citations: `/techniques/configuration`, `/techniques/logger`, `/recipes/terminus`, `/openapi/introduction`, `/fundamentals/lifecycle-events`

### 8. Database / ORM

- ✅ `PrismaService extends PrismaClient` in a non-global `PrismaModule`; connect on `onModuleInit`, disconnect on `onModuleDestroy`
- ✅ Production refuses a `DATABASE_URL` without `sslmode=require`, `verify-ca` or `verify-full` (`DB_ALLOW_INSECURE_TRANSPORT=true` opts out), `src/config/env.base.ts`
- ✅ SSL via the `deriveSslOption` util (with spec test): `sslmode=verify-ca` and `verify-full` verify the server certificate, `require` only encrypts, and `stripSslParameters` keeps `node-postgres` from overriding the decision; health probe runs `SELECT 1`
- ✅ Client-side timeouts and pool: `DB_CONNECT_TIMEOUT_MS` (connect), `DB_QUERY_TIMEOUT_MS` (`query_timeout` on the pool) and `DB_POOL_MAX` (the pool size)
- ✅ Circuit breaker around repository calls and the health probe (`DB_BREAKER_FAILURE_THRESHOLD`, `DB_BREAKER_RESET_MS`): once open, requests get a fast 503 instead of queueing on a dead database, and readiness reports the `circuit` state
- ✅ Migrations via `prisma migrate dev/deploy`; every migration ships a `down.sql` (rollback with `npx prisma db execute --file prisma/migrations/<dir>/down.sql`, newest first — see "Database migrations and rollback")
- ✅ Supabase variant: a migration enables Row Level Security on every table, `_prisma_migrations` included, so the Data API cannot reach them with the publishable key; `down.sql` backups go to the `migration_backup` schema
- Citations: `/recipes/prisma`, `/techniques/database`

### 9. Testing

- ✅ Jest configured; `npm test` and `npm run test:e2e` scripts present; `npm run test:cov` enforces a 75% line and statement threshold
- ✅ Service/controller unit specs next to their sources: `items.service.spec.ts`, `health.controller.spec.ts`, `src/serialization.spec.ts`
- ✅ e2e scaffold: `test/app.e2e-spec.ts` (supertest, plus `test/auth.e2e-spec.ts` in auth variants) + `test/jest-e2e.json`, built on `test/support/create-e2e-app.ts`, which swaps Prisma and the token verifier for in-memory fakes (no Postgres needed)
- ✅ Lint (`npm run lint`, type-checked ESLint, no warnings allowed) and Prettier (`npm run format:check`)
- Citations: `/fundamentals/testing`

## Global acceptance criteria

| # | Criterion | Status | Citation |
|---|-----------|--------|----------|
| 1 | Auth guard registered as `APP_GUARD` in every auth overlay — routes protected by default | ✅ | token/supabase/entra `src/app.auth.ts` (`AccessTokenGuard`, listed after `ThrottlerGuard` by the shared `src/app.module.ts`) |
| 2 | `ConfigModule` validates env and fails fast on missing secrets (`DATABASE_URL`, `SUPABASE_*`) | ✅ | `src/config/env.base.ts` — `createEnvValidator()` throws; wired via `ConfigModule.forRoot({ validate })` |
| 3 | Response schemas whitelist fields — Prisma rows cannot leak secret columns through the serializer | ✅ | `src/serialization.spec.ts` — `ItemResponseSchema.parse({ password: 'leak' })` strips `password` |
| 4 | Terminus health module: liveness/readiness probes (DB, disk, memory) | ✅ | `src/modules/health/health.controller.ts` — `@nestjs/terminus` |
| 5 | e2e test scaffold + service unit specs | ✅ | `test/app.e2e-spec.ts`, `test/jest-e2e.json`, `test/support/create-e2e-app.ts`; `items.service.spec.ts` |
"""

# The --legacy-peer-deps rationale is shared verbatim by every README that has a
# frontend dev section, so it lives in one place.
_LEGACY_PEER_DEPS_NOTE = (
    "> **Why `--legacy-peer-deps`?** The frontend `Dockerfile` and CI install with this flag, so a\n"
    "> local install resolves the same dependency tree. The flag makes npm 7+ ignore peer dependencies\n"
    "> while it builds the tree, as npm 3–6 did, so a peer-range conflict can't abort the install with\n"
    "> `ERESOLVE`. `ng build` and `ng test` still run against the installed packages, so a real\n"
    "> incompatibility still fails there."
)


# ── shared helpers ────────────────────────────────────────────────────────────


def _framework_label(framework: str) -> str:
    return "FastAPI" if framework == "fastapi" else "NestJS"


def _stack_line(framework: str, auth: str | None, *, frontend: bool) -> str:
    """One-line project summary in the README/CLAUDE overview."""
    fw = f"**{_framework_label(framework)}**"
    parts = [fw]
    if frontend:
        parts.append("**Angular**")
    parts.append("**Docker**")
    base = ", ".join(parts[:-1]) + f", and {parts[-1]}"
    if auth == "supabase":
        base = base.replace("**Docker**", "**Supabase**") + ", and **Docker**"
    elif auth == "entra":
        base += ", with **Microsoft Entra ID** authentication"
    elif auth == "token":
        base += ", with **bearer-token** authentication"
    return f"Full-stack application with {base}."


def _docker_services_table(framework: str, auth: str | None, *, frontend: bool) -> str:
    """Compose services table — omits db/adminer for supabase."""
    rows = ["| Service | Port | Description |", "|---------|------|-------------|"]
    if auth != "supabase":
        rows.append("| `db` | 5433:5432 | PostgreSQL 16 |")
    rows.append(
        f"| `api` | 8000:8000 | {_framework_label(framework)} with hot reload |"
    )
    if frontend:
        rows.append("| `frontend` | 4200:80 | Angular + nginx |")
    if auth != "supabase":
        rows.append("| `adminer` | 8080:8080 | Database admin UI |")
    return "\n".join(rows)


def _backend_dev_block(framework: str) -> list[str]:
    """The README '### Backend' fenced command block for the framework."""
    if framework == "fastapi":
        return [
            "### Backend (FastAPI)",
            "",
            "```bash",
            "cd api",
            'pip install ".[dev]"                   # Dependencies come from pyproject.toml',
            "uvicorn app.main:app --reload          # Runs on :8000",
            "",
            "# Database",
            "alembic upgrade head                   # Apply migrations",
            'alembic revision --autogenerate -m "description"',
            "",
            "# Tests",
            "pytest",
            "```",
        ]
    return [
        "### Backend (NestJS)",
        "",
        "```bash",
        "cd api",
        "npm install",
        "npm run start:dev                      # Runs on :8000",
        "",
        "# Database (Prisma)",
        "npx prisma migrate dev                 # Create + apply migration",
        "npx prisma migrate deploy              # Apply migrations (production)",
        "npx prisma generate                    # Regenerate Prisma client",
        "",
        "# Tests and checks",
        "npm test",
        "npm run test:e2e                       # No Postgres needed",
        "npm run lint",
        "```",
    ]


def _frontend_dev_block() -> list[str]:
    return [
        "### Frontend (Angular)",
        "",
        "```bash",
        "cd frontend",
        "npm install --legacy-peer-deps         # See note below",
        "ng serve                               # Runs on :4200",
        "ng test",
        "```",
        "",
        _LEGACY_PEER_DEPS_NOTE,
    ]


def _entra_prereq_section() -> list[str]:
    """Entra app-registration setup block (root README, auth == entra)."""
    return [
        "## Prerequisites",
        "",
        "Two Entra app registrations in your tenant:",
        "",
        "1. **API registration** — expose a scope (`access_as_user`), set `requestedAccessTokenVersion: 2` in the manifest.",
        "   > **Important:** the default manifest value (`null`) issues v1 tokens with an `sts.windows.net` issuer; this backend validates the v2 issuer and every request will fail with 401 unless you set `requestedAccessTokenVersion: 2`.",
        "2. **SPA registration** — single-page application (public client), add `http://localhost:4200` as a redirect URI.",
        "",
        "Map the IDs to your `.env`:",
        "",
        "| Registration | Value | Env var |",
        "|---|---|---|",
        "| Tenant | Directory (tenant) ID | `ENTRA_TENANT_ID` |",
        "| API app | Application (client) ID | `ENTRA_API_CLIENT_ID` |",
        "| API app | App ID URI or GUID | `ENTRA_API_AUDIENCE` |",
        "| API app | Scope URI | `ENTRA_API_SCOPE` |",
        "| SPA app | Application (client) ID | `ENTRA_SPA_CLIENT_ID` |",
        "",
        "`ENTRA_TENANT_ID` and `ENTRA_API_CLIENT_ID` must be GUIDs as the portal shows them; a domain name or `common` never matches the `tid` claim, so the API refuses to start with one. `ENTRA_API_SCOPE` may be the bare name or the full URI.",
        "",
        "No client secret is needed — the backend validates tokens via RS256 signature only.",
    ]


def _services_url_list(*, frontend: bool, auth: str | None) -> list[str]:
    lines = []
    if frontend:
        lines.append("- Frontend: http://localhost:4200")
    lines.append("- API: http://localhost:8000")
    lines.append("- API Docs: http://localhost:8000/docs")
    if auth != "supabase":
        lines.append("- Adminer: http://localhost:8080")
    return lines


def _nestjs_root_readme_notes(auth: str | None) -> list[str]:
    """Secrets, proxy, database-TLS and log-level notes for the NestJS root README."""
    lines: list[str] = []
    if auth == "token":
        lines += [
            "The scaffolded `.env` holds a generated random `AUTH_TOKEN`. "
            "`.env.example` leaves it empty because it is the file you commit; never commit `.env`.",
            "",
        ]
    lines += [
        "The rate limiter keys on the client address that `X-Forwarded-For` names. `TRUST_PROXY_HOPS` "
        "(default 1, the bundled nginx) is the number of proxies in front of the API; set it to `0` "
        "when the API is exposed directly, or a client can spoof the header and dodge the limit. "
        "JSON request bodies above 512 KiB answer 413.",
        "",
        "Swagger UI at `/docs` is served unless `NODE_ENV=production`; `API_DOCS_ENABLED=true` or `false` "
        "overrides that. The container entrypoint waits for the database named in `DATABASE_URL`, at most "
        "`DB_WAIT_TIMEOUT_SECONDS` seconds (default 60), then exits with status 1. The generated `.env` "
        "sets `NODE_ENV=development` for the compose `dev` target; the production image sets "
        "`NODE_ENV=production` itself and must not be started with that file.",
        "",
        "With `NODE_ENV=production` the API refuses a `DATABASE_URL` unless every `sslmode` in it is "
        "`require`, `verify-ca` or `verify-full`; `DB_ALLOW_INSECURE_TRANSPORT=true` is the explicit "
        "opt-out for a database on the same host or on a private network without TLS. The compose stack "
        "runs with `NODE_ENV=development` and is unaffected. `kill -HUP <pid>` (`docker kill --signal=HUP "
        "<container>` in Docker) reloads `LOG_LEVEL` from the `.env` file; a container reads no `.env` "
        "file (compose passes the variables), so there a reload re-applies the start-up value.",
    ]
    return lines


def _edit_env_comment(auth: str | None) -> str:
    """The README hint on reviewing ``.env``; it mentions generated secrets only when there are some."""
    if auth == "token":
        return "# Review .env (generated secrets are already filled in)"
    return "# Review .env (scaffolding already wrote it)"


def _fastapi_root_readme_notes(auth: str | None) -> list[str]:
    """Secrets, docs-visibility, proxy, database-TLS and log-level notes for the FastAPI root README."""
    lines: list[str] = []
    if auth == "token":
        lines += [
            "The scaffolded `.env` holds generated random secrets (`AUTH_TOKEN` and `JWT_SECRET_KEY`). "
            "`.env.example` leaves them empty because it is the file you commit; never commit `.env`. "
            "At every stage the API refuses to start with a placeholder such as `changeme` or a "
            "non-empty secret that is too short (`AUTH_TOKEN` under 16 characters, `JWT_SECRET_KEY` "
            "under 32). With `ENVIRONMENT=staging` or `production` an empty secret is refused as well.",
            "",
        ]
    lines += [
        "The interactive docs at `/docs` are served in every environment except `production`; "
        "set `API_DOCS_ENABLED=true` to serve them there as well. "
        "`GET /health` is the liveness probe and `GET /health/ready` the readiness probe "
        "(503 while the database is unreachable).",
        "",
        "The in-memory rate limiter (active when `ENVIRONMENT` is `staging` or `production`) keys on "
        "the client address. Behind a reverse proxy, list that proxy in `FORWARDED_ALLOW_IPS`, "
        "or every caller shares one bucket.",
        "",
        "The container waits for the database named in `DATABASE_URL`, at most `DB_WAIT_TIMEOUT_SECONDS` "
        "seconds (default 60), then exits with status 1 instead of hanging. Uvicorn's access log is off "
        "(`--no-access-log`): the app writes one structured `http.request` line per request, without "
        "query string or client address.",
        "",
        "In `staging` and `production` the API refuses a database connection that is not TLS-protected: "
        "`DATABASE_SSL_MODE`, or the `sslmode` of `DATABASE_URL` (and of `DIRECT_DATABASE_URL`), must be "
        "`require`, `verify-ca` or `verify-full`. " + _fastapi_database_tls_hint(auth),
        "",
        "`kill -HUP <pid>` (`docker kill --signal=HUP <container>` in Docker) makes the API re-read "
        "`LOG_LEVEL` without a restart; the value in the project `.env` file wins over the environment. "
        "A container reads no `.env` file (compose passes the variables), so there a reload re-applies the "
        "start-up value.",
    ]
    return lines


def _fastapi_database_tls_hint(auth: str | None) -> str:
    """The variant-specific end of the README note on the database TLS rule."""
    if auth == "supabase":
        return (
            "The generated `.env` sets `DATABASE_SSL_MODE=require` and `sslmode=require` in both "
            "URLs, so it already meets the rule."
        )
    return (
        "The bundled compose `db` serves no TLS, so `ENVIRONMENT=production docker compose up` needs "
        "`DATABASE_ALLOW_INSECURE_TRANSPORT=true`, the explicit opt-out for a database on the same host "
        "or on a private network."
    )


# ── ROOT README.md ─────────────────────────────────────────────────────────────


def generate_root_readme(
    framework: str,
    auth: str | None,
    *,
    api: bool = True,
    frontend: bool = True,
    async_db: bool = False,
) -> str:
    """Build the project-root README.md for the given flags."""
    if not api:
        # frontend-only scope
        return "\n".join(
            [
                "# project-initializer",
                "",
                "Angular single-page application scaffolded by "
                "[project-initializer](https://github.com/silviobaratto/project-initializer).",
                "",
                "## Getting Started",
                "",
                "```bash",
                "cd frontend",
                "npm install --legacy-peer-deps",
                "ng serve                               # http://localhost:4200",
                "```",
                "",
                _LEGACY_PEER_DEPS_NOTE,
                "",
                "## License",
                "",
                _LICENSE,
                "",
            ]
        )

    sections = [
        "# Project",
        "",
        _stack_line(framework, auth, frontend=frontend),
    ]
    if auth == "entra":
        sections += [
            "",
            "Local Docker PostgreSQL database — no hosted auth backend required at runtime.",
            "",
        ]
        sections += _entra_prereq_section()
    elif auth == "supabase":
        sections += [
            "",
            "No local database required - uses hosted Supabase for database and authentication.",
        ]
    sections += ["", "## Getting Started", "", "```bash"]
    if auth == "entra":
        sections.append(
            "# Edit .env with your Entra credentials (scaffolding already wrote it)"
        )
    elif auth == "supabase":
        direct_url_key = (
            "DIRECT_DATABASE_URL" if framework == "fastapi" else "DIRECT_URL"
        )
        database_keys = f"DATABASE_URL, {direct_url_key}"
        sections += [
            "# Edit .env with your Supabase credentials:",
            f"#   {database_keys}, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY",
        ]
    else:
        sections.append(_edit_env_comment(auth))
    sections += ["docker compose up -d --build", "```", ""]
    sections += ["Services will be available at:"] + _services_url_list(
        frontend=frontend, auth=auth
    )
    if framework == "nestjs":
        sections += [""] + _nestjs_root_readme_notes(auth)
    else:
        sections += [""] + _fastapi_root_readme_notes(auth)
    sections += ["", "## Development", ""]
    sections += _backend_dev_block(framework)
    if frontend:
        sections += [""] + _frontend_dev_block()
    sections += [
        "",
        "## Docker Services",
        "",
        _docker_services_table(framework, auth, frontend=frontend),
        "",
        "## License",
        "",
        _LICENSE,
        "",
    ]
    return "\n".join(sections)


# ── ROOT CLAUDE.md ───────────────────────────────────────────────────────────


def _fastapi_root_claude(auth: str | None) -> list[str]:
    sections = [
        "## API Template (`api/`)",
        "",
        "FastAPI application with clean / hexagonal architecture (four layers):",
        "",
        "| Layer | Purpose |",
        "|-------|---------|",
        "| `app/domain/` | Pure core: `entities/` (frozen dataclasses), `ports/` (`ItemRepositoryPort`, `UnitOfWorkPort`, `TokenVerifierPort`), `services/`, `constants.py` (shared limits), `exceptions.py` (`DomainError` hierarchy, no HTTP) — no framework/ORM imports |",
        "| `app/application/` | Use-case orchestration: `services/` (depend on domain ports, own the commit), `commands/` (inputs), `dto/` (outputs) — imports domain only |",
        "| `app/infrastructure/` | The only tech layer: `settings.py` + `auth_settings.py`, `config.py` (walk-up `.env` loader), `database.py` (pooling + circuit breaker), `orm/` (SQLAlchemy), `repositories/` (port adapters), `unit_of_work.py`, `structured_logging.py`, `log_level.py` (SIGHUP reloads `LOG_LEVEL`), `migration_safety.py`, `audit.py` |",
        "| `app/api/` | HTTP surface: `deps.py` (composition root, the only place that names concrete adapters), `auth_deps.py` (the auth seam), `bearer.py`, `authorization.py`, `pagination.py`, `errors.py` + `handlers.py` (one error envelope), `docs.py`, `health.py`, `schemas/` (Pydantic), `middleware/`, `v1/router.py` + `v1/endpoints/` |",
        "| `alembic/` | Schema migrations: Alembic owns the schema, every migration has a data-preserving `downgrade()` |",
        "",
        "Dependencies point strictly inward: `api → application → domain`, `infrastructure → domain`. An AST fitness test (`api/tests/unit/test_architecture.py`) enforces it with an allowlist: `domain` imports the standard library and `app.domain` only, `application` adds `app.application`, neither calls `importlib.import_module` or `__import__`, `infrastructure` never imports `app.api` or `app.main`, and `app/api` imports no repository, ORM model or `get_db` except in the composition roots `deps.py` and `auth_deps.py`.",
        "",
        "**Auth seam**: a variant changes who the caller is by replacing two files, `app/api/auth_deps.py` and `app/infrastructure/auth_settings.py`. `deps.py` is never replaced, so a fix there reaches every variant. Routes depend on `CurrentUser` only.",
        "",
        "**Sync vs async**: DB endpoints are sync `def` (offloaded to a threadpool with the sync `Session`); `async def` is reserved for real async I/O. See `api/.claude/CLAUDE.md` for the full rule.",
        "",
        '**Request pipeline** (outermost first): CORS, request logging (assigns `X-Request-ID`), security headers, the catch-all that answers an unhandled exception with the generic 500 envelope, rate limiting (only when `ENVIRONMENT` is `staging` or `production`). Every error response is one JSON envelope, `{"error": {"code", "message", "timestamp", "request_id"}}`.',
        "",
        "### Mapping from the FastAPI tutorial",
        "",
        'The official FastAPI "Bigger Applications" tutorial organizes path operations into a `routers/` package where each router file also holds inline DB queries and business logic. This scaffold keeps the routers at `app/api/v1/endpoints/` (aggregated by `app/api/v1/router.py`, all under the `/api/v1` prefix) and splits what the tutorial keeps inline across the four hexagonal layers: router (`app/api/v1/endpoints/`) → application service (`app/application/services/`) → domain port (`app/domain/ports/`) implemented by an infrastructure repository (`app/infrastructure/repositories/`) → ORM model (`app/infrastructure/orm/`) → Pydantic schema (`app/api/schemas/`).',
        "",
        "Unlike the tutorial's flat layout, **this is a real restructure — the code is physically split across `domain`/`application`/`infrastructure`/`api`, not just conceptually.**",
    ]
    if auth == "token":
        sections += [
            "",
            "## Token auth (`--auth token`)",
            "",
            '`POST /auth/validate` is a validity **probe**: it returns **HTTP 200 with `authenticated=false`** for an invalid token, because both outcomes are successful *answers* to "is this token valid?". **401 is reserved for guarded endpoints that refuse access** (`/auth/me`, item writes), never for the probe. The supabase variant has **no** `/auth/validate` endpoint; token validity is resolved server-side through Supabase Auth (`get_user()` on the bearer JWT) instead.',
            "",
            "Two modes live side by side. The shared `AUTH_TOKEN` guards item writes and `GET /auth/me`. JWT login (`POST /auth/register`, `POST /auth/token`, `GET /auth/me/jwt`) identifies individual users. Scaffolding generates `AUTH_TOKEN` and `JWT_SECRET_KEY` into `.env` and leaves them empty in `.env.example`; at every stage the API refuses a placeholder or a non-empty secret shorter than 16 and 32 characters, and outside development it refuses an empty one too. `POST /auth/token` and `GET /auth/me/jwt` answer 503 while `JWT_SECRET_KEY` is empty. A successful registration and a successful login write the audit actions `user.register` and `user.login`, which name the account by id and never by email or username.",
        ]
    return sections


def _nestjs_modules(auth: str | None) -> str:
    """Feature modules under ``src/modules/``; ``auth`` exists only in an auth variant."""
    modules = "health, items, test"
    return f"{modules}, auth" if auth else modules


def _nestjs_root_claude(auth: str | None) -> list[str]:
    return [
        "## API Template (`api/`)",
        "",
        "NestJS application with modular architecture:",
        "",
        "| Layer | Purpose |",
        "|-------|---------|",
        "| `src/app.module.ts` | Root module, identical in every variant; authentication enters only through `src/app.auth.ts` |",
        f"| `src/modules/` | Feature modules ({_nestjs_modules(auth)}) |",
        "| `src/prisma/` | PrismaModule (not global), PrismaService, database circuit breaker |",
        "| `src/common/` | Shared auth (guard, verifier port, `@Roles` and `RolesGuard`), audit (`AuditLogger`), decorators, filters, resilience (circuit breaker) |",
        "| `prisma/schema.prisma` | Database models; every migration under `prisma/migrations/` ships a `down.sql` |",
        "",
        "Roll a migration back with `npx prisma db execute --file prisma/migrations/<dir>/down.sql`, newest first. Do not use `prisma migrate resolve --rolled-back`: it rejects an applied migration.",
        "",
        "See `api/.claude/CLAUDE.md` for the production-readiness checklist.",
    ]


def generate_root_claude(
    framework: str,
    auth: str | None,
    *,
    api: bool = True,
    frontend: bool = True,
    async_db: bool = False,
) -> str:
    """Build the project-root CLAUDE.md for the given flags."""
    if not api:
        return "\n".join(
            [
                "# CLAUDE.md",
                "",
                "This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.",
                "",
                "## Project Overview",
                "",
                "Angular frontend scaffolded by `project-initializer`.",
                "",
                "## Frontend Template (`frontend/`)",
                "",
                "Angular 21 with Angular Material 3 (`mat.theme()` and `--mat-sys-*` tokens). See `frontend/.claude/CLAUDE.md` for conventions.",
                "",
            ]
        )

    sections = [
        "# CLAUDE.md",
        "",
        "This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.",
        "",
        "## Project Overview",
        "",
        _stack_line(framework, auth, frontend=frontend),
        "",
        "## Build & Run Commands",
        "",
        "```bash",
        "# Run full stack with Docker",
        "docker compose up -d --build",
        "",
        "# Stop all services",
        "docker compose down",
        "```",
        "",
    ]
    if framework == "fastapi":
        sections += _fastapi_root_claude(auth)
    else:
        sections += _nestjs_root_claude(auth)
    if frontend:
        sections += [
            "",
            "## Frontend Template (`frontend/`)",
            "",
            "Angular 21 with Angular Material 3 (standalone components, signals, native control flow, OnPush, `inject()`, `--mat-sys-*` tokens). See `frontend/.claude/CLAUDE.md` for the full conventions.",
        ]
    sections += [
        "",
        "## Docker Services",
        "",
        _docker_services_table(framework, auth, frontend=frontend),
        "",
    ]
    return "\n".join(sections)


def _nestjs_src_tree(auth: str | None) -> list[str]:
    """The ``src/`` tree both NestJS api docs print."""
    return [
        "src/",
        "├── main.ts               # bootstrap(): create app, configureApp, OpenAPI, listen",
        "├── app.setup.ts          # configureApp(): logger, Helmet, CORS, api/v1 prefix, exception filters",
        "├── app.module.ts         # Root module, identical in every variant (Config, pino, Throttler, features)",
        "├── app.auth.ts           # AUTH_MODULES / AUTH_GUARDS seam: empty here, replaced by an auth overlay",
        "├── prisma/               # PrismaModule (not global), PrismaService, circuit breaker, DB health port",
        "├── common/               # auth/ (guard, roles, verifier port, /auth/me), audit/ (AuditLogger), decorators, dto/, filters/, resilience/",
        "├── config/               # env.base.ts (shared env schema), env.validation.ts, logger.config.ts, log-level-reload.ts (SIGHUP), rate-limit.ts",
        f"└── modules/              # {_nestjs_modules(auth)}",
    ]


# ── api/README.md ─────────────────────────────────────────────────────────────


def generate_api_readme(
    framework: str, *, async_db: bool = False, auth: str | None = None
) -> str:
    """Build api/README.md for the framework.

    ``auth`` only changes the NestJS source tree, which lists the ``auth`` module in an
    auth variant; FastAPI ignores it.
    """
    if framework == "fastapi":
        tree = [
            "app/",
            "├── main.py                     # App factory: load .env → logging → error handlers → middleware → routers",
            "├── domain/                     # Pure core (entities, constants, exceptions, ports: ItemRepositoryPort, UnitOfWorkPort, TokenVerifierPort) — no framework imports",
            "├── application/                # Use-case orchestration (services, commands, dto) — domain-only deps",
            "├── infrastructure/             # Tech layer: settings, auth_settings, database + circuit breaker, orm/, repositories/, log_level (SIGHUP reloads LOG_LEVEL)",
            "└── api/                        # HTTP: deps.py (composition root), auth_deps.py (auth seam), bearer.py, authorization.py, pagination.py, errors.py, handlers.py, docs.py, health.py, schemas/, middleware/ (request id, security headers, catch-all 500, rate limiting), v1/",
            "",
            "alembic/                        # Schema migrations: upgrade head, downgrade -1",
            "tests/                          # unit / integration / e2e on in-memory SQLite (no Docker needed)",
        ]
        return "\n".join(
            [
                "# FastAPI Backend",
                "",
                "## Quick Start",
                "",
                "```bash",
                'pip install ".[dev]"             # Dependencies come from pyproject.toml',
                "uvicorn app.main:app --reload    # http://localhost:8000",
                "```",
                "",
                "## Key Commands",
                "",
                "```bash",
                "pytest                                            # Run tests (fails below 75% branch coverage of app/)",
                "pytest -m unit --no-cov                           # One level or one file: --no-cov, the gate needs the whole suite",
                "alembic upgrade head                              # Apply migrations",
                "alembic downgrade -1                              # Roll the newest migration back (rows are kept)",
                'alembic revision --autogenerate --rev-id 0003_add_widget -m "add widget"  # Create migration',
                "```",
                "",
                "## Architecture (four-layer hexagonal)",
                "",
                "```",
                *tree,
                "```",
                "",
                "Dependencies point strictly inward: `api → application → domain`, `infrastructure → domain`. See `.claude/CLAUDE.md` for the full guide.",
                "",
            ]
        )
    return "\n".join(
        [
            "# NestJS Backend",
            "",
            "## Quick Start",
            "",
            "```bash",
            "npm install",
            "npm run start:dev    # http://localhost:8000",
            "```",
            "",
            "## Key Commands",
            "",
            "```bash",
            "npm test                          # Run unit tests",
            "npm run test:cov                  # Unit tests + 75% coverage gate",
            "npm run test:e2e                  # e2e tests (in-memory fakes, no Postgres)",
            "npm run lint                      # ESLint, fails on warnings",
            "npm run format:check              # Prettier check (npm run format to fix)",
            "npx prisma migrate dev            # Create + apply migration",
            "npx prisma migrate deploy         # Apply migrations (production)",
            "npx prisma db execute --file prisma/migrations/<dir>/down.sql  # Roll a migration back",
            "npx prisma generate               # Regenerate Prisma client",
            "npx prisma studio                 # Visual DB editor",
            "```",
            "",
            "## Architecture",
            "",
            "```",
            *_nestjs_src_tree(auth),
            "",
            "prisma/schema.prisma       # Database models",
            "prisma/migrations/         # One directory per migration: migration.sql + down.sql",
            "```",
            "",
        ]
    )


# ── api/.claude/CLAUDE.md ─────────────────────────────────────────────────────


_FASTAPI_TREE = [
    "app/",
    "├── main.py                     # App factory: load .env → logging → error handlers → middleware → routers; lifespan",
    "├── domain/                     # Pure core — NO framework/ORM imports",
    "│   ├── constants.py            # Business limits shared by every layer",
    "│   ├── entities/               # Frozen dataclasses (Item, AuthenticatedUser)",
    "│   ├── ports/                  # Protocols: ItemRepositoryPort, UnitOfWorkPort, TokenVerifierPort",
    "│   ├── services/               # Pure domain logic",
    "│   └── exceptions.py           # DomainError hierarchy (public message + log context, no HTTP status)",
    "├── application/                # Use-case orchestration — depends on domain only",
    "│   ├── services/               # ItemService (depends on ports, commits after a write)",
    "│   ├── commands/               # Inputs (CreateItemCommand, UpdateItemCommand)",
    "│   └── dto/                    # Outputs (ItemDTO, ItemPageDTO)",
    "├── infrastructure/             # The ONLY tech layer",
    "│   ├── config.py               # Walk-up .env loader (load_configuration)",
    "│   ├── settings.py             # Settings (pydantic-settings, Literal-validated)",
    "│   ├── auth_settings.py        # Auth settings seam (an auth overlay replaces it)",
    "│   ├── database.py             # DatabaseManager: sync SQLAlchemy + psycopg2 pooling + circuit breaker",
    "│   ├── circuit_breaker.py      # Closed / open / half-open breaker around database sessions",
    "│   ├── errors.py               # Driver errors → CircuitOpenError, DatabaseUnavailableError, DatabaseOperationError, ConflictError",
    "│   ├── health.py               # Database probe behind /health/ready",
    "│   ├── unit_of_work.py         # SqlAlchemyUnitOfWork (commit, rollback)",
    "│   ├── orm/                    # SQLAlchemy models (Base in base.py)",
    "│   ├── repositories/           # Port adapters (SqlAlchemyItemRepository) + item_mapping.py",
    "│   ├── auth/                   # TokenVerifierPort adapters of the auth variant",
    "│   ├── structured_logging.py   # JSON / text log formatters that carry the request id",
    "│   ├── request_context.py      # Request id in a ContextVar",
    "│   ├── log_level.py            # SIGHUP re-reads LOG_LEVEL (reload_log_level_on_sighup, run by the lifespan)",
    "│   ├── migration_safety.py     # preserve_and_drop_table / preserve_and_drop_column: data-preserving downgrades",
    "│   └── audit.py                # Audit-log helper (event audit.action on logger app.audit; resource and actor ids only)",
    "└── api/                        # HTTP surface",
    "    ├── deps.py                 # Composition root: services bound to adapters (an overlay never replaces it)",
    "    ├── auth_deps.py            # Auth seam: get_current_user / CurrentUser (an auth overlay replaces it)",
    "    ├── bearer.py               # Bearer-token extraction (length-capped)",
    "    ├── authorization.py        # require_roles(...) guard",
    "    ├── pagination.py           # skip / limit query parameters with bounds",
    "    ├── errors.py               # error_response() and error_responses() for OpenAPI",
    "    ├── handlers.py             # Exception handlers and the domain-error → status table",
    "    ├── docs.py                 # Swagger UI and ReDoc routes (only when docs are enabled)",
    "    ├── health.py               # /, /health, /health/ready",
    "    ├── schemas/                # Pydantic request/response schemas; errors.py holds ErrorEnvelope, common.py NulFreeStr",
    "    ├── middleware/             # Request logging, security headers, catch-all 500, rate limiting",
    "    └── v1/                     # router.py aggregates endpoints/ (all under /api/v1)",
    "",
    "alembic/                        # Migrations: env.py reads the settings, versions/ holds the chain",
    "tests/                          # unit / integration / e2e, fakes.py, conftest.py (in-memory SQLite)",
]

_FASTAPI_ROUTES_SECTION = [
    "## Routes",
    "",
    "All v1 routes sit under `/api/v1`: add an endpoint module under `app/api/v1/endpoints/` and register it in `app/api/v1/router.py`. The health routes sit at the root, outside the version prefix.",
    "",
    "| Route | Auth | Notes |",
    "|-------|------|-------|",
    "| `GET /api/v1/items` | public | `skip` 0..10000 and `limit` 1..100 (default 100); answers `items` and `total` |",
    "| `POST /api/v1/items` | `CurrentUser` | 201; `PUT` and `DELETE /api/v1/items/{id}` also need `CurrentUser`; `GET /api/v1/items/{id}` is public. Item ids are UUIDs: any other id is a 422, not a 404 |",
    "| `GET /api/v1/auth/me` | `CurrentUser` | `{id, email, username, roles, auth_method}` in every variant |",
    "| `GET /api/v1/test/ping`, `/test/echo/{message}`, `POST /api/v1/test/echo` | public | Demo routes |",
    "| `GET /`, `GET /health`, `GET /health/ready` | public | Liveness and readiness probes, exempt from rate limiting |",
    "",
    "Schema naming: `<Entity>Create`, `<Entity>Update`, `<Entity>Response`. A text field that reaches the database is declared `NulFreeStr` (`app/api/schemas/common.py`) with its length bounds, because PostgreSQL drivers cannot bind a NUL character and it would otherwise surface as a 500 instead of a 422.",
]

_FASTAPI_ERRORS_SECTION = [
    "## Errors",
    "",
    "Every non-2xx response has one JSON shape, `ErrorEnvelope` (`app/api/schemas/errors.py`):",
    "",
    "```json",
    '{"error": {"code": "NOT_FOUND", "message": "Item not found", "timestamp": "...", "request_id": "...", "details": null}}',
    "```",
    "",
    "`details` lists `{field, message}` pairs and appears only for validation failures. The message never echoes a submitted value.",
    "",
    "A `DomainError` (`app/domain/exceptions.py`) carries two separate texts. `public_message` goes to the client and is written for end users. `log_context` goes to the log only: ids, reasons and error classes, never tokens or personal data. The domain layer knows no HTTP status; `app/api/handlers.py` owns the table:",
    "",
    "| Error | Status | Logged at |",
    "|-------|--------|-----------|",
    "| `DomainValidationError` | 422 | INFO |",
    "| `EntityNotFoundError` | 404 | INFO |",
    "| `ConflictError` | 409 | INFO |",
    "| `DatabaseOperationError` | 500, code `DATABASE_ERROR`, generic message | ERROR |",
    "| `AuthenticationError` | 401 with `WWW-Authenticate: Bearer` | WARNING |",
    "| `AuthorizationError` | 403 | WARNING |",
    "| `ExternalServiceError` | 503 with `Retry-After: 30` | ERROR |",
    "| `RequestValidationError` (FastAPI) | 422 with `details` | n/a |",
    "| anything else | 500, generic message `An unexpected error occurred`, logged with its traceback | ERROR |",
    "",
    "Driver exceptions never leave the infrastructure layer, because their text quotes the SQL and the offending values. `app/infrastructure/errors.py` translates them: an integrity violation, a deadlock or a serialization failure becomes a `ConflictError` (409, safe to retry); an outage becomes a 503; anything else the database refuses becomes a `DatabaseOperationError` (500, `DATABASE_ERROR`). Repositories flush through `flush_or_conflict` and the unit of work commits through the same translation, so a uniqueness race answers 409 whichever moment the database rejects it.",
    "",
    "`UnhandledErrorMiddleware` answers an exception that no handler took with the same generic 500 envelope. It sits inside the logging, security and CORS layers, so that 500 carries the request id, the security headers and the CORS headers, and it never re-raises, so the failure is logged once with its traceback instead of twice.",
    "",
    "Declare the statuses a route can return with `responses=error_responses(401, 404, ...)` so the OpenAPI document matches what clients get. The rate limiter answers 429 with the same envelope (code `RATE_LIMITED`).",
]

_FASTAPI_REQUEST_LOGGING_SECTION = [
    "## Request IDs and logging",
    "",
    "`RequestLoggingMiddleware` (`app/api/middleware/logging.py`) gives every request an id. A valid incoming `X-Request-ID` (letters, digits, `.`, `_`, `-`; at most 64 characters) is reused so a gateway can correlate its logs; otherwise a UUID is generated. The id is stored in a context variable and in `request.state.request_id`, returned in the `X-Request-ID` response header, and copied into the `request_id` field of every error body and every log line.",
    "",
    "- Logs are one JSON object per line (`timestamp`, `level`, `logger`, `message`, `request_id`, plus any `extra=` fields). Set `LOG_FORMAT=text` for a readable terminal format; `LOG_LEVEL` sets the threshold.",
    "- Each request writes one `http.request` line: method, path, status and duration in milliseconds. The `path` is the matched route template (`/api/v1/items/{item_id}`), never the raw URL, because a path parameter can hold user text. Request and response bodies, query strings and client addresses are never logged, because they carry tokens, emails and other personal data. Keep it that way, and log ids rather than usernames or emails.",
    "- Middleware order, outermost first: CORS, request logging, security headers, `UnhandledErrorMiddleware`, rate limiting. CORS is outermost so its headers also appear on 429 and 500 responses and preflight requests never use rate-limit quota; the catch-all sits inside the logging, security and CORS layers so its 500 carries their headers, and outside the limiter so a failure there is answered too. Starlette adds each middleware at the front, so `main.py` adds them in the reverse order. CORS never allows credentials, because the API authenticates with a bearer header.",
    '- Uvicorn\'s own access log is off (`--no-access-log` in the Dockerfile, the compose files and `python -m app.main`). `configure_logging` also routes the `uvicorn` error loggers through the same formatter, so server errors come out as JSON too. `set_log_level("debug")` in `app/infrastructure/structured_logging.py` changes the level of a running process without a restart; no HTTP route exposes it.',
    "- **SIGHUP reloads `LOG_LEVEL`.** The lifespan installs `reload_log_level_on_sighup` (`app/infrastructure/log_level.py`), so `kill -HUP <pid>`, or `docker kill --signal=HUP <container>`, makes the process re-read the level without a restart. On a reload the value in the project `.env` file wins over the one in the process environment (the reverse of start-up, where the environment wins), and the environment is the fallback when the file has none; letter case is free, as at start-up. An invalid value is ignored: the level stays and one `log_level.reload_rejected` warning records the length of the rejected text and the accepted names, never the text. An applied reload logs `log_level.reloaded`, an unexpected failure logs `log_level.reload_failed` with the error class only, and nothing but the level changes (`os.environ` and every other setting stay as they were). The previous SIGHUP handler is restored on shutdown, and nothing is installed on Windows or outside the main thread. Two caveats: a terminal hang-up also sends SIGHUP, so a server started from a terminal that closes keeps running instead of exiting; and without a `.env` file, as in a Docker container where compose passes the variables, the environment cannot change, so a reload re-applies the start-up value.",
    "- `write_audit_log` (`app/infrastructure/audit.py`) records state-changing actions as the event `audit.action` on the logger `app.audit`, with `action`, `resource_id` and `actor_id` fields. `configure_logging` pins that logger to INFO, so a high `LOG_LEVEL` does not switch the trail off. Pass an opaque actor id, never an email or a username. The item routes write `item.create`, `item.update` and `item.delete` as background tasks, so the log write never delays the response.",
]

_FASTAPI_RESILIENCE_SECTION = [
    "## Resilience and readiness",
    "",
    "Database sessions run inside a circuit breaker (`app/infrastructure/circuit_breaker.py`):",
    "",
    "- `DATABASE_BREAKER_FAILURE_THRESHOLD` (default 5) consecutive connectivity failures open the circuit. While it is open every request fails fast with `503 SERVICE_UNAVAILABLE` and `Retry-After: 30`, instead of queueing behind pool timeouts.",
    "- After `DATABASE_BREAKER_RESET_TIMEOUT` seconds (default 30) the circuit goes half-open and lets one probe call through: success closes it, failure re-opens it. Every state change is logged at WARNING.",
    "- Only connectivity failures count: a pool timeout, a dropped connection, a PostgreSQL SQLSTATE of class 08, 53, 57P or 58. A constraint violation, a bad query, a deadlock, a serialization failure or a lock timeout does not trip the breaker (the last three answer 409). A request that never reached the database, such as one refused by validation, frees its slot without a vote. `DATABASE_CONNECT_TIMEOUT` and `DATABASE_POOL_TIMEOUT` bound how long a request can wait on the database.",
    "- The fallback is deliberate and simple: a fast, uniform 503 with the standard envelope. There is no cache or read-only mode.",
    "",
    '`GET /health` is the liveness probe: it checks nothing, so a database outage never gets the container restarted. `GET /health/ready` is the readiness probe: it answers `200 {"status": "ok", "database": "up", "circuit": "closed", "additional_databases": {}}`, or `503` with `"status": "degraded"` while the database is down or the circuit is open, without touching the database in the open case. A database outage at start-up is logged and never aborts the process.',
    "",
    "A component that owns a second database or other resources hooks into the lifecycle through `app/infrastructure/database.py`, so `main.py` never learns about it: `register_shutdown_hook(hook)` adds a callable (sync or `async`) that the lifespan runs last-registered-first when the app stops, and a failing hook is logged without stopping the others; `register_readiness_probe(name, probe)` adds a coroutine that returns a `DatabaseHealth`, which `/health/ready` reports under `additional_databases` and counts towards `status`. The async overlay registers both when its module is imported.",
]


def _fastapi_test_database_section(auth: str | None) -> list[str]:
    """The test-database section of the FastAPI api CLAUDE.md.

    Args:
        auth: Auth mode. Supabase has no local PostgreSQL service to point at.
    """
    real_database = (
        "your Supabase project (or a throwaway PostgreSQL)"
        if auth == "supabase"
        else "a real PostgreSQL (`docker compose up db`)"
    )
    return [
        "## Test database",
        "",
        "The suite needs no Docker and no PostgreSQL: `pytest` runs against an in-memory SQLite database that `tests/conftest.py` creates and drops.",
        "",
        "- `test_engine` (session scope) builds the schema once from the ORM metadata, on one shared connection (`StaticPool`) because the `TestClient` runs sync routes in a worker thread.",
        "- `db_session` wraps each test in an outer transaction and a SAVEPOINT, then rolls back. A `commit()` inside the code under test releases the savepoint only, so every test starts from an empty database and none leaks into the next.",
        "- `conftest.py` pins `ENVIRONMENT=test`, `DEBUG=false` and `LOG_LEVEL=warning` before it imports the app, so a developer's `.env` cannot change a result. The `client` fixture does not run the lifespan, so nothing touches a real database.",
        "- External services are stubbed, never called: `tests/fakes.py` has an in-memory item repository, unit of work and token verifier, and each auth variant stubs its identity provider.",
        "- Levels are pytest markers (`unit`, `integration`, `e2e`). `pytest.ini` enforces a coverage gate: line and branch coverage of `app/` over the whole suite must stay at or above 75% (`--cov-fail-under=75`), or the run fails. A subset cannot reach it, so run one level or one file with `--no-cov`: `pytest -m unit --no-cov`. Add tests; do not lower the threshold.",
        "- SQLite cannot prove PostgreSQL-only behaviour. `tests/integration/test_migrations.py` compares the migrated schema with the ORM models, but run `alembic upgrade head` against "
        + real_database
        + " before you deploy.",
    ]


_FASTAPI_TEST_TRACEABILITY_SECTION = [
    "## Test traceability",
    "",
    "Each test names the code it validates, and a test that covers a requirement also names the requirement, so a reviewer can walk from a requirement to its tests and on to the code:",
    "",
    "- **Code**: a docstring line, `Validates app.application.services.item_service.ItemService.create_item().`",
    '- **Requirement**: the `requirement` pytest marker, `@pytest.mark.requirement("<id>")`. It is registered in `pytest.ini`, which runs with `--strict-markers`, so a misspelled marker fails the run.',
    "",
    "The requirement IDs come from your project's own requirements source. The template ships none, because it has no requirements of its own, and you should not invent them. List the tests that carry a requirement with `pytest --collect-only -q -m requirement`, and a requirement's tests with `grep -rn 'requirement(\"<id>\")' tests`.",
]


def _fastapi_auth_section(auth: str | None) -> list[str]:
    """The authentication section of the FastAPI api CLAUDE.md for one auth mode."""
    seam = (
        "Authentication is a seam: `app/api/auth_deps.py` exports `get_current_user` and `CurrentUser`, "
        "and `app/infrastructure/auth_settings.py` holds the variant's settings. An auth overlay replaces "
        "exactly those two files (plus `tests/auth_test_env.py` and `tests/integration/test_auth.py`) and adds "
        "its verifier under `app/infrastructure/auth/`. Routes and the `require_roles` guard depend on "
        "`CurrentUser` only, and verifiers implement `TokenVerifierPort`, so nothing else changes between variants. "
        "Item reads are public; item writes require `CurrentUser`."
    )
    if auth == "token":
        return [
            "## Authentication (token)",
            "",
            seam,
            "",
            "Two modes live side by side and never accept each other's tokens.",
            "",
            "- **Static token.** Callers send `Authorization: Bearer <AUTH_TOKEN>`. It guards item writes and `GET /auth/me`. The check compares SHA-256 digests in constant time, and an empty `AUTH_TOKEN` matches nothing. Every holder is the same principal (`token-user`), so this mode suits service-to-service calls. `POST /auth/validate` is a public probe: it answers **200 with `authenticated: false`** for a wrong token, and 401 is reserved for the guarded routes. Each rejection is logged as `auth.validate_rejected` with its reason and without the token, so a burst of guesses is visible.",
            "- **JWT login.** `POST /auth/register` creates an account (201); a duplicate email or username answers a generic 409 that does not say which one matched. `POST /auth/token` (OAuth2 form, `username` is the email) returns a signed access token with `Cache-Control: no-store`; an unknown email, a wrong password and an inactive account all answer the same 401. `GET /auth/me/jwt` returns the same current-user shape as `/auth/me`; the account is re-read on every call, so a deactivated account loses access at once (401). Login input is length-bounded (422), and a password needs 8+ characters and at most 72 bytes, because bcrypt ignores the rest.",
            "- **Accounts.** Emails are stored and matched in lower case, so `Jane@Example.com` and `jane@example.com` are one account. A blank `username` means none, so a form that submits an empty optional field does not claim the empty handle. `RegistrationService` (`app/application/services/registration.py`) creates accounts and needs no token issuer; `AuthService` handles login and resolves access tokens.",
            "- **Audit.** A successful `POST /auth/register` writes the audit action `user.register` and a successful `POST /auth/token` writes `user.login`, each queued as a background task so the response is not delayed. Both name the account by its id (`resource_id` and `actor_id` are the user id) and carry no email or username; a failed login is only warn-logged by the exception handler. `AuthService.authenticate` returns an `AccessTokenDTO` that gained `user_id` for this purpose. It stays internal: `TokenResponse` does not expose it, so clients still receive only `access_token` and `token_type`.",
            "- **Signing key off.** While `JWT_SECRET_KEY` is empty, `POST /auth/token` and `GET /auth/me/jwt` answer **503** before they look at the credentials, so the status never tells whether they were right. Registration keeps working.",
            "",
            "Scaffolding generates `AUTH_TOKEN` and `JWT_SECRET_KEY` as random values in the root `.env` and leaves them empty in `.env.example`, because that file is committed. At every stage a non-empty secret must meet its minimum (`AUTH_TOKEN` 16+ characters, `JWT_SECRET_KEY` 32+) and not be a placeholder such as `changeme`, or the app refuses to start. An empty secret is accepted only outside `staging` and `production`, where it switches its mode off and never authenticates anyone. `JWT_ALGORITHM` is `HS256` by default (`HS384` and `HS512` are allowed); `ACCESS_TOKEN_EXPIRE_MINUTES` defaults to 30 (1 to 1440).",
        ]
    if auth == "supabase":
        return [
            "## Authentication (Supabase)",
            "",
            seam,
            "",
            "The bearer token is verified by asking Supabase Auth (`get_user()`) on every request, so no JWT secret is held here and revoked sessions and deleted users are rejected at the cost of one HTTP round trip. An invalid or expired token is a 401. When Supabase Auth cannot answer (a network error, a timeout, a 429, a 5xx, or a 200 whose body is not a user) the API returns **503**, so an outage reads as an outage and not as every user being logged out. `SUPABASE_AUTH_TIMEOUT` (default 5 seconds, at most 30) bounds the wait. `GET /auth/me` returns the shared current-user shape. A user created by an anonymous sign-in has the role `anonymous`, not `authenticated`, so a role guard for `authenticated` does not admit somebody who never identified themselves.",
            "",
            "The backend reads only `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`. `SUPABASE_SECRET_KEY` is no longer read: the service-role key bypasses Row Level Security, and this service never needs to. With `ENVIRONMENT=staging` or `production` the app refuses to start while either value is empty or still a placeholder, the URL is not https, or the key starts with `sb_secret_` (a secret key, not a publishable one). There is no `/auth/validate` endpoint in this variant.",
            "",
            "Supabase hosts the database: `DATABASE_URL` is the pooled connection and `DIRECT_DATABASE_URL` the direct one that migrations use. The generated `.env` sets `DATABASE_SSL_MODE=require`, carries `sslmode=require` in both URLs and sets `DATABASE_POOL_RECYCLE=300` because the pooler drops idle connections. It therefore already meets the database TLS rule of `staging` and `production` (see Settings), and needs no `DATABASE_ALLOW_INSECURE_TRANSPORT`. Supabase Auth owns the users, so the ORM has a `profiles` table that extends `auth.users` (display name, avatar, bio, and a JSON `preferences` column that is `JSONB` on PostgreSQL) and no `users` table.",
        ]
    if auth == "entra":
        return [
            "## Authentication (Microsoft Entra ID)",
            "",
            seam,
            "",
            "The token is verified in-process by `EntraTokenVerifier` (`app/infrastructure/auth/entra.py`); no call to Entra happens per request once the keys are cached, and no client secret is involved.",
            "",
            "- Only `RS256` is accepted (the token header cannot pick the algorithm). The signature is checked against the tenant's signing keys, fetched by `PyJWKClient`, which caches them. `CooldownSigningKeyResolver` (`app/infrastructure/auth/entra_jwks.py`) wraps it: a token that names an unknown `kid` forces one reload of the key set, at most once per `ENTRA_JWKS_REFRESH_COOLDOWN`, so a stranger sending random `kid` values cannot make the API call Entra on every request, and a failing endpoint is not retried inside the cooldown either. `PyJWT` stays pinned to `2.15.1`: from 2.13 on a failed reload keeps the cached keys, which keeps known users signed in during an Entra outage.",
            "- `exp`, `iat`, `iss` and `aud` are required, with a 30-second clock-skew allowance. The issuer is the v2 issuer, so set `requestedAccessTokenVersion: 2` in the API registration's manifest. The audience may be the client id, `api://<client id>` or `ENTRA_API_AUDIENCE`.",
            "- `tid` must equal `ENTRA_TENANT_ID`, and `scp` must hold the required scope. `ENTRA_TENANT_ID` and `ENTRA_API_CLIENT_ID` must be GUIDs written with hyphens and are stored in lower case, the way `tid` and `iss` are written, so a placeholder such as `your-tenant-id` fails at start-up instead of producing an issuer no token matches. `ENTRA_API_SCOPE` accepts the bare name (`access_as_user`) and the full `api://.../access_as_user` URI that MSAL requests; it is stored as the bare name and can never be empty, so `api://<client id>/` fails at start-up.",
            "- The principal's id is the `oid` claim, else `sub`; `roles` holds the `roles` claim. `email` comes from the `email` claim alone: `preferred_username` is a mutable sign-in name that need not be an address, so it becomes `username` and is never promoted to `email`. `GET /auth/me` returns `{id, email, username, roles, auth_method}`.",
            "",
            "An invalid token is a **401** with one generic message (the reason goes to the log). A valid token without the scope is a **403**. A key set that cannot be fetched (an unreachable endpoint, a reset connection, a non-JSON body, no usable key) is a **503** with `Retry-After`, not a 401. Optional settings: `ENTRA_AUTHORITY` (an https URL, for sovereign clouds; default `https://login.microsoftonline.com`), `ENTRA_JWKS_TIMEOUT` (seconds, default 5, at most 30) and `ENTRA_JWKS_REFRESH_COOLDOWN` (seconds, default 30, at most 3600). With `ENVIRONMENT=staging` or `production` the app refuses to start while the tenant id or the API client id is empty or still one of the placeholder ids of the generated `.env`.",
        ]
    return [
        "## Authentication (none)",
        "",
        seam,
        "",
        "This variant has no authentication: `get_current_user` resolves every caller to the development principal `dev-user`. In `development` and `test` the `X-User-Id` header (`[A-Za-z0-9_-]`, at most 64 characters, else 422) picks another id, so one developer can exercise ownership rules; in any other environment the header is ignored, so nobody can impersonate a user with it. Scaffold with `--auth token`, `--auth supabase` or `--auth entra`, or replace `auth_deps.py`, before you expose the API.",
    ]


def _fastapi_migrations_section(auth: str | None) -> list[str]:
    """The migration-process section of the FastAPI api CLAUDE.md."""
    lines = [
        "## Database migrations and rollback",
        "",
        "Alembic owns the schema in every variant. The application never runs `create_all`: `entrypoint.sh` runs `alembic upgrade head` before it starts uvicorn, and the migrations connect through `DIRECT_DATABASE_URL` when it is set, otherwise `DATABASE_URL`. A new database therefore stays empty until a migration creates its tables.",
        "",
        "To change the schema, edit the ORM model, then:",
        "",
        "```bash",
        'alembic revision --autogenerate --rev-id 0003_add_widget -m "add widget table"   # draft the migration',
        "alembic upgrade head                                                             # apply it",
        "```",
        "",
        '`alembic.ini` sets `file_template = %%(rev)s`, so the revision id is the file name: pass `--rev-id <NNNN>_<slug>` (sequence number and slug, at most 32 characters, the width of `alembic_version.version_num`) or the id will be random. `alembic/env.py` reads the database URL from the settings and logs through the application\'s structured logger, from `LOG_LEVEL` and `LOG_FORMAT`, not through Alembic\'s `fileConfig`. A caller that embeds the migrations, such as the test suite, sets `config.attributes["embedded"] = True` to keep its own environment and logging, and may pass an open connection as `config.attributes["connection"]`.',
        "",
        "Review the draft before you commit it. Autogenerate compares types and server defaults but cannot see everything (renames look like a drop plus a create), and it renders an empty `downgrade()` as `raise NotImplementedError`, so a missing rollback cannot ship by accident. Keep literal column lengths in the migration, not imports from `app.domain.constants`: a migration is a snapshot of the schema at its revision. The first migration creates `idx_items_created_at`, which serves the newest-first item listing.",
        "",
        "Roll back one migration at a time, **newest first**:",
        "",
        "```bash",
        "alembic downgrade -1",
        "```",
        "",
        '- A downgrade that drops a table calls `preserve_and_drop_table("<table>", indexes=(...))`, and one that drops a column calls `preserve_and_drop_column("<table>", "<column>", key_columns=("id",))` (`app/infrastructure/migration_safety.py`). Autogenerate writes the table call for you: a `process_revision_directives` hook rewrites every drafted `op.drop_table` in a downgrade; a column drop you write by hand. Both copy the rows aside first, so a rollback does not destroy data.',
        "- On PostgreSQL the copy goes to `migration_backup.<table>__rollback_<UTC YYYYmmddHHMMSSffffff>`. The schema `migration_backup` is created closed, so the Supabase Data API and the application role cannot read it (keep it out of the exposed schemas), and the migration role needs the `CREATE` privilege on the database. The microsecond suffix keeps two rollbacks inside one second apart. SQLite has no schemas, so there the copy sits next to the table under the same name. The log records `migration.preserved` with `table=` and `backup=`.",
        '- Restore after `alembic upgrade head`: `psql "$DIRECT_DATABASE_URL" -c "INSERT INTO <table> SELECT * FROM migration_backup.<table>__rollback_<timestamp>"`. The copy carries rows only, no constraints or indexes, so upgrading again does not collide with them.',
        "- Alembic ignores the backup tables (`include_object`), so autogenerate neither reports nor drops them. Drop them yourself, and `DROP SCHEMA migration_backup` once it is empty, when you no longer need them.",
        "- Try a rollback on a staging database before you rely on it in production. `tests/integration/test_migrations.py` upgrades, compares the result with the ORM models, downgrades to base and checks that the rows survive.",
        "- `alembic upgrade head --sql` prints the SQL without connecting, for review.",
    ]
    if auth == "supabase":
        lines += [
            "",
            "### Supabase",
            "",
            "The Supabase variant's second migration keeps the file name `0002_create_users_table.py` on purpose, with revision `0002_create_profiles`. Template layers overwrite by path, so this file replaces the base migration of the same name and the project gets a `profiles` table, never a stray `users` table next to it. Keep that file name if you rewrite it.",
            "",
            "The variant adds a third migration, `0003_enable_row_level_security.py`, which has no base counterpart. It enables row level security on `items`, `profiles` and `alembic_version`, and adds no policy, so the Data API roles (`anon`, `authenticated`) can read and write nothing there, even with the publishable key that the single-page app ships. The API connects as the table owner, which row level security does not apply to, so it is unaffected. A table you add needs its own `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` in its migration, and a policy only when the Data API should serve it. The migration does nothing on SQLite.",
        ]
    return lines


_FASTAPI_CONTAINER_SECTION = [
    "## Container",
    "",
    "- `entrypoint.sh` takes the host and port from `DATABASE_URL`, so it waits for the database the app will actually use (`pg_isready`), gives up after `DB_WAIT_TIMEOUT_SECONDS` (default 60) with exit status 1, and then runs `alembic upgrade head` and the server. Alembic takes no lock: run one migration job before you scale out and keep this step for a single instance.",
    "- The application code is root-owned and the process runs as the unprivileged `appuser`, so it can neither rewrite the code nor write bytecode next to it (`PYTHONDONTWRITEBYTECODE=1`).",
    "- Uvicorn starts with `--no-access-log`; the structured `http.request` line replaces it. Behind a proxy, set `FORWARDED_ALLOW_IPS` (see Settings), or the rate limiter sees only the proxy's address.",
]


def _fastapi_settings_section() -> list[str]:
    """The settings section of the FastAPI api CLAUDE.md."""
    return [
        "## Settings",
        "",
        "`Settings` (`app/infrastructure/settings.py`, pydantic-settings) reads environment variables, whose names are case-insensitive. `load_configuration()` copies the project `.env` into the environment first, and in Docker compose passes the variables. Scaffolding writes the root `.env` (with generated secrets where the variant has any) and a `.env.example` with the secrets blank, which is the file you commit. Constructing `Settings` with an empty environment works, so tools can import it without a `.env`.",
        "",
        "- Values are validated when the process starts, and a bad one stops start-up with a message that names the key: `ENVIRONMENT` is `development`, `test`, `staging` or `production`; `LOG_LEVEL` is `debug` to `critical` in any letter case; `LOG_FORMAT` is `json` or `text`; `DATABASE_SSL_MODE` is a libpq mode (`disable` to `verify-full`).",
        "- `DEBUG` defaults to `false`, and the app refuses to start with `DEBUG=true` outside `ENVIRONMENT=development`, because debug mode makes the framework return tracebacks to clients.",
        "- `API_DOCS_ENABLED` is unset by default, which serves Swagger UI (`/docs`), ReDoc (`/redoc`) and `/openapi.json` in every environment except `production`. Set it to `true` or `false` to override. The two pages load their scripts from a pinned CDN URL (`app/api/docs.py`), so they need internet access, and their relaxed content security policy applies to those paths only.",
        "- `DATABASE_URL` defaults to a URL without credentials. Pool: `DATABASE_POOL_SIZE` (5), `DATABASE_MAX_OVERFLOW` (10), `DATABASE_POOL_TIMEOUT` (30), `DATABASE_POOL_RECYCLE` (3600), `DATABASE_POOL_PRE_PING` (true), `DATABASE_CONNECT_TIMEOUT` (10). `DATABASE_ECHO` logs SQL statements, and the app refuses to start with it on outside `ENVIRONMENT=development`: SQLAlchemy writes those lines outside the structured formatter, and they carry bound parameter values.",
        "- **Database TLS.** With `ENVIRONMENT=staging` or `production` the app refuses to start unless the database connection is TLS-protected. It checks `DATABASE_URL` and, when set, `DIRECT_DATABASE_URL`, and a URL passes when its effective mode is `require`, `verify-ca` or `verify-full`. The effective mode is `DATABASE_SSL_MODE` when that is set, which wins over the URL (so `DATABASE_SSL_MODE=disable` is refused even beside `sslmode=require`), and otherwise the `sslmode` parameter of the URL; `prefer`, `allow`, `disable` and a repeated `sslmode` parameter do not pass. `development` and `test` are exempt, and so is a SQLite URL. For a database on the same host or on a private network that serves no TLS, `DATABASE_ALLOW_INSECURE_TRANSPORT=true` (default `false`) is the explicit opt-out for both URLs. The bundled compose `db` serves no TLS, so `ENVIRONMENT=production docker compose up` needs that opt-out, or a database that does serve TLS with `DATABASE_SSL_MODE`. The error names the variable and the settings that fix it, never the URL, which holds the password.",
        "- `CORS_ORIGINS` is a comma-separated list and defaults to `http://localhost:4200`; the generated `.env` lists the local frontend origins. The wildcard `*` is refused in `staging` and `production`, and credentialed cross-origin requests are never allowed.",
        "- A rejected value never appears in the start-up error (`hide_input_in_errors`), because it would print the raw environment, secrets included, to the logs.",
        "- Rate limiting is active only when `ENVIRONMENT` is `staging` or `production`: `RATE_LIMIT_REQUESTS` (100) per `RATE_LIMIT_WINDOW` seconds (60) per client, with the health routes exempt. The counters are in this process's memory, so each replica counts separately, and the limiter keys on the connection's peer address. It is therefore correct only behind a proxy that you list in `FORWARDED_ALLOW_IPS` (uvicorn reads it and rewrites the client address from `X-Forwarded-For`); otherwise every caller shares the proxy's bucket. For a scaled-out deployment, rate-limit at a gateway or back the counters with an external shared store.",
    ]


def _fastapi_async_note(async_db: bool) -> str:
    """The paragraph that describes the opt-in async database path, empty when it is off."""
    if not async_db:
        return ""
    return (
        "\n- An opt-in async DB path (async engine + `AsyncSession` over asyncpg) is included, gated "
        "behind the `--async-db` generator flag: `infrastructure/database_async.py` (engine, "
        "`get_async_db` dependency and its own circuit breaker), "
        "`infrastructure/repositories/item_async.py` (`SqlAlchemyAsyncItemRepository`), "
        "`infrastructure/unit_of_work_async.py` and the `AsyncItemRepositoryPort` / "
        "`AsyncUnitOfWorkPort` ports. The sync path above stays the default and no route uses the "
        "async one: to use it, write `async def` routes on a service built over the async ports and "
        "depend on `get_async_db`. Importing `database_async` registers its engine disposal as a "
        "shutdown hook, which the lifespan in `app/main.py` runs through `run_shutdown_hooks`, and its "
        "health probe as a readiness probe, which `/health/ready` reports under `additional_databases`; "
        "`main.py` needs no edit. Keep other blocking file or socket work out of the request code that "
        "runs inside that dependency, or its failures are reported as a database outage."
    )


def _fastapi_api_claude(auth: str | None, async_db: bool) -> str:
    lines = [
        "# CLAUDE.md",
        "",
        "This file provides guidance to Claude Code when working with this FastAPI API.",
        "",
        "## Build & Run Commands",
        "",
        "```bash",
        'pip install ".[dev]"                     # Dependencies come from pyproject.toml',
        "uvicorn app.main:app --reload            # Run dev server (:8000)",
        "pytest                                   # Run tests (fails below 75% branch coverage of app/)",
        "pytest -m unit --no-cov                  # One level or one file: add --no-cov, the gate needs the whole suite",
        "alembic upgrade head                     # Apply migrations",
        "alembic downgrade -1                     # Roll the newest migration back (rows are kept)",
        'alembic revision --autogenerate --rev-id 0003_add_widget -m "add widget"',
        "```",
        "",
        "## Dependencies and version",
        "",
        '`pyproject.toml` is the only place that declares them: `[project] dependencies` for the application, the `dev` extra for the test tooling, `[project] version` for the application version. There is no `requirements.txt`, and no module repeats the version: `Settings.version` reads it from the installed project\'s metadata, so run `pip install ".[dev]"` again after changing `pyproject.toml`.',
        "",
        "## Architecture: clean / hexagonal — four layers",
        "",
        "```",
        *_FASTAPI_TREE,
        "```",
        "",
        "Dependency direction: `api → application → domain`, `infrastructure → domain`.",
        "`tests/unit/test_architecture.py` parses every module with `ast` and enforces it with an allowlist, so a package nobody thought to name cannot slip in:",
        "",
        "- `app/domain` imports the standard library and `app.domain` only; `app/application` adds `app.application`.",
        "- Neither inner layer calls `importlib.import_module` or `__import__`, because a dynamic import hides a dependency from the scan.",
        "- `app/infrastructure` never imports `app.api` or `app.main`.",
        "- `app/api` imports no repository, ORM model or `get_db`, except in the composition roots `api/deps.py` and `api/auth_deps.py`.",
        "",
        '## "Start from the Port" Workflow',
        "",
        "1. Define the entity in `app/domain/entities/` (a frozen dataclass; its invariants raise `DomainValidationError`) and its port in `app/domain/ports/` (a `runtime_checkable` Protocol). Repositories only flush; they never commit.",
        "2. Write the command, the DTO and the application service against the port and `UnitOfWorkPort`. The service commits after a successful write, and a missing row raises `EntityNotFoundError`.",
        "3. Implement the adapter in `app/infrastructure/repositories/`, with its ORM record in `orm/` and an Alembic migration.",
        "4. Wire abstract → concrete in `api/deps.py` **only**: `get_<name>_service(session = Depends(get_db))` builds the service from the adapter.",
        "5. Add the route under `app/api/v1/endpoints/` and register it in `app/api/v1/router.py`. Routes stay thin (schema → command → service → DTO → schema), declare `responses=error_responses(...)`, and take `CurrentUser` on every write.",
        "6. Test the entity and the service with the fakes in `tests/fakes.py`, test the router through the `client` fixtures, and inject a fake through `app.dependency_overrides` where a route needs one.",
        "",
        "## Key Patterns",
        "",
        "**Sync vs async**: DB-backed endpoints are sync `def` handlers. Pick the keyword from the I/O, not by convention.",
        "",
        "- Sync `def` path operations are offloaded to an `anyio` threadpool, so a blocking sync SQLAlchemy `Session` runs in a worker thread and never blocks the event loop. This is the **default and correct** path for DB routes — see `app/api/v1/endpoints/items.py`.",
        "- `async def` runs directly on the event loop; reserve it for real async I/O, such as an `await` on an HTTP client or an async driver. Never mix a sync `Session` into an `async def` handler."
        + _fastapi_async_note(async_db),
        "",
        "**Composition root**: `app/api/deps.py` is the only API module that names concrete adapters. Routes ask for `ItemServiceDep`, so they stay thin and tests swap any adapter with `app.dependency_overrides`.",
        "",
    ]
    lines += _FASTAPI_ROUTES_SECTION + [""]
    lines += _fastapi_auth_section(auth) + [""]
    lines += _FASTAPI_ERRORS_SECTION + [""]
    lines += _FASTAPI_REQUEST_LOGGING_SECTION + [""]
    lines += _FASTAPI_RESILIENCE_SECTION + [""]
    lines += _fastapi_migrations_section(auth) + [""]
    lines += _fastapi_settings_section() + [""]
    lines += _FASTAPI_CONTAINER_SECTION + [""]
    lines += _fastapi_test_database_section(auth) + [""]
    lines += _FASTAPI_TEST_TRACEABILITY_SECTION + [""]
    return "\n".join(lines)


_NESTJS_AUTH_SECTIONS = {
    "token": [
        "## Authentication (token)",
        "",
        "Callers send `Authorization: Bearer <AUTH_TOKEN>`. `AUTH_TOKEN` must be at least 32 characters and a valid bearer credential (RFC 6750 `token68`: letters, digits and `- . _ ~ + /`, with optional `=` padding, no blank inside), or the app refuses to start; a value the header could not carry unchanged would otherwise refuse every request while looking valid at start-up. Scaffolding writes a random value into the root `.env` and leaves `.env.example` empty, because that file is committed. The check compares SHA-256 digests in constant time.",
        "",
        "Every holder of the secret is the same identity (`token-client`, role `service`), so this mode is for service-to-service calls, not for end users. `GET /auth/me` returns the caller's identity.",
        "",
        '`POST /auth/validate` is a public validity probe, limited to 5 requests per minute: a wrong token gets **HTTP 200 with `authenticated: false`**, because both outcomes are successful answers to "is this token valid?". 401 is reserved for guarded routes.',
    ],
    "supabase": [
        "## Authentication (Supabase)",
        "",
        "The bearer token is verified by `supabase.auth.getUser()` on each request, so no JWT secret is held here. Only a 4xx answer other than 429, or a signed-out session, is a verdict on the token: that is a 401 whose text never says why. Anything else (a network error, a timeout, a 429, a 5xx, an unparseable or empty answer) is a **503**, so a Supabase outage or a rate limit reads as an outage and not as every user being logged out. Each check waits at most 5 seconds (`SUPABASE_AUTH_TIMEOUT_MS`), and an expired wait counts as an outage.",
        "",
        "`GET /auth/me` returns `{ id, email, roles }`. A user created by an anonymous sign-in has the role `anonymous`, not `authenticated`, so a guard for `authenticated` does not admit somebody who never identified themselves. `email` is `null` for phone and anonymous users and for an address that does not conform to the HTML5 email grammar.",
        "",
        "The backend reads only `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`. With `NODE_ENV=production` the URL must use https, because every check sends the caller's token and the key there; plain http is accepted elsewhere for the local Supabase CLI. The service-role (secret) key is not used: it bypasses Row Level Security.",
    ],
    "entra": [
        "## Authentication (Microsoft Entra ID)",
        "",
        "The token is verified in-process: RS256 signature against the tenant's JWKS, v2 issuer, audience (`ENTRA_API_CLIENT_ID` or `ENTRA_API_AUDIENCE`), the `tid` and `oid` claims, and the required `exp` and `iat` claims, with a 30-second clock tolerance. A token without `exp` would never expire, which is why it is required. No client secret is involved.",
        "",
        "The JWKS client caches keys for 24 hours, waits at most 5 seconds for a fetch and rate-limits refetches, so a flood of unknown key ids cannot become a flood of requests to Microsoft; once the limit is hit the verifier answers 503.",
        "",
        "`ENTRA_TENANT_ID` and `ENTRA_API_CLIENT_ID` must be GUIDs and are lowercased, the way `iss` and `tid` are written; a placeholder such as `your-tenant-id` fails at start-up. `ENTRA_API_SCOPE` is compared by its bare name against the `scp` claim, so both `access_as_user` and the full `api://.../access_as_user` form work, and a value that reduces to nothing (`api://<client id>/`) fails at start-up instead of rejecting every token with 403. An invalid token is a 401, a missing scope is a 403, and a key set that cannot be fetched is a 503. `GET /auth/me` returns `{ id, email, roles }`; `email` is the `preferred_username` claim when it conforms to the HTML5 email grammar and `null` otherwise.",
    ],
}

_NESTJS_CONFIG_INTRO = [
    "## Configuration",
    "",
    "`src/config/env.base.ts` declares every key all variants share (database URLs, `PORT`, `NODE_ENV`, `CORS_ORIGINS`, `LOG_LEVEL`, `TRUST_PROXY_HOPS`, `API_DOCS_ENABLED`, the `DB_*` timeouts, pool size and breaker thresholds, the `HEALTH_HEAP_*_MB` limits) and `createEnvValidator()`. Each variant's `src/config/env.validation.ts` extends `baseEnvSchema` with its own keys and exports `validate`, which `AppModule` hands to `ConfigModule.forRoot`.",
    "",
    "- A bad or missing value stops start-up with `Invalid environment variables: KEY: reason`. The message names the key, never its value.",
    "- Read configuration through `ConfigService<BaseEnv, true>` with `get(key, { infer: true })`. Nothing else reads `process.env`, apart from `prisma.config.ts` and `test/support/test-env.ts`.",
    "- The project `.env` sits at the repository root; `envFilePath` is `['../.env', '.env']`. In Docker no file is read, compose passes the variables.",
]

_NESTJS_CONFIG_DETAILS = [
    "- `TRUST_PROXY_HOPS` (0 to 10, default 1) is the number of reverse proxies between the client and the API. The client address the rate limiter keys on is read that many entries from the right of `X-Forwarded-For`: 1 suits the bundled nginx, 0 an API exposed directly (otherwise a client can spoof the header and dodge the limit).",
    "- `API_DOCS_ENABLED` publishes Swagger UI at `/docs`; unset means on everywhere except `NODE_ENV=production`.",
    "- `DB_POOL_MAX` (default 10) is the only connection pool size: the `pg` driver adapter ignores Prisma's `connection_limit` URL parameter. `DB_CONNECT_TIMEOUT_MS` and `DB_QUERY_TIMEOUT_MS` bound how long a request waits on the database.",
    "- **Database TLS.** With `NODE_ENV=production` the schema refuses a `DATABASE_URL` unless every `sslmode` parameter in it is `require`, `verify-ca` or `verify-full`, spelled exactly in lower case: `REQUIRE`, a URL without `sslmode`, and `sslmode=require&sslmode=disable` are all refused. `DB_ALLOW_INSECURE_TRANSPORT=true` (a boolean, default `false`) is the explicit opt-out for a database on the same host or on a private network that serves no TLS. The error message is fixed and names neither the URL nor the host, which would leak the password. Other `NODE_ENV` values are exempt, so the compose stack, whose generated `.env` sets `NODE_ENV=development`, is unaffected, while the production image needs the `sslmode` or the opt-out. The Supabase pooler URL of the generated `.env` carries `sslmode=require` and passes. `DIRECT_URL` is not checked: only migrations use it.",
    "- **Log level reload.** `SIGHUP` reloads `LOG_LEVEL` without a restart (`src/config/log-level-reload.ts`, installed by `main.ts` once the server listens and removed when it closes): edit the file or export a new value, then `kill -HUP <pid>` (`docker kill --signal=HUP <container>` in Docker). The handler reads `../.env` and then `.env` with dotenv's parser, without touching `process.env`, and the first file that sets the key wins. A value you exported that differs from what the file held at start-up wins; otherwise the edited file wins, because `ConfigModule` copied the file value into `process.env` at start-up and that copy must not shadow your edit. A key set nowhere means the default level. A value that is not a level is ignored, with one warning that names only the accepted set, never the value. Both pino root loggers move together, requests already in flight keep the level they started with, and the audit logger is not touched. Nothing is installed on Windows. Two caveats: a terminal hang-up also sends `SIGHUP`, so a server started from a terminal that closes keeps running instead of exiting; and without a `.env` file, as in Docker where compose passes the variables, the environment cannot change, so a reload re-applies the start-up value.",
    "- The generated `.env` sets `NODE_ENV=development`, which matches the compose `dev` target: it installs devDependencies and runs `npm run start:dev`, and `pino-pretty`, the development log transport, is a devDependency. The production image sets `NODE_ENV=production` itself and `.dockerignore` keeps `.env` out of it, so never hand that image the generated file.",
    "- `entrypoint.sh` reads the database host and port from `DATABASE_URL`, waits for it at most `DB_WAIT_TIMEOUT_SECONDS` (default 60) and exits with status 1 when it never answers, then runs `prisma migrate deploy`. The production image copies `prisma.config.ts` for that command, which takes its datasource URL from it.",
]


def _nestjs_config_section(auth: str | None) -> list[str]:
    """The configuration section of the NestJS api CLAUDE.md.

    Args:
        auth: Auth mode. Only the token variant has a generated secret to describe.
    """
    secret_note = (
        [
            "- Scaffolding writes a random `AUTH_TOKEN` into `.env`. `.env.example` leaves it empty so no working credential is ever committed."
        ]
        if auth == "token"
        else []
    )
    return _NESTJS_CONFIG_INTRO + secret_note + _NESTJS_CONFIG_DETAILS


_NESTJS_PLATFORM_SECTION = [
    "## Request handling and errors",
    "",
    "- **Body limit.** `configureApp` registers the JSON body parser with a 512 KiB limit (`src/config/http-limits.ts`), above Express's 100 kB default so routes can take larger documents, yet small enough that a client cannot make the process buffer megabytes per request. A larger body answers **413** with the standard reason phrase and the CORS headers, so a browser can read it. Raise the limit together with the bounds the routes validate, never alone.",
    "- **Body-parser errors.** A body that is not valid JSON answers 400 `Malformed JSON request body`, because the parser's own text quotes the input. Any other 4xx raised by Express middleware about the request itself keeps its status under the standard reason phrase, never the library text.",
    "- **Health probes.** `HealthCheckExceptionFilter`, applied to the health controller only, answers an unhealthy probe with the Terminus result itself (each indicator, its details and the circuit state) at 503, so an operator sees which dependency is down. It writes the one `warn` line a failed probe produces; Terminus' own logging is off.",
    "- **Prisma errors.** `P2002` answers 409, `P2003` 400 and `P2025` 404, each with a fixed message that names no column. An error that means the database cannot take the work (unreachable, timed out, no connection slot: `P2024` and `P2037`, and a raw-query failure `P2010` whose driver error kind is a connection problem) answers 503 like an open circuit and does not count as a query mistake. Any other code is a 500 with a fixed message, logged with its stack.",
    "- **Logging.** The pino request serializer keeps the request `id`, `method` and `path` without the query string; headers, route parameters and the client address are not logged. A 5xx response is a `warn` access line, because the exception filter has already logged the cause once at `error`. `x-request-id` is kept when it matches a safe pattern, otherwise a UUID is generated.",
    "- **Rate limits.** 100 requests per minute and client on every route and 5 on `POST /auth/validate`; the 429 message is `Too many requests`. The counters are in this process's memory, so each replica counts on its own.",
    "- **Database TLS.** `deriveSslOption` decides TLS from `sslmode` and the host (loopback and single-label hosts such as the compose `db` stay plaintext), and `stripSslParameters` removes `sslmode`, `sslrootcert`, `sslcert`, `sslkey` and `uselibpqcompat` from the URL that reaches the pool, because `node-postgres` would otherwise build its own `ssl` object from them and discard that decision. A private CA goes through `NODE_EXTRA_CA_CERTS`. Whether production may connect without TLS at all is a separate, earlier check (see Configuration).",
    "- **Responses.** Every handler declares its response with `@ZodResponse`, including the demo routes under `/test` (status 200), so the OpenAPI document and the serializer agree.",
]

_NESTJS_ROLE_SOURCES = {
    None: "This variant wires no authentication, so `request.user` is never set and every `@Roles` route is denied: the guard fails closed instead of leaving the route open. Scaffold with an auth variant, or wire your own guard through `src/app.auth.ts`, before you use `@Roles`.",
    "token": "Every holder of `AUTH_TOKEN` has the single role `service`, so `@Roles('service')` is the only role a token caller can satisfy.",
    "supabase": "The caller's role is the one Supabase reports for the user (normally `authenticated`), or `anonymous` for an anonymous sign-in. A route that needs a signed-in person lists `authenticated`.",
    "entra": "The roles are the `roles` claim of the access token (the app roles assigned in Entra). A token without that claim has no role, so it never passes a `@Roles` route.",
}


def _nestjs_roles_section(auth: str | None) -> list[str]:
    """The role-based access control section of the NestJS api CLAUDE.md.

    Args:
        auth: Auth mode; decides where the caller's roles come from.
    """
    lines = [
        "## Roles (RBAC)",
        "",
        "`@Roles(...roles)` (`src/common/auth/roles.decorator.ts`) restricts a route, or a whole controller, to callers that hold at least one of the listed roles, and the global `RolesGuard` (`roles.guard.ts`) enforces it. `AppModule` registers it last, `[ThrottlerGuard, ...AUTH_GUARDS, RolesGuard]`, so it checks an identity that the access-token guard has already verified.",
        "",
        "- A route without `@Roles` passes this guard: it is open to every caller the other guards admit.",
        "- With `@Roles` the caller needs at least one of the roles. Names are compared exactly, case included, against `AuthenticatedUser.roles`.",
        "- A request with no identity, an empty `@Roles()` and a role mismatch all answer **403** with the same generic message, `Insufficient permissions`. It never lists the required roles, so a response does not map the permission model.",
        "- A `@Roles` on the handler replaces one on the controller; the two are not merged.",
        "- A denial writes one `warn` line (`Request rejected by roles guard`) with the status and the caller's opaque `actorId` when there is one, never the roles or an email.",
        "- No sample route uses it. Add it where a route needs it: `@Get('payroll') @Roles('finance', 'admin') payroll() { ... }`.",
        "",
    ]
    lines.append(_NESTJS_ROLE_SOURCES[auth])
    return lines


_NESTJS_AUDIT_SECTION = [
    "## Audit trail",
    "",
    "`AuditLogger` (`src/common/audit/audit-logger.ts`, provided by `AuditModule`) writes the trail: one structured line per state-changing action on data that may be privacy relevant, to answer who did what to which record. `record(action, resourceId, actorId)` writes one line with `event: 'audit.action'`, `action`, `resourceId` and `actorId`, plus the request id of the request it ran in.",
    "",
    "- The line goes through a pino child logger whose level is pinned to `info`, so `LOG_LEVEL=warn`, `error` or `silent`, and a level change by `SIGHUP`, cannot silence it. Route it to a retained store in the log collector by filtering on `event`.",
    "- `ItemsService.create`, `update` and `remove` record `item.create`, `item.update` and `item.delete` after the repository call succeeded, so a failed write or a 404 records nothing. Their signatures take the actor: `create(item, actorId)`, `update(id, changes, actorId)` and `remove(id, actorId)`.",
    "- The actor is the caller's opaque id, or the constant `anonymous` when no authentication is wired (`auditActorIdOf(user)`, which the controller passes). Never an email, a username or a token: nobody can trace the log back to a person by reading it.",
    "- To audit another service: import `AuditModule`, inject `AuditLogger`, and call `record` after the change succeeded with a stable dotted action name.",
]

_NESTJS_LINT_SECTION = [
    "## Lint, format and coverage",
    "",
    "- `npm run lint` runs ESLint (`eslint.config.mjs`: typescript-eslint `recommendedTypeChecked` plus `eslint-config-prettier`) with `--max-warnings 0`.",
    "- `npm run format` writes and `npm run format:check` verifies Prettier formatting (`.prettierrc`: single quotes, trailing commas).",
    "- `npm run test:cov` fails below 75% lines or statements (`coverageThreshold` in `package.json`). Add tests; do not lower the threshold.",
    "- `typescript-eslint` only supports the TypeScript versions its peer range lists, so bump the two together.",
]

_NESTJS_TEST_TRACEABILITY_SECTION = [
    "## Test traceability",
    "",
    "Each test names the requirement it verifies and the code it validates, so a reviewer can walk from a requirement to its tests and on to the code, and back:",
    "",
    "- **Requirement**: a title prefix, `it('[REQ-ITEMS-012] when the item does not exist, then the API answers 404', ...)` or `describe('[REQ-AUTH-003] ...')`. Where a prefix does not fit, put a TSDoc line `Validates REQ-ITEMS-012.` above the spec.",
    "- **Code**: a TSDoc line above the spec, `Validates ItemsService.remove().`",
    "",
    "The requirement format is `[REQ-<AREA>-<NNN>]`: the feature area (`AUTH`, `ITEMS`) and a three-digit number. The IDs come from your project's own requirements source. The template ships none, because it has no requirements of its own, and you should not invent them. Find a requirement's tests with `grep -rn \"REQ-ITEMS-012\" src test`.",
]


def _nestjs_migrations_section(auth: str | None) -> list[str]:
    lines = [
        "## Database migrations and rollback",
        "",
        "Every directory under `prisma/migrations/` holds two scripts: `migration.sql`, which Prisma applies, and `down.sql`, its rollback. Prisma does not generate `down.sql`: after `npx prisma migrate dev --name <name>`, write one next to the migration.",
        "",
        "Roll back one migration at a time, **newest first**:",
        "",
        "```bash",
        "npx prisma db execute --file prisma/migrations/<dir>/down.sql",
        "```",
        "",
        '- `down.sql` copies the table into `migration_backup."<table>__rollback_<UTC YYYYMMDDHHMMSSuuuuuu>"` before dropping it, so a rollback does not destroy data. Restore with `INSERT INTO "<table>" SELECT * FROM migration_backup."<table>__rollback_<timestamp>"`. The suffix has microsecond resolution (from `clock_timestamp()`), so back-to-back rollbacks never collide.',
        "- The backup goes to the schema `migration_backup`, never to `public`: the Supabase Data API serves `public` with a publishable key that ships in the browser, so a backup table there would expose its rows. The script creates the schema and revokes it from `PUBLIC`; the copy carries rows only, no constraints or indexes.",
        "- `down.sql` also deletes the migration's own row from `_prisma_migrations` as its last statement, so `npx prisma migrate deploy` applies the migration again. Do not use `prisma migrate resolve --rolled-back`: Prisma rejects it for a migration that finished successfully (P3012).",
        "- Prisma inspects only the schema named in the datasource, so `prisma migrate diff` ignores the backups. Drop them once the restore is verified.",
        "- Try a rollback on a staging database before you rely on it in production.",
    ]
    if auth == "supabase":
        lines += [
            "",
            "### Row Level Security (Supabase)",
            "",
            "The migration `..._enable_row_level_security` enables RLS on `profiles`, `items` and Prisma's own `_prisma_migrations` table, which sits in `public` and lists every migration name, with no policies. The API connects as the table owner, which bypasses RLS, while the Supabase Data API with the publishable key is denied. Any table you add needs its own `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` in its migration, and a `down.sql` that undoes it.",
            "",
            "The Supabase init migration replaces the base one by path: its `down.sql` drops `profiles`, not `users`.",
        ]
    return lines


def _nestjs_api_claude(auth: str | None, async_db: bool) -> str:
    lines = [
        "# CLAUDE.md",
        "",
        "This file provides guidance to Claude Code when working with this NestJS API.",
        "",
        "## Build & Run Commands",
        "",
        "```bash",
        "npm install",
        "npm run start:dev             # Run development server (:8000)",
        "npm run build                 # Build for production",
        "npm test                      # Run unit tests",
        "npm run test:cov              # Unit tests + 75% coverage gate",
        "npm run test:e2e              # e2e tests (in-memory fakes, no Postgres)",
        "npm run lint                  # ESLint, fails on warnings",
        "npm run format:check          # Prettier check (npm run format to fix)",
        "npx prisma migrate dev        # Create and apply migration (dev)",
        "npx prisma migrate deploy     # Apply migrations (production)",
        "npx prisma db execute --file prisma/migrations/<dir>/down.sql  # Roll one migration back",
        "npx prisma generate           # Regenerate Prisma client",
        "```",
        "",
        "## Architecture Overview",
        "",
        "This is a NestJS application with a modular architecture on Prisma and PostgreSQL.",
        "",
        "### Core Structure",
        "",
        "```",
        *_nestjs_src_tree(auth),
        "",
        "prisma/schema.prisma       # Database models",
        "prisma/migrations/         # One directory per migration: migration.sql + down.sql",
        "test/                      # e2e specs; support/ holds the harness and the in-memory fakes",
        "```",
        "",
        "### Key Patterns",
        "",
        "**Database Access**: `PrismaService` is injected via DI. `PrismaModule` is not global: a module that needs the database imports it, and it exports `PrismaService`, `DATABASE_CIRCUIT_BREAKER` and `DATABASE_HEALTH_PORT`.",
        "",
        "**Ports and adapters**: services depend on a port token (`ITEM_REPOSITORY`, `DATABASE_HEALTH_PORT`, `ACCESS_TOKEN_VERIFIER`) and a module binds the adapter with `{ provide, useClass }`. Specs bind fakes instead.",
        "",
        "**Models**: Defined in `prisma/schema.prisma`. Regenerate client with `npx prisma generate`.",
        "",
        "**API Routes**: the `api/v1` prefix is applied once, by `configureApp` in `src/app.setup.ts`; controllers do not repeat it. Sample resource: `/api/v1/items` (GET, POST, GET/PUT/DELETE `:id`), backed by Postgres. Smoke routes: `GET /api/v1/test/ping`, `/api/v1/test/echo/:message`, `POST /api/v1/test/echo`.",
        "",
        "**DTO Naming**: `Create<Entity>Dto`, `Update<Entity>Dto`, `<Entity>ResponseDto` pattern (Zod-based via nestjs-zod). Handlers declare the response schema with `@ZodResponse`.",
        "",
    ]
    lines += _nestjs_config_section(auth) + [""]
    lines += _NESTJS_PLATFORM_SECTION + [""]
    if auth in _NESTJS_AUTH_SECTIONS:
        lines += _NESTJS_AUTH_SECTIONS[auth] + [""]
    lines += _nestjs_roles_section(auth) + [""]
    lines += _NESTJS_AUDIT_SECTION + [""]
    lines += _nestjs_migrations_section(auth) + [""]
    lines += _NESTJS_LINT_SECTION + [""]
    lines += _NESTJS_TEST_TRACEABILITY_SECTION + [""]
    lines.append(_NESTJS_READINESS_CHECKLIST)
    return "\n".join(lines)


def generate_api_claude(
    framework: str, auth: str | None, *, async_db: bool = False
) -> str:
    """Build api/.claude/CLAUDE.md for the framework + auth combination."""
    if framework == "fastapi":
        return _fastapi_api_claude(auth, async_db)
    return _nestjs_api_claude(auth, async_db)


# ── frontend/README.md + frontend/.claude/CLAUDE.md ────────────────────────────


def generate_frontend_readme() -> str:
    """Build frontend/README.md (Angular quick-start; framework-agnostic)."""
    return "\n".join(
        [
            "# Frontend",
            "",
            "Angular single-page application (standalone components, signals, Angular Material 3).",
            "",
            "## Installing dependencies",
            "",
            "Install packages with the `--legacy-peer-deps` flag:",
            "",
            "```bash",
            "npm install --legacy-peer-deps",
            "```",
            "",
            _LEGACY_PEER_DEPS_NOTE,
            "",
            "## Development server",
            "",
            "```bash",
            "ng serve                    # http://localhost:4200",
            "```",
            "",
            "## Building",
            "",
            "```bash",
            "ng build                    # Production build into dist/",
            "```",
            "",
            "## Running unit tests",
            "",
            "```bash",
            "ng test",
            "```",
            "",
            "## Additional Resources",
            "",
            "For the Angular CLI command reference, visit "
            "[angular.dev/tools/cli](https://angular.dev/tools/cli).",
            "",
        ]
    )


def generate_frontend_claude() -> str:
    """Build frontend/.claude/CLAUDE.md (Angular best-practices; framework-agnostic)."""
    return "\n".join(
        [
            "You are an expert in TypeScript, Angular, and scalable web application development. "
            "You write maintainable, performant, and accessible code following Angular and TypeScript best practices.",
            "",
            "## TypeScript Best Practices",
            "",
            "- Use strict type checking",
            "- Prefer type inference when the type is obvious",
            "- Avoid the `any` type; use `unknown` when type is uncertain",
            "",
            "## Angular Best Practices",
            "",
            "- Always use standalone components over NgModules",
            "- Must NOT set `standalone: true` inside Angular decorators. It's the default.",
            "- Use signals for state management",
            "- Implement lazy loading for feature routes",
            "- Do NOT use `@HostBinding`/`@HostListener`; put host bindings in the `host` object of the decorator",
            "- Use `NgOptimizedImage` for all static images (not for inline base64)",
            "",
            "## Components",
            "",
            "- Keep components small and focused on a single responsibility",
            "- Use `input()` and `output()` functions instead of decorators",
            "- Use `computed()` for derived state",
            "- Set `changeDetection: ChangeDetectionStrategy.OnPush` in the `@Component` decorator",
            "- Prefer Reactive forms over Template-driven ones",
            "- Do NOT use `ngClass`/`ngStyle`; use `class`/`style` bindings instead",
            "- Split every component into `<name>.ts`, `<name>.html` and `<name>.css`, wired with `templateUrl` and `styleUrl`; no inline `template` or `styles`. Directives and services without a template stay `.ts` only",
            "",
            "## State Management",
            "",
            "- Use signals for local component state and `computed()` for derived state",
            "- Do NOT use `mutate` on signals; use `update` or `set`",
            "- `effect()` is for side effects only; never copy signal→signal in an effect — use `computed()`",
            "",
            "## Templates",
            "",
            "- Use native control flow (`@if`, `@for`, `@switch`) instead of `*ngIf`, `*ngFor`, `*ngSwitch`",
            "- Use the async pipe to handle observables",
            "",
            "## Services",
            "",
            "- Design services around a single responsibility",
            "- Use `providedIn: 'root'` for singleton services",
            "- Use the `inject()` function instead of constructor injection",
            "",
            "## Styling with Angular Material 3",
            "",
            "- The UI is built with Angular Material 3 (Angular Material + CDK 21.2). Use the matching Material component first; build only the gaps (such as the navigation bar and rail) on `--mat-sys-*` tokens",
            "- There is no utility-class CSS framework and there are no global utility classes: style with Material components plus each component's own CSS. A component at a screen edge pads itself by `env(safe-area-inset-*)`, which works because `src/index.html` sets `viewport-fit=cover`",
            "- `src/styles.scss` owns the theme: `mat.theme()` on `html` emits every color, typography, shape and elevation value as a `--mat-sys-*` token (density 0). Don't add a second theme or per-component palettes",
            "- Component CSS uses tokens only: colors from `--mat-sys-*` roles (content on a container uses its `on-` role; `--mat-sys-outline` is for borders, never text), type as `font: var(--mat-sys-<role>)` plus `letter-spacing: var(--mat-sys-<role>-tracking)`, shape from `--mat-sys-corner-*`, elevation from `--mat-sys-level0` to `--mat-sys-level5`",
            "- No hex, `rgb()` or `hsl()` color literals, no `!important` and no `::ng-deep` in component CSS",
            "- Success, warning and info have no M3 role: use `--app-success`, `--app-on-success`, `--app-success-container` and `--app-on-success-container` (and the same for `warning` and `info`), defined once in `src/styles.scss`. `success` shares the green palette with the tertiary accent, so `--app-success*` and `--mat-sys-tertiary*` resolve to the same colors: always pair a status color with an icon or text",
            "- Tune a Material component by setting its token custom properties (for example `--mat-button-filled-container-color`) in the component's CSS, not by overriding its internal classes",
            "- Custom interactive elements show state layers with `--mat-sys-hover-state-layer-opacity`, `--mat-sys-focus-state-layer-opacity` and `--mat-sys-pressed-state-layer-opacity`, and a keyboard focus ring outside the element with a gap",
            "- Spacing sits on the 4/8px grid",
            "",
            "## Light and dark",
            "",
            "- `ThemeService` (`src/app/services/theme.ts`) stores the chosen mode (system, light or dark, picked from the rail's Change theme menu, the compact actions sheet or the Settings page) and puts exactly one of `.light` / `.dark` on `<html>`",
            "- `.light` and `.dark` only set `color-scheme`, which picks the light or dark value of every `--mat-sys-*` token. There is no dark stylesheet or dark variant to maintain",
            "- A stored Light or Dark choice paints from the first frame: a script in `src/index.html` reads the same `app-theme` key and sets an inline `color-scheme` on `<html>` before Angular boots (the inlined critical CSS has no `.light` / `.dark` rule), and `ThemeService` removes that inline `color-scheme` when it applies the class",
            '- A region that forces a scheme (`class="dark"` on a subtree) must paint its own `background` and `color` from `--mat-sys-*` tokens',
            "",
            "## Overlay panels",
            "",
            "- Dialogs, snackbars, menus and tooltips render in the body-level `.cdk-overlay-container`, which component CSS can't reach",
            "- Style a panel from the owning component's global partial in `src/styles/overlays/` (`@use`d by `src/styles.scss`), selected by the `panelClass` the component passes to `MatDialog`, `MatBottomSheet` or `MatSnackBar`. On `mat-menu`, use a static `class`: its `panelClass` input is an alias of `class`",
            "",
            "## Window size classes and navigation",
            "",
            "- Layout follows the M3 window size classes: compact below 600px, medium 600–839px, expanded 840–1199px, large 1200–1599px, extra-large from 1600px",
            "- In TypeScript, read `WindowSizeClassService` (`src/app/services/window-size-class.ts`): `current()`, `isCompact()` and `atLeast(sizeClass)`",
            "- In CSS, repeat the same literals: `(max-width: 599.98px)`, `(min-width: 600px)`, `(min-width: 840px)`, `(min-width: 1200px)`, `(min-width: 1600px)`. Prefer CSS when only styles change; use the service when the component tree differs",
            "- Never use the CDK `Breakpoints` presets (600/960/1280/1920) or a 768px breakpoint",
            "- The shell (`src/app/shared/layout/`) follows the M3 navigation pattern strictly. Below 600px: a top app bar plus a navigation bar (`app-bottom-tab-bar`, 64px + `env(safe-area-inset-bottom)` tall); a button in the top app bar opens the theme and account actions, never destinations. From 600px: a collapsed navigation rail docked in `mat-sidenav`; from 840px a toggle expands it; from 1600px it starts expanded, unless the user has toggled the rail: that choice is stored in localStorage (`app-rail-expanded`, `RAIL_EXPANDED_STORAGE_KEY` in `layout.ts`) and wins at every width from 840px, across reloads. There is no navigation drawer, and the bar and the rail never show the same destinations at one width",
            "- Destinations live in `NAV_ITEMS` (`src/app/shared/nav-item.ts`); the bar and the rail both render that list",
            "",
            "## Icons",
            "",
            "- Icons come from `@lucide/angular`, registered by PascalCase name in `src/app/icons.ts` (`ICON_PROVIDER`, built with `provideLucideIcons`) and rendered with `<svg lucideIcon=\"Name\">` or `[lucideIcon]` (import `LucideDynamicIcon`). Type an icon field as `IconName` so a typo fails the build. Register an icon there before using it: an unregistered name throws `Unable to resolve icon '<name>'` the first time the icon renders",
            '- Icons default to 24px with stroke width 2. Inside a text, filled, outlined or tonal Material button, add `matButtonIcon` (plus `iconPositionEnd` when the icon trails) and `[size]="18"`. `matIconButton` sizes its svg to 24px itself',
            "- Material's button icon margins target `.mat-icon` only, so give the icon's `svg` `flex-shrink: 0` and `margin-inline: -8px 8px` when it leads (`8px -8px` when it trails; -4px instead of -8px on text buttons)",
            '- The `svg` writes its whole `class` attribute from its `class` input, so pass icon classes with `class="..."` or `[class]`, never `[class.x]`, and put `matListItemIcon` or `matListItemMeta` on a wrapping `span` rather than on the `svg`: the classes that `[class.x]` and those directives add would be wiped when the icon renders',
            '- Lucide sets `aria-hidden="true"` unless `title` is bound, so name the action on the control instead (`aria-label` on icon buttons, without role words such as "button")',
            "",
            "## Accessibility and copy",
            "",
            "- Interactive targets are at least 48×48px; text contrast is at least 4.5:1 (3:1 for large text, icons and component boundaries) in both schemes",
            '- One `h1` per routed view with no skipped heading levels. When a landmark role repeats (for example two `nav` elements, or a `nav` beside a `mat-nav-list`, which renders `role="navigation"`), give each a distinct `aria-label`; a single `main` needs none',
            "- Every pointer interaction has a keyboard path; Esc closes modal surfaces and focus returns to the trigger",
            "- `src/styles.scss` honours `prefers-reduced-motion` for every animation and transition, including the router's view transitions (`::view-transition-*`). Material's indeterminate progress indicators keep their slowed animation",
            "- Screen-reader-only text uses `.cdk-visually-hidden`",
            '- Buttons and menu items use a specific verb ("Delete item", not "OK"), and all UI text uses sentence case',
            "- No trailing period on labels, tooltips, list items, links, dialog body text or any single-sentence message; use periods only when there are several sentences",
            "",
            "## Testing",
            "",
            "- `ng test` runs Vitest through `@angular/build:unit-test` with zoneless change detection (`src/test-providers.ts`); import `vi` from `vitest`",
            "- Query Material components through their test harnesses (`@angular/material/<component>/testing` with `TestbedHarnessEnvironment`) rather than internal class names",
            "- Dialogs, snackbars and menus render in `document.body`'s `.cdk-overlay-container`, not inside the fixture",
            "- jsdom has no `window.matchMedia`: define it with `Object.defineProperty` (see `theme.spec.ts`) or provide a fake `MediaMatcher` (see `window-size-class.spec.ts`)",
            "",
            "## Security",
            "",
            "- Never use `bypassSecurityTrust*` APIs or bind untrusted data to `[innerHTML]`; "
            "Angular's built-in sanitization is the only safe path",
            '- `src/index.html` puts `ngCspNonce="CSP_NONCE"` on `<app-root>`. `nginx.conf` replaces `CSP_NONCE` with `$request_id`, a fresh random value on every request, through `sub_filter`, and allows that nonce in the `script-src` and `style-src` of its `Content-Security-Policy`; any other server for `index.html` must do the same. The build copies the nonce onto inline `<script>` and `<style>` tags (including the critical-CSS loader), and Angular adds it to every component style it injects',
            '- That policy blocks a static `style="…"` attribute in a template, because Angular writes it with `setAttribute`: bind `[style.<property>]` or use the component\'s CSS instead',
            "",
        ]
    )
