# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Full-stack application scaffolded by `project-initializer` with Docker orchestration.

## Build & Run Commands

```bash
# Run full stack with Docker
docker compose up -d --build

# Stop all services
docker compose down
```

## Repository Structure

```
project/
├── api/                           # Backend API
│   └── .claude/CLAUDE.md          # Detailed API guidance
├── frontend/                      # Angular frontend
│   └── .claude/CLAUDE.md          # Detailed frontend guidance
├── docker-compose.yml             # Full stack orchestration
└── .vscode/                       # VS Code debug configs
```

**Note:** For detailed guidance on each component, see:
- `api/.claude/CLAUDE.md` - API patterns, database access, BAML integration
- `frontend/.claude/CLAUDE.md` - Angular best practices, signals, components

## Frontend Template (`frontend/`)

Angular 21 with Tailwind CSS. Key conventions:

- **Standalone components only** (no NgModules, don't set `standalone: true` - it's default)
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
