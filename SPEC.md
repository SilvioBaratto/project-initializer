# Spec: NestJS API Template — Dependency Upgrade to Latest npm Releases

## Objective

Bring the NestJS API templates up to the latest npm releases in a single coordinated
sweep, so that every project scaffolded by `project-initializer --nestjs` ships current,
supported dependencies on the **Node 24 Active-LTS** runtime, still `npm ci` + `nest build`
cleanly, and passes the repo's `pytest` suite.

Scope is the **three NestJS overlays that own a `package.json`**:

- `project_initializer/templates-api-nestjs/api/` (base; also used by the `token` variant)
- `project_initializer/templates-supabase-nestjs/api/`
- `project_initializer/templates-entra-nestjs/api/`

The `token` overlay ships no `package.json` and inherits the base pair — it must **not**
gain one. Only the base overlay ships a `Dockerfile` (inherited by all variants). FastAPI
templates and the Angular frontend are out of scope.

> **Status: SPEC ONLY.** No template files have been edited. This document is for review;
> nothing is applied until explicitly approved.

## Intake Decisions (locked)

| Decision | Choice | Notes |
|---|---|---|
| Batching | **All-at-once** | One pass across the three `package.json` files; regenerate the three locks; fix fallout together. |
| TypeScript | **Attempt TS 7.0.2** | Chosen despite research showing it currently breaks `nest build` + `npm ci` (see Group 4). Documented as a target with its full migration recipe and known-blocking status. |
| Prisma | **Hold at 7.10.0 stable** | Not the `8.0.0-rc.17` that npm mislabels `latest`. |
| Runtime base | **Node 24 (Active LTS)** | `node:24-alpine` (both `FROM` lines) + `@types/node@24.19.0`; locks regenerated on `node:24-alpine`. Chosen over Node 26 (still "Current", LTS ~Oct 2026) because a scaffolding template should stamp the Active LTS. |
| Verification bar | **Build + tests** | Scaffold, regen locks on `node:24-alpine`, `docker compose build api`, full `pytest` — plus a mandatory bullmq/ioredis runtime smoke test. |

## Deliberate Non-"latest" Pins (with rationale)

Not every package goes to its bare npm `latest`; each exception is a research finding, not a
preference:

1. **Prisma trio → `7.10.0` (not `8.0.0-rc.17`).** npm's `prisma` `latest` dist-tag points at a
   release candidate; `@prisma/client` `latest` is stable `7.10.0`. Keep `prisma`,
   `@prisma/client`, `@prisma/adapter-pg` on `7.10.0` and aligned.

2. **`@types/node` → `24.19.0` (not `26.6.3`).** Types must match the runtime. The base is Node 24
   LTS, so the Node-24 types line is correct; the npm `latest` (v26) would type APIs absent at
   runtime.

3. **`typescript` → `7.0.2` is a *known-blocking* target.** Chosen by intake. It cannot produce a
   green Docker build today (see Group 4). Included as the target with its migration recipe; expect
   the build gate to remain red until upstream support lands (`ts-jest` peer + `@nestjs/cli` TS 7.1).

## Applied Version Matrix

Pin **exact** versions (repo convention — no caret ranges). "—" = already at target, no edit.

### Runtime base (base overlay only — `templates-api-nestjs/api/Dockerfile`)

| Item | Current | Target |
|---|---|---|
| Docker base (both `FROM` lines) | `node:22-alpine` | `node:24-alpine` |
| Lockfile regeneration platform | node:22-alpine | **node:24-alpine** |

### Base + shared (all three `package.json`)

#### dependencies

| Package | Current | Target | Jump | Risk |
|---|---|---|---|---|
| @nestjs/common | 11.1.24 | 12.1.1 | major | med |
| @nestjs/core | 11.1.24 | 12.1.1 | major | med |
| @nestjs/platform-express | 11.1.24 | 12.1.1 | major | low |
| @nestjs/config | 4.0.4 | 12.0.1 | major* | low |
| @nestjs/swagger | 11.4.4 | 12.0.2 | major | low |
| @nestjs/terminus | 11.1.1 | 12.1.0 | major | med |
| @nestjs/bullmq | 11.0.4 | 12.0.0 | major | low |
| @nestjs/throttler | 6.5.0 | 6.7.1 | minor | low |
| @bull-board/api | 8.0.0 | 9.10.1 | major | low |
| @bull-board/express | 8.0.0 | 9.10.1 | major | low |
| @bull-board/nestjs | 8.0.0 | 9.10.1 | major | low |
| bullmq | 5.78.0 | 6.3.9 | major | med |
| **ioredis** | *(absent)* | **5.11.1** | **new** | med |
| @prisma/client | 7.8.0 | 7.10.0 | minor | low |
| @prisma/adapter-pg | 7.8.0 | 7.10.0 | minor | low |
| @boundaryml/baml | 0.223.0 | 0.226.2 | minor | low |
| helmet | 8.2.0 | 8.3.0 | minor | none |
| nestjs-pino | 4.6.1 | 5.2.1 | major | low |
| nestjs-zod | 5.4.0 | 5.5.0 | minor | none |
| pg | 8.21.0 | 8.23.0 | minor | low |
| pino | 9.14.0 | 10.3.1 | major | none |
| pino-http | 10.5.0 | 11.0.0 | major | none |
| uuid | 14.0.0 | 14.0.2 | patch | none |
| zod | 4.4.3 | 4.6.5 | minor | low |
| express-basic-auth | 1.2.1 | — | none | none |
| reflect-metadata | 0.2.2 | — | none | none |
| rxjs | 7.8.2 | — | none | none |

\* `@nestjs/config` 4→12 is a version-line **renumber** to match the platform, not 8 majors of breakage.

#### devDependencies

| Package | Current | Target | Jump | Risk |
|---|---|---|---|---|
| @nestjs/cli | 11.0.21 | 12.0.8 | major | low |
| @nestjs/schematics | 11.1.0 | 12.0.6 | major | low |
| @nestjs/testing | 11.1.24 | 12.1.1 | major | low |
| prisma | 7.8.0 | 7.10.0 | minor | low |
| prisma-zod-generator | 2.1.4 | 3.3.1 | major | low |
| jest | 30.4.2 | 30.5.2 | minor | low |
| @types/supertest | 6.0.2 | 7.2.1 | major | low |
| supertest | 7.1.0 | 7.3.0 | minor | low |
| eslint | 10.4.1 | 10.11.0 | minor | low |
| ts-jest | 29.4.11 | 29.4.14 | patch | low |
| tsc-alias | 1.8.16 | 1.9.5 | minor | low |
| @types/node | 25.9.1 | **24.19.0** | *(align to LTS)* | med |
| **typescript** | 6.0.3 | **7.0.2** | **major** | **high / blocking** |
| pino-pretty | 13.1.3 | — | none | none |
| @types/express | 5.0.6 | — | none | none |
| @types/jest | 30.0.0 | — | none | none |
| @types/uuid | 11.0.0 | — (optional remove) | none | none |
| ts-node | 10.9.2 | — | none | none |
| tsconfig-paths | 4.2.0 | — | none | none |

### Auth-overlay extras

| Overlay | Package | Current | Target | Jump | Risk |
|---|---|---|---|---|---|
| supabase | @supabase/supabase-js | 2.107.0 | 2.117.2 | minor | low |
| entra | jsonwebtoken | 9.0.2 | 9.0.3 | patch | none |
| entra | @types/jsonwebtoken | 9.0.9 | 9.0.10 | patch | none |
| entra | jwks-rsa | 3.1.0 | 4.1.0 | major | med |

## Per-Package Detail — What To Do

Grouped by ecosystem. Every version edit lands in **all three** `package.json` unless the
row says "base only" / "supabase only" / "entra only". No source change is required except
where explicitly listed under **Code/config**.

### Group 1 — NestJS platform 11 → 12 (atomic set)

All eleven `@nestjs/*` packages share tight peer constraints and **must move in one commit**.

- **Breaking changes that matter here:** Node floor `>=22.12` (Node 24 base satisfies it); core
  packages now pure ESM but CJS output keeps working via Node's `require(esm)` (`skipLibCheck: true`
  means no type-resolution errors); Express 5 was already default in v11; path-to-regexp v8 wildcard
  syntax — **no wildcard routes exist**; `@Optional()` no longer inherited by subclasses — **no
  subclassed providers**; lifecycle hooks now ordered by hierarchy depth — no deliberate cross-module
  ordering exists.
- **`@nestjs/config` 4→12:** the `validate` function option (used in `src/config/env.validation.ts`
  via Zod `.safeParse()` + `.passthrough()`) is unaffected; only `validationSchema` (unused) changed.
- **`@nestjs/terminus` 12 — the one real code change (base only):** the legacy `HealthIndicator`
  base class + `getStatus()` are removed. `dbPing()` in `src/modules/health/health.controller.ts`
  returns a **plain** `HealthIndicatorResult` (`{ database: { status: 'up'|'down' } }`) and never
  extends the removed class, so it likely still works — **verify** against v12's
  `HealthCheckService.check()`. If the plain-object path regresses, migrate `dbPing()` to the new
  `HealthIndicatorService` API (inject it, provide it in `health.module.ts`, return `.up()`/`.down()`).
- **`@nestjs/bullmq` 12:** required by the bullmq 6 bump (v11 peer rejects bullmq 6). The
  `WorkerHost` + `@Processor` + `@OnWorkerEvent` pattern is unchanged.
- **Actions:** bump all eleven to the matrix versions in the three `package.json`; verify/migrate the
  health controller (base only); no other source edits.

### Group 2 — Bull Board 8 → 9 + bullmq 5 → 6 (+ ioredis)

- **`@bull-board/{api,express,nestjs}` 8→9:** no server-side API break — `BullMQAdapter`,
  `ExpressAdapter`, `BullBoardModule.forRoot/forFeature`, the `middleware` option (basic-auth in
  token/supabase/entra), and `BULL_BOARD_INSTANCE` are unchanged. The three **must move in lockstep**
  (shared internal types); v9 declares bullmq peer `^5.56 || ^6`.
- **bullmq 5→6 — highest runtime risk:** `ioredis` is no longer bundled (now an optional peer).
  **`npm ci` installs bullmq 6 without ioredis and the app crashes at startup** when
  `BullModule.forRoot` opens a Redis connection. Invisible to `nest build` and unit tests (which mock
  the queue) — **only a `docker compose up` smoke test catches it.** Removed APIs (repeatable-job
  legacy calls, `Job#discard`, `Queue#client`, debounce, paused state) are **not used**. Flow job IDs
  are now UUID strings — `ChatJobService.enqueueChat` casts `job.id` to string, still safe.
- **Code/config:** **add `"ioredis": "5.11.1"`** to `dependencies` in all three `package.json`. At
  apply time, read bullmq 6's declared `peerDependencies.ioredis` range; only pin `ioredis@6.0.0` if
  that range includes it, otherwise keep `5.11.1`.
- **Actions:** bump the three bull-board packages + bullmq + (Group 1's) `@nestjs/bullmq@12`, add
  ioredis, in one pass. No `.ts` changes.

### Group 3 — pino stack (pino 10 / pino-http 11 / nestjs-pino 5)

- **All three move together** — `nestjs-pino@5` peer-requires `pino@^10` + `pino-http@^11`.
- **Breaking changes that matter here:** none for this repo. pino 10 drops Node 18, removes
  `prettyPrint` (template uses `transport`) and the `pino` CLI (unused), swaps
  `fast-redact`→`slow-redact` (external `redact` API unchanged). pino-http 11's only change is the
  `pino@^10` peer bump; `genReqId` signature unchanged. nestjs-pino 5 removes deep sub-path imports —
  template imports only the main entry.
- **Code/config:** none. `src/config/logger.config.ts` (transport, genReqId, redact, level) is stable.

### Group 4 — TypeScript toolchain (TS7 attempt — known-blocking)

- **`ts-jest` 29.4.11 → 29.4.14 (patch):** safe. **Its peer is `typescript >=4.3 <7`** — this is the
  first hard TS7 blocker. Apply the patch regardless.
- **`tsc-alias` 1.8.16 → 1.9.5 (minor):** CLI-only usage; 1.9.5 fixes a false-rewrite case for
  `baseUrl` setups. Apply.
- **`@types/node` 25.9.1 → 24.19.0:** align to the Node 24 LTS base (see Deliberate Pins #2). `@types/node`
  patch (24.19.0) and the runtime patch (`node:24-alpine`) track independently — both on the 24 line.
- **`ts-node` / `tsconfig-paths`:** already latest, no change (both also break under TS7, see below).

- **`typescript` 6.0.3 → 7.0.2 (chosen) — full recipe + honest status:**

  **Required tsconfig surgery** (base `tsconfig.json`, plus any overlay that ships its own — verify
  at apply time):
  1. Remove `"baseUrl": "./"` (hard error in TS7).
  2. Rewrite `paths` to `./`-prefixed roots:
     `"@/*": ["./src/*"]`, `"@generated/prisma": ["./generated/prisma/client"]`,
     `"@generated/zod": ["./generated/zod/schemas/index"]`, `"@generated/zod/*": ["./generated/zod/schemas/*"]`.
  3. Remove `"ignoreDeprecations": "6.0"` (invalid flag in TS7).

  **Blockers that prevent a green build today (not fixable in this repo alone):**
  - `ts-jest@29.4.x` peer `typescript <7` → `npm ci` in the Dockerfile hard-fails on peer conflict.
    (A `--legacy-peer-deps` / npm `overrides` hack bypasses install but does not fix the next item.)
  - `nest build` calls the TS **programmatic API** (`createProgram`/`program.emit`), removed until
    TS 7.1 → build emits **zero files** / crashes.
  - `ts-node` (dev `--watch`) uses the same programmatic API → dev server breaks.

  **Consequence:** with TS7 in the sweep, the **"docker build green" success criterion cannot pass**
  until `ts-jest` lifts the `<7` peer **and** `@nestjs/cli` gains TS 7.1 programmatic-API support.
  **Sequencing recommendation (does not re-litigate the choice):** apply TS7 as the **last, isolated
  layer** so the other ~40 upgrades can be built and verified green independently; keep TS7's tsconfig
  edits in a separate commit that can be reverted without unwinding the rest.

### Group 5 — Prisma (client/CLI/adapter 7.10 + zod generator 3)

- **`prisma` / `@prisma/client` / `@prisma/adapter-pg` 7.8 → 7.10 (minor, keep aligned):** no relevant
  break. 7.9 raw-query fails fast on invalid `Date` (no raw Date params); 7.10 P2002 preserves
  constraint names via adapter-pg (filter reads `error.meta?.target` array — path unchanged); 7.10
  maps deadlocks→P2034, RESTRICT→P2003 (filter has a catch-all). **No schema change → no new migration.**
- **`prisma-zod-generator` 2 → 3 (major):** v3's breaking items are all pro-tier (policy matching,
  Performance Pack, Server Actions); template uses OSS core with `provider` + `output` only. Output
  structure (`<output>/schemas/` + `index.ts` barrel) unchanged, so jest `moduleNameMapper` +
  tsconfig `paths` for `@generated/zod` need no edit. Requires Prisma `^7` (met); zod peer `>=3.25 <5`
  (met). *Confidence: medium* — v3.3.1's tested Prisma range tops at 7.9; run `npx prisma generate`
  right after bumping.
- **Code/config:** none required. Optional: add `zodImportTarget = "v4"` to each `schema.prisma` zod
  generator block.

### Group 6 — Test + lint (jest / supertest / eslint)

- **`jest` 30.4.2 → 30.5.2 (minor):** no behavior change (30.5.1 regression reverted).
- **`@types/supertest` 6 → 7 (major) + `supertest` 7.1 → 7.3 (minor) — co-upgrade:** the major is a
  version-align, not a type break; v7 keeps `export = supertest`, so `import * as request from
  'supertest'` stays valid under `module: commonjs`. Apply both together.
- **`eslint` 10.4.1 → 10.11.0 (minor):** **no active config** (no `eslint.config.js`/`.eslintrc.*`),
  so the bump is inert; pre-existing "no config" condition noted, out of scope.
- **`@types/jest`:** already latest — exclude from the PR.

### Group 7 — Runtime libs (baml / helmet / pg / zod / nestjs-zod / uuid)

- **`@boundaryml/baml` 0.223 → 0.226.2:** no `b.*` / `b.stream` API break. **Code/config (base only):**
  update `templates-api-nestjs/api/baml_src/generators.baml` `version "0.223.0"` → `"0.226.2"` — a
  mismatch makes `npx baml-cli generate` warn/fail. supabase/entra inherit the base `baml_src`.
  *Confidence: medium* — re-run `baml-cli generate` after bumping.
- **`zod` 4.4.3 → 4.6.5 + `nestjs-zod` 5.4 → 5.5 — co-upgrade:** nestjs-zod 5.5 carries a named-schema
  fix targeting zod `>=4.4`. zod 4.6 changes are additive / lazy error-maps (`env.validation.ts` reads
  `.error.issues` only after `!success`, correct). No code change.
- **`helmet` 8.2 → 8.3, `pg` 8.21 → 8.23, `uuid` 14.0.0 → 14.0.2:** additive/patch, no impact.
- **`@types/uuid` (optional):** uuid v14 bundles its own types; optional cleanup = remove from all
  three `devDependencies`.

### Group 8 — Auth overlays

- **supabase — `@supabase/supabase-js` 2.107 → 2.117.2 (minor, supabase only):** no impact.
  `createClient(url, key)` + `auth.getUser(jwt)` unchanged (v2.110 enforces Node `>=22`, met by Node 24).
  Optional: `auth.getClaims(jwt)` for asymmetric-key projects — not required.
- **entra — `jsonwebtoken` 9.0.3 + `@types/jsonwebtoken` 9.0.10 (patch, entra only):** no impact.
- **entra — `jwks-rsa` 3.1 → 4.1 (major, entra only) — verify Jest:** runtime path
  (`new JwksClient({ jwksUri, cache, rateLimit })` + callback `getSigningKey`) unchanged; ES256K
  removal irrelevant (Entra uses RS256). **Risk:** v4 pulls `jose@6` (ESM-only, currently 6.2.12).
  Node 24 loads it via `require(esm)`, but **Jest's module sandbox may throw "Cannot require() ES
  Module"** when `auth.guard.spec.ts` loads `AuthService`. **Code/config (entra only), only if Jest
  fails:** add `moduleNameMapper` `"^jwks-rsa$": "<rootDir>/../test-stubs/jwks-rsa.stub"` to the entra
  `package.json` jest config + a stub exporting a mock `JwksClient` (the guard spec already mocks
  `AuthService`). Bump all three entra packages in one pass.

## Consolidated Non-Version Changes (checklist)

1. **Dockerfile (base only):** `node:22-alpine` → `node:24-alpine` on both `FROM` lines.
2. **Add `ioredis` `5.11.1`** to `dependencies` in all three `package.json` (bullmq 6 needs it).
3. **`baml_src/generators.baml`** (base only): `version "0.223.0"` → `"0.226.2"`.
4. **TS7 tsconfig surgery** (base + any overlay tsconfig): remove `baseUrl`, rewrite `paths` to `./`
   roots, remove `ignoreDeprecations`.
5. **Health check** (base only): verify `dbPing()` under terminus 12; migrate to
   `HealthIndicatorService` only if it regresses.
6. **jwks-rsa Jest** (entra only): add the `jwks-rsa` moduleNameMapper stub **only if** `npm test`
   fails on the jose-v6 ESM require.
7. **@types/node** → `24.19.0` (align to Node 24 base).
8. **Optional:** remove `@types/uuid`; add `zodImportTarget = "v4"` to each `schema.prisma`.
9. **Regenerate three `package-lock.json`** on **`node:24-alpine`** (never on the host).
10. **Docs:** confirm no generated doc in `docs_generator.py` hard-codes a bumped version or the Node
    base image tag.

## Commands

```bash
# Regenerate a lock (run inside each api/ dir whose package.json changed) — NOTE node:24 now
docker run --rm -v "$PWD:/w" -w /w node:24-alpine npm install --package-lock-only --ignore-scripts

# Reinstall the CLI after editing templates
pip install -e .

# Scaffold every affected variant (non-interactive)
project-initializer test-nestjs          --nestjs                 --force --yes
project-initializer test-nestjs-token    --nestjs --auth token    --force --yes
project-initializer test-nestjs-supabase --nestjs --auth supabase --force --yes
project-initializer test-nestjs-entra    --nestjs --auth entra    --force --yes

# Build (npm ci + nest build) — the gate for lock/peer correctness
# EXPECTED RED while TS7 is in the sweep (ts-jest peer <7; nest build emits nothing)
cd test-nestjs && docker compose build api

# Runtime smoke test (REQUIRED for the bullmq/ioredis change)
docker compose up -d && curl -s http://localhost:8000/api/v1/health/readiness   # expect database: up
docker compose down

# In-container unit + e2e tests
docker compose run --rm --entrypoint sh api -c "npm test && npm run test:e2e"

# CLI test suite (authoritative gate)
pytest
pytest tests/test_nestjs_lockfile_sync.py tests/test_nestjs_migrations.py tests/test_docker_runtime_invariants.py
```

## Project Structure (files this change touches)

```
project_initializer/
├── templates-api-nestjs/api/
│   ├── Dockerfile                                    # node:22-alpine -> node:24-alpine (both FROM)
│   ├── package.json                                  # version bumps + ioredis + typescript 7 + @types/node 24
│   ├── package-lock.json                             # regenerated on node:24-alpine
│   ├── tsconfig.json                                 # TS7: drop baseUrl/ignoreDeprecations, rewrite paths
│   ├── baml_src/generators.baml                      # baml version pin 0.226.2
│   └── src/modules/health/health.controller.ts       # verify; migrate only if terminus 12 regresses
│       (+ health.module.ts if migrating)
├── templates-supabase-nestjs/api/
│   ├── package.json                                  # base bumps + ioredis + supabase-js
│   ├── package-lock.json                             # regenerated on node:24-alpine
│   └── tsconfig.json                                 # TS7 surgery if it ships its own
├── templates-entra-nestjs/api/
│   ├── package.json                                  # base bumps + ioredis + jwt/jwks
│   ├── package-lock.json                             # regenerated on node:24-alpine
│   ├── tsconfig.json                                 # TS7 surgery if it ships its own
│   └── test-stubs/jwks-rsa.stub.(ts)                 # ONLY if Jest needs it
└── templates-token-nestjs/                           # NO package.json — must stay lock-free
```

## Code Style

- Keep the existing **exact-version** pin style (`"pkg": "1.2.3"`), not caret ranges.
- Preserve each file's existing key ordering and formatting; touch only version strings, the one new
  `ioredis` line, and the tsconfig/paths edits. No reordering, no reformat.
- Any new stub (jwks-rsa) comments only the non-obvious *why* (why the real client is stubbed in
  tests), never the what.
- No new `README.md`/`CLAUDE.md` in overlays — edit `docs_generator.py` if anything user-facing changes.

## Testing Strategy / Verification

Verification bar = **Build + tests**, per affected variant, with a mandatory smoke addition:

1. **Lock regen** on **`node:24-alpine`** for base, supabase, entra (never token, never host OS).
2. **`docker compose build api`** for each variant (`npm ci` strictness surfaces bad lock/peer).
   **Known red while TS7 is in the sweep** — verify the non-TS7 upgrades on a branch that holds
   TypeScript at 6.0.3, then layer TS7 last so its failure is isolated.
3. **Runtime smoke (mandatory):** `docker compose up -d` + `/api/v1/health/readiness` for base + entra
   — the **bullmq→ioredis** gap and **jwks-rsa/jose** load fail only at runtime.
4. **In-container `npm test` + `npm run test:e2e`** per variant (terminus health, monitoring/bull-board,
   zod serialization, auth-guard specs).
5. **Node 24 stack check:** confirm NestJS 12 / Prisma 7.10 / bullmq 6 / jose 6 all run on Node 24 LTS
   (well-trodden — lower risk than Node 26 Current).
6. **`pytest`** — authoritative. `test_nestjs_lockfile_sync.py` (layered lock drift for every auth mode),
   `test_nestjs_migrations.py`, `test_docker_runtime_invariants.py`, and `test_docs_*` must stay green.
   CI (`.github/workflows`) re-runs the NestJS scaffolding path.

## Boundaries

**Always**
- Bump the whole `@nestjs/*` set (Group 1) + `@nestjs/bullmq` together with bullmq 6 — never split.
- Bump the three `@bull-board/*` together; `pino`+`pino-http`+`nestjs-pino` together;
  `zod`+`nestjs-zod` together; `supertest`+`@types/supertest` together.
- Regenerate locks on **`node:24-alpine`** after every `package.json` edit.
- Run the runtime smoke test before declaring the bullmq change done.

**Ask first**
- Migrating the health controller to `HealthIndicatorService` (only if terminus 12 regresses).
- Adopting `ioredis@6.0.0` instead of `5.11.1` (only if bullmq 6's peer range allows it).
- Any TS7 install hack (`--legacy-peer-deps` / npm `overrides`) to bypass the ts-jest peer.
- Any deviation that would add a `package.json`/lock to the `token` overlay.

**Never**
- Ship `prisma@8.0.0-rc.*` (release candidate on the `latest` tag).
- Ship `@types/node@26` while the base is Node 24 (type/runtime mismatch).
- Give `templates-token-nestjs` its own `package.json` or lock.
- Regenerate a lock on the host OS — `npm ci` on `node:24-alpine` will reject a foreign-platform lock.
- Add a `README.md`/`CLAUDE.md` to any overlay.

## Success Criteria

- [ ] Three `package.json` carry the matrix targets (exact pins); `ioredis` added; Prisma trio at
      7.10.0; `@types/node` at 24.19.0; `typescript` at 7.0.2.
- [ ] Dockerfile base is `node:24-alpine` (both `FROM`); three locks regenerated on `node:24-alpine`;
      `test_nestjs_lockfile_sync.py` green for all four auth modes.
- [ ] `/api/v1/health/readiness` returns `database: up` at runtime (bullmq/ioredis + Redis wiring
      intact) for base + entra.
- [ ] `npm test` + `npm run test:e2e` pass in-container for every variant.
- [ ] Full `pytest` green (lockfile-sync, migrations, docker-invariants, docs).
- [ ] **TS7 caveat:** `docker compose build api` is expected to stay **red** until `ts-jest` lifts the
      `typescript <7` peer **and** `@nestjs/cli` supports the TS 7.1 programmatic API. Until then, the
      "build green" criterion is met only on the non-TS7 subset (TypeScript held at 6.0.3).
- [ ] No dependency more than one release behind latest except the recorded holds (Prisma 7.10,
      @types/node 24).

## Open Questions

1. **TS7 sequencing:** apply TS7 as an isolated final layer (recommended) so the other upgrades verify
   green, or insist on one combined commit that builds red? Default if unanswered: **isolate TS7.**
2. **TS7 tracking:** watch `ts-jest` lifting the `typescript <7` peer and `@nestjs/cli` gaining TS 7.1
   support; the build gate stays red until both land.
3. **`ioredis` pin:** `5.11.1` unless bullmq 6's declared peer range explicitly includes `^6`.
4. **Optional cleanups:** remove redundant `@types/uuid`? add `zodImportTarget = "v4"` to the Prisma
   zod generator blocks? Default: skip unless requested.
</content>
