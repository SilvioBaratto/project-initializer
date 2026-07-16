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
# static doc carried is preserved.
_NESTJS_READINESS_CHECKLIST = """\
### Middleware Stack

1. Helmet (security headers)
2. CORS
3. Throttler (rate limiting)
4. nestjs-pino HTTP logging (request-id correlation via `x-request-id`)
5. ZodValidationPipe (global)
6. HttpExceptionFilter + PrismaClientExceptionFilter (global)
7. TransformInterceptor (global)

## Production-readiness acceptance checklist

> **Research provenance:** deep research — 110 agents, 28 primary sources, 24 claims at 3-0 adversarial verification against official NestJS docs (https://docs.nestjs.com/). Statuses reflect **verified current state** of this template.
>
> **Legend:** ✅ done in template · ⚠️ partial / worth hardening · ❌ gap / not present (non-goal)

### 1. Core building blocks & DI

- ✅ `@Module()` with providers/controllers/imports/exports — feature modules under `src/modules/*`
- ✅ `PrismaModule` is `@Global()` and exports `PrismaService`; never re-register in another `providers:` array
- ✅ Type-based constructor injection; default singleton scope (use REQUEST only when strictly needed)
- Citations: `/modules`, `/providers`, `/fundamentals/injection-scopes`

### 2. Controllers & routing

- ✅ `@Controller('prefix')` + HTTP-method decorators; request-data decorators (`@Body/@Query/@Param`) over raw `@Req()`
- ✅ `app.setGlobalPrefix('api/v1')` in `main.ts`
- ⚠️ URI/header versioning (`VersioningType`) — static `api/v1` prefix is sufficient for a single version (non-goal)
- Citations: `/controllers`, `/techniques/versioning`

### 3. DTOs, validation & serialization

- ✅ Zod schemas via `nestjs-zod` as DTOs (not erased interfaces)
- ✅ `ZodValidationPipe` registered as `APP_PIPE` — strips unknown fields from all incoming bodies
- ✅ `ZodSerializerInterceptor` registered as `APP_INTERCEPTOR`; response schemas whitelist fields so Prisma rows cannot leak secret columns
- ⚠️ Built-in transform pipes — Zod coercion covers primitive coercion; no `ParseIntPipe` needed
- Citations: `/pipes`, `/techniques/validation`, `/techniques/serialization`

### 4. Request pipeline — pipes, guards, interceptors, filters, middleware

- ✅ Global Zod pipe, auth guards, `TransformInterceptor`, `ZodSerializerInterceptor`
- ✅ `HttpExceptionFilter` + `PrismaClientExceptionFilter` registered via `useGlobalFilters()` in `main.ts`
- ✅ `LoggingMiddleware` (nestjs-pino) applied globally; `@CurrentUser()`, `@Public()` custom decorators
- ⚠️ **Filter DI caveat:** filters registered via `useGlobalFilters()` in `main.ts` live outside the Nest DI container and cannot inject providers. The current filters are dependency-free (`new`-instantiated in `main.ts`) — **no change is required today**.

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

  Keep dependency-free filters in `main.ts` via `useGlobalFilters()` — switching them to `APP_FILTER` without a real DI need adds unnecessary indirection.

- Citations: `/pipes`, `/guards`, `/interceptors`, `/exception-filters`, `/middleware`, `/custom-decorators`

### 5. Authentication & authorization

- ✅ Token auth: `AuthGuard` registered as `APP_GUARD`
- ✅ Supabase JWT auth: `SupabaseAuthGuard` registered as `APP_GUARD`
- ✅ `@Public()` opt-out via `Reflector.getAllAndOverride` — both guards honor it
- ❌ RBAC / CASL — non-goal (add only when multi-role or fine-grained authz is needed)
- Citations: `/security/authentication`, `/security/authorization`, `/guards`

### 6. Security hardening

- ✅ Helmet (`app.use(helmet())`) — `main.ts`
- ✅ CORS restricted to `CORS_ORIGINS` env (not `*`), credentials/methods/headers configured — `main.ts`
- ✅ Rate limiting: `ThrottlerModule` 100 req/60s + global `ThrottlerGuard` — `app.module.ts`
- ✅ Secrets via `@nestjs/config` with `ConfigModule.forRoot({ isGlobal: true })`
- ❌ CSRF — non-goal (bearer-token APIs are largely CSRF-immune; add `csurf` only if cookie auth is introduced)
- Citations: `/security/helmet`, `/security/rate-limiting`, `/security/csrf`

### 7. Operational concerns

- ✅ Env validation: `src/config/env.validation.ts` — `validate()` throws on missing `DATABASE_URL`/`DIRECT_URL`; wired via `ConfigModule.forRoot({ validate })`
- ✅ Structured logging: `nestjs-pino` with `x-request-id` correlation — `src/config/logger.config.ts`
- ✅ Health checks: `@nestjs/terminus` liveness + readiness probes (DB, disk, memory) — `src/modules/health/health.controller.ts`
- ✅ OpenAPI/Swagger at `/docs` with bearer auth and `cleanupOpenApiDoc` — `main.ts`
- ✅ Graceful shutdown: `app.enableShutdownHooks()` + Prisma `$disconnect` on `onModuleDestroy`
- Citations: `/techniques/configuration`, `/techniques/logger`, `/recipes/terminus`, `/openapi/introduction`, `/fundamentals/lifecycle-events`

### 8. Database / ORM

- ✅ `PrismaService extends PrismaClient` in `@Global() PrismaModule`; connect on `onModuleInit`, disconnect on `onModuleDestroy`
- ✅ Migrations via `prisma migrate dev/deploy`; SSL via `deriveSslOption` util (with spec test); health probe runs `SELECT 1`
- Citations: `/recipes/prisma`, `/techniques/database`

### 9. Testing

- ✅ Jest configured; `npm test` and `npm run test:e2e` scripts present
- ✅ Service/controller unit specs: `chatbot.service.spec.ts`, `chat-job.service.spec.ts`, `health.controller.spec.ts`, `serialization.spec.ts`
- ✅ e2e scaffold: `test/app.e2e-spec.ts` (supertest) + `test/jest-e2e.json`
- Citations: `/fundamentals/testing`

## Global acceptance criteria

| # | Criterion | Status | Citation |
|---|-----------|--------|----------|
| 1 | Auth guard registered as `APP_GUARD` in both overlays — routes protected by default | ✅ | token/supabase `app.module.ts` (AuthGuard / SupabaseAuthGuard) |
| 2 | `ConfigModule` validates env and fails fast on missing secrets (`DATABASE_URL`, `SUPABASE_*`) | ✅ | `src/config/env.validation.ts` — `validate()` throws; wired via `ConfigModule.forRoot({ validate })` |
| 3 | Response schemas whitelist fields — Prisma rows cannot leak secret columns through the serializer | ✅ | `src/modules/test/serialization.spec.ts` — `ItemResponseSchema.parse({ password: 'leak' })` strips `password` |
| 4 | Terminus health module: liveness/readiness probes (DB, disk, memory) | ✅ | `src/modules/health/health.controller.ts` — `@nestjs/terminus` |
| 5 | e2e test scaffold + service unit specs | ✅ | `test/app.e2e-spec.ts`, `test/jest-e2e.json`; `chatbot.service.spec.ts` |
| 6 | (Optional) Blocking BAML/LLM calls offloaded to BullMQ background jobs | ✅ | `src/modules/chatbot/chat-job.service.ts` + `chat.processor.ts`; `POST /chat/jobs` / `GET /chat/jobs/:id` |
"""

# The --legacy-peer-deps rationale is shared verbatim by every README that has a
# frontend dev section, so it lives in one place.
_LEGACY_PEER_DEPS_NOTE = (
    "> **Why `--legacy-peer-deps`?** `@angular/build` declares an optional peer dependency on\n"
    "> `vitest@^4`, but the project pins `vitest@^3`. npm 7+ treats this mismatch as a hard\n"
    "> `ERESOLVE` error and aborts `npm install`. `--legacy-peer-deps` skips npm's peer-dependency\n"
    "> check and installs anyway. Safe here: `vitest` is a test-only devDependency and Angular's build\n"
    "> only optionally peers it, so app build/serve are unaffected."
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
    """Compose services table — omits db/adminer for supabase, adds redis for NestJS."""
    rows = ["| Service | Port | Description |", "|---------|------|-------------|"]
    if auth != "supabase":
        rows.append("| `db` | 5433:5432 | PostgreSQL 16 |")
    if framework == "nestjs":
        rows.append("| `redis` | internal | Redis (BullMQ) |")
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
            "pip install -r requirements.txt",
            "uvicorn app.main:app --reload          # Runs on :8000",
            "",
            "# Database",
            "alembic upgrade head                   # Apply migrations",
            'alembic revision --autogenerate -m "description"',
            "",
            "# Tests",
            "pytest",
            "",
            "# BAML (AI/LLM)",
            "baml-cli generate",
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
        "# Tests",
        "npm test",
        "",
        "# BAML (AI/LLM)",
        "npx baml-cli generate",
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
        sections += [
            "# Edit .env with your Entra credentials",
            "cp .env.example .env",
        ]
    elif auth == "supabase":
        sections += [
            "# Edit .env with your Supabase credentials:",
            "#   DATABASE_URL, DIRECT_URL, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY",
        ]
    else:
        sections.append("# Edit .env with your real keys (ships with working dev defaults)")
    sections += ["docker compose up -d --build", "```", ""]
    sections += ["Services will be available at:"] + _services_url_list(
        frontend=frontend, auth=auth
    )
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
        "| `app/domain/` | Pure core: `entities/` (dataclasses), `ports/` (repository interfaces), `services/`, `exceptions.py` — no framework/ORM imports |",
        "| `app/application/` | Use-case orchestration: `services/` (depend on domain ports), `dto/`, `commands/` — imports domain only |",
        "| `app/infrastructure/` | The only tech layer: `settings.py`, `config.py` (walk-up `.env` loader), `database.py`, `orm/` (SQLAlchemy), `repositories/` (port adapters), `audit.py` |",
        "| `app/api/` | HTTP surface: `deps.py` (composition root), `handlers.py`, `schemas/` (Pydantic), `middleware/`, `v1/router.py` + `v1/endpoints/` |",
        "| `baml_src/` | LLM function definitions (regenerate client with `baml-cli generate`) |",
        "",
        "Dependencies point strictly inward: `api → application → domain`, `infrastructure → domain`. Enforced by an AST fitness test (`api/tests/unit/test_architecture.py`).",
        "",
        "**Sync vs async**: DB endpoints are sync `def` (offloaded to a threadpool with the sync `Session`); `async def` is reserved for BAML/LLM calls. See `api/.claude/CLAUDE.md` for the full rule.",
        "",
        "### Mapping from the FastAPI tutorial",
        "",
        "The official FastAPI \"Bigger Applications\" tutorial organizes path operations into a `routers/` package where each router file also holds inline DB queries and business logic. This scaffold keeps the routers at `app/api/v1/endpoints/` (aggregated by `app/api/v1/router.py`, all under the `/api/v1` prefix) and splits what the tutorial keeps inline across the four hexagonal layers: router (`app/api/v1/endpoints/`) → application service (`app/application/services/`) → domain port (`app/domain/ports/`) implemented by an infrastructure repository (`app/infrastructure/repositories/`) → ORM model (`app/infrastructure/orm/`) → Pydantic schema (`app/api/schemas/`).",
        "",
        "Unlike the tutorial's flat layout, **this is a real restructure — the code is physically split across `domain`/`application`/`infrastructure`/`api`, not just conceptually.**",
    ]
    if auth == "token":
        sections += [
            "",
            "## Token auth (`--auth token`)",
            "",
            "`POST /auth/validate` is a validity **probe**: it returns **HTTP 200 with `authenticated=false`** for an invalid token, because both outcomes are successful *answers* to \"is this token valid?\". **401 is reserved for guarded endpoints that refuse access** (`/auth/me`, item writes), never for the probe. The supabase variant has **no** `/auth/validate` endpoint; token validity is resolved server-side via JWT / `supabase.auth.getUser()` instead.",
        ]
    return sections


def _nestjs_root_claude(auth: str | None) -> list[str]:
    return [
        "## API Template (`api/`)",
        "",
        "NestJS application with modular architecture:",
        "",
        "| Layer | Purpose |",
        "|-------|---------|",
        "| `src/modules/` | Feature modules (health, auth, chatbot, test) |",
        "| `src/prisma/` | Global PrismaModule and PrismaService |",
        "| `src/common/` | Decorators, filters, exceptions, interceptors, middleware |",
        "| `prisma/schema.prisma` | Database models |",
        "| `baml_src/` | LLM function definitions (regenerate client with `npx baml-cli generate`) |",
        "",
        "See `api/.claude/CLAUDE.md` for the full BAML call flow and production-readiness checklist.",
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
                "Angular 21 with Tailwind CSS. See `frontend/.claude/CLAUDE.md` for conventions.",
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
            "Angular 21 with Tailwind CSS (standalone components, signals, native control flow, OnPush, `inject()`). See `frontend/.claude/CLAUDE.md` for the full conventions.",
        ]
    sections += [
        "",
        "## Docker Services",
        "",
        _docker_services_table(framework, auth, frontend=frontend),
        "",
    ]
    return "\n".join(sections)


# ── api/README.md ─────────────────────────────────────────────────────────────


def generate_api_readme(framework: str, *, async_db: bool = False) -> str:
    """Build api/README.md for the framework."""
    if framework == "fastapi":
        tree = [
            "app/",
            "├── main.py                     # App factory: load_configuration → logging → lifespan → CORS → router",
            "├── domain/                     # Pure core (entities, ports, services, exceptions) — no framework imports",
            "├── application/                # Use-case orchestration (services, dto, commands) — domain-only deps",
            "├── infrastructure/             # Tech layer: settings, config, database, orm/, repositories/, audit",
            "└── api/                        # HTTP: deps.py, handlers.py, schemas/, middleware/, v1/router.py + v1/endpoints/",
            "",
            "baml_src/                       # BAML LLM function definitions",
            "baml_client/                    # Auto-generated BAML client (don't edit)",
        ]
        return "\n".join(
            [
                "# FastAPI Backend",
                "",
                "## Quick Start",
                "",
                "```bash",
                "pip install -r requirements.txt",
                "uvicorn app.main:app --reload    # http://localhost:8000",
                "```",
                "",
                "## Key Commands",
                "",
                "```bash",
                "pytest                                            # Run tests",
                "alembic upgrade head                              # Apply migrations",
                'alembic revision --autogenerate -m "description"  # Create migration',
                "baml-cli generate                                 # Regenerate BAML client",
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
            "npm test                          # Run tests",
            "npx prisma migrate dev            # Create + apply migration",
            "npx prisma migrate deploy         # Apply migrations (production)",
            "npx prisma generate               # Regenerate Prisma client",
            "npx prisma studio                 # Visual DB editor",
            "npx baml-cli generate             # Regenerate BAML client",
            "```",
            "",
            "## Architecture",
            "",
            "```",
            "src/",
            "├── main.ts               # Bootstrap, Swagger, Helmet, CORS",
            "├── app.module.ts          # Root module",
            "├── prisma/                # Global PrismaModule + PrismaService",
            "├── common/                # decorators, filters, exceptions, interceptors",
            "├── config/                # env validation (zod) + pino logger config",
            "└── modules/               # health, auth, test, chatbot",
            "",
            "prisma/schema.prisma       # Database models",
            "baml_src/                  # BAML LLM function definitions",
            "baml_client/               # Auto-generated BAML client (don't edit)",
            "```",
            "",
        ]
    )


# ── api/.claude/CLAUDE.md ─────────────────────────────────────────────────────


def _fastapi_api_claude(auth: str | None, async_db: bool) -> str:
    tree = [
        "app/",
        "├── main.py                     # App factory: load_configuration → logging → lifespan → CORS → router",
        "├── domain/                     # Pure core — NO framework/ORM imports",
        "│   ├── entities/               # Plain dataclasses (e.g. Item) — no SQLAlchemy/Pydantic",
        "│   ├── ports/                  # Abstract repository interfaces (e.g. ItemRepositoryPort)",
        "│   ├── services/               # Pure domain logic",
        "│   └── exceptions.py           # Domain exception types (framework-free)",
        "├── application/                # Use-case orchestration — depends on domain only",
        "│   ├── services/               # Application services (depend on ports, own the transaction)",
        "│   ├── dto/                    # Use-case DTOs",
        "│   └── commands/               # Command DTOs",
        "├── infrastructure/             # The ONLY tech layer",
        "│   ├── config.py               # Walk-up .env loader (load_configuration)",
        "│   ├── settings.py             # Settings (pydantic-settings, reads os.environ)",
        "│   ├── database.py             # DatabaseManager: sync SQLAlchemy + psycopg2 pooling",
        "│   ├── orm/                    # SQLAlchemy models (Base in base.py)",
        "│   ├── repositories/           # Port adapters (e.g. ItemRepository) + BaseRepository",
        "│   └── audit.py                # Audit-log helper",
        "└── api/                        # HTTP surface",
        "    ├── deps.py                 # FastAPI deps (auth, pagination, rate limiting)",
        "    ├── handlers.py             # Centralized exception handlers",
        "    ├── schemas/                # Pydantic request/response schemas",
        "    ├── middleware/             # Security, logging, rate limiting",
        "    └── v1/                     # router.py aggregates endpoints/ (all under /api/v1)",
        "",
        "baml_src/                       # BAML definitions for LLM functions",
        "baml_client/                    # Auto-generated BAML Python client (don't edit)",
    ]
    async_note = (
        "\n- An opt-in async DB path (async engine + `AsyncSession`) is included, gated "
        "behind the `--async-db` generator flag "
        "(`infrastructure/database_async.py`, `infrastructure/repositories/base_async.py`); "
        "the sync path above stays the default."
        if async_db
        else ""
    )
    return "\n".join(
        [
            "# CLAUDE.md",
            "",
            "This file provides guidance to Claude Code when working with this FastAPI API.",
            "",
            "## Build & Run Commands",
            "",
            "```bash",
            "pip install -r requirements.txt",
            "uvicorn app.main:app --reload            # Run dev server (:8000)",
            "pytest                                   # Run tests",
            "alembic upgrade head                     # Apply migrations",
            'alembic revision --autogenerate -m "description"',
            "baml-cli generate                        # Regenerate BAML client",
            "```",
            "",
            "## Architecture: clean / hexagonal — four layers",
            "",
            "```",
            *tree,
            "```",
            "",
            "Dependency direction: `api → application → domain`, `infrastructure → domain`.",
            "`domain` imports nothing outward; `application` never imports `infrastructure`/`api`.",
            "Enforced by `tests/unit/test_architecture.py` (AST fitness test).",
            "",
            '## "Start from the Port" Workflow',
            "",
            "1. Define an abstract port in `app/domain/ports/` — the domain owns the contract.",
            "2. Write the application service against the port; import only the abstract type.",
            "3. Implement the adapter in `app/infrastructure/repositories/`.",
            "4. Wire abstract → concrete in `api/v1/endpoints/` (or `api/deps.py`) **only**.",
            "5. Inject a fake via `app.dependency_overrides` in tests.",
            "",
            "## Key Patterns",
            "",
            "**Sync vs async**: DB-backed endpoints are sync `def` handlers; BAML/LLM endpoints are `async def`. Pick the keyword from the I/O, not by convention.",
            "",
            "- Sync `def` path operations are offloaded to an `anyio` threadpool, so a blocking sync SQLAlchemy `Session` runs in a worker thread and never blocks the event loop. This is the **default and correct** path for DB routes — see `app/api/v1/endpoints/items.py`.",
            "- `async def` runs directly on the event loop; reserve it for real async I/O — BAML/LLM `await` calls — see `app/application/services/chatbot_service.py`. Never mix a sync `Session` into an `async def` handler."
            + async_note,
            "",
            "**API Routes**: All v1 routes go through `/api/v1`. Add an endpoint module under `app/api/v1/endpoints/` and register it in `app/api/v1/router.py`.",
            "",
            "**BAML Integration**: Define LLM functions in `baml_src/*.baml`, regenerate with `baml-cli generate`. Access via `from baml_client.async_client import b as baml_async_client`.",
            "",
            "**Schema Naming**: `<Entity>Create`, `<Entity>Update`, `<Entity>Response` pattern.",
            "",
        ]
    )


def _nestjs_api_claude(auth: str | None, async_db: bool) -> str:
    return "\n".join(
        [
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
            "npm test                      # Run tests",
            "npx prisma migrate dev        # Create and apply migration (dev)",
            "npx prisma migrate deploy     # Apply migrations (production)",
            "npx prisma generate           # Regenerate Prisma client",
            "npx baml-cli generate         # Regenerate BAML client",
            "```",
            "",
            "## Architecture Overview",
            "",
            "This is a NestJS application with BAML-powered AI chatbot functionality.",
            "",
            "### Core Structure",
            "",
            "```",
            "src/",
            "├── main.ts               # Bootstrap, Swagger, Helmet, CORS, ValidationPipe",
            "├── app.module.ts          # Root module (Prisma, Config, Throttler)",
            "├── prisma/                # @Global() PrismaModule + PrismaService",
            "├── common/                # decorators (@CurrentUser, @Public), filters, exceptions, interceptors",
            "├── config/                # env validation (zod) + pino logger config",
            "└── modules/               # health (Terminus), auth, test (CRUD), chatbot (BAML)",
            "",
            "prisma/schema.prisma       # Database models",
            "baml_src/                  # BAML definitions for LLM functions",
            "baml_client/               # Auto-generated BAML TypeScript client (don't edit)",
            "```",
            "",
            "### Key Patterns",
            "",
            "**Database Access**: PrismaService injected via DI. PrismaModule is @Global.",
            "",
            "**Models**: Defined in `prisma/schema.prisma`. Regenerate client with `npx prisma generate`.",
            "",
            "**API Routes**: All v1 routes go through `/api/v1` prefix set in controllers.",
            "",
            "**DTO Naming**: `Create<Entity>Dto`, `Update<Entity>Dto`, `<Entity>ResponseDto` pattern (Zod-based via nestjs-zod).",
            "",
            "## BAML Integration",
            "",
            "LLM functions are defined in `baml_src/*.baml`. The BAML compiler emits a generated TypeScript client into `baml_client/`. The generated client must not be hand-edited — always regenerate it after any `.baml` change:",
            "",
            "```bash",
            "npx baml-cli generate",
            "```",
            "",
            "### Generator configuration (`baml_src/generators.baml`)",
            "",
            "The generator targets TypeScript with async default client mode (`default_client_mode async`), so every `b.FunctionName()` call returns a `Promise`. The output directory is `baml_client/` (one level above `baml_src/`).",
            "",
            "### Chatbot call flow",
            "",
            "```",
            "ChatbotController",
            "├── POST /chat         → ChatbotService.chat(request)",
            "│                          └─ const { b } = await import('../../../baml_client')",
            "│                          └─ b.Chat(user_question, conversation_history) → { answer }",
            "├── POST /chat/stream  → ChatbotService.streamChat(request)  [SSE]",
            "│                          └─ b.stream.StreamChat(user_question, conversation_history)",
            "├── POST /chat/jobs    → ChatJobService.enqueueChat(request) → { jobId }",
            "└── GET  /chat/jobs/:id → ChatJobService.getJobStatus(id)",
            "                             └─ ChatProcessor.process(job)  [BullMQ worker]",
            "                                   └─ b.Chat(user_question, conversation_history)",
            "```",
            "",
            "`ChatbotService.chat` and `ChatbotService.streamChat` run on the request path. The `ChatProcessor` worker runs blocking BAML/LLM calls off the request path via BullMQ.",
            "",
            _NESTJS_READINESS_CHECKLIST,
        ]
    )


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
            "Angular single-page application (standalone components, signals, Tailwind CSS).",
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
            "## Security",
            "",
            "- Never use `bypassSecurityTrust*` APIs or bind untrusted data to `[innerHTML]`; "
            "Angular's built-in sanitization is the only safe path",
            "",
        ]
    )
