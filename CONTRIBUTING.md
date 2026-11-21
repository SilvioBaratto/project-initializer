# Contributing

## Prerequisites

- Python 3.10+
- Node.js 20+
- Docker and Docker Compose
- [BAML CLI](https://docs.boundaryml.com/) (`pip install baml-py` for FastAPI, `npm install @boundaryml/baml` for NestJS)

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/silviobaratto/project-initializer.git
   cd project-initializer
   ```

2. Install in development mode:
   ```bash
   pip install -e .
   ```

3. Copy the environment template:
   ```bash
   cp .env.example .env
   # Edit .env with your database URLs and API keys
   ```

4. Verify the CLI works:
   ```bash
   project-initializer --version
   ```

## VS Code One-Click Debug

The repository includes `.vscode/launch.json` and `.vscode/tasks.json` with pre-configured debug targets for all 8 auth/framework variants (the opt-in `--async-db` path is a ninth scaffold, FastAPI only). Press **F5** and select a variant — the `preLaunchTask` will:

1. Scaffold the test project (e.g., `test-fastapi/`) if it doesn't exist
2. Generate the project's root `.env` via `env_generator.py`
3. Run `baml-cli generate` to create the BAML client

This means you can start debugging any variant without manual setup.

## Testing a Variant Manually

```bash
# Scaffold a specific variant
project-initializer test-fastapi --fastapi --force
project-initializer test-nestjs-token --nestjs --auth token --force

# Run with Docker
cd test-fastapi && docker-compose up -d

# Or run the API directly
cd test-fastapi/api && uvicorn app.main:app --reload      # FastAPI
cd test-nestjs/api && npm install && npm run start:dev     # NestJS
```

Test output directories (`test-fastapi/`, `test-nestjs-token/`, etc.) are gitignored.

## Running the Tests

```bash
pytest -m "not integration"      # Repo suite without the scaffold-and-build tests
pytest                           # Whole repo suite
INTEGRATION_BUILD=1 pytest tests/test_integration_build.py   # Heavy NestJS build tests (minutes)
```

In a git worktree run `PYTHONPATH=<worktree> pytest`: the `project-initializer` console script imports the checkout that `pip install -e .` points at, so without it the tests that call the script exercise the old templates.

The repo suite does not run the tests a scaffolded project ships. CI does, in the `test-variant-suites` job; locally, scaffold the variant and run `pip install -r requirements.txt && pytest -q` in its `api/` (FastAPI) or `npm ci && npm run test:cov && npm run test:e2e` (NestJS). A FastAPI project enforces 75% branch coverage of `app/`, so a single file or marker needs `pytest --no-cov`.

### Test traceability (repo suite)

Code standard 6.6 asks each test to cite its requirement ID and the code it validates. This project has no requirement tracker, so the repo suite carries **no requirement IDs**; this is the written-down adaptation (standard 1.4). Traceability is the test's `Validates ...` docstring line to the code, plus the `CHANGELOG.md` `[Unreleased]` entry of the change.

- A covered test function ends its docstring with one line `Validates <repo-relative path or dotted symbol>.`, naming the file the test really inspects, not only a helper it calls. For example `Validates project_initializer/env_generator.py generate_env().` or `Validates project_initializer/templates-api-fastapi/api/alembic/versions.`. A parametrized test carries the line once, not per case.
- Covered are every test function of the modules listed in `NEW_MODULES`, plus the functions listed per older module in `TRACED_FUNCTIONS`: the tests written or rewritten in this change (a new test, or an existing one whose body or target the change altered). The other tests of those older modules are legacy: they predate the convention, carry no line yet and are not checked. When you next touch one, annotate it and list it in `TRACED_FUNCTIONS`; a module moves to `NEW_MODULES` once all its tests carry the line.
- A new test module follows this convention and is added to `NEW_MODULES` in `tests/test_repo_test_traceability.py` in the same change. That test parses the covered modules and fails for a covered test function whose docstring does not end with a `Validates` line, and for a `TRACED_FUNCTIONS` name that is no longer defined.
- The tests a scaffolded project ships follow the convention in its own generated docs, not this one.

## Template Overlay Architecture

The CLI scaffolds projects by merging template layers in order. See [CLAUDE.md](CLAUDE.md) for the full explanation. In summary:

```
Layer 1: templates/                    → Shared base (frontend + root configs)
Layer 2: templates-api-{framework}/    → Framework API + docker-compose + nginx
Layer 3a: templates-{auth}-{framework}/ → Auth API overlay (optional)
Layer 3b: templates-{auth}-frontend/   → Auth frontend overlay (optional)
Layer 4: templates-asyncdb-fastapi/    → Async SQLAlchemy overlay (--async-db, optional)
```

Later layers overwrite files from earlier layers.

## Adding a New Framework

1. Create `project_initializer/templates-api-{name}/` with:
   - `api/` directory (Dockerfile, source code, package config)
   - `docker-compose.yml`
   - `frontend/nginx.conf` (proxy config for the new backend)
2. Add the framework name to `FRAMEWORKS` in `cli.py`
3. Add env generation logic to `env_generator.py`
4. Add VS Code tasks and launch config in `.vscode/`
5. Add the template dir to `MANIFEST.in` and `pyproject.toml` package-data
6. Add a CI matrix entry in `.github/workflows/test-package.yml`

## Adding a New Auth Mode

1. Create `project_initializer/templates-{auth}-fastapi/` and `templates-{auth}-nestjs/` with API overlay files
2. Create `project_initializer/templates-{auth}-frontend/` with frontend overlay files
3. Add the auth mode to `AUTH_MODES` in `cli.py`
4. Add env generation logic to `env_generator.py`
5. Add the template dirs to `MANIFEST.in` and `pyproject.toml` package-data

## PR Process

1. Create a feature branch from `development`
2. Make changes and test by scaffolding the affected variants
3. Ensure `pip install -e .` succeeds
4. Open a PR against `development` with a clear description of what changed and which variants are affected
