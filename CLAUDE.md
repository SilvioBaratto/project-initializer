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
- `--async-db` — add the opt-in async SQLAlchemy path (FastAPI only): merges the `templates-asyncdb-fastapi` overlay and adds `asyncpg` + `sqlalchemy[asyncio]` to `api/pyproject.toml` (`aiosqlite` joins its `dev` extra). The sync path stays the default. **Cannot be combined with `--nestjs` or `--scope frontend`** (it is an api concern).
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
Contains the Angular frontend, root configs (`.env.example`, `.gitignore`), and shared `.vscode/` setup. Copied for every variant. For the api scopes the CLI then overwrites the root `.env.example` with the generated one (see `env_generator.py`).

### Layer 2: Framework API (`templates-api-{framework}/`)
Adds the `api/` directory, `docker-compose.yml`, and `frontend/nginx.conf` for the chosen framework. These differ between FastAPI (Python Dockerfile, SQLAlchemy) and NestJS (Node Dockerfile, Prisma).

### Layer 3a: Auth API Overlay (`templates-{auth}-{framework}/`)
Replaces, by path, the few API files that decide who the caller is, and adds the files that implement it. Only applied when `--auth` is specified. An overlay ships only what differs from the base: a copy of a base file silently forks it, so the base keeps every fix (see the FastAPI and NestJS template sections for each stack's seam files).

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
├── env_generator.py                # Generates the root .env (with secrets) and .env.example (blank secrets)
├── file_transforms.py              # Compose/nginx/pyproject text transforms
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

After the layers merge, `copy_template()` writes the root `.env` (generated secrets) and `.env.example` (blank secrets) for the api scopes, and the six generated docs.

#### File transforms (`file_transforms.py`)

Layers carry an optional transform applied to file text during the copy:

- `filter_compose(text, scope)` — drops the `frontend` service from `docker-compose.yml` for `--scope api`
- `generate_frontend_compose()` — emits the minimal frontend-only compose for `--scope frontend`
- `strip_nginx_proxy_block(text)` — removes the `/api/` proxy block from `nginx.conf` for `--scope frontend`
- `append_async_dependencies(text)` — adds `asyncpg` + `sqlalchemy[asyncio]` to the `dependencies` array of `pyproject.toml` (and `aiosqlite` to its `dev` extra) for `--async-db`

Because the async overlay ships no `pyproject.toml`, the dependencies transform is composed (via `_combine()`) onto whichever earlier layers do carry one.

#### Scope-based layer selection

`select_layers(scope, framework, auth, async_db)` (in `cli.py`) decides which layers above are merged, and `validate_scope()` rejects illegal combinations. The `frontend` branch must **not** consult `framework` — it is scope-only.

- **`fullstack`** (default) — all layers above, as listed.
- **`api`** — skips the `frontend/` subtree from every layer and applies a transform that drops the `frontend` service from `docker-compose.yml`. Writes the root `.env` and `.env.example`.
- **`frontend`** — copies the base layer only (no api framework/auth overlays) and strips the `/api/` proxy block from `nginx.conf`. No `.env`; emits a minimal frontend-only `docker-compose.yml`.
- Root configs (`.env.example`, `.gitignore`, `.vscode/`) are copied for **every** scope, and the root `README.md`/`CLAUDE.md` are generated for every scope.

## `env_generator.py`

Generates the root `.env` and `.env.example` at scaffold time (`cli._write_env_files()`), assembling per-variant sections. Non-secret values come from `env_defaults.env` (or the `source_env` dict a caller passes). The no-auth and token variants then run `docker compose up` with no edits; supabase needs its project URLs and keys, and entra its app registration ids, because their defaults are placeholders. Secrets never have a default.

- **Secrets**: `GENERATED_SECRET_KEYS` (`AUTH_TOKEN`, `JWT_SECRET_KEY`) get a fresh `secrets.token_urlsafe(32)` value (43 characters) in the `.env`. The `.env.example` leaves them blank, because it is the file a project commits (`use_placeholders=True`). Re-scaffolding over an existing `.env` keeps the secrets it already holds. A generated secret only fills a key that is blank or still the legacy `changeme`; any other value in the source wins.
- **Database**: local Docker PostgreSQL URL for non-supabase; Supabase connection strings for supabase variants (FastAPI adds `DATABASE_SSL_MODE=require` and `DATABASE_POOL_RECYCLE=300`; both default Supabase URLs already carry `sslmode=require`, so the generated Supabase `.env` meets the staging/production database TLS rule of the FastAPI template, and the NestJS pooler URL meets the production rule of the NestJS one. Neither generated file sets the opt-outs `DATABASE_ALLOW_INSECURE_TRANSPORT` and `DB_ALLOW_INSECURE_TRANSPORT`)
- **Auth**: `AUTH_TOKEN` (+ `JWT_SECRET_KEY`, FastAPI only) for token variants; `SUPABASE_URL` + `SUPABASE_PUBLISHABLE_KEY` for supabase (no `SUPABASE_SECRET_KEY`: neither backend reads it); tenant/client/scope ids for entra
- **Server**: `ENVIRONMENT`/`DEBUG=false` for FastAPI; `NODE_ENV=development` for NestJS. That value suits the compose `dev` target, which installs devDependencies (`pino-pretty` is one) and runs `start:dev`; the production image sets `NODE_ENV=production` itself and `.dockerignore` keeps `.env` out of it, so a comment in the file warns against passing it to that image. `tests/test_env_generator_runtime_defaults.py` pins the pairing
- **Compose topology**: `API_HOST_PORT`, `FRONTEND_HOST_PORT` (frontend scopes), `DB_HOST_PORT` + `ADMINER_HOST_PORT` (both omitted for supabase — no local `db`/`adminer` services). Read by `docker-compose.yml` as `${VAR:-default}`, not by the app; an unset var falls back to the same fixed port used before the vars existed. Every published host port belongs here — a literal one collides across projects.

Can be run standalone: `python -m project_initializer.env_generator fastapi --auth token --source .env --dest .env.new`. It generates a secret for every key the source leaves blank and keeps the ones it holds.

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
│   ├── file_transforms.py          # Compose/nginx/pyproject transforms
│   ├── env_defaults.env            # Default env values
│   ├── py.typed                    # PEP 561 type marker
│   └── templates*/                 # 13 template overlay directories (see above)
├── .vscode/                        # VS Code debug configs for all 8 variants
│   ├── launch.json                 # One-click debug for each variant
│   ├── tasks.json                  # Pre-launch: scaffold + env (+ npm install for NestJS)
│   ├── settings.json               # Editor settings
│   └── extensions.json             # Recommended extensions
├── tests/                          # Pytest suite for the CLI itself
├── reference/                      # Design notes and comparisons
├── .github/workflows/              # CI: scaffold every variant, then run each scaffolded variant's own suites
├── pyproject.toml                  # Package config with console_scripts
├── MANIFEST.in                     # sdist inclusion for all template dirs
└── CONTRIBUTING.md                 # Contributor setup guide
```

Runtime dependencies: `typer`, `questionary`, `rich`. Dev extras: `ruff`, `pytest`, `hypothesis`, `pyyaml`.

## VS Code Development Setup

The `.vscode/` directory provides one-click debug for all 8 variants via `launch.json`. Each launch config has a `preLaunchTask` in `tasks.json` that:

1. Scaffolds the test project (if not already present)
2. Generates the root `.env` for the variant (`env_generator`)
3. Installs the API dependencies (NestJS only)

This means contributors can press F5 and get a running API immediately.

## FastAPI Template (`api/` in FastAPI variants)

**Hexagonal (ports & adapters) architecture.** Dependencies point inward only: `api` → `application` → `domain`, with `infrastructure` implementing the domain's ports.

| Layer | Path | Purpose |
|-------|------|---------|
| **domain** | `app/domain/constants.py` | Business limits shared by schemas, ORM and services (migrations keep their own literals) |
| | `app/domain/entities/` | Frozen dataclasses (`Item`, `AuthenticatedUser`); invariants raise `DomainValidationError` |
| | `app/domain/ports/` | `runtime_checkable` Protocols: `ItemRepositoryPort`, `UnitOfWorkPort`, `TokenVerifierPort` |
| | `app/domain/exceptions.py` | `DomainError` hierarchy: `public_message` goes to the client, `log_context` to the log; no HTTP status |
| | `app/domain/services/` | Pure domain services |
| **application** | `app/application/services/` | `ItemService`: orchestrates ports, commits after a successful write |
| | `app/application/commands/`, `dto/` | Commands in, DTOs out; entities never leave the layer |
| **infrastructure** | `app/infrastructure/settings.py` | `Settings`: Literal-validated, `DEBUG` off by default and refused outside development |
| | `app/infrastructure/auth_settings.py` | The auth-settings seam: empty in the base, replaced by each auth overlay |
| | `app/infrastructure/database.py`, `circuit_breaker.py`, `errors.py`, `health.py` | Sync pooled engine behind a circuit breaker that counts connectivity failures only; driver errors translated to domain errors (deadlocks to `ConflictError`); readiness probe; the shutdown-hook and readiness-probe registries that optional components such as the async overlay use |
| | `app/infrastructure/orm/`, `repositories/`, `unit_of_work.py` | SQLAlchemy records (mixins in `orm/base.py` supply string UUID keys and timestamps), port adapters, commit/rollback |
| | `app/infrastructure/structured_logging.py`, `request_context.py` | JSON logs that carry the request id |
| | `app/infrastructure/log_level.py` | `reload_log_level_on_sighup`: SIGHUP re-reads `LOG_LEVEL`; on a reload the `.env` file wins over the process environment |
| | `app/infrastructure/migration_safety.py` | `preserve_and_drop_table` and `preserve_and_drop_column`: data-preserving downgrades, backups in the PostgreSQL schema `migration_backup` |
| | `app/infrastructure/config.py`, `audit.py` | Walk-up `.env` loader; audit-log helper (ids only) |
| **api** | `app/api/deps.py` | Composition root: binds adapters to services. **Never replaced by an overlay** |
| | `app/api/auth_deps.py` | The auth seam: `get_current_user`, `CurrentUser`. Replaced by each auth overlay |
| | `app/api/bearer.py`, `authorization.py`, `pagination.py` | Length-capped bearer extraction, `require_roles`, bounded `skip`/`limit` |
| | `app/api/errors.py`, `handlers.py`, `schemas/errors.py` | One error envelope; the only domain-error → HTTP status table |
| | `app/api/docs.py`, `health.py` | Swagger/ReDoc routes (only when docs are enabled); `/`, `/health`, `/health/ready` |
| | `app/api/schemas/`, `middleware/`, `v1/` | Pydantic schemas (`<Entity>Create`, `<Entity>Update`, `<Entity>Response`, `NulFreeStr` for text); request logging, security headers, the catch-all that answers an unhandled exception with the generic 500 envelope, rate limiting; routes under `/api/v1` |
| **schema** | `alembic/` | Alembic owns the schema (the app never calls `create_all`); every migration ships a data-preserving `downgrade()` |

### Dependency rule (enforced by tests)

`api/tests/unit/test_architecture.py` parses every module with the stdlib `ast`, resolves relative imports, and fails the build on an import outside what the layer may use. The inner layers are an allowlist, not a denylist: a denylist is silent about every package nobody thought to name, while an allowlist fails on the first third-party import.

- `app/domain` may import the standard library and `app.domain`, nothing else
- `app/application` may import the standard library, `app.domain` and `app.application`, nothing else
- neither inner layer calls `importlib.import_module` or `__import__`, because a dynamic import hides a dependency from the scan
- `app/infrastructure` must not import `app.api` or `app.main`
- `app/api` must not import `app.infrastructure.repositories`, `app.infrastructure.orm` or `get_db`, except in the composition roots `api/deps.py` and `api/auth_deps.py`

When adding a feature: define the entity and its port in `domain/`, write the command, DTO and service in `application/` against the port and `UnitOfWorkPort`, implement the port in `infrastructure/repositories/` with an Alembic migration, and wire the route in `api/v1/endpoints/`, with `api/deps.py` supplying the concrete repository.

Key commands:
```bash
pytest                                            # Run tests; fails below 75% branch coverage of app/
pytest -m unit --no-cov                           # One level or one file needs --no-cov (the gate needs the whole suite)
alembic upgrade head                              # Apply migrations
alembic downgrade -1                              # Roll the newest migration back (rows are kept)
alembic revision --autogenerate --rev-id 0003_add_widget -m "add widget"  # Create migration
```

`pytest.ini` of the template enforces the coverage gate (`--cov-fail-under=75`, branch coverage). `tests/test_asyncdb_overlay.py` runs a single scaffolded test file in a subprocess, so it passes `--no-cov`.

To verify a FastAPI change, scaffold all five variants (none, token, supabase, entra, `--async-db`) and run `pip install ".[dev]" && pytest -q` in each `api/`. CI does the same in `test-variant-suites`.

### The auth seam: overlays replace by path, never copy a base file

Layers overwrite by path, so an overlay file that duplicates a base file forks it silently and the base's fixes stop reaching that variant. A FastAPI overlay replaces only:

- `app/api/auth_deps.py` (`get_current_user`, `CurrentUser`, and `get_token_verifier` in the auth variants)
- `app/infrastructure/auth_settings.py` (an `AuthSettings` mixin that `Settings` inherits, with `validate_auth_secrets(production_like=...)`)
- `tests/auth_test_env.py` (the variables the tests need) and `tests/integration/test_auth.py`

and adds its own files: **token** adds `domain/entities/user.py`, the user and credential ports, `AuthService` (login, access-token use) and `RegistrationService` (`registration.py`, account creation, needs no signing key), `infrastructure/auth/static_token.py`, `security.py`, `repositories/user.py` and its routes in `v1/endpoints/auth.py` (the one base route file it replaces, to keep `/me`); **supabase** adds `infrastructure/auth/supabase.py`, replaces `orm/user.py` with a `profiles` model plus the matching migration, and ships its own `pyproject.toml`, `entrypoint.sh` (no local db to wait for) and `docker-compose.yml`; **entra** adds `infrastructure/auth/entra.py`, `entra_jwks.py` (`CooldownSigningKeyResolver`: unknown-`kid` reloads of the key set at most once per `ENTRA_JWKS_REFRESH_COOLDOWN`), `tests/entra_tokens.py` and `PyJWT[crypto]==2.15.1`, and inherits the base compose and entrypoint because it uses the local Postgres. An overlay must not ship `deps.py`, `settings.py`, `v1/router.py` or a `.env.example`: `tests/test_entra_fastapi_overlay.py` fails if one appears.

Everything an overlay must keep stable is a contract in the base: routes import only `CurrentUser`; verifiers implement `TokenVerifierPort` and raise `AuthenticationError` (401), `AuthorizationError` (403) or `ExternalServiceError` (503); the base tests override `get_current_user`, so they pass unchanged in every variant.

### Alembic migrations — own the schema, and mind the overlay

Alembic is the only thing that creates tables: `entrypoint.sh` runs `alembic upgrade head`, and the runtime `create_all` was removed on purpose. So a model change must ship its migration in the same edit; `tests/integration/test_migrations.py` (in the scaffold) compares the migrated schema with the ORM and fails otherwise.

Which layer owns a migration follows its ORM model: the base carries `0001_create_items_table.py` and `0002_create_users_table.py` (`users`, used by the token variant, and present in none and entra), and `templates-supabase-fastapi` carries a `0002_create_users_table.py` that creates `profiles`. **The supabase migration reuses the base migration's file name on purpose** (revision `0002_create_profiles`): layers overwrite by path, so the identical name makes it *replace* the base file, whereas a different name would leave both and a supabase scaffold would create a stray `users` table next to `profiles`.

The supabase layer also ships `0003_enable_row_level_security.py`, which has no base counterpart. It enables row level security on `items`, `profiles` and `alembic_version` without a policy (the Data API roles can touch nothing, the table-owner connection of the API is unaffected) and does nothing on SQLite. A table added to a supabase project needs its own `ENABLE ROW LEVEL SECURITY` statement.

Every downgrade that drops a table goes through `preserve_and_drop_table`, and one that drops a column through `preserve_and_drop_column`. On PostgreSQL the rows are copied to `migration_backup.<table>__rollback_<UTC YYYYmmddHHMMSSffffff>` (a schema the Supabase Data API does not expose, created closed; the microsecond suffix keeps two rollbacks inside one second apart), on SQLite next to the table. The shared `alembic/script.py.mako` renders an empty downgrade as `raise NotImplementedError`, and `process_revision_directives` in `env.py` rewrites a drafted `op.drop_table` into `preserve_and_drop_table`. `alembic.ini` sets `file_template = %%(rev)s`, so create revisions with `--rev-id <NNNN>_<slug>` (at most 32 characters). `env.py` logs through the application's structured logger and, when `config.attributes["embedded"]` is set, leaves the environment and logging to the caller; the first migration creates `idx_items_created_at`. Roll back with `alembic downgrade -1`, newest first. `tests/test_fastapi_migrations.py` asserts each variant's merged `alembic/versions` creates exactly the tables its ORM maps to (`users` + `items`, or `profiles` + `items` and no `users`), that every migration has a `downgrade()` that preserves rows, that the supabase 0002 file replaces the base one by name, that 0003 exists only in the supabase layer and secures every table, and that backups go to the `migration_backup` schema.

### Python metadata: `pyproject.toml` only

For Python projects, dependencies and the version live in `pyproject.toml` and nowhere else. There is no `requirements.txt` in this repo or in any scaffold, and no `__version__` or version literal in `__init__.py` or any other module.

- **This CLI**: `[project] version` of the root `pyproject.toml`. `--version` reads the installed package metadata (`_installed_version()` in `cli.py`). After a bump, `pip install -e .` again, or `--version` keeps the old number.
- **FastAPI scaffolds**: `api/pyproject.toml` in `templates-api-fastapi` (also used by the token overlay), `templates-supabase-fastapi` and `templates-entra-fastapi`. Runtime dependencies in `dependencies`, test tooling in the `dev` extra, `[tool.setuptools] packages = []` so the install adds metadata and dependencies but never the code. `Settings.version` reads the installed metadata under `DISTRIBUTION_NAME`, which must equal `[project] name` (`tests/unit/test_version_source.py` checks it). The Dockerfile runs `pip install .`; developers and CI run `pip install ".[dev]"`.
- `--async-db` edits the arrays of `pyproject.toml` through `append_async_dependencies()`, which raises when an array is missing instead of dropping the dependencies silently.
- NestJS keeps its version in `package.json`; the rule does not apply there.
- `tests/test_python_metadata_single_source.py` guards all of this.

### Settings, async path and traceability

`Settings` rejects a bad value at start-up without echoing it (`hide_input_in_errors`), defaults `DEBUG` to false and refuses it and `DATABASE_ECHO` outside development, refuses `CORS_ORIGINS=*` in staging and production (credentialed CORS is never allowed), serves the interactive docs except in production (`API_DOCS_ENABLED` overrides), and enables the in-memory rate limiter only in staging and production. That limiter keys on the client address, so it is correct only behind a proxy listed in `FORWARDED_ALLOW_IPS`; behind several replicas it needs a gateway or an external shared store. The generated api docs say so.

The container waits for the database named in `DATABASE_URL`, bounded by `DB_WAIT_TIMEOUT_SECONDS` (default 60), runs as an unprivileged user over root-owned code, and starts uvicorn with `--no-access-log`; `main.py` and `structured_logging.configure_logging` route server errors through the JSON formatter and write the one `http.request` line per request (its `path` is the route template). `set_log_level()` changes the level of a running process and has no route. Audit events are `audit.action` on the logger `app.audit`, pinned to INFO whatever `LOG_LEVEL` is. `tests/test_docker_runtime_invariants.py` pins the Dockerfile, entrypoint and compose commands.

In `staging` and `production` `Settings` refuses a database connection that is not TLS-protected, for `DATABASE_URL` and `DIRECT_DATABASE_URL`: the effective mode must be `require`, `verify-ca` or `verify-full`, where `DATABASE_SSL_MODE` wins over the `sslmode` of the URL. `development`, `test` and SQLite are exempt, and `DATABASE_ALLOW_INSECURE_TRANSPORT=true` is the documented opt-out for a database on the same host or a private network without TLS. The bundled compose `db` serves no TLS, so `ENVIRONMENT=production docker compose up` needs the opt-out. The error never contains the URL. The generated Supabase `.env` already meets the rule.

SIGHUP reloads `LOG_LEVEL` (`app/infrastructure/log_level.py`, run by the lifespan): the `.env` file wins over the process environment on a reload, an invalid value is ignored with `log_level.reload_rejected`, and the handler is restored on shutdown. A terminal hang-up also sends SIGHUP, and without a `.env` file (Docker) a reload re-applies the start-up value. The token overlay writes the audit actions `user.register` and `user.login` as background tasks, naming the account by id only; `AccessTokenDTO` gained `user_id` for that and `TokenResponse` does not expose it.

`--async-db` adds `database_async.py`, `repositories/item_async.py`, `unit_of_work_async.py` and the async ports. It is opt-in and no route uses it, but it is wired into the lifecycle without touching `main.py`: importing `database_async` registers `dispose_async_engine` through `register_shutdown_hook` (run by the lifespan via `run_shutdown_hooks`) and its probe through `register_readiness_probe`, so `/health/ready` reports it under `additional_databases`.

The templates ship no requirement IDs. Each test carries a `Validates module.func()` docstring line, and `@pytest.mark.requirement("<id>")` is a registered marker; the generated docs describe the convention and each generated project supplies its own IDs, so test traceability is a convention here, not something the templates enforce.

## NestJS Template (`api/` in NestJS variants)

Modular architecture with **one root module for every variant**. What differs between variants enters through a seam (`src/app.auth.ts`), not through a copy of the module.

| Layer | Purpose |
|-------|---------|
| `src/app.module.ts` | The single root module, shipped by the base layer only. Lists `ThrottlerGuard` first, spreads `AUTH_GUARDS`, then `RolesGuard` last; spreads `AUTH_MODULES` into its imports |
| `src/app.auth.ts` | The auth seam. Empty in the base (every route public); each overlay (token, supabase, entra) **replaces it by path** with `[AuthModule]` and `{ provide: APP_GUARD, useClass: AccessTokenGuard }` |
| `src/app.setup.ts` | `configureApp()`: logger, shutdown hooks, `TRUST_PROXY_HOPS`, helmet, CORS, the 512 KiB JSON body limit (413 above it), `api/v1` prefix, global exception filters. `main.ts` and the e2e harness both call it |
| `src/common/auth/` | Shared `AccessTokenGuard`, bearer parsing, the `ACCESS_TOKEN_VERIFIER` port, `GET /auth/me`, and `@Roles` with the global `RolesGuard`. It also ships in the no-auth variant, where nothing wires the access-token guard |
| `src/common/audit/` | `AuditLogger` and `AuditModule`: the audit trail, written through a pino child pinned to `info` |
| `src/modules/` | Feature modules: health, items, test. `auth` exists only in an overlay |
| `src/config/` | `env.base.ts` (shared env schema, `createEnvValidator`, the production database TLS rule), `log-level-reload.ts` (SIGHUP reloads `LOG_LEVEL`). Each overlay replaces `env.validation.ts` with a schema that `extend`s the base one |
| `src/prisma/`, `src/common/resilience/` | `PrismaModule` (not global), `PrismaService`, the database circuit breaker |
| `prisma/` | Schema and migrations; every migration directory ships a `down.sql` |
| `test/support/` | e2e harness (`create-e2e-app.ts`), test doubles, `test-env.ts`. Overlays replace `auth-test-env.ts` |

Key commands:
```bash
npm run start:dev                     # Dev server with hot reload
npm run test                          # Unit tests
npm run test:cov                      # Unit tests + 75% line/statement gate
npm run test:e2e                      # e2e on in-memory fakes, no Postgres
npm run lint                          # ESLint (type-checked), --max-warnings 0
npm run format:check                  # Prettier; `npm run format` fixes
npx prisma migrate dev                # Create + apply migration
npx prisma generate                   # Regenerate Prisma client
```

To verify a NestJS change, scaffold all four variants and run, in each `api/`: `npm ci`, `npx prisma generate`, `npx tsc --noEmit -p tsconfig.json`, `npm run lint`, `npm run format:check`, `npm run test:cov`, `npm run test:e2e`.

### Overlay files replace by path; never copy a base file

Layers overwrite by path, so an overlay file that duplicates a base file forks it silently. An overlay therefore ships only what differs:

- **token**: `src/app.auth.ts`, `src/config/env.validation.ts`, `src/modules/auth/*` (verifier, `POST /auth/validate`), `test/support/auth-test-env.ts`, `test/auth.e2e-spec.ts`, `.env.example`. No `package.json`.
- **supabase**: the same seam files plus `package.json` and lock (adds `@supabase/supabase-js`), `prisma/schema.prisma` (`profiles`), its own init migration and the RLS migration, and its own `docker-compose.yml` and `entrypoint.sh` (no local `db`).
- **entra**: the same seam files plus `package.json` and lock (adds `jsonwebtoken` and `jwks-rsa`). It uses the local Postgres, so it **inherits** the base `schema.prisma`, `docker-compose.yml` and `entrypoint.sh` (which waits for the db).

An overlay must not ship `src/app.module.ts`, `tsconfig.json`, `test/jest-e2e.json` or a per-variant guard: `tests/test_entra_nestjs_overlay.py` fails if one appears, because a copy of the root module would drop the global pipe and interceptor.

### Prisma migrations — ship them, and mind the overlay

The entrypoint runs `prisma migrate deploy`, which is a **no-op when no migration exists** ("No migration found in prisma/migrations", exit 0) — the stack then starts against an empty database and `/health/readiness` reports `database: down`. So a schema change must ship its migration in the same edit.

Which overlay owns a migration follows its `schema.prisma`: `templates-api-nestjs` (base: `users`, plus the shared `items` migration) and `templates-supabase-nestjs` (`profiles`) each carry an init migration. Supabase inherits the base `create_items` migration and adds `20261121000100_enable_row_level_security`. `templates-entra-nestjs` ships no schema and `templates-token-nestjs` has none, so both inherit the base migrations.

**The supabase init migration reuses the base migration's directory name on purpose.** Layers overwrite by path, so an identical name means supabase's `migration.sql` *replaces* the base's; a different name would leave both and a supabase scaffold would create a stray `users` table alongside `profiles`. Regenerate against a live DB from a scaffolded project (the standalone CLI needs the project's `prisma.config.ts` for the datasource URL):

```bash
docker compose run --rm --entrypoint sh api -c "npx prisma migrate dev --name init"
```

**The same rule covers `down.sql`.** Every migration directory ships a `down.sql`, and the supabase init `down.sql` must exist so that it replaces the base one by path. Without it the base `down.sql` (which drops `users`) would sit next to the supabase `migration.sql`.

**Rollback is one command per migration, newest first**, and there is no second step:

```bash
npx prisma db execute --file prisma/migrations/<dir>/down.sql
```

Each `down.sql` copies its table to `migration_backup."<table>__rollback_<UTC YYYYMMDDHHMMSSuuuuuu>"` before dropping it (a schema outside `public`, because the Data API would serve a backup in `public`; the microsecond suffix comes from `clock_timestamp()` so back-to-back rollbacks cannot collide), then deletes its own row from `_prisma_migrations` as its last statement, so `prisma migrate deploy` applies the migration again. Never add `prisma migrate resolve --rolled-back` to the procedure: Prisma rejects it with P3012 for a migration that finished successfully. A `down.sql` is not generated; write it by hand with the migration.

**Supabase tables need Row Level Security.** The Data API is reachable with the publishable key, so a table without RLS is readable and writable by anyone holding it. The RLS migration enables it with no policies on `profiles`, `items` and Prisma's own `_prisma_migrations` (which sits in `public` too): the API connects as the table owner, which bypasses RLS, and the Data API is denied. A new table needs its own `ENABLE ROW LEVEL SECURITY` statement in a supabase migration. Check with `prisma migrate diff --from-config-datasource --to-schema prisma/schema.prisma --script` that RLS does not show as drift.

`tests/test_nestjs_migrations.py` asserts each variant's migrations create exactly its tables (`users` or `profiles`, plus `items`), that every migration has a `down.sql` that un-records itself as its last statement, that each backs up into `migration_backup` and never `public` under a microsecond-stamped name, that the supabase init `down.sql` drops `profiles` and not `users`, and that every supabase table, `_prisma_migrations` included, has an RLS statement. The exact lists are also what catches the stacking mistake. `tests/test_nestjs_auth_seam.py` keeps the three overlay copies of `src/app.auth.ts` byte-identical.

### Lint, format, coverage

The three layers that ship a `package.json` (base, supabase, entra) carry the same toolchain: `lint`, `format`, `format:check`, a `coverageThreshold` of 75 lines and statements, and `setupFiles` pointing at `test/support/test-env.ts` (the env schema is validated at import time, so the variables must exist before any spec). Keep their `jest` blocks identical outside `dependencies`; `tests/test_nestjs_build_config.py` checks it. The lint packages are pinned exactly, and `typescript-eslint` only supports the TypeScript versions its peer range lists, so bump the two together.

### Database TLS, roles, audit and log-level reload

With `NODE_ENV=production` `baseEnvSchema` refuses a `DATABASE_URL` unless every `sslmode` in it is `require`, `verify-ca` or `verify-full` (case-sensitive); `DB_ALLOW_INSECURE_TRANSPORT=true` (a boolean, default `false`) opts out. The message is fixed and names no URL or host. The compose stack runs `NODE_ENV=development` and is unaffected, the Supabase pooler URL passes, and `DIRECT_URL` is not checked because only migrations use it.

`@Roles(...roles)` and `RolesGuard` (`src/common/auth/roles.*`) implement role-based access control. The guard is registered last, `[ThrottlerGuard, ...AUTH_GUARDS, RolesGuard]`. A route without `@Roles` passes; with it the caller needs one of the roles (exact, case-sensitive), and no identity, an empty `@Roles()` or a mismatch answers 403 with the generic message, never listing the required roles. Handler metadata overrides class metadata, a denial logs one warn with the opaque `actorId`, and no sample route uses it. The base no-auth variant has no identity, so every `@Roles` route is denied (fail closed).

`AuditLogger.record(action, resourceId, actorId)` writes one `audit.action` line through a pino child pinned to `info`, so `LOG_LEVEL=warn`, `error` or `silent` cannot silence it. `ItemsService` records `item.create`, `item.update` and `item.delete` after the repository call succeeded, with the user id or the constant `anonymous` as actor; its method signatures take `actorId`.

`SIGHUP` reloads `LOG_LEVEL` (`src/config/log-level-reload.ts`): it reads `../.env` then `.env` with dotenv's parser, without mutating `process.env`. A value the operator exported that differs from the file's start-up value wins, otherwise the edited file wins. An invalid value is ignored with one warning that names only the accepted set. Nothing is installed on Windows, the listener is removed when the server closes, a terminal hang-up also sends SIGHUP, and without a `.env` file (Docker) a reload re-applies the start-up value. `tests/test_docs_compliance_sync.py` pins the generated docs for all of this.

### Secrets and traceability

The token variant needs `AUTH_TOKEN` of at least 32 characters, in the `token68` alphabet a bearer header carries. The CLI generates it into the scaffolded `.env` and leaves it empty in `.env.example` (see `env_generator.py`).

The templates ship no requirement IDs. The generated docs describe the `[REQ-<AREA>-<NNN>]` test-title convention and each generated project supplies its own IDs, so test traceability is a convention here, not something the templates enforce.

### package-lock.json — regenerate on linux

The API Dockerfile runs `npm ci`, which hard-fails on **any** drift between `package.json` and its lock, so a stale lock means the image never builds. After changing a NestJS dependency, regenerate the lock **inside the build's own platform** — a lock resolved on macOS/arm64 pins different native/optional packages (`@emnapi/*`, …) and `npm ci` then rejects it on `node:22-alpine`:

```bash
docker run --rm -v "$PWD:/w" -w /w node:22-alpine npm install --package-lock-only --ignore-scripts
```

Which overlay owns a lock follows its `package.json`: `templates-api-nestjs` (base) and the overlays that ship their own `package.json` (`templates-supabase-nestjs`, `templates-entra-nestjs`) each carry one. `templates-token-nestjs` ships no `package.json`, so it must **not** carry a lock — it inherits the base pair. `tests/test_nestjs_lockfile_sync.py` checks the **layered** result for every auth mode, which is the only place the drift is visible, and pins which layers own a lock. A change to a dependency shared by all variants (anything in the base `package.json`) has to be made in the base, supabase and entra manifests, and in all three locks.

## Frontend Template (`frontend/`)

Angular 22 with Angular Material 3 (`@angular/material` + `@angular/cdk` 22.3), TypeScript 6.0 and `@lucide/angular` icons. There is no utility-class CSS framework and no PostCSS config. Key conventions:

- **Standalone components only** (no NgModules, don't set `standalone: true` — it's default)
- **Signals for state**: Use `signal()`, `computed()`, `input()`, `output()`
- **Native control flow**: Use `@if`, `@for`, `@switch` instead of `*ngIf`, `*ngFor`
- **OnPush change detection**: Set `changeDetection: ChangeDetectionStrategy.OnPush`
- **Inject function**: Use `inject()` instead of constructor injection; singleton services are declared with `@Service()`, Angular 22's shorthand for `@Injectable({ providedIn: 'root' })`
- **Three files per component**: `<name>.ts` + `<name>.html` + `<name>.css`, wired with `templateUrl` / `styleUrl`; no inline templates or styles
- **Theme and tokens**: `src/styles.scss` applies `mat.theme()` on `html` with `color-scheme: light dark` (violet primary, green tertiary, density 0). Component CSS uses only `--mat-sys-*` tokens plus the `--app-{success,warning,info}*` status roles defined there: no color literals, no `!important`, no `::ng-deep`. Tune a Material component through its token custom properties (`--mat-button-*`, `--mat-list-*`, …)
- **Light and dark**: `ThemeService` puts exactly one of `.light` / `.dark` on `<html>`; those classes only set `color-scheme`. Before Angular boots, a script in `src/index.html` pins a stored choice (`app-theme`) as an inline `color-scheme`, which `ThemeService` removes when it applies the class
- **CSP nonce**: `src/index.html` renders `<app-root ngCspNonce="CSP_NONCE">`; `frontend/nginx.conf` swaps the placeholder for `$request_id` with `sub_filter` and allows that nonce in its `Content-Security-Policy` `script-src` and `style-src`. The base and both api layers ship the same file; the supabase and entra frontend overlays ship their own, which also allows their provider in `connect-src` (and `frame-src` for Entra). `tests/test_frontend_nginx_csp.py` keeps the copies identical apart from that policy
- **Overlay panels**: dialogs, snackbars and menus render in the body-level `.cdk-overlay-container`, so their panel styles live in `src/styles/overlays/_<component>.scss` (`@use`d by `styles.scss`), selected by the `panelClass` passed to `MatDialog`, `MatBottomSheet` or `MatSnackBar`; `mat-menu` takes a static `class` instead (its `panelClass` input aliases `class`)
- **Window size classes**: `WindowSizeClassService` (`src/app/services/window-size-class.ts`) on the M3 breakpoints 600 / 840 / 1200 / 1600px, with the same literals in CSS media queries. Never the CDK `Breakpoints` presets or 768px
- **Navigation shell**: below 600px a top app bar plus a navigation bar, with a top app bar button that opens the theme and account actions (never destinations); from 600px a collapsed rail docked in `mat-sidenav`, which a toggle expands from 840px and which starts expanded from 1600px, unless the user has toggled the rail: that choice is stored in localStorage (`app-rail-expanded`, `RAIL_EXPANDED_STORAGE_KEY` in `layout.ts`) and wins at every width from 840px; never a navigation drawer
- **Icons**: registered by PascalCase name in `src/app/icons.ts` (`ICON_PROVIDER`, built with `provideLucideIcons`) and rendered as `<svg lucideIcon="Name">` (`LucideDynamicIcon`); an unregistered name throws `Unable to resolve icon '<name>'` when the icon renders. `provideLucideIcons` is not a multi provider: a second call (in a route's or a component's `providers`) replaces the registry for that injector, so every icon goes in `icons.ts`. Inside Material text, filled, outlined or tonal buttons add `matButtonIcon` (plus `iconPositionEnd` when trailing) and `[size]="18"`. Material's icon margins target `.mat-icon` only, so give the `svg` `flex-shrink: 0; margin-inline: -8px 8px` when leading (`8px -8px` when trailing, -4px instead of -8px on text buttons). The `svg` writes its whole `class` attribute, so pass classes through `class` or `[class]`, never `[class.x]`, and put `matListItemIcon` / `matListItemMeta` on a wrapping `span`
- **Specs**: Vitest through `ng test` (zoneless, `src/test-providers.ts`); prefer Angular Material test harnesses. jsdom evaluates `@media` against a fixed 1024x768 window and substitutes `var()` in `getComputedStyle()`, so specs read authored `var()` references and the compact layout through the CSSOM (`declaredValue()` in `checkbox.spec.ts`) and keep `getComputedStyle()` for literal values and "not set" checks, which it still answers

The generated `frontend/.claude/CLAUDE.md` (`generate_frontend_claude()` in `docs_generator.py`) carries the full list; change both together. `tests/test_docs_frontend_material.py` cross-checks each convention it names against the template.

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

The `project-initializer` console script imports whichever checkout `pip install -e .` points at. In a git worktree, run `PYTHONPATH=<worktree> pytest` (and `PYTHONPATH=<worktree> python -m project_initializer.cli ...` to scaffold), otherwise the tests that call the script exercise the old templates.

A scaffolded variant carries its own test suite, which the repo suite does not run: run it in each `api/` (see the FastAPI and NestJS template sections). CI runs every variant's suite in the `test-variant-suites` job.

When a template change affects what the docs say (a moved module, a new layer, a new command), update `docs_generator.py` in the same change — the generated `README.md`/`CLAUDE.md` are the only docs a scaffolded project gets, and `tests/test_docs_*.py` assert they match the templates. Behaviour a template user can notice (a route, a status code, a setting) also goes into `CHANGELOG.md` under `[Unreleased]`.

## Running the Tests: traceability of the repo suite

`pytest` runs the repo suite (see "Build & Run Commands"). Code standard 6.6 asks each test to cite its requirement ID and the code it validates. This project has no requirement tracker, so the repo suite carries **no requirement IDs**: that is the written-down adaptation (standard 1.4), and it applies to `tests/` only. The tests a scaffolded project ships follow the convention its own generated docs describe.

- Traceability is the test's `Validates ...` docstring line to the code, plus the `CHANGELOG.md` `[Unreleased]` entry of the change.
- A covered test function ends its docstring with one line `Validates <repo-relative path or dotted symbol>.`, naming the file the test really inspects, not only a helper it calls: a template file (`Validates project_initializer/templates-api-fastapi/api/alembic/versions.`), a generator function (`Validates project_initializer/env_generator.py generate_env().`) or a document. A parametrized test carries the line once, not per case.
- Covered are every test function of the modules listed in `NEW_MODULES`, plus the functions listed per older module in `TRACED_FUNCTIONS`: the tests written or rewritten in this change (a new test, or an existing one whose body or target the change altered). The other tests of those older modules are legacy: they predate the convention, carry no line yet and are not checked. The change that next touches one annotates it and lists it in `TRACED_FUNCTIONS`; a module moves to `NEW_MODULES` once all its tests carry the line.
- A new test module follows the convention and is added to `NEW_MODULES` in `tests/test_repo_test_traceability.py` in the same change. That test parses the covered modules with `ast` and fails for a covered test function whose docstring does not end with a `Validates` line, and for a `TRACED_FUNCTIONS` name that is no longer defined.
