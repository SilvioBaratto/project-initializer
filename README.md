# project-initializer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
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
# .env is generated at the project root with working dev defaults — edit for real keys
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
| Language | Python 3.12 | TypeScript (Node 20) |
| ORM | SQLAlchemy + Alembic | Prisma |
| AI/LLM | BAML (Python) | BAML (TypeScript) |
| API style | REST with Pydantic | REST with class-validator |
| Architecture | Clean / hexagonal (domain/application/infrastructure/api) | Modular (controllers/services/modules) |

## Authentication Modes

Add authentication with `--auth token`, `--auth supabase`, or `--auth entra`:

```bash
project-initializer my-app --auth token      # Simple bearer-token auth
project-initializer my-app --auth supabase    # Supabase JWT auth + RLS
project-initializer my-app --auth entra       # Microsoft Entra ID (Azure AD) OIDC
```

- **No auth** (default) — No authentication middleware. Good for prototyping.
- **Token auth** (`--auth token`) — Bearer-token middleware on the API. Frontend gets a login guard and an HTTP interceptor that attaches the token.
- **Supabase auth** (`--auth supabase`) — Supabase JWT validation on the API. Frontend integrates `@supabase/supabase-js` for login/signup. Docker Compose omits the local `db` service since Supabase hosts the database.
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
- Additive: the sync path stays the default; the async modules are an isolated overlay you wire in explicitly.
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
│   ├── src/ (NestJS)       # modules / prisma / common / config (modular)
│   ├── Dockerfile
│   ├── README.md           # generated backend quick-start
│   └── .claude/CLAUDE.md   # generated deep architecture guide
├── frontend/               # Angular + Tailwind CSS
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── src/
│   ├── README.md           # generated Angular quick-start
│   └── .claude/CLAUDE.md   # generated Angular guidance
├── docker-compose.yml      # Full-stack orchestration
├── .env                    # Generated at the ROOT with working dev defaults
├── .env.example            # Committed reference (byte-identical to .env)
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

The CLI generates a single `.env` (plus a byte-identical `.env.example`) at the
**project root** — the one source of truth for both `docker compose` and the app.
Docker Compose loads it via `env_file`; the FastAPI backend walks up to it
(`infrastructure/config.py`) so `cd api && uvicorn` resolves it too, and NestJS
points `ConfigModule`/Prisma at it. The placeholder values double as working dev
defaults, so `docker compose up` runs with no edits. Host ports are parametrized
(`API_HOST_PORT`, `FRONTEND_HOST_PORT`, `DB_HOST_PORT`) with the previous fixed
ports as defaults.

For Supabase variants, configure these in the root `.env`:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...   # client-side (replaces legacy anon key)
SUPABASE_SECRET_KEY=sb_secret_...             # server-side, bypasses RLS (replaces service_role)
```

## Development

### FastAPI

```bash
cd api
pip install -r requirements.txt
uvicorn app.main:app --reload          # API on :8000
alembic upgrade head                   # Run migrations
pytest                                 # Run tests
```

### NestJS

```bash
cd api
npm install
npm run start:dev                      # API on :8000
npx prisma migrate dev                 # Run migrations
npm run test                           # Run tests
```

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
