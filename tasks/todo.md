# TODO: NestJS API Template — NestJS 12 Upgrade

Checklist companion to `tasks/plan.md` (full detail) and `SPEC.md` (rationale). Revised 2026-09-29
after live-source research: `nestjs-zod` has no v12 peer → **migrate to native validation**; bullmq 6
is optional but **chosen** (+ ioredis).

Legend: scope XS/S/M/L · `→` verification gate.

## Phase 0 — Foundation
- [x] **T1** Docker base `node:22-alpine` → `node:24-alpine` (both `FROM`, base Dockerfile) · XS — committed `b8c7686`

## Phase 1 — NestJS 12 core + native validation + queue (coupled, fail fast)
- [ ] **T2** Manifests (3 `package.json`): NestJS 12 set (11 pkgs → core 12.1.1 / config 12.0.1 / swagger 12.0.2 / terminus 12.1.0 / throttler 6.7.1 / cli 12.0.8 / schematics 12.0.6) + `@nestjs/bullmq`12.0.0 + `bullmq`6.3.9 + **add `ioredis`6.0.0** + `@bull-board/*`9.10.1 + `nestjs-pino`5.2.1 (+`pino`10 +`pino-http`11 +`pino-pretty`); **remove `nestjs-zod`**; keep `zod`4.4.3; don't touch `typescript` · S
  → JSON valid; `nestjs-zod` absent + `ioredis` present in all 3; swagger 12.0.2; targets consistent.
- [ ] **T3** Native validation refactor (drop `nestjs-zod` in code, ~15 `.ts` + 2 tests): global `StandardSchemaValidationPipe`/`StandardSchemaSerializerInterceptor` ×4 `app.module.ts`; `createZodDto`→`z.infer` + `@Body({schema})`; `@ZodSerializerDto`→`@SerializeOptions({schema})` + `@ApiOkResponse/@ApiCreatedResponse({standardSchema})`; drop `cleanupOpenApiDoc` in `main.ts`; update `serialization.spec.ts` + `test_issue_003_zod_serialization.py` · L
  → zero `nestjs-zod` imports; OpenAPI doc has request **and** response schemas; TS compiles.
- [ ] **T4** bullmq 6 wiring + audit (guard only — no removed-API usage): processor/queue typecheck on bullmq 6; `BullModule` connection resolves via `ioredis` · XS
  → verified by T5 readiness smoke.
- [ ] **T5** Regenerate 3 locks on `node:24-alpine` + core verify — 3 `package-lock.json` · M
  → `docker compose build api` (base+entra) green; `/health/readiness` = up; `/admin/queues` reachable; `npm test` green on Node ≥24.9; `@nestjs/bull-shared`12 resolves; `pytest tests/test_nestjs_lockfile_sync.py` green.

- [ ] **✔ CHECKPOINT 1 — core + native validation green** → review with human before Phase 2.

## Phase 2 — Remaining upgrades + toolchain + docs
- [ ] **T6** Prisma trio→7.10.0 + prisma-zod-generator→3.3.1 + jest30.5.2/ts-jest29.4.14/tsc-alias1.9.5/eslint10.11.0 + `@types/node`→24.19.0 + supertest pair — 3 `package.json` · S · **do NOT touch `typescript`**
  → Prisma trio aligned; `@types/node` on 24; `typescript` still 6.0.3.
- [ ] **T7** supabase→`@supabase/supabase-js`2.117.2; entra→`jsonwebtoken`9.0.3 + `@types/jsonwebtoken`9.0.10 + `jwks-rsa`4.1.0 — 2 `package.json` · XS
- [ ] **T8** baml pin: `@boundaryml/baml` + `generators.baml` → matching latest · XS
  → `baml-cli generate` no version-mismatch (checked at T11).
- [ ] **T9** Terminus 12 health: `dbPing()` 200/503 still works (throw=500, returned `.down()`=503); migrate to `HealthIndicatorService` only if regressed · S
- [ ] **T10** Docs sync: `docs_generator.py` — swap `nestjs-zod` guidance for native validation; drop stale `node:22`/versions; reflect bullmq 6 + ioredis; fix repo `CLAUDE.md` NestJS section · M
  → `pytest tests/test_docs_*.py` green.
- [ ] **T11** Regenerate 3 locks on `node:24-alpine` + FULL verify — 3 `package-lock.json` · M
  → all 4 variants build; readiness up (base+entra); `npm test` + `test:e2e` per variant; full `pytest` green.
- [ ] **T12** jwks-rsa 4 / jose 6 Jest fix — *conditional* moduleNameMapper stub in entra jest config · XS–S
  → entra auth specs pass; runtime path untouched.

- [ ] **✔ CHECKPOINT 2 — green baseline (shippable minus TS7)** → review with human before Phase 3.

## Phase 3 — TypeScript 7 (isolated last; expected red)
- [ ] **T13** `typescript` → 7.0.2 — 3 `package.json` · XS
- [ ] **T14** TS7 tsconfig surgery (drop `baseUrl`+`ignoreDeprecations`, rewrite `paths`; ≤5 files) · M
- [ ] **T15** TS7 lock/build attempt + document blocking (ERESOLVE `ts-jest` peer `<7`; `nest build` blocked — CLI pins `~6.0.2`); record revert-vs-tracked-red; peer-bypass **ask-first** · S

- [ ] **✔ CHECKPOINT 3 — final** → non-TS7 shippable; TS7 per human decision; reconcile `SPEC.md`.

## Standing gates (every task)
- [ ] Exact-version pins; no `package.json` reordering.
- [ ] Locks only ever regenerated on `node:24-alpine`.
- [ ] `token` overlay: no `package.json`/lock (tsconfig edit only, T14).
- [ ] No overlay `README.md`/`CLAUDE.md`; doc changes via `docs_generator.py`.
- [ ] No `nestjs-zod` import or dependency remains anywhere.
