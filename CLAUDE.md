# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a pip-installable CLI tool (`project-initializer`) that scaffolds full-stack projects in **8 variants**: 2 frameworks (FastAPI, NestJS) x 4 auth modes (none, token, supabase, entra). The repository contains the CLI package and all template files it copies.

## CLI Flags

Built on **Typer** (`app = typer.Typer()` in `cli.py`), with an interactive **questionary** wizard (`wizard.py`) for anything not passed as a flag.

```bash
project-initializer [name] [--framework fastapi|nestjs] [--fastapi | --nestjs] [--auth none|token|supabase|entra] [--scope fullstack|api|frontend] [--async-db] [--force] [--yes] [--verbose]
```

- `name` — project directory to create; defaults to `.` (current directory)
- `--framework fastapi|nestjs` — backend framework (`--fastapi` / `--nestjs` are shorthands; cannot be combined with `--framework`, and are mutually exclusive)
- `--auth none` — no authentication (default)
- `--auth token` — bearer-token authentication
- `--auth supabase` — Supabase JWT auth (replaces local DB with Supabase-hosted)
- `--auth entra` — Microsoft Entra ID (formerly Azure AD) OIDC; in-process RS256 JWT validation on both backends, MSAL login on the Angular frontend
- `--scope fullstack` (default) — scaffold both halves (`api/` + `frontend/`)
- `--scope api` — backend only: skips the `frontend/` subtree and drops the `frontend` service from `docker-compose.yml`
- `--scope frontend` — frontend only: base layer only, strips the `/api/` proxy block from `nginx.conf`; **cannot be combined with `--framework`/`--fastapi`/`--nestjs`/`--auth`/`--async-db`** (those are api concerns)
- `--async-db` — add the opt-in async SQLAlchemy path (FastAPI only): merges the `templates-asyncdb-fastapi` overlay and appends `asyncpg` + `sqlalchemy[asyncio]` to `api/requirements.txt`. The sync path stays the default. **Cannot be combined with `--nestjs` or `--scope frontend`** (it is an api concern).
- `--force` / `-f` — overwrite existing files without prompting
- `--yes` / `-y` — non-interactive: skip all prompts, apply defaults for unset options
- `--verbose` / `-V` — list every file created, in addition to the summary tree
- `--version` / `-v` — print version and exit

### Wizard vs non-interactive

`_resolve_choices()` in `cli.py` decides whether to prompt:

- **Interactive** (`sys.stdin.isatty()` and no `--yes`) — `run_wizard()` prompts only for options not already supplied as flags. A fully-flagged invocation runs zero prompts. A frontend-only scope skips the framework/auth/async-db menus entirely (they are api concerns).
- **Non-interactive** (piped stdin, or `--yes`) — `_noninteractive_defaults()` fills unset options: scope → `fullstack`, framework → `fastapi`, auth → `None`, async_db → `False`. This is what CI and the `.vscode` tasks hit.
- **Graceful degradation** — if the terminal cannot host prompts (no console screen buffer on Git Bash/mintty, closed stdin, EOF), the wizard falls back to non-interactive defaults instead of crashing. A user Ctrl-C (`SystemExit`) is re-raised, and any other wizard error propagates rather than being masked as "user chose defaults".

Flag validation (`validate_scope()`) runs **before** any prompt, so an illegal combination fails fast with a Typer `BadParameter` (exit code 2) and never reaches the wizard. Resolved values are deliberately not re-validated — the resolver always fills a concrete framework, which `validate_scope()` would misread as an explicit flag.

## Build & Run Commands

```bash
# Install CLI tool in development mode
pip install -e .

# Run the tests
pytest

# Scaffold variants for testing (--yes keeps it non-interactive)
project-initializer test-fastapi --fastapi --force --yes
project-initializer test-fastapi-token --fastapi --auth token --force --yes
project-initializer test-fastapi-supabase --fastapi --auth supabase --force --yes
project-initializer test-fastapi-entra --fastapi --auth entra --force --yes
project-initializer test-nestjs --nestjs --force --yes
project-initializer test-nestjs-token --nestjs --auth token --force --yes
project-initializer test-nestjs-supabase --nestjs --auth supabase --force --yes

# Async SQLAlchemy path (FastAPI only)
project-initializer test-fastapi-async --fastapi --async-db --force --yes

# Scaffold scope subsets (backend-only / frontend-only)
project-initializer test-api --fastapi --scope api --force --yes
project-initializer test-frontend --scope frontend --force --yes

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

Note: `README.md` and `CLAUDE.md` files are **not** part of any layer — they are generated from the flags by `docs_generator.py` after the layers merge. See "docs_generator.py" below.

### Layer 1: Shared Base (`templates/`)
Contains the Angular frontend, root configs (`.env.example`, `.gitignore`), and shared `.vscode/` setup. Copied for every variant.

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
├── templates-entra-fastapi/        # Layer 3a: entra auth for FastAPI
├── templates-entra-nestjs/         # Layer 3a: entra auth for NestJS
├── templates-entra-frontend/       # Layer 3b: entra auth frontend (shared)
├── templates-asyncdb-fastapi/      # Layer 4: opt-in async SQLAlchemy overlay (--async-db)
├── cli.py                          # Entry point — select_layers() + copy_tree()
├── wizard.py                       # Interactive questionary prompts
├── docs_generator.py               # Builds README.md / CLAUDE.md from the flags
├── env_generator.py                # Generates variant-specific api/.env
├── file_transforms.py              # Compose/nginx/requirements text transforms
├── env_defaults.env                # Default values for env generation
└── __init__.py
```

### How `select_layers()` and `copy_tree()` Merge Layers

`select_layers(scope, framework, auth, async_db)` returns an ordered list of `(src_dir, skip_subdirs, file_transform)` tuples. `copy_tree()` then walks each layer, recursively copying `src` into `dst` — creating directories as needed, skipping any subdir in `skip_subdirs`, applying `file_transform` to file contents, and overwriting files that already exist. For a `fullstack` scaffold the order is:

1. `templates/` — full base
2. `templates-api-{framework}/` — framework overlay
3. If `--auth`: `templates-{auth}-{framework}/` — auth API overlay
4. If `--auth`: `templates-{auth}-frontend/` — auth frontend overlay
5. If `--async-db` (FastAPI): `templates-asyncdb-fastapi/` — async overlay, appended last

After the layers merge, `copy_template()` generates `api/.env` (api scopes) and writes the six generated docs.

#### File transforms (`file_transforms.py`)

Layers carry an optional transform applied to file text during the copy:

- `filter_compose(text, scope)` — drops the `frontend` service from `docker-compose.yml` for `--scope api`
- `generate_frontend_compose()` — emits the minimal frontend-only compose for `--scope frontend`
- `strip_nginx_proxy_block(text)` — removes the `/api/` proxy block from `nginx.conf` for `--scope frontend`
- `append_async_requirements(text)` — appends `asyncpg` + `sqlalchemy[asyncio]` to `requirements.txt` for `--async-db`

Because the async overlay ships no `requirements.txt`, the requirements transform is composed (via `_combine()`) onto whichever earlier layers do carry one.

#### Scope-based layer selection

`select_layers(scope, framework, auth, async_db)` (in `cli.py`) decides which layers above are merged, and `validate_scope()` rejects illegal combinations. The `frontend` branch must **not** consult `framework` — it is scope-only.

- **`fullstack`** (default) — all layers above, as listed.
- **`api`** — skips the `frontend/` subtree from every layer and applies a transform that drops the `frontend` service from `docker-compose.yml`. Generates `api/.env`.
- **`frontend`** — copies the base layer only (no api framework/auth overlays) and strips the `/api/` proxy block from `nginx.conf`. No `api/.env`; emits a minimal frontend-only `docker-compose.yml`.
- Root configs (`.env.example`, `.gitignore`, `.vscode/`) are copied for **every** scope, and the root `README.md`/`CLAUDE.md` are generated for every scope.

## `env_generator.py`

Generates the `api/.env` file at scaffold time, assembling per-variant sections. Defaults come from `env_defaults.env`; values present in the root `.env` override them.

- **Database**: local Docker PostgreSQL URL for non-supabase; Supabase connection strings for supabase variants
- **Auth**: `AUTH_TOKEN` for token variants; `SUPABASE_URL` + `SUPABASE_PUBLISHABLE_KEY` for supabase; tenant/client/JWKS settings for entra
- **Server**: `ENVIRONMENT`/`DEBUG` for FastAPI; `NODE_ENV` for NestJS
- **Redis**: `REDIS_HOST` / `REDIS_PORT` (NestJS BullMQ)
- **Compose topology**: `API_HOST_PORT`, `FRONTEND_HOST_PORT` (frontend scopes), `DB_HOST_PORT` + `ADMINER_HOST_PORT` (both omitted for supabase — no local `db`/`adminer` services). Read by `docker-compose.yml` as `${VAR:-default}`, not by the app; an unset var falls back to the same fixed port used before the vars existed. Every published host port belongs here — a literal one collides across projects.
- **LLM**: Azure OpenAI + alternative provider keys (shared across all variants)

Can be run standalone: `python -m project_initializer.env_generator fastapi --auth token --dest api/.env`

## `docs_generator.py`

Generated projects' docs are **built from the flags**, not copied from static overlay files — the static per-overlay docs had to be maintained in N places and drifted (the hexagonal refactor exposed it). Six documents are produced:

| Path | Contents |
|------|----------|
| `<root>/README.md` | Human quick-start for the whole project |
| `<root>/CLAUDE.md` | Repo-level AI-assistant guidance |
| `api/README.md` | Backend quick-start |
| `api/.claude/CLAUDE.md` | Deep backend architecture guide |
| `frontend/README.md` | Angular quick-start |
| `frontend/.claude/CLAUDE.md` | Angular best-practices guidance |

Each document is assembled from a base plus per-flag sections (framework / auth / scope), so a NestJS project never mentions SQLAlchemy and a no-auth project never documents Entra. Pure string assembly — stdlib only, no I/O (`cli.py` writes the results). Scope gates which files are emitted: `api/*` docs only for api scopes, `frontend/*` docs only for frontend scopes.

**Do not add `README.md` or `CLAUDE.md` files to the template overlays** — edit `docs_generator.py` instead. `tests/test_docs_generator_selfcheck.py` and the `test_docs_*.py` suite assert the generated content stays in sync with the templates.

## Repository Structure

```
project-initializer/
├── project_initializer/            # CLI package (pip installable)
│   ├── cli.py                      # Typer entry point, select_layers(), copy_tree()
│   ├── wizard.py                   # Interactive questionary prompts
│   ├── docs_generator.py           # README.md / CLAUDE.md generation
│   ├── env_generator.py            # Variant-specific .env generation
│   ├── file_transforms.py          # Compose/nginx/requirements transforms
│   ├── env_defaults.env            # Default env values
│   ├── py.typed                    # PEP 561 type marker
│   └── templates*/                 # 13 template overlay directories (see above)
├── .vscode/                        # VS Code debug configs for all 8 variants
│   ├── launch.json                 # One-click debug for each variant
│   ├── tasks.json                  # Pre-launch: scaffold + env + BAML generate
│   ├── settings.json               # Editor settings
│   └── extensions.json             # Recommended extensions
├── tests/                          # Pytest suite for the CLI itself
├── reference/                      # Design notes and comparisons
├── .github/workflows/              # CI: test scaffolding for FastAPI + NestJS
├── pyproject.toml                  # Package config with console_scripts
├── MANIFEST.in                     # sdist inclusion for all template dirs
└── CONTRIBUTING.md                 # Contributor setup guide
```

Runtime dependencies: `typer`, `questionary`, `rich`. Dev extras: `ruff`, `pytest`, `hypothesis`, `pyyaml`.

## VS Code Development Setup

The `.vscode/` directory provides one-click debug for all 8 variants via `launch.json`. Each launch config has a `preLaunchTask` in `tasks.json` that:

1. Scaffolds the test project (if not already present)
2. Generates the `api/.env` from the root `.env`
3. Runs `baml-cli generate` (FastAPI) or `npx baml-cli generate` (NestJS)

This means contributors can press F5 and get a running API immediately.

## FastAPI Template (`api/` in FastAPI variants)

**Hexagonal (ports & adapters) architecture.** Dependencies point inward only: `api` → `application` → `domain`, with `infrastructure` implementing the domain's ports.

| Layer | Path | Purpose |
|-------|------|---------|
| **domain** | `app/domain/entities/` | Framework-free business entities (plain dataclasses) |
| | `app/domain/ports/` | Repository interfaces (e.g. `ItemRepositoryPort`, a `runtime_checkable` `Protocol`) |
| | `app/domain/exceptions.py` | Domain exception hierarchy |
| | `app/domain/services/` | Pure domain services |
| **application** | `app/application/services/` | Use-case orchestration (`item_service`, `chatbot_service`) |
| | `app/application/dto/` | Data-transfer objects between layers |
| | `app/application/commands/` | Command objects |
| **infrastructure** | `app/infrastructure/orm/` | SQLAlchemy models (inherit `Base` for UUID + timestamps) |
| | `app/infrastructure/repositories/` | Port implementations (`BaseRepository` with CRUD) |
| | `app/infrastructure/database.py` | Engine + session factory |
| | `app/infrastructure/settings.py` | Pydantic settings (was `app/config.py`) |
| | `app/infrastructure/config.py` | Logging/config wiring |
| | `app/infrastructure/audit.py` | Audit helpers |
| **api** | `app/api/v1/endpoints/` | Routes, mounted by `app/api/v1/router.py` under `/api/v1` |
| | `app/api/deps.py` | FastAPI dependencies (was `app/dependencies.py`) |
| | `app/api/schemas/` | Pydantic request/response schemas (`<Entity>Create`, `<Entity>Update`, `<Entity>Response`) |
| | `app/api/handlers.py` | Exception handlers (was `app/exceptions.py`) |
| | `app/api/middleware/` | Security, logging, rate limiting |

Outside the layering: `baml_src/` holds the LLM function definitions (regenerate the client with `baml-cli generate`; never edit `baml_client/`).

### Dependency rule (enforced by tests)

`api/tests/unit/test_architecture.py` parses every module in the inner layers with the stdlib `ast` and fails the build on any outward import:

- `app/domain` must not import `app.application`, `app.infrastructure`, `app.api`, `fastapi`, `sqlalchemy`, or `pydantic_settings`
- `app/application` must not import `app.infrastructure`, `app.api`, or `fastapi`

When adding a feature: define the entity and its port in `domain/`, orchestrate in `application/services/`, implement the port in `infrastructure/repositories/`, and wire the route in `api/v1/endpoints/` with `api/deps.py` supplying the concrete repository.

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

### package-lock.json — regenerate on linux

The API Dockerfile runs `npm ci`, which hard-fails on **any** drift between `package.json` and its lock, so a stale lock means the image never builds. After changing a NestJS dependency, regenerate the lock **inside the build's own platform** — a lock resolved on macOS/arm64 pins different native/optional packages (`@emnapi/*`, …) and `npm ci` then rejects it on `node:22-alpine`:

```bash
docker run --rm -v "$PWD:/w" -w /w node:22-alpine npm install --package-lock-only --ignore-scripts
```

Which overlay owns a lock follows its `package.json`: `templates-api-nestjs` (base) and the overlays that ship their own `package.json` (`templates-supabase-nestjs`, `templates-entra-nestjs`) each carry one. `templates-token-nestjs` ships no `package.json`, so it must **not** carry a lock — it inherits the base pair. `tests/test_nestjs_lockfile_sync.py` checks the **layered** result for every auth mode, which is the only place the drift is visible.

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

| Service | Host port | Description |
|---------|-----------|-------------|
| `db` | `${DB_HOST_PORT:-5433}`:5432 | PostgreSQL 16 |
| `adminer` | `${ADMINER_HOST_PORT:-8080}`:8080 | Database management UI |
| `api` | `${API_HOST_PORT:-8000}`:8000 | Backend with hot reload |
| `frontend` | `${FRONTEND_HOST_PORT:-4200}`:80 | Angular + nginx (proxies `/api/` to backend) |

Host ports are overridable via the generated `.env` (see the topology section in `env_generator.py`); unset vars fall back to the defaults above. Supabase variants omit `db` and `adminer` (Supabase hosts the database), and `--scope api` drops the `frontend` service.

**Every published host port must stay parametrized, and no service may pin a `container_name`.** Both are global to the Docker daemon, so a literal makes a second scaffolded project fail to `docker compose up` — with `port is already allocated` or `container name is already in use`. Without `container_name`, Compose derives `<project>-<service>-1` from the project directory, which is unique per scaffold. `tests/test_docker_runtime_invariants.py` enforces both.

## Template Sync

After modifying template source files, re-install and re-scaffold to test:
```bash
pip install -e .
project-initializer test-fastapi --fastapi --force --yes
pytest
```

When a template change affects what the docs say (a moved module, a new layer, a new command), update `docs_generator.py` in the same change — the generated `README.md`/`CLAUDE.md` are the only docs a scaffolded project gets, and `tests/test_docs_*.py` assert they match the templates.
