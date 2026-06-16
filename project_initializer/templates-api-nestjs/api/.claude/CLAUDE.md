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
npx prisma migrate dev        # Create and apply migration (dev)
npx prisma migrate deploy     # Apply migrations (production)
npx prisma generate           # Regenerate Prisma client

# Prisma Studio (visual DB editor)
npx prisma studio

# Regenerate BAML client (after modifying .baml files)
npx baml-cli generate
```

## Architecture Overview

This is a NestJS application with BAML-powered AI chatbot functionality.

### Core Structure

```
src/
├── main.ts               # Bootstrap, Swagger, Helmet, CORS, ValidationPipe
├── app.module.ts          # Root module (Prisma, Config, Throttler)
├── prisma/
│   ├── prisma.module.ts   # @Global() PrismaModule
│   └── prisma.service.ts  # PrismaService (extends PrismaClient)
├── common/
│   ├── decorators/        # Custom decorators (@CurrentUser, @Public)
│   ├── filters/           # Exception filters (HTTP, Prisma)
│   ├── exceptions/        # Custom API exceptions
│   └── interceptors/      # Response transform interceptor
├── config/                # env validation (zod) + pino logger config
└── modules/
    ├── health/            # Terminus liveness/readiness probes
    ├── auth/              # Authentication (stub in base, replaced by overlays)
    ├── test/              # CRUD test endpoints
    └── chatbot/           # BAML-powered chatbot
                           #   POST /chat          — blocking sync call
                           #   POST /chat/stream   — SSE streaming
                           #   POST /chat/jobs     — enqueue async job → { jobId }
                           #   GET  /chat/jobs/:id — poll state/result → { jobId, state, result }

prisma/
└── schema.prisma          # Database models

baml_src/                  # BAML definitions for LLM functions
baml_client/               # Auto-generated BAML TypeScript client (don't edit)
```

### Key Patterns

**Database Access**: PrismaService injected via DI. PrismaModule is @Global.

**Models**: Defined in `prisma/schema.prisma`. Regenerate client with `npx prisma generate`.

**API Routes**: All v1 routes go through `/api/v1` prefix set in controllers.

**BAML Integration**: Define LLM functions in `baml_src/*.baml`, regenerate client with `npx baml-cli generate`.

**DTO Naming**: `Create<Entity>Dto`, `Update<Entity>Dto`, `<Entity>ResponseDto` pattern (Zod-based via nestjs-zod).

### Middleware Stack

1. Helmet (security headers)
2. CORS
3. Throttler (rate limiting)
4. nestjs-pino HTTP logging (request-id correlation via `x-request-id`)
5. ZodValidationPipe (global)
6. HttpExceptionFilter + PrismaClientExceptionFilter (global)
7. TransformInterceptor (global)

## BAML Integration

LLM functions are defined in `baml_src/*.baml`. The BAML compiler emits a generated TypeScript client into `baml_client/`. The generated client must not be hand-edited — always regenerate it after any `.baml` change:

```bash
npx baml-cli generate
```

### Generator configuration (`baml_src/generators.baml`)

The generator targets TypeScript with async default client mode (`default_client_mode async`), so every `b.FunctionName()` call returns a `Promise`. The output directory is `baml_client/` (one level above `baml_src/`).

### Chatbot call flow

```
ChatbotController
├── POST /chat         → ChatbotService.chat(request)
│                          └─ const { b } = await import('../../../baml_client')
│                          └─ b.Chat(user_question, conversation_history) → { answer }
├── POST /chat/stream  → ChatbotService.streamChat(request)  [SSE]
│                          └─ const { b } = await import('../../../baml_client')
│                          └─ b.stream.StreamChat(user_question, conversation_history)
├── POST /chat/jobs    → ChatJobService.enqueueChat(request) → { jobId }
└── GET  /chat/jobs/:id → ChatJobService.getJobStatus(id)
                             └─ ChatProcessor.process(job)  [BullMQ worker]
                                   └─ const { b } = await import('../../../baml_client')
                                   └─ b.Chat(user_question, conversation_history)
```

`ChatbotService.chat` and `ChatbotService.streamChat` run on the request path. The `ChatProcessor` worker runs blocking BAML/LLM calls off the request path via BullMQ.

### Adding a new LLM function

1. Define the function and any classes in `baml_src/chatbot.baml` (or a new `.baml` file).
2. Run `npx baml-cli generate` to regenerate `baml_client/`.
3. Call the new function: `const { b } = await import('../../../baml_client')` then `await b.YourFunction(...)`.

## Production-readiness acceptance checklist

> **Research provenance:** deep research — 110 agents, 28 primary sources, 24 claims at 3-0 adversarial verification against official NestJS docs (https://docs.nestjs.com/). Statuses reflect **verified current state** of this template (reconciled from pre-work gap analysis — several ⚠️/❌ rows in the original analysis have since been closed).
>
> **Legend:** ✅ done in template · ⚠️ partial / worth hardening · ❌ gap / not present (non-goal)

### 1. Core building blocks & DI

- ✅ `@Module()` with providers/controllers/imports/exports — feature modules under `src/modules/*`
- ✅ `PrismaModule` is `@Global()` and exports `PrismaService`; never re-register in another `providers:` array
- ✅ Type-based constructor injection; default singleton scope (use REQUEST only when strictly needed)
- Citations: `/modules`, `/providers`, `/fundamentals/injection-scopes`

### 2. Controllers & routing

- ✅ `@Controller('prefix')` + HTTP-method decorators; request-data decorators (`@Body/@Query/@Param`) over raw `@Req()`
- ✅ `app.setGlobalPrefix('api/v1')` in `main.ts`
- ⚠️ URI/header versioning (`VersioningType`) — static `api/v1` prefix is sufficient for a single version (non-goal)
- Citations: `/controllers`, `/techniques/versioning`

### 3. DTOs, validation & serialization

- ✅ Zod schemas via `nestjs-zod` as DTOs (not erased interfaces)
- ✅ `ZodValidationPipe` registered as `APP_PIPE` — strips unknown fields from all incoming bodies
- ✅ `ZodSerializerInterceptor` registered as `APP_INTERCEPTOR`; response schemas whitelist fields so Prisma rows cannot leak secret columns — `serialization.spec.ts:17-19` proves `password` is stripped
- ⚠️ Built-in transform pipes — Zod coercion covers primitive coercion; no `ParseIntPipe` needed
- Citations: `/pipes`, `/techniques/validation`, `/techniques/serialization`

### 4. Request pipeline — pipes, guards, interceptors, filters, middleware

- ✅ Global Zod pipe, auth guards, `TransformInterceptor`, `ZodSerializerInterceptor`
- ✅ `HttpExceptionFilter` + `PrismaClientExceptionFilter` registered via `useGlobalFilters()` in `main.ts:51-56`
- ✅ `LoggingMiddleware` (nestjs-pino) applied globally; `@CurrentUser()`, `@Public()` custom decorators
- ⚠️ **Filter DI caveat:** filters registered via `useGlobalFilters()` in `main.ts` live outside the Nest DI container and cannot inject providers. The current `HttpExceptionFilter` and `PrismaClientExceptionFilter` are dependency-free (`new`-instantiated in `main.ts:51-56`) — **no change is required today**.

  If a filter gains a DI dependency (e.g. a logger service), move it to a module provider instead:

  ```typescript
  // app.module.ts — use when a filter needs DI (e.g. an injected LoggerService)
  import { APP_FILTER } from '@nestjs/core';
  import { MyLoggedFilter } from './common/filters/my-logged.filter';

  @Module({
    providers: [
      { provide: APP_FILTER, useClass: MyLoggedFilter },
    ],
  })
  export class AppModule {}
  ```

  Keep dependency-free filters in `main.ts` via `useGlobalFilters()` — switching them to `APP_FILTER` without a real DI need adds unnecessary indirection.

- Citations: `/pipes`, `/guards`, `/interceptors`, `/exception-filters`, `/middleware`, `/custom-decorators`

### 5. Authentication & authorization

- ✅ Token auth: `AuthGuard` registered as `APP_GUARD` — `templates-token-nestjs/api/src/app.module.ts:70-73`
- ✅ Supabase JWT auth: `SupabaseAuthGuard` registered as `APP_GUARD` — `templates-supabase-nestjs/api/src/app.module.ts:70-73`
- ✅ `@Public()` opt-out via `Reflector.getAllAndOverride` — both guards honor it
- ❌ RBAC / CASL — non-goal (add only when multi-role or fine-grained authz is needed)
- Citations: `/security/authentication`, `/security/authorization`, `/guards`

### 6. Security hardening

- ✅ Helmet (`app.use(helmet())`) — `main.ts`
- ✅ CORS restricted to `CORS_ORIGINS` env (not `*`), credentials/methods/headers configured — `main.ts`
- ✅ Rate limiting: `ThrottlerModule` 100 req/60s + global `ThrottlerGuard` — `app.module.ts`
- ✅ Secrets via `@nestjs/config` with `ConfigModule.forRoot({ isGlobal: true })`
- ❌ CSRF — non-goal (bearer-token APIs are largely CSRF-immune; add `csurf` only if cookie auth is introduced)
- Citations: `/security/helmet`, `/security/rate-limiting`, `/security/csrf`

### 7. Operational concerns

- ✅ Env validation: `src/config/env.validation.ts:16-25` — `validate()` throws on missing `DATABASE_URL`/`DIRECT_URL`; wired via `ConfigModule.forRoot({ validate })`
- ✅ Structured logging: `nestjs-pino` with `x-request-id` correlation — `src/config/logger.config.ts`
- ✅ Health checks: `@nestjs/terminus` liveness + readiness probes (DB, disk, memory) — `src/modules/health/health.controller.ts`
- ✅ OpenAPI/Swagger at `/docs` with bearer auth and `cleanupOpenApiDoc` — `main.ts`
- ✅ Graceful shutdown: `app.enableShutdownHooks()` + Prisma `$disconnect` on `onModuleDestroy`
- Citations: `/techniques/configuration`, `/techniques/logger`, `/recipes/terminus`, `/openapi/introduction`, `/fundamentals/lifecycle-events`

### 8. Database / ORM

- ✅ `PrismaService extends PrismaClient` in `@Global() PrismaModule`; connect on `onModuleInit`, disconnect on `onModuleDestroy`
- ✅ Migrations via `prisma migrate dev/deploy`; SSL via `deriveSslOption` util (with spec test); health probe runs `SELECT 1`
- Citations: `/recipes/prisma`, `/techniques/database`

### 9. Testing

- ✅ Jest configured; `npm test` and `npm run test:e2e` scripts present
- ✅ Service/controller unit specs: `chatbot.service.spec.ts`, `chat-job.service.spec.ts`, `health.controller.spec.ts`, `serialization.spec.ts`
- ✅ e2e scaffold: `test/app.e2e-spec.ts` (supertest) + `test/jest-e2e.json`
- Citations: `/fundamentals/testing`

## Global acceptance criteria

| # | Criterion | Status | Citation |
|---|-----------|--------|----------|
| 1 | Auth guard registered as `APP_GUARD` in both overlays — routes protected by default | ✅ | `templates-token-nestjs/.../app.module.ts:70-73` (AuthGuard), `templates-supabase-nestjs/.../app.module.ts:70-73` (SupabaseAuthGuard) |
| 2 | `ConfigModule` validates env and fails fast on missing secrets (`DATABASE_URL`, `SUPABASE_*`) | ✅ | `src/config/env.validation.ts:16-25` — `validate()` throws; wired via `ConfigModule.forRoot({ validate })` |
| 3 | Response schemas whitelist fields — Prisma rows cannot leak secret columns through the serializer | ✅ | `src/modules/test/serialization.spec.ts:17-19` — `ItemResponseSchema.parse({ password: 'leak' })` strips `password` |
| 4 | Terminus health module: liveness/readiness probes (DB, disk, memory) | ✅ | `src/modules/health/health.controller.ts` — `@nestjs/terminus` `HealthCheckService`, `DiskHealthIndicator`, `MemoryHealthIndicator` |
| 5 | e2e test scaffold + service unit specs | ✅ | `test/app.e2e-spec.ts`, `test/jest-e2e.json`; `chatbot.service.spec.ts`, `chat-job.service.spec.ts`, `health.controller.spec.ts` |
| 6 | (Optional) Blocking BAML/LLM calls offloaded to BullMQ background jobs | ✅ | `src/modules/chatbot/chat-job.service.ts` + `chat.processor.ts`; `POST /chat/jobs` / `GET /chat/jobs/:id` |
