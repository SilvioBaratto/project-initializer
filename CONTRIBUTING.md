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

The repository includes `.vscode/launch.json` and `.vscode/tasks.json` with pre-configured debug targets for all 6 variants. Press **F5** and select a variant — the `preLaunchTask` will:

1. Scaffold the test project (e.g., `test-fastapi/`) if it doesn't exist
2. Generate `api/.env` from the root `.env` via `env_generator.py`
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

## Template Overlay Architecture

The CLI scaffolds projects by merging template layers in order. See [CLAUDE.md](CLAUDE.md) for the full explanation. In summary:

```
Layer 1: templates/                    → Shared base (frontend + root configs)
Layer 2: templates-api-{framework}/    → Framework API + docker-compose + nginx
Layer 3a: templates-{auth}-{framework}/ → Auth API overlay (optional)
Layer 3b: templates-{auth}-frontend/   → Auth frontend overlay (optional)
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
