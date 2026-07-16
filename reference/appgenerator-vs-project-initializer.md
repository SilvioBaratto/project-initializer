# AppGenerator vs project-initializer — Differences

Comparison of two CLI scaffolding tools:

- **project-initializer** — this repo (`C:\Users\Baratto Silvio\project-initializer`), v0.3.5
- **AppGenerator** — `Fincantieri.AIPlatform.AppGenerator` (`C:\Users\Baratto Silvio\DevOps\Fincantieri.AIPlatform.AppGenerator`), v0.1.1

Both scaffold full-stack projects by merging ordered template overlay layers (`copy_tree` + `select_layers`). AppGenerator is a **Fincantieri-internal fork/rewrite** focused on Azure + enterprise concerns. project-initializer is the broader, general-purpose, multi-framework tool. Below is what actually differs.

---

## 1. Identity & Packaging

| | project-initializer | AppGenerator |
|---|---|---|
| CLI name | `project-initializer` | `appgenerator` |
| Entry point | `project_initializer.cli:main` | `appgenerator.cli:main` |
| Version | 0.3.5 | 0.1.1 |
| License | MIT | Proprietary (Fincantieri S.p.A.) |
| CLI framework | stdlib `argparse` | **Typer + questionary** (interactive wizard) |
| Runtime deps | none (stdlib only) | `typer`, `questionary` |
| Version source | hardcoded in `__init__.py` | read from package metadata at runtime |

Biggest structural difference: AppGenerator uses **Typer** with a `generate` subcommand and a **questionary interactive wizard** (`wizard.py`) that prompts when flags are omitted. project-initializer is pure `argparse`, non-interactive.

---

## 2. Support Matrix — the core divergence

| Dimension | project-initializer | AppGenerator |
|---|---|---|
| **Backend** | FastAPI **+ NestJS** | FastAPI **only** |
| **Frontend** | **Angular 21** + Tailwind 4 | **React 19** + Vite + Mantine + Redux Toolkit |
| **Auth modes** | none, `token`, `supabase`, `entra` | `entra`, `none` **only** (no token, no supabase) |
| **Scopes** | fullstack / api / frontend | monorepo / backend / frontend (same 3 concepts, different names) |
| **Database** | PostgreSQL (Docker) or Supabase | **SQL Server** (`mssql-python`) and/or **Cosmos DB** (`azure-cosmos`) |
| **Store combos** | one DB per variant | `--sql` and `--cosmos` **combinable** (multi-store) |
| **async-db** | `--async-db` overlay (FastAPI) | **removed** in 0.1.0 (sync SQL only) |

Key takeaways:
- **AppGenerator dropped NestJS, token, and supabase** — narrowed to a single opinionated stack (FastAPI + Entra + Azure data stores).
- **AppGenerator swapped Angular → React** for the frontend.
- **AppGenerator swapped Postgres/Supabase → SQL Server + Cosmos DB** (Azure-native), and made the two stores combinable rather than mutually exclusive.
- **project-initializer keeps async-db**; AppGenerator deleted it.

---

## 3. Architecture

- **project-initializer FastAPI**: layered — `api/v1` routes → services → repositories → models/schemas. Uses `requirements.txt`.
- **AppGenerator FastAPI**: **Clean/Hexagonal 4-layer** — `domain / application / infrastructure / api`. Uses `pyproject.toml` for the generated api (no `requirements.txt`); deps injected post-merge via `_inject_store_deps()` / `inject_dependencies()`.

AppGenerator ships an **AST architecture-fitness test** (`test_architecture_scanner.py`) that enforces the hexagonal layer boundaries in generated code.

---

## 4. Template Overlays

| project-initializer (13 dirs) | AppGenerator (7 dirs) |
|---|---|
| `templates/` (Angular base + configs) | `templates/` (root configs only) |
| `templates-api-fastapi/` | `templates-api-fastapi/` |
| `templates-api-nestjs/` | — |
| `templates-token-*` (3) | — |
| `templates-supabase-*` (3) | — |
| `templates-entra-{fastapi,nestjs,frontend}` | `templates-entra-fastapi/` |
| `templates-asyncdb-fastapi/` | — (removed) |
| — | `templates-sql-fastapi/` (store overlay) |
| — | `templates-cosmos-fastapi/` (store overlay) |
| — | `templates-frontend-react/` |
| — | `templates-frontend-entra-react/` |

Merge engine is conceptually the same (`select_layers` → ordered layers → `copy_tree` overwrite). AppGenerator adds **store-axis overlays** (sql/cosmos) that project-initializer doesn't have, since project-initializer's DB choice is bound to the auth/framework axis instead.

---

## 5. Generators

| | project-initializer | AppGenerator |
|---|---|---|
| `.env` generation | `env_generator.py` | `env_generator.py` + `env_defaults.env` |
| `docker-compose.yml` | static templates + `filter_compose()` transform | **`compose_generator.py`** — generated per-flag, zero-hardcoded `${VAR}` |
| README / CLAUDE.md | static template files | **`docs_generator.py`** — generated per-flag to avoid drift |
| nginx transform | `strip_nginx_proxy_block()` | (N/A — React/Vite frontend) |

AppGenerator generates compose files and docs **programmatically** (anti-drift), whereas project-initializer ships static templates and applies targeted text transforms.

---

## 6. BAML (LLM layer)

- **project-initializer**: **BAML is a first-class feature.** Both backends ship `baml_src/` (chatbot, clients, generators) + FastAPI ships generated `baml_client/`. Scaffolds an LLM chatbot service. Azure OpenAI + Anthropic/OpenAI/Google/Ollama keys in `.env`.
- **AppGenerator**: **No BAML.** Appears only as a ruff-exclude glob and a *banned-word* stale-doc guard. Removed from the stack.

---

## 7. CI / Enterprise Tooling

| | project-initializer | AppGenerator |
|---|---|---|
| CI | **GitHub Actions** (`ci.yml`, `release.yml`, `test-package.yml`) | **Azure Pipelines** (`.azure-pipelines/`) |
| CI in generated project | — | ships `.azure-pipelines/` into scaffolded projects |
| Corporate proxy | — | ships **Zscaler Root CA** into generated Docker images |
| Test framework | pytest + hypothesis (~90 files) | pytest + hypothesis (~48 files) |
| Extra tests | issue-numbered regression suite | **architecture-fitness (AST) + self-enforcement (anti-stale-doc) tests** |

AppGenerator is built for Fincantieri's Azure DevOps environment: Azure Pipelines instead of GitHub Actions, Zscaler CA baked in, self-enforcement tests that fail the build if generated docs go stale.

---

## 8. Summary — one line each

- **project-initializer** = broad, general-purpose. 2 backends (FastAPI/NestJS) × 4 auth × 3 scopes, Angular frontend, BAML/LLM built-in, Postgres/Supabase, GitHub Actions.
- **AppGenerator** = narrow, Fincantieri/Azure-opinionated fork. FastAPI-only hexagonal, React frontend, Entra-or-none auth, SQL Server + Cosmos DB (combinable), no BAML, Typer wizard, Azure Pipelines + Zscaler + programmatic doc/compose generation.

**Direction of the fork:** AppGenerator drops breadth (NestJS, token, supabase, Angular, BAML, async-db) and adds Azure depth (Entra-first, SQL Server/Cosmos, hexagonal architecture, enterprise CI/proxy, generated docs & compose, interactive wizard).

---
---

# Part 2 — Migration Plan: adopt 3 AppGenerator patterns into project-initializer

**Goal.** Keep project-initializer's current structure, matrix, and feature set exactly as-is. Adopt **only three** AppGenerator patterns:

1. **Hexagonal (clean) architecture** — FastAPI backend restructure.
2. **Env generation** — root `.env` + `.env.example`, sectioned builders, dev defaults baked in.
3. **Interactive wizard** — replace the argparse-prompt CLI with a Typer + questionary wizard.

**Locked decisions (do not re-litigate):**
- **`.env` location** → root `.env` **+** `.env.example` (AppGenerator topology). Drop the current `api/.env`-only behavior.
- **Hexagonal scope** → **FastAPI only**. NestJS keeps its idiomatic modular (module/controller/service/DTO) architecture. No ports/adapters in Nest.
- **Wizard deps** → accept **Typer + questionary** as runtime deps (project-initializer currently has zero runtime deps).

**Non-goals (explicitly unchanged):** framework matrix (FastAPI+NestJS), auth modes (none/token/supabase/entra), scopes (fullstack/api/frontend), async-db, BAML/LLM, Angular frontend, GitHub Actions CI, SQL choice (Postgres/Supabase — **not** adopting SQL Server/Cosmos), overlay-layer merge engine (`copy_tree`/`select_layers`).

---

## A. Hexagonal architecture (FastAPI only)

### Current → target layout

Current FastAPI app (`templates-api-fastapi/api/app/`) is layered-by-technical-type:
```
app/
├── api/v1/           routes (chatbot, items, users, test, router)
├── config.py
├── database.py
├── dependencies.py
├── exceptions.py
├── main.py
├── middleware/       logging, rate_limiting, security
├── models/           SQLAlchemy (base, item, user)
├── repositories/     base, item
├── schemas/          Pydantic (chatbot, item, user)
├── services/         chatbot_service, item_service
├── core/
└── utils/audit.py
```

Target hexagonal layout (mirror AppGenerator `templates-api-fastapi/api/app/`):
```
app/
├── domain/                       # pure business core — no framework imports
│   ├── entities/                 # domain models (was models/ minus ORM concerns)
│   ├── ports/                    # interfaces/protocols (e.g. health_probe, repo ports)
│   ├── services/                 # domain services
│   └── exceptions.py             # was app/exceptions.py
├── application/                  # use-case orchestration
│   ├── commands/
│   └── services/                 # application services (was services/*_service.py)
├── infrastructure/               # framework/IO adapters
│   ├── gateways/                 # port implementations (DB, LLM, external)
│   ├── config.py                 # was app/config.py
│   ├── base_settings.py
│   ├── settings.py
│   ├── logging_config.py
│   ├── lifespan.py
│   └── audit.py                  # was utils/audit.py
├── api/                          # HTTP delivery
│   ├── deps.py                   # was app/dependencies.py
│   ├── handlers.py               # exception handlers
│   ├── security.py
│   ├── schemas/                  # request/response DTOs (common, health, + domain)
│   ├── middleware/
│   └── v1/
│       ├── router.py
│       └── endpoints/            # health, chatbot, items, users
└── main.py
```

### Mapping table (current file → hexagonal home)

| Current | Hexagonal target |
|---|---|
| `app/models/*` (SQLAlchemy) | `domain/entities/*` (domain) + ORM mapping in `infrastructure/` |
| `app/repositories/base.py, item.py` | port interface in `domain/ports/`; impl in `infrastructure/gateways/` |
| `app/services/*_service.py` | `application/services/*` |
| `app/schemas/*` (Pydantic) | `api/schemas/*` |
| `app/config.py` | `infrastructure/config.py` (+ `settings.py`, `base_settings.py`) |
| `app/database.py` | `infrastructure/` (session/engine) |
| `app/dependencies.py` | `api/deps.py` |
| `app/exceptions.py` | `domain/exceptions.py` + `api/handlers.py` (HTTP mapping) |
| `app/utils/audit.py` | `infrastructure/audit.py` |
| `app/middleware/*` | `api/middleware/*` (move under `api/`) |
| `app/api/v1/*.py` routes | `api/v1/endpoints/*.py` + `api/v1/router.py` |

### Dependency-flow rule (the point of hexagonal)
`domain` imports nothing outward. `application` imports `domain` only. `infrastructure` + `api` import inward (`domain`/`application`), implementing `domain/ports`. Wiring happens at `main.py` / `api/deps.py`.

### Affected overlays (auth + async-db must follow the new paths)
The auth/asyncdb overlays overwrite specific files by **path**. Moving files means every overlay that touches them must be re-pathed:
- `templates-token-fastapi/`, `templates-supabase-fastapi/`, `templates-entra-fastapi/` — re-home their overrides (e.g. `dependencies.py` → `api/deps.py`, auth guards → `api/security.py` or `infrastructure/`).
- `templates-asyncdb-fastapi/` — async engine/session now under `infrastructure/`.
- `select_layers()` order is unchanged; only in-layer paths change.
- **NestJS overlays untouched.**

### Verification hook worth porting
AppGenerator ships an AST **architecture-fitness test** (`test_architecture_scanner.py`) that fails the build if `domain` imports `infrastructure`/framework code. Recommend porting a slimmed version into project-initializer's `tests/` to keep the boundary honest.

---

## B. Env generation (root `.env` + `.env.example`, sectioned builders)

### What changes
project-initializer's `env_generator.py` today: one flat `generate_env(framework, auth, ...)` builds a single `api/.env` as a flat line list (`env_generator.py:24-137`).

Adopt AppGenerator's shape (`env_generator.py`):
1. **Split into private section builders** — `_server_section`, `_telemetry_section`, `_db_section`, `_supabase_section`, `_entra_section`, `_token_section`, `_frontend_section`, `_llm_section` — each returns `list[str]`, composed by flags in `generate_env`. Replaces the current inline `if` blocks.
2. **App-config vs topology split** — emit both the app-read vars (e.g. `DATABASE_URL`) **and** compose-topology vars (`DB_HOST_PORT`, `API_HOST_PORT`, `FRONTEND_HOST_PORT`) from one source, commented into `── app config ──` / `── compose topology ──` sub-sections.
3. **Bake working dev defaults** — every var has a sane fallback (AppGenerator style: `DB_PASSWORD=DevPassword1!`, emulator keys, etc.) so `docker compose up` runs with **zero edits**. `.env.example` = same content.
4. **Write to root, not `api/`** — `generate_env(...)` writes `dest/.env` **and** `dest/.env.example`. docker-compose reads the root `.env`.

### `.env` topology to preserve (project-initializer's own stack)
Keep project-initializer's variable set — do **not** import SQL Server/Cosmos vars. Sections needed:
- **Server**: `ENVIRONMENT`/`DEBUG`/`PORT` (FastAPI) or `NODE_ENV`/`PORT` (NestJS), `LOG_LEVEL`, `CORS_ORIGINS`, `API_HOST_PORT`.
- **Database**: Docker Postgres URL (sync + Prisma variants) or Supabase URLs — as today.
- **Redis**: NestJS/BullMQ only.
- **Auth**: `AUTH_TOKEN`/`JWT_*` (token); `SUPABASE_URL`/`SUPABASE_PUBLISHABLE_KEY` (supabase); `ENTRA_*` (entra).
- **Frontend**: Angular topology (`FRONTEND_HOST_PORT=4200`) + MSAL vars when entra.
- **LLM/BAML**: Azure OpenAI + Anthropic/OpenAI/Google/Ollama (unchanged).

### Wiring in cli.py
Move `.env` generation into the scaffold flow (as AppGenerator does in `copy_template`): after layer merge, `generate_env(...)` writes root `.env` + `.env.example`. Update `.vscode/tasks.json` preLaunch: `--dest .env` (root) instead of `api/.env`.

### Impact
- `docker-compose.yml` templates / `filter_compose` must read topology vars from root `.env` (paths change from `api/.env`).
- The standalone CLI (`python -m project_initializer.env_generator ... --dest`) keeps working; default dest becomes root `.env`.

---

## C. Interactive wizard (Typer + questionary)

### What changes
Replace project-initializer's argparse parser (`cli.py:287-355`, `build_parser()`) with AppGenerator's Typer app + questionary wizard pattern (`cli.py:410-523`, `wizard.py`).

### Design (port AppGenerator's, adapt choices to project-initializer's matrix)
- **Typer app**, single `generate` subcommand + top-level `--version` eager callback + `no_args_is_help=True`.
- **`wizard.py`** with a `WizardResult` dataclass and single-select `questionary.select` prompts, **only prompting for values not passed as flags** (a fully-flagged call runs zero prompts → preserves scriptability/CI).
- **`-y/--yes`** non-interactive flag: skip all prompts, apply defaults (framework=fastapi, auth=none, scope=fullstack).
- **`_abort_if_cancelled`** — Ctrl-C / None answer → clean `sys.exit(0)`.
- Keep `--force`; add `-V/--verbose` (per-file listing) as AppGenerator has.

### Prompts to expose (project-initializer's dimensions, not AppGenerator's)
| Prompt | Choices | Default | Skip when |
|---|---|---|---|
| Scope | fullstack / api / frontend | fullstack | `--scope` given |
| Framework | fastapi / nestjs | fastapi | scope=frontend **or** `--fastapi`/`--nestjs` given |
| Auth | none / token / supabase / entra | none | scope=frontend **or** `--auth` given |
| Async DB | yes / no | no | framework=nestjs, scope=frontend, or `--async-db` given |

### Validation must survive the port
Current `validate_scope()` rules (`cli.py:358-379`) still apply — enforce them **after** the wizard resolves values (reject `frontend`+framework, `frontend`+auth, `async-db`+nestjs, `async-db`+frontend). The wizard should also **skip** framework/auth/async prompts when scope=frontend so illegal combos are never offered.

### Nice-to-haves from AppGenerator (optional)
- **Rich config panel + summary tree** (`_config_panel`, `_summary_tree`) — pretty scaffold output. Rich comes transitively with Typer.
- **Rich spinner** during merge.

### pyproject.toml changes
```toml
dependencies = [
    "typer>=0.26",
    "questionary>=2.1",
]
```
(project-initializer currently declares no runtime deps.) Keep argparse **only** inside `env_generator.__main__` standalone entry (independent of the main CLI).

---

## D. What explicitly does NOT change

- Overlay directory count/names (13 dirs), merge engine (`copy_tree`, `select_layers`, `validate_scope`), `file_transforms.py` (compose/nginx transforms) — **all stay**.
- NestJS backend (modular, Prisma) — **untouched** by hexagonal.
- Auth matrix, scope matrix, async-db, BAML, Angular 21 frontend, GitHub Actions CI, Postgres/Supabase DB choice.
- No SQL Server, no Cosmos DB, no Azure Pipelines, no Zscaler, no docs_generator/compose_generator adoption (compose stays static-template + transform).

## E. Suggested order of work

1. **Env** (lowest risk, isolated): refactor `env_generator.py` into section builders, write root `.env`+`.env.example`, re-point compose/tasks.json. Update tests.
2. **Wizard** (isolated to `cli.py` + new `wizard.py`): add Typer/questionary, port wizard, keep validation. Update parser tests.
3. **Hexagonal** (highest blast radius): restructure `templates-api-fastapi`, then re-path the 3 FastAPI auth overlays + asyncdb overlay, then port the architecture-fitness test. Verify all FastAPI variants still scaffold and boot.
