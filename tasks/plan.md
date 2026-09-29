# Implementation Plan: NestJS API Template — NestJS 12 Upgrade

Derived from `SPEC.md` and the live-source research of 2026-09-29 (see memory
`nestjs-12-migration-research`). Read-only planning artifact — the only code changed so far is T1
(Node 24 base, committed `b8c7686`).

## Overview

Upgrade the three NestJS overlays (`templates-api-nestjs`, `templates-supabase-nestjs`,
`templates-entra-nestjs`; `token` inherits the base) from NestJS 11.1.24 to **NestJS 12.1.1** on a
Node 24 base, in one sweep. Verified facts changed two premises from the original plan:

1. **`nestjs-zod` has no NestJS 12 peer** (`@nestjs/common ^10 || ^11`) → `npm ci` ERESOLVE. The user
   chose to **drop `nestjs-zod` and migrate to the framework-native `StandardSchemaValidationPipe` /
   `StandardSchemaSerializerInterceptor`** rather than a peer-`overrides` bridge. This is a real code
   refactor across all overlays, not a version bump.
2. **`@nestjs/bullmq` 12 does NOT force bullmq 6** (peer `^3||^4||^5||^6`). The user chose to
   **go to bullmq 6.3.9 + ioredis 6.0.0 anyway**. Our template uses none of bullmq 6's removed APIs
   (legacy repeatable jobs, `Queue#client`, `debounce`, async `resume()`), so the runtime risk is the
   ioredis wiring, caught by the readiness smoke.

The build-blocking **TypeScript 7** attempt stays isolated last (Phase 3); research confirms it is
blocked (`@nestjs/cli` pins `typescript ~6.0.2`; TS7 lacks the programmatic API the CLI needs).

## Locked decisions

- All-at-once delivery (one PR/sweep), executed in verifiable phases · Node 24 base
  (`node:24-alpine`; locks regenerated on it) · Jest stays (base already jest 30) — valid because
  Node ≥ 24.9 can load the ESM-only v12 packages · zod stays 4.4.3 (≥ 4.2 → `@nestjs/swagger` 12
  converts schemas with zero config) · TS held at 6.0.3 until Phase 3 · verification bar = build +
  tests + mandatory runtime smoke.

## Architecture Decisions

- **Core 12 ⇄ `nestjs-zod` removal ⇄ swagger 12 are one coupled unit.** Bumping `@nestjs/*` to 12
  ERESOLVEs while `nestjs-zod` is present; the native pipe only exists in v12; `@nestjs/swagger` 12
  peers `@nestjs/core ^12` only. So the manifest bump, the `nestjs-zod` code migration, and swagger
  12 must land together (Phase 1) and are verified as one green state.
- **Fail fast on the queue + validation stack.** Phase 1 carries the two highest-risk changes
  (ioredis wiring, native-validation refactor) behind a runtime smoke gate (Checkpoint 1).
- **Native validation, request vs response asymmetry.** `@nestjs/swagger` 12 auto-documents request
  bodies/queries/params from `@Body({ schema })` (zero-config on zod ≥ 4.2), but **response docs are
  NOT automatic** — every handler that used `@ZodSerializerDto` needs an explicit
  `@ApiOkResponse`/`@ApiCreatedResponse({ standardSchema })` + `@SerializeOptions({ schema })`.
- **Lock regen is idempotent**, always on `node:24-alpine`, never the host. Intermediate regens are
  throwaway; only the final committed lock per `package.json` matters.
- **TS7 isolated last** keeps a green, shippable non-TS7 baseline at Checkpoint 2.

## Verified target versions (npm `latest`, 2026-09-29)

| Package | From | To | Peer note |
|---|---|---|---|
| `@nestjs/{common,core,platform-express,testing}` | 11.1.24 | **12.1.1** | ESM-only |
| `@nestjs/config` | 4.0.4 | **12.0.1** | `^11 \|\| ^12` |
| `@nestjs/swagger` | 11.4.4 | **12.0.2** | `@nestjs/core ^12` only, ESM |
| `@nestjs/terminus` | 11.1.1 | **12.1.0** | `^11 \|\| ^12`; base class removed (our `dbPing` is safe) |
| `@nestjs/throttler` | 6.5.0 | **6.7.1** | includes `^12` |
| `@nestjs/cli` | 11.0.21 | **12.0.8** | bundles `typescript ~6.0.2` |
| `@nestjs/schematics` | 11.1.0 | **12.0.6** | node `^22.22.3 \|\| ^24.15 \|\| >=26` |
| `@nestjs/bullmq` | 11.0.4 | **12.0.0** | `bullmq ^3..^6`, `@nestjs/core ^10..^12` |
| `bullmq` | 5.78.0 | **6.3.9** | ioredis now optional peer `>=5` |
| `ioredis` | (none) | **6.0.0** | new direct dep; needs Node ≥ 20 |
| `@bull-board/{api,express,nestjs}` | 8.0.0 | **9.10.1** | `@nestjs/core ^9..^12`, `bullmq ^5.56 \|\| ^6`, `@nestjs/bull-shared ^10..^12` |
| `nestjs-pino` | 4.6.1 | **5.2.1** | forces `pino ^10`, `pino-http ^11` |
| `pino` / `pino-http` | 9.14.0 / 10.5.0 | **10.x / 11.x** | confirm exact latest at edit |
| `pino-pretty` | 13.1.3 | latest 13.x | bump alongside pino 10 |
| `nestjs-zod` | 5.4.0 | **removed** | no v12 peer; replaced by native |
| `zod` | 4.4.3 | **unchanged** | ≥ 4.2 → swagger zero-config |
| `prisma`/`@prisma/client`/`@prisma/adapter-pg` | 7.8.0 | **7.10.0** | aligned trio |
| `prisma-zod-generator` | 2.1.4 | **3.3.1** | `@prisma/client ^7.9`; no `@nestjs` peer |
| `jest` / `ts-jest` / `tsc-alias` / `eslint` | 30.4.2 / 29.4.11 / 1.8.16 / 10.4.1 | **30.5.2 / 29.4.14 / 1.9.5 / 10.11.0** | ts-jest peer `typescript <7` |
| `@types/node` | 25.9.1 | **24.19.0** | match Node 24 runtime |
| `@supabase/supabase-js` (supabase) | — | **2.117.2** | overlay |
| `jsonwebtoken`/`@types/jsonwebtoken`/`jwks-rsa` (entra) | — | **9.0.3 / 9.0.10 / 4.1.0** | overlay |

> Exact latest patch for pino/pino-http/prisma/jest should be re-confirmed at edit time; the
> NestJS/bullmq/nestjs-zod/swagger facts above are live-verified.

## Task List

### Phase 0 — Foundation

#### Task 1 ✅ DONE — Node 24 base
Both `FROM` stages of `templates-api-nestjs/api/Dockerfile` on `node:24-alpine`. Committed `b8c7686`;
guarded by `tests/test_nestjs_node_base_image.py`. Runtime `node -v` check deferred to Checkpoint 1.

### Phase 1 — NestJS 12 core + native validation + queue (coupled, fail-fast)

#### Task 2 — Manifests: NestJS 12 set + queue + pino, remove nestjs-zod
**Description:** In all 3 `package.json`, apply the version table above: the 11 `@nestjs/*` targets,
`@nestjs/bullmq` 12.0.0, `bullmq` 6.3.9, **add `ioredis` 6.0.0**, `@bull-board/*` 9.10.1,
`nestjs-pino` 5.2.1 + `pino` 10.x + `pino-http` 11.x (+ `pino-pretty`), and **delete the `nestjs-zod`
dependency**. Keep `zod` 4.4.3. Do NOT touch `typescript`.
**Acceptance:** all 3 parse as valid JSON with exact pins; `nestjs-zod` absent from all 3; `ioredis`
present in all 3; `@nestjs/swagger` = 12.0.2 (core-12 only); targets consistent across
base/supabase/entra.
**Verification:** static grep + JSON lint now; install/build deferred to T5. (Source temporarily
imports the removed `nestjs-zod` — expected red until T3.)
**Depends on:** T1. **Files:** the 3 `package.json`. **Scope:** S

#### Task 3 — Native validation refactor (drop nestjs-zod in code)
**Description:** Across all overlays, replace the `nestjs-zod` surface with NestJS 12 native APIs:
- `app.module.ts` (×4): `APP_PIPE` → `StandardSchemaValidationPipe`, `APP_INTERCEPTOR` →
  `StandardSchemaSerializerInterceptor` (both from `@nestjs/common`/`@nestjs/core`).
- DTOs (`createZodDto(X)` in test/auth/chatbot dto files): keep the zod schemas, export
  `type XDto = z.infer<typeof XSchema>`; drop the generated classes.
- Controllers: `@Body() dto: XDto` → `@Body({ schema: XSchema }) dto: z.infer<...>`; replace
  `@ZodSerializerDto(XDto)` with `@SerializeOptions({ schema: XSchema })` **and**
  `@ApiOkResponse`/`@ApiCreatedResponse({ standardSchema: XSchema })` so response docs are retained.
- `main.ts`: remove `cleanupOpenApiDoc` / any `patchNestjsSwagger` (swagger 12 auto-reads schemas).
- Update `src/modules/test/serialization.spec.ts` and the pytest that asserts `nestjs-zod`
  (`tests/test_issue_003_zod_serialization.py`) to assert the native metadata instead.
**Acceptance:** no `nestjs-zod` import anywhere under the NestJS overlays; global native pipe +
interceptor wired in all 4 `app.module.ts`; every previously-serialized handler has an explicit
response schema; TS compiles.
**Verification (RED-first):** new test asserts zero `nestjs-zod` imports remain and that the built
OpenAPI doc contains both request and response schemas; full nestjs unit suite green at T5.
**Depends on:** T2. **Files:** ~15 `.ts` across the 4 overlays + 2 spec/test files. **Scope:** L

#### Task 4 — bullmq 6 wiring + audit
**Description:** Confirm `chat.processor.ts` (`@Processor`/`WorkerHost`/`OnWorkerEvent`) and
`chat-job.service.ts` (`Queue` enqueue) compile against bullmq 6; ensure `BullModule.forRoot`
connection resolves through `ioredis`. No removed-API usage exists (verified), so no code change is
expected — this task is the guard, not a rewrite.
**Acceptance:** processor + queue code typechecks on bullmq 6; readiness smoke (T5) proves the
BullMQ→ioredis→Redis path.
**Depends on:** T2. **Files:** none expected (guard only). **Scope:** XS

#### Task 5 — Regenerate locks + core verification (Phase-1 gate)
**Description:** Regenerate the 3 `package-lock.json` on `node:24-alpine`; scaffold base + entra;
build the API image; run the mandatory runtime smoke.
**Acceptance:** `npm ci` succeeds in `docker compose build api` (base + entra); `docker compose up`
→ `GET /api/v1/health/readiness` = `database: up`; Bull-board reachable at `/api/v1/admin/queues`;
`npm test` green (ESM v12 loads under Node ≥ 24.9); generated OpenAPI has request+response schemas;
`@nestjs/bull-shared` 12.x resolves in the lock.
**Verification:** `docker run --rm -v "$PWD:/w" -w /w node:24-alpine npm install --package-lock-only
--ignore-scripts` per api dir; `pytest tests/test_nestjs_lockfile_sync.py`; smoke curl + `npm test`.
**Depends on:** T2, T3, T4. **Files:** the 3 `package-lock.json`. **Scope:** M

> ### Checkpoint 1 — Core platform + native validation green
> - [ ] Node 24 confirmed in-container (`node -v` ≥ 24.9).
> - [ ] base + entra build; readiness = up; queue + Swagger + validation tests pass.
> - [ ] `test_nestjs_lockfile_sync.py` green. **Review with human before Phase 2.**

### Phase 2 — Remaining upgrades + toolchain + docs

#### Task 6 — Prisma + zod-generator + test/lint + @types/node
**Description:** In all 3 `package.json`: Prisma trio → 7.10.0 (aligned), `prisma-zod-generator` →
3.3.1, `jest` → 30.5.2, `ts-jest` → 29.4.14, `tsc-alias` → 1.9.5, `eslint` → 10.11.0,
`@types/node` → 24.19.0, `supertest`+`@types/supertest` co-bumped. **Do not touch `typescript`.**
**Acceptance:** Prisma trio aligned; `@types/node` on 24 line; `typescript` still 6.0.3.
**Verification:** static now; at T11 `npx prisma generate` populates `generated/zod/schemas/`,
`tsc --noEmit` clean, `test:e2e` passes. **Depends on:** T5. **Scope:** S

#### Task 7 — Auth-overlay extras
supabase → `@supabase/supabase-js` 2.117.2; entra → `jsonwebtoken` 9.0.3 + `@types/jsonwebtoken`
9.0.10 + `jwks-rsa` 4.1.0 (one edit). **Depends on:** T6. **Scope:** XS

#### Task 8 — baml pin
`@boundaryml/baml` + `baml_src/generators.baml` bumped to matching latest; `baml-cli generate` emits
no version-mismatch (checked at T11). **Depends on:** T5. **Scope:** XS

#### Task 9 — Terminus 12 health verify
Confirm `dbPing()`'s plain result still drives 200/503 via `HealthCheckService.check()`. Note the v12
semantics: a **thrown** error now = 500, only a returned `.down()` = 503 — verify the down path
returns `.down()` (migrate to `HealthIndicatorService` only if regressed).
**Verification:** `npm test` health spec; compose up, stop `db`, re-curl → 503. **Depends on:** T5. **Scope:** S

#### Task 10 — Docs sync
In `docs_generator.py`: replace all `nestjs-zod`/Zod-DTO validation guidance with the native
`StandardSchemaValidationPipe` + `@Body({ schema })` pattern; remove any `node:22` / stale version
strings; reflect bullmq 6 + ioredis. Update the repo `CLAUDE.md` NestJS section if it names
`nestjs-zod`. **Verification:** `pytest tests/test_docs_*.py` green. **Depends on:** T1, T3, T6–T8. **Scope:** M

#### Task 11 — Regenerate locks + full verification (Phase-2 gate)
Regenerate 3 locks on `node:24-alpine`; scaffold all four variants; build, smoke, unit + e2e per
variant; full `pytest`. **Acceptance:** all four build; readiness up (base+entra); `npm test` +
`test:e2e` pass; full `pytest` green. **Depends on:** T6–T10. **Scope:** M

#### Task 12 — jwks-rsa 4 / jose 6 Jest fix (conditional)
If entra `npm test` throws `Cannot require() ES Module` (jose 6 ESM under Jest), add the
`moduleNameMapper` stub for `jwks-rsa` (+ `test-stubs/jwks-rsa.stub.ts`); runtime path untouched.
**Depends on:** T7, T11. **Scope:** XS–S

> ### Checkpoint 2 — Green baseline (shippable minus TS7)
> - [ ] All four variants build + test + smoke green on Node 24; full `pytest` green.
> - [ ] Fallback ship state if TS7 is deferred. **Review with human before Phase 3.**

### Phase 3 — TypeScript 7 (isolated last; expected red)

#### Task 13 — `typescript` → 7.0.2 (3 `package.json`). **Scope:** XS
#### Task 14 — TS7 tsconfig surgery (drop `baseUrl`/`ignoreDeprecations`, rewrite `paths`; ≤5 files). **Scope:** M
#### Task 15 — TS7 lock/build attempt + document blocking
Capture the two blockers (research-confirmed): `npm install --package-lock-only` ERESOLVE on
`ts-jest` peer `typescript <7`; `nest build` blocked (CLI pins `~6.0.2`, TS7 lacks the programmatic
API). Record revert-to-6.0.3-to-ship vs tracked-red decision. Peer-bypass is **ask-first**. **Scope:** S

> ### Checkpoint 3 — Final
> - [ ] Non-TS7 sweep green + shippable; TS7 status documented per human decision; `SPEC.md` reconciled.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `nestjs-zod` blocks `npm ci` on NestJS 12 | High | Remove it; native pipe (T2/T3). |
| Native migration regresses **response** OpenAPI docs | High | T3 adds explicit `@ApiOkResponse({ standardSchema })` per serialized handler; T5 asserts request+response schemas present. |
| bullmq 6 drops bundled ioredis → runtime crash invisible to unit tests | High | Add ioredis 6.0.0 (T2); readiness smoke (T5). |
| swagger 12 is core-12-only + ESM | Med | Bump atomically in Phase 1; Jest runs on Node ≥ 24.9. |
| Jest + ESM v12 cycle error via CJS peer (`@nestjs/throttler` still CJS) | Med | Watch T5/T11 `npm test`; if `ERR_REQUIRE_CYCLE_MODULE`, apply a `moduleNameMapper` stub like T12. |
| nestjs-pino 5 forces pino 10 + pino-http 11 | Med | Co-bump all three + pino-pretty (T2); dev-log check at T11. |
| TS7 blocks `npm ci`/`nest build` | High | Isolate to Phase 3; keep Checkpoint 2 baseline; peer-bypass ask-first. |
| Lock regenerated on host | Med | Always `node:24-alpine`; `test_nestjs_lockfile_sync.py`. |

## Open Questions

1. **TS7 end-state:** revert to 6.0.3 to ship, or keep a tracked-red TS7 branch? (Default: revert.)
2. **Native DTO shape:** export `z.infer` type aliases vs a thin schema-only module — pick the form
   that keeps service signatures readable (decide in T3).
3. **`@types/node`:** hold at 24.19.0 (match runtime) even though 25.9.1 is currently pinned.

## Definition of Done (every task clears this)

- Exact-version pins; no `package.json` reordering/reformatting.
- Locks regenerated on `node:24-alpine`; `test_nestjs_lockfile_sync.py` green for all four auth modes.
- No `README.md`/`CLAUDE.md` in overlays; user-facing doc changes via `docs_generator.py`.
- `token` overlay has no `package.json`/lock (only its `tsconfig.json` is edited, in T14).
- No `nestjs-zod` import or dependency remains anywhere.
- Full `pytest` green (except the explicitly-tracked TS7 build caveat).

## Standing gates (every task)

- [ ] Exact-version pins; no `package.json` reordering.
- [ ] Locks only ever regenerated on `node:24-alpine`.
- [ ] `token` overlay: no `package.json`/lock (tsconfig edit only).
- [ ] No overlay `README.md`/`CLAUDE.md`; doc changes via `docs_generator.py`.
