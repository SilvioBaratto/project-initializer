# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a pip-installable CLI tool (`project-initializer`) that scaffolds full-stack projects in **6 variants**: 2 frameworks (FastAPI, NestJS) x 3 auth modes (none, token, supabase). The repository contains the CLI package and all template files it copies.

## CLI Flags

```bash
project-initializer <name> [--fastapi | --nestjs] [--auth token | --auth supabase] [--force]
```

- `--fastapi` (default) or `--nestjs` — backend framework
- `--auth token` — bearer-token authentication
- `--auth supabase` — Supabase JWT auth (replaces local DB with Supabase-hosted)
- `--force` — overwrite existing files without prompting

## Build & Run Commands

```bash
# Install CLI tool in development mode
pip install -e .

# Scaffold all 6 variants for testing
project-initializer test-fastapi --fastapi --force
project-initializer test-fastapi-token --fastapi --auth token --force
project-initializer test-fastapi-supabase --fastapi --auth supabase --force
project-initializer test-nestjs --nestjs --force
project-initializer test-nestjs-token --nestjs --auth token --force
project-initializer test-nestjs-supabase --nestjs --auth supabase --force

# Run full stack with Docker
cd test-fastapi && docker-compose up -d

# Individual services (FastAPI variant)
cd test-fastapi/api && uvicorn app.main:app --reload    # Backend on :8000
cd test-fastapi/frontend && ng serve                     # Frontend on :4200

# Individual services (NestJS variant)
cd test-nestjs/api && npm run start:dev                  # Backend on :8000
```

## Template Overlay System

The CLI merges template layers in order — later layers overwrite earlier files. This is the core architecture:

### Layer 1: Shared Base (`templates/`)
Contains the Angular frontend, root configs (`.env.example`, `CLAUDE.md`, `.gitignore`), and shared `.vscode/` setup. Copied for every variant.

### Layer 2: Framework API (`templates-api-{framework}/`)
Adds the `api/` directory, `docker-compose.yml`, and `frontend/nginx.conf` for the chosen framework. These differ between FastAPI (Python Dockerfile, SQLAlchemy) and NestJS (Node Dockerfile, Prisma).

### Layer 3a: Auth API Overlay (`templates-{auth}-{framework}/`)
Overwrites specific API files to add authentication middleware, guards, and config. Only applied when `--auth` is specified.

### Layer 3b: Auth Frontend Overlay (`templates-{auth}-frontend/`)
Overwrites specific frontend files to add login components, auth guards, and HTTP interceptors. Shared across frameworks for the same auth mode.

### Overlay Directories

```
project_initializer/
├── templates/                      # Layer 1: shared base (frontend + root configs)
├── templates-api-fastapi/          # Layer 2: FastAPI API + docker-compose + nginx
├── templates-api-nestjs/           # Layer 2: NestJS API + docker-compose + nginx
├── templates-token-fastapi/        # Layer 3a: token auth for FastAPI
├── templates-token-nestjs/         # Layer 3a: token auth for NestJS
├── templates-token-frontend/       # Layer 3b: token auth frontend (shared)
├── templates-supabase-fastapi/     # Layer 3a: supabase auth for FastAPI
├── templates-supabase-nestjs/      # Layer 3a: supabase auth for NestJS
├── templates-supabase-frontend/    # Layer 3b: supabase auth frontend (shared)
├── cli.py                          # Entry point — copy_tree() merges layers
├── env_generator.py                # Generates variant-specific api/.env
└── __init__.py
```

### How `copy_tree()` Merges Layers

In `cli.py`, the `copy_tree(src, dst)` function recursively copies `src` into `dst`, creating directories as needed and overwriting files that already exist. The merge order is:

1. `copy_tree(templates/, dest/)` — full base
2. `copy_tree(templates-api-{framework}/, dest/)` — framework overlay
3. If `--auth`: `copy_tree(templates-{auth}-{framework}/, dest/)` — auth API overlay
4. If `--auth`: `copy_tree(templates-{auth}-frontend/, dest/)` — auth frontend overlay

## `env_generator.py`

Generates the `api/.env` file at scaffold time. Picks different environment variables based on the variant:

- **Database**: local Docker PostgreSQL URL for non-supabase; Supabase connection strings for supabase variants
- **Auth**: `AUTH_TOKEN` for token variants; `SUPABASE_URL` + `SUPABASE_PUBLISHABLE_KEY` for supabase
- **Server**: `ENVIRONMENT`/`DEBUG` for FastAPI; `NODE_ENV` for NestJS
- **LLM**: Azure OpenAI + alternative provider keys (shared across all variants)

Can be run standalone: `python -m project_initializer.env_generator fastapi --auth token --dest api/.env`

## Repository Structure

```
project-initializer/
├── project_initializer/            # CLI package (pip installable)
│   ├── cli.py                      # Entry point, argument parsing, copy_tree()
│   ├── env_generator.py            # Variant-specific .env generation
│   ├── py.typed                    # PEP 561 type marker
│   └── templates*/                 # 9 template overlay directories (see above)
├── .vscode/                        # VS Code debug configs for all 6 variants
│   ├── launch.json                 # One-click debug for each variant
│   ├── tasks.json                  # Pre-launch: scaffold + env + BAML generate
│   ├── settings.json               # Editor settings
│   └── extensions.json             # Recommended extensions
├── .github/workflows/              # CI: test scaffolding for FastAPI + NestJS
├── pyproject.toml                  # Package config with console_scripts
├── MANIFEST.in                     # sdist inclusion for all template dirs
└── CONTRIBUTING.md                 # Contributor setup guide
```

## VS Code Development Setup

The `.vscode/` directory provides one-click debug for all 6 variants via `launch.json`. Each launch config has a `preLaunchTask` in `tasks.json` that:

1. Scaffolds the test project (if not already present)
2. Generates the `api/.env` from the root `.env`
3. Runs `baml-cli generate` (FastAPI) or `npx baml-cli generate` (NestJS)

This means contributors can press F5 and get a running API immediately.

## FastAPI Template (`api/` in FastAPI variants)

Layered architecture:

| Layer | Purpose |
|-------|---------|
| `app/api/v1/` | Routes with `/api/v1` prefix |
| `app/services/` | Business logic |
| `app/repositories/` | Data access (BaseRepository with CRUD) |
| `app/models/` | SQLAlchemy models (inherit BaseModel for UUID + timestamps) |
| `app/schemas/` | Pydantic schemas (`<Entity>Create`, `<Entity>Update`, `<Entity>Response`) |
| `app/middleware/` | Security, logging, rate limiting |
| `baml_src/` | LLM function definitions (regenerate client with `baml-cli generate`) |

Key commands:
```bash
pytest                                            # Run tests
alembic upgrade head                              # Apply migrations
alembic revision --autogenerate -m "description"  # Create migration
```

## NestJS Template (`api/` in NestJS variants)

Modular architecture:

| Layer | Purpose |
|-------|---------|
| `src/modules/` | Feature modules (controllers + services + DTOs) |
| `src/common/` | Shared guards, interceptors, filters |
| `prisma/` | Prisma schema and migrations |
| `baml_src/` | LLM function definitions (regenerate with `npx baml-cli generate`) |

Key commands:
```bash
npm run start:dev                     # Dev server with hot reload
npm run test                          # Unit tests
npx prisma migrate dev                # Create + apply migration
npx prisma generate                   # Regenerate Prisma client
```

## Frontend Template (`frontend/`)

Angular 21 with Tailwind CSS. Key conventions:

- **Standalone components only** (no NgModules, don't set `standalone: true` — it's default)
- **Signals for state**: Use `signal()`, `computed()`, `input()`, `output()`
- **Native control flow**: Use `@if`, `@for`, `@switch` instead of `*ngIf`, `*ngFor`
- **OnPush change detection**: Set `changeDetection: ChangeDetectionStrategy.OnPush`
- **Inject function**: Use `inject()` instead of constructor injection

Key commands:
```bash
ng serve                    # Dev server on :4200
ng build                    # Production build
ng test                     # Unit tests
```

## Docker Services

Non-supabase variants:

| Service | Port | Description |
|---------|------|-------------|
| `db` | 5433:5432 | PostgreSQL 16 |
| `adminer` | 8080:8080 | Database management UI |
| `api` | 8000:8000 | Backend with hot reload |
| `frontend` | 4200:80 | Angular + nginx (proxies `/api/` to backend) |

Supabase variants omit `db` and `adminer` (Supabase hosts the database).

## Template Sync

After modifying template source files, re-install and re-scaffold to test:
```bash
pip install -e .
project-initializer test-fastapi --fastapi --force
```
