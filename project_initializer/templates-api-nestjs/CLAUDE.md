# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Full-stack application with **NestJS** backend, Angular frontend, and Docker orchestration.

## Build & Run Commands

```bash
# Run full stack with Docker
docker compose up -d --build

# Individual services
cd api && npm run start:dev                       # Backend on :8000
cd frontend && ng serve                           # Frontend on :4200

# API development
cd api
npm install
npm test                                          # Run tests
npx prisma migrate dev                            # Create and apply migration (dev)
npx prisma migrate deploy                         # Apply migrations (production)
npx prisma generate                               # Regenerate Prisma client
npx baml-cli generate                             # Regenerate BAML client
```

## API Template (`api/`)

NestJS application with modular architecture:

| Layer | Purpose |
|-------|---------|
| `src/modules/` | Feature modules (health, auth, chatbot, test) |
| `src/prisma/` | Global PrismaModule and PrismaService |
| `src/common/` | Decorators, filters, exceptions, interceptors, middleware |
| `prisma/schema.prisma` | Database models |
| `baml_src/` | LLM function definitions (regenerate client with `npx baml-cli generate`) |

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| `db` | 5433:5432 | PostgreSQL 16 |
| `api` | 8000:8000 | NestJS with hot reload |
| `frontend` | 4200:80 | Angular + nginx (proxies `/api/` to backend) |
| `adminer` | 8080:8080 | Database admin UI |
