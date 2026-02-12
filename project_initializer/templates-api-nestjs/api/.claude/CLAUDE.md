# CLAUDE.md

This file provides guidance to Claude Code when working with this NestJS API.

## Build & Run Commands

```bash
# Install dependencies
npm install

# Run development server (port 3000)
npm run start:dev

# Run with debug
npm run start:debug

# Build for production
npm run build

# Run tests
npm test

# Database migrations
npm run migration:run       # Apply migrations
npm run migration:generate  # Create migration
npm run migration:revert    # Rollback one migration

# Regenerate BAML client (after modifying .baml files)
npx baml-cli generate
```

## Architecture Overview

This is a NestJS application with BAML-powered AI chatbot functionality.

### Core Structure

```
src/
├── main.ts               # Bootstrap, Swagger, Helmet, CORS, ValidationPipe
├── app.module.ts          # Root module (TypeORM, Config, Throttler)
├── config/
│   └── data-source.ts     # TypeORM CLI data source
├── entities/              # TypeORM entities (base.entity.ts)
├── common/
│   ├── repositories/      # Generic CRUD base repository
│   ├── middleware/         # Logging middleware
│   ├── filters/           # Exception filters
│   ├── exceptions/        # Custom API exceptions
│   ├── decorators/        # Custom decorators (@CurrentUser)
│   └── interceptors/      # Response transform interceptor
└── modules/
    ├── health/            # Health check endpoint
    ├── test/              # CRUD test endpoints
    └── chatbot/           # BAML-powered chatbot

baml_src/                  # BAML definitions for LLM functions
baml_client/               # Auto-generated BAML TypeScript client (don't edit)
```

### Key Patterns

**Database Access**: TypeORM repositories injected via DI. Use BaseRepository for generic CRUD.

**API Routes**: All v1 routes go through `/api/v1` prefix set in controllers.

**BAML Integration**: Define LLM functions in `baml_src/*.baml`, regenerate client with `npx baml-cli generate`.

**DTO Naming**: `Create<Entity>Dto`, `Update<Entity>Dto`, `<Entity>ResponseDto` pattern.

**Entities**: Inherit from `BaseEntity` (includes UUID PK + timestamps).

### Middleware Stack

1. Helmet (security headers)
2. CORS
3. Throttler (rate limiting)
4. Logging middleware
5. ValidationPipe (global)
6. HttpExceptionFilter (global)
7. TransformInterceptor (global)
