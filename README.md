# project-initializer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/silviobaratto/project-initializer/actions/workflows/test-package.yml/badge.svg)](https://github.com/silviobaratto/project-initializer/actions)

CLI tool to scaffold full-stack projects with **FastAPI** or **NestJS**, **Angular**, and **Docker** — with optional authentication via token, Supabase, or Microsoft Entra ID. Scaffold the full stack, or just the **backend** or **frontend** with `--scope`.

## Installation

```bash
pip install project-initializer
```

Or install from source:

```bash
git clone https://github.com/silviobaratto/project-initializer.git
cd project-initializer
pip install -e .
```

## Quick Start

```bash
project-initializer my-project
cd my-project
# .env is generated at the project root, with random secrets where the variant has any
docker compose up -d --build
```

Run `project-initializer` with no flags in a terminal and an **interactive wizard**
(Typer + questionary) prompts for scope, framework, auth, and the async-DB option.
Pass any of those as flags to skip its prompt; pass `-y/--yes` (or pipe stdin) to
run fully non-interactive with defaults.

## Framework Selection

Choose a backend framework with `--fastapi` (default) or `--nestjs`:

```bash
project-initializer my-app --fastapi    # FastAPI backend (default)
project-initializer my-app --nestjs     # NestJS backend
```

| Feature | FastAPI | NestJS |
|---------|---------|--------|
| Language | Python 3.12 | TypeScript (Node 22) |
| ORM | SQLAlchemy + Alembic | Prisma |
| API style | REST with Pydantic | REST with Zod (`nestjs-zod`) |
| Architecture | Clean / hexagonal (domain/application/infrastructure/api) | Modular (feature modules; ports and adapters for the database and token verification) |

## Authentication Modes

Add authentication with `--auth token`, `--auth supabase`, or `--auth entra`:

```bash
project-initializer my-app --auth token      # Simple bearer-token auth
project-initializer my-app --auth supabase    # Supabase JWT auth (NestJS migrations also enable RLS)
project-initializer my-app --auth entra       # Microsoft Entra ID (Azure AD) OIDC
```

- **No auth** (default) — No authentication: every caller is a development principal. Good for prototyping, not for exposing the API.
- **Token auth** (`--auth token`) — A shared bearer token (`AUTH_TOKEN`, generated per scaffold) guards item writes. FastAPI adds JWT login (`/auth/register`, `/auth/token`). Frontend gets a login guard and an HTTP interceptor that attaches the token.
- **Supabase auth** (`--auth supabase`) — Each bearer token is verified through Supabase Auth; when Supabase cannot answer, the API returns 503, not 401. Frontend integrates `@supabase/supabase-js` for login/signup. Docker Compose omits the local `db` service since Supabase hosts the database.
- **Entra auth** (`--auth entra`) — Microsoft Entra ID (formerly Azure AD) OIDC. Both backends validate Entra v2 JWT bearer tokens in-process via RS256 + JWKS. The Angular frontend uses MSAL for login. Requires two Entra app registrations (API + SPA).

## Project Scope (full-stack / backend-only / frontend-only)

By default the CLI scaffolds both halves (`api/` + `frontend/`). Use `--scope` to generate only one:

```bash
project-initializer my-app                      # fullstack (default): api + frontend
project-initializer my-app --scope api          # backend only — no frontend/, no frontend service
project-initializer my-app --scope frontend     # frontend only — Angular app, no api/
```

- **`--scope api`** — emits `api/` + `docker-compose.yml` (without the `frontend` service) + the root `.env`/`.env.example`. Combine with `--fastapi`/`--nestjs`/`--auth` as usual.
- **`--scope frontend`** — emits just the Angular `frontend/` (nginx `/api/` proxy stripped). Cannot be combined with `--fastapi`/`--nestjs`/`--auth` (those are backend concerns).
- **`--scope fullstack`** (default) — both halves, current behavior.

## Async Database (opt-in)

FastAPI backends scaffold the **sync** SQLAlchemy path by default — sync `def` path operations run in Starlette's threadpool, so a blocking `Session` never stalls the event loop. This is the recommended default per the FastAPI tutorial.

Pass `--async-db` to additionally lay down the **async** SQLAlchemy overlay (async engine + `AsyncSession` + `get_async_db` dependency, asyncpg driver):

```bash
project-initializer my-app --async-db              # fullstack + async DB path
project-initializer my-app --scope api --async-db  # backend only + async DB path
```

- FastAPI only — rejected with `--nestjs` and with `--scope frontend`.
- Additive: the sync path stays the default; the async modules (`database_async.py`, `repositories/item_async.py`, `unit_of_work_async.py` and the async ports) are an isolated overlay, and no route uses them until you write one. Importing `database_async` registers its engine disposal as a shutdown hook and its health probe as a readiness probe (`additional_databases` in `/health/ready`), so `main.py` needs no edit.
- See the generated `api/.claude/CLAUDE.md` for the sync-vs-async convention (pick the keyword from the I/O, not by style).

## All 8 Variants

| Command | Backend | Auth |
|---------|---------|------|
| `project-initializer app` | FastAPI | None |
| `project-initializer app --auth token` | FastAPI | Token |
| `project-initializer app --auth supabase` | FastAPI | Supabase |
| `project-initializer app --auth entra` | FastAPI | Entra ID |
| `project-initializer app --nestjs` | NestJS | None |
| `project-initializer app --nestjs --auth token` | NestJS | Token |
| `project-initializer app --nestjs --auth supabase` | NestJS | Supabase |
| `project-initializer app --nestjs --auth entra` | NestJS | Entra ID |

Additional flags:

```bash
project-initializer my-project --scope api       # Backend only
project-initializer my-project --scope frontend  # Frontend only
project-initializer my-project --async-db        # FastAPI async SQLAlchemy path (opt-in)
project-initializer my-project --force           # Overwrite existing files
project-initializer my-project -y                # Non-interactive (defaults for unset options)
project-initializer my-project -V                # Verbose: list every file created
project-initializer .                            # Scaffold in current directory
project-initializer --version                    # Show version
```

## Generated Project Structure

```
my-project/
├── api/                    # Backend (FastAPI or NestJS)
│   ├── app/ (FastAPI)      # domain / application / infrastructure / api (hexagonal)
│   ├── src/ (NestJS)       # app.module + app.auth seam / modules / prisma / common / config
│   ├── Dockerfile
│   ├── README.md           # generated backend quick-start
│   └── .claude/CLAUDE.md   # generated deep architecture guide
├── frontend/               # Angular + Angular Material 3
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── src/
│   ├── README.md           # generated Angular quick-start
│   └── .claude/CLAUDE.md   # generated Angular guidance
├── docker-compose.yml      # Full-stack orchestration
├── .env                    # Generated at the ROOT, with random secrets; never commit it
├── .env.example            # Committed reference: the same keys, secrets left blank
├── README.md               # generated per-flag
└── CLAUDE.md               # generated AI-assistant guidance
```

Docs (`README.md` + `CLAUDE.md` at the root, in `api/`, and in `frontend/`) are
**generated per-flag** from a single source, not copied from static templates —
so a NestJS project never mentions SQLAlchemy, a no-auth project never documents
Entra, and the docs cannot drift from the code.

## Docker Services

| Service | Port | Description | Supabase variants |
|---------|------|-------------|-------------------|
| `db` | 5433:5432 | PostgreSQL 16 | Omitted (Supabase hosts DB) |
| `adminer` | 8080:8080 | DB management UI | Omitted |
| `api` | 8000:8000 | Backend with hot reload | Present |
| `frontend` | 4200:80 | Angular + nginx (proxies `/api/` to backend) | Present |

## Environment Configuration

The CLI generates a single `.env` and a `.env.example` at the **project root** —
the one source of truth for both `docker compose` and the app. Docker Compose
loads `.env` via `env_file`; the FastAPI backend walks up to it
(`infrastructure/config.py`) so `cd api && uvicorn` resolves it too, and NestJS
points `ConfigModule`/Prisma at it. Non-secret values are dev defaults: the no-auth
and token variants run `docker compose up` with no edits,
while supabase needs its project URLs and keys and entra its app registration ids.
Secrets (`AUTH_TOKEN`, `JWT_SECRET_KEY`) are random values written into `.env` only; the
committed `.env.example` leaves them blank, and re-scaffolding keeps the secrets an
existing `.env` already holds. Host ports are parametrized (`API_HOST_PORT`,
`FRONTEND_HOST_PORT`, `DB_HOST_PORT`) with the previous fixed ports as defaults.
A NestJS `.env` sets
`NODE_ENV=development`, which matches the compose `dev` target; the production image
sets `NODE_ENV=production` itself and must not be started with that file.

For Supabase variants, configure these in the root `.env`:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...   # replaces the legacy anon key
```

Neither backend reads `SUPABASE_SECRET_KEY`: the secret (service-role) key would bypass Row
Level Security. The NestJS migrations enable RLS on every table.

## Development

### FastAPI

```bash
cd api
pip install ".[dev]"
uvicorn app.main:app --reload          # API on :8000
alembic upgrade head                   # Run migrations
alembic downgrade -1                   # Roll the newest migration back (rows are kept in a backup table)
pytest                                 # Run tests on in-memory SQLite; fails below 75% branch coverage
pytest -m unit --no-cov                # A subset cannot reach the gate: add --no-cov
alembic revision --autogenerate --rev-id 0003_add_widget -m "add widget"   # New migration
```

Interactive docs (`/docs`) are served in every environment except `production`
(`API_DOCS_ENABLED` overrides). `/health` is the liveness probe and `/health/ready` the
readiness probe. The rate limiter is in-memory and active only in `staging` and
`production`: behind a reverse proxy, list the proxy in `FORWARDED_ALLOW_IPS`, and use a
gateway or an external shared store once you run several replicas. With `--auth token`, `AUTH_TOKEN` and
`JWT_SECRET_KEY` are generated into `.env`; a placeholder or a non-empty secret shorter than
16 and 32 characters is refused at every stage, and an empty one outside development.
Migration backups of a rollback go to the PostgreSQL schema `migration_backup`, and the
Supabase variant enables row level security on every table. The container waits for the
database in `DATABASE_URL` for at most `DB_WAIT_TIMEOUT_SECONDS` (default 60) and uvicorn runs
with `--no-access-log`.

In `staging` and `production` the API refuses a database connection that is not TLS-protected:
`DATABASE_SSL_MODE`, or the `sslmode` of `DATABASE_URL` and `DIRECT_DATABASE_URL`, must be
`require`, `verify-ca` or `verify-full`. `DATABASE_ALLOW_INSECURE_TRANSPORT=true` is the opt-out for
a database on the same host or a private network without TLS, which the bundled compose `db`
needs under `ENVIRONMENT=production`; the generated Supabase `.env` already meets the rule.
`kill -HUP <pid>` re-reads `LOG_LEVEL` (the `.env` file wins over the environment; in Docker, where
no `.env` file is read, it re-applies the start-up value). Item changes, and with `--auth token`
registration (`user.register`) and login (`user.login`), write an `audit.action` log line that
names the actor by id only.

### NestJS

```bash
cd api
npm install
npm run start:dev                      # API on :8000
npx prisma migrate dev                 # Run migrations
npx prisma db execute --file prisma/migrations/<dir>/down.sql   # Roll one migration back, newest first
npm run test                           # Unit tests
npm run test:e2e                       # e2e tests on in-memory fakes (no Postgres)
npm run lint                           # ESLint, no warnings allowed
```

With `--auth token`, scaffolding writes a random `AUTH_TOKEN` into `.env` and leaves it empty in
`.env.example`; it must be at least 32 characters.
`TRUST_PROXY_HOPS` (default 1, the bundled nginx) says how many proxies sit in front of the
API for the rate limiter; use `0` when it is exposed directly. JSON bodies above 512 KiB answer
413, and the container entrypoint waits for the database in `DATABASE_URL` for at most
`DB_WAIT_TIMEOUT_SECONDS`.

With `NODE_ENV=production` the API refuses a `DATABASE_URL` whose `sslmode` is not `require`,
`verify-ca` or `verify-full`; `DB_ALLOW_INSECURE_TRANSPORT=true` is the opt-out for a database on
the same host or a private network without TLS (the compose stack runs `NODE_ENV=development` and
is unaffected). `kill -HUP <pid>` reloads `LOG_LEVEL` from `.env`. `@Roles(...)` and the global
`RolesGuard` restrict a route to callers that hold one of the roles (403 otherwise; the no-auth
variant denies every `@Roles` route), and the items service writes `item.create`, `item.update`
and `item.delete` as `audit.action` lines that `LOG_LEVEL` cannot silence.

### Frontend (Angular)

```bash
cd frontend
npm install --legacy-peer-deps
ng serve                               # Dev server on :4200
ng build                               # Production build
ng test                                # Unit tests
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, template architecture, and PR guidelines.

## License

MIT
