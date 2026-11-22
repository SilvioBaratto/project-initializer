# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Breaking changes for newly scaffolded projects

- **The frontend image serves from `nginx:1.30-alpine` instead of the moving `nginx:alpine` tag.** The runtime stage follows the stable nginx branch, so a rebuild no longer changes nginx branch by itself. `nginx.conf` is unchanged: the non-root user, the pid file, the healthcheck and the CSP nonce swap behave as before.
- **The scaffolded `test-package.yml` workflow uses `actions/checkout@v7` and `actions/setup-node@v7`.** This repo's own workflow moves the same way.
- **The frontend builds on Node 26.** The builder stage of `frontend/Dockerfile` moves from `node:22-alpine` to `node:26-alpine`, and the step that sets Node up before the Angular build installs Node 26 instead of 20, both in the `.github/workflows/test-package.yml` a scaffold ships and in this repo's own `.github/workflows/test-package.yml`. `CONTRIBUTING.md` asks for Node.js 26. The Angular 22 CLI needs Node 22.22.3 or later (the engines of the Angular packages are `^22.22.3 || ^24.15.0 || >=26.0.0`) and refuses Node 20, so a project that builds its frontend on the host needs one of those. The unit tests pass on Node 26 since the move to Vitest 5.
- **Icons come from `@lucide/angular` (`^1.77.0`) instead of `lucide-angular`, which is deprecated and stops at Angular 21.** `src/app/icons.ts` registers them through `provideLucideIcons`, and templates render `<svg lucideIcon="Name">` (or `[lucideIcon]`, with `LucideDynamicIcon` imported) instead of `<lucide-icon name="...">`, so the icon is the `svg` itself and CSS selects `svg.my-icon` rather than `lucide-icon`. The hand-written `LUCIDE_ICONS` multi-provider and the `LucideIconConfig` factory are gone: `provideLucideIcons` fills the icon registry, and the library defaults are already 24px with stroke width 2. `provideLucideIcons` is not a multi provider: a second call, for example in a route's or a component's `providers`, replaces the registry for that injector instead of extending it, so register every icon in `icons.ts`. An unregistered name now throws `Unable to resolve icon '<name>'` when the icon renders. `IconName` drops the deprecated keys `Home`, `CheckCircle`, `Loader2`, `Sliders` and `FunctionSquare`: use `House` and `CircleCheckBig` (`LoaderCircle`, `SlidersVertical` and `SquareFunction` are no longer registered either, see the Angular 22 entry below). The `svg` writes its whole `class` attribute, so icon classes go through `class` or `[class]` (never `[class.x]`), and `matListItemIcon` / `matListItemMeta` sit on a wrapping `span`, as the sidebar now does. What else a scaffold user notices:
  - **Icon classes move to the `svg`.** The old library put `lucide-<Name>` (the name as written, such as `lucide-Menu`) on an `svg` inside `<lucide-icon>`. Now the `svg` itself carries `lucide-<kebab-name>` (`lucide-menu`), the classes of its Lucide aliases, and the class of its `IconName` key (`lucide-Menu`, because `icons.ts` registers the key as an alias). Selectors that go through `lucide-icon`, and the classes of the dropped keys such as `lucide-Home`, stop matching without an error; new CSS and tests should use the kebab-case class.
  - **Cold builds are slower and need more memory.** The Angular linker processes the whole single-entry library, whichever icons are used. On a frontend-only scaffold (host Node 24, two cold runs each), `ng build` went from 3.7-4.8 s to 14.1-15.2 s and its peak memory from 1.53-1.58 GB to 2.04-2.19 GB. A warm `.angular` cache builds in about 3.3 s either way, so the cost lands on Docker image builds, CI and the first local build. The Docker build container peaked at 2.34 GiB (measured on the Node 22 builder, before the Angular 22 move; the peak of the Node 26 builder was not measured): a Docker VM with 2 GiB can kill the image build for lack of memory, so give it more.
  - **The initial bundle grows by about 135 kB raw and 4 kB transferred in every variant** (no-auth: 336.61 to 471.48 kB raw, 94.07 to 98.07 kB transferred; the `angular.json` budget warns at 500 kB). Each registered `Lucide*` class carries its compiled component definition, and the package exports no data-only icons.
- **The frontend moves to Angular 22.3, Angular Material and CDK 22.3 and TypeScript 6.0.** Every `@angular/*` package is declared `^22.3.0`, `typescript` `~6.0.3` (the Angular 22 compiler accepts only 6.0) and `tslib` `^2.9.1`; `rxjs` stays `~7.8.0`. The base manifest and the supabase and entra overlays declare the same ranges, and the base lock resolves 22.3.0, TypeScript 6.0.3, tslib 2.9.1 and rxjs 7.8.2. Angular 22 needs Node.js 22.22.3, 24.15 or 26 and later; the `node:26-alpine` builder meets it. Install with `npm install --legacy-peer-deps` as before: npm finds no peer range conflict in the new tree, but the lock is resolved in legacy-peer mode and `npm ci` without the flag rejects it. What a scaffold user notices:
  - **`withFetch()` is gone from `provideHttpClient(...)`** in the four `app.config.ts` files and in `error.interceptor.spec.ts`. Angular 22 deprecates it because `FetchBackend` is now the default backend, so requests behave as before; a project that needs upload progress events opts into `withXhr()`.
  - **OnPush is now Angular's default change detection, and every component still sets it explicitly**, as the template convention says (Angular's own best practices now say to leave it out). Test host components that set nothing are OnPush now too, and all of them pass unchanged. No file opts out with `ChangeDetectionStrategy.Eager`, which `ng update` writes into every such host (67 in a no-auth scaffold).
  - **The six singleton services are declared with `@Service()`**, Angular 22's documented shorthand for `@Injectable({ providedIn: 'root' })`: `ThemeService`, `WindowSizeClassService`, `ToastService` and the `AuthService` of each auth variant. Each stays one root instance, and `ToastService.ngOnDestroy` still runs when the root injector is destroyed. The component-scoped tooltip helper keeps `@Injectable()`. The generated frontend `CLAUDE.md` now prescribes `@Service` for singleton services.
  - **The production build also stamps the CSP nonce on `<link rel="stylesheet">` tags**, the font stylesheet and the global styles, and on `<link rel="modulepreload">` tags where a build emits them. nginx already replaces every `CSP_NONCE`; the comment in `src/index.html` and the generated docs now list these tags.
  - **The three frontend `package.json` files carry a name-only `allowScripts` list**: `@parcel/watcher`, `esbuild`, `fsevents`, `lmdb` and `msgpackr-extract`, the packages the lock marks with an install script. npm 11.20, which the `node:26-alpine` builder ships, warns on every install about install scripts the list does not cover, and npm 12 blocks them; npm 10, which a project that builds on Node 22 gets, ignores the key. A dependency change that brings a new install script needs its name added here.
  - **`FocusTrapDirective` moves focus only from the innermost trap when nested traps activate in the same render.** CDK 22 no longer treats elements under `inert` as focusable, so the outer trap's first focus target became the inner trap's start anchor, which sent focus through the inner trap's last element (opening an autocomplete there) before the inner trap took it.
  - **The 16 seed icons no template uses are no longer registered**: `Bell`, `CircleX`, `EllipsisVertical`, `Eye`, `EyeOff`, `Inbox`, `LoaderCircle`, `Lock`, `Minus`, `PanelLeftOpen`, `Pencil`, `Plus`, `Search`, `SlidersVertical`, `SquareFunction` and `Trash2`. Each registered icon class adds about 3 kB to the initial bundle, and after the upgrade the token variant's initial bundle sat 8.5 kB under the 500 kB budget warning (491.49 kB). Add an icon back to `src/app/icons.ts` when a template uses it.
  - **Initial bundles, raw and transferred** (measured in the Node 22 container build used before this release's Node 26 builder; the Node 26 build gives the same sizes in all four variants): no-auth 434.96 kB and 95.08 kB, token 440.10 kB and 96.45 kB, supabase 670.36 kB and 145.86 kB, entra 742.30 kB and 157.15 kB (before this change: 471.48, 476.35, 702.37 and 777.26 kB raw). The supabase and entra bundles still exceed the 500 kB budget warning, as before.
  - **Cold builds are faster again.** On a no-auth scaffold (host Node 24, two cold runs), `ng build` takes 6.9-8.9 s with a peak memory of 1.46-1.71 GB, against 14.1-15.2 s and 2.04-2.19 GB on Angular 21 with `@lucide/angular`; the build step in the Node 22 container used before this release takes 11-12 s and in the Node 26 builder 9-10 s.
- **The unit-test toolchain moves to Vitest 5 and jsdom 31.** The three frontend manifests declare `vitest` `^5.1.1` and `jsdom` `^31.0.1`, and the base lock resolves 5.1.1 and 31.0.1. `@angular/build` 22.3 accepts Vitest 4 or 5, so `angular.json`, `tsconfig.spec.json` and `src/test-providers.ts` are unchanged; Vitest 5 makes `vite` a peer dependency, which the builder's own `vite` 8.3.8 satisfies. jsdom 31 needs Node.js 22.22.2, 24.15 or 26 and later. What a scaffold user's own specs may hit:
  - **jsdom computes CSS like a browser with a fixed 1024x768 window.** `getComputedStyle()` now substitutes `var()` and applies the `@media` blocks a 1024px-wide, 768px-tall window matches; assigning `window.innerWidth` does not change that window. A spec that expected the declared `var(--token)` text, or the mobile-first layout below a `min-width` query, now gets the resolved value (a spec loads no global theme, so a `--mat-sys-*` reference resolves to nothing: an empty custom property, an inherited color) or the wide layout. Lengths compute in pixels (`0px` where jsdom 26 returned `0`). The shipped specs read what a computed value can no longer show through the CSSOM instead, with the `declaredValue()` helper of `checkbox.spec.ts`, which follows document order rather than specificity, `!important` or inheritance: the stat-card, radio, button, grid and components-page specs keep their assertions and read their `var()` references that way, while the button's literal padding tokens and its "not overridden" checks stay on `getComputedStyle()`, which also catches an override on `:host`. `table.spec.ts` reads the compact layout from the rules outside its media query after checking that this query is the stylesheet's only grouping rule, and its wide-window test now also checks the computed layout at the 1024px window. The keyboard helper of `responsive-shell.integration.spec.ts` passes `keyCode` in the `KeyboardEvent` init, which jsdom honours, instead of redefining the property. `window.matchMedia`, `ResizeObserver` and `IntersectionObserver` are still missing, so their fakes stay.
  - **Specs that use `localStorage` pass on Node.js 25 and later.** Those versions define a Web Storage `localStorage` global; Vitest 4 left it in place over jsdom's, so `localStorage.clear()` threw in about 70 specs on Node 26. Vitest 5 maps jsdom's `localStorage` and `sessionStorage` over it, and every variant's suite passes on Node 22 and on Node 26.
  - **Vitest 5's other breaking changes** leave the shipped specs untouched but may reach a project's own: `clearMocks` is on by default, an unawaited `.resolves` or `.rejects` assertion fails its test, `vi.mock` and `vi.hoisted` must be at the top level of a file, assigning a DOM global such as `innerWidth` is written through to jsdom's `window` object (its media queries keep the fixed 1024x768 window), and fake timers now mock `Temporal`. See the Vitest 5 migration guide.
  - **`npm install` prints no deprecation warning any more**: jsdom 31 dropped `whatwg-encoding`. After the regeneration, `npm audit fix --package-lock-only` moved `browserslist` to 4.29.6 and `baseline-browser-mapping` to 2.11.39 inside their ranges (lock only), and `npm audit` reports no advisory: `ws` left the tree with jsdom 31, and Vitest 5.1.1 is outside the `@vitest/mocker` advisories.
- **The Entra overlay moves to `@azure/msal-angular` 6 and `@azure/msal-browser` 5.** The manifest declares `@azure/msal-angular` `^6.3.3` and `@azure/msal-browser` `^5.30.0`. msal-angular 6 needs Angular 22 and peers `@azure/msal-browser` `^5.30.0`; it declares no `@angular/*` peer, so npm does not enforce the Angular floor. The overlay's own code is unchanged: it calls `instance.*` directly, has its own guard and interceptor and never calls `MsalService.logout()`, so the msal-angular 5 and 6 breaking changes do not reach it, and `app.config.ts` still runs `initialize()` once, then `handleRedirectPromise()` once, before the active account is set. What an Entra project notices:
  - **Known limitation: the msal-browser 5 redirect bridge is not adopted.** msal-browser 5 documents that every authentication flow needs a dedicated redirect page that implements its redirect bridge (`@azure/msal-browser/redirect-bridge`, `broadcastResponseToMainFrame()`), and its hidden-iframe silent renewal rejects with `timed_out` after 10 seconds without one. The overlay keeps `redirectUri: '/'`, because redirect sign-in and sign-out still work with it and the bridge would force every new Entra project to register a second redirect URI (`/redirect`) or sign-in fails with `redirect_uri_mismatch`. The only path that degrades is the silent renewal that falls back to the hidden iframe once the refresh token has expired (24 hours after sign-in, not sliding): that user waits about 10 seconds. A project that wants the bridge adds the dedicated redirect page, registers its URI in the SPA app registration and allows `'self'` in the `frame-src` of the CSP in `nginx.conf`.
  - **MSAL error classes take a correlation id.** `InteractionRequiredAuthError` and the other MSAL error classes require it as their second constructor argument, so a project's own spec that builds one needs it: `new InteractionRequiredAuthError('interaction_required', 'spec-correlation-id')`. The shipped `auth.service.spec.ts` does.
- **The Supabase overlay declares `@supabase/supabase-js` `^2.119.2`** instead of `^2.49.0`. The overlay ships no lock, so a fresh install already resolved the newest 2.x; the new floor makes the manifest say what the template is written against, and every auth call and error helper `AuthService` uses keeps its signature. The package needs Node.js 22 or later (its engines field) and has only an optional `@opentelemetry/api` peer.

### Repo tests

- `tests/test_frontend_dependency_upgrade.py` pins the Node 26 builder and the nginx runtime tag of the frontend Dockerfile (a version on a stable branch, so an even minor), `actions/checkout@v7` and `actions/setup-node@v7` on every live `uses:` line of both workflow files (a commented-out line is ignored, a quoted one is read), Node 26 in the step before the Angular build of both workflows, and the Node.js 26 prerequisite in `CONTRIBUTING.md`.
- `tests/test_frontend_dependency_upgrade.py` also checks that no frontend manifest lists `lucide-angular`, that the three manifests declare the same `@lucide/angular` caret range and the base lock resolves a release inside it, that no frontend source imports `lucide-angular`, uses `<lucide-icon>` or imports a deprecated icon class such as `LucideTrash2`, and that no `<svg lucideIcon>` carries a `[class.x]` binding, `matListItemIcon` or `matListItemMeta`. The icon-tag scan reads quoted attribute values whole, so a `>` inside a binding does not hide the attributes after it; it fails on an `<svg` start tag it cannot read, and the guards fail when they find no icon at all.
- `tests/test_docs_frontend_material.py`, `tests/test_issue_9_feedback_atoms.py` and `tests/test_issue_19_avatar_stat_card.py` follow the new icon element, registration and error message.
- `tests/test_frontend_dependency_upgrade.py` also checks the Angular 22 move: every `@angular/*` package of the three manifests declares a caret range on 22 from 22.3.0; a package the manifests share has one specifier in all of them; each Angular release group (framework, CLI, Material and CDK) shares one range; TypeScript is a `~6.0.x` range that the lock resolves inside the compiler's and builder's peer range; the base lock declares the manifest's ranges and resolves a release inside each; no frontend source calls `withFetch` or sets `ChangeDetectionStrategy.Eager` or `Default`; no tsconfig configures the two extended diagnostics Angular 22.3 removed; the six singleton services use `@Service()` and no file keeps `providedIn: 'root'`; the generated docs and `CLAUDE.md` name the declared Angular and Material versions; the CSP nonce docs name the stylesheet and modulepreload links; and `allowScripts` lists exactly the locked packages with an install script.
- `tests/test_frontend_dependency_upgrade.py` also checks the test toolchain: the three manifests declare one Vitest 5 and one jsdom 31-or-later caret range, the base lock declares both and resolves inside them, the resolved Vitest is inside `@angular/build`'s peer range and the lock still resolves a `vite` inside Vitest's peer range; and the generated frontend `CLAUDE.md` and the repo `CLAUDE.md` describe jsdom's fixed window and `var()` substitution and point at a `declaredValue()` helper that `checkbox.spec.ts` and `table.spec.ts` define.
- `tests/test_issue_1_tailwind_bump.py` expects Material and CDK on a `^22.3` range. `tests/test_issue_12_toast.py` and `tests/test_issue_7_entra_auth_service.py` accept `@Service()` as a root singleton declaration and reject `autoProvided`. `tests/test_docs_frontend_material.py` and `tests/test_issue_20_pagination_accordion.py` cite Material 22.3, whose compiled CSS still bears out both claims, and `tests/test_frontend_nginx_csp.py` describes the link tags that carry the nonce.
- `tests/test_entra_frontend_overlay.py` expects `@azure/msal-angular` on major 6 and `@azure/msal-browser` on major 5: the two tests that named major 4 are renamed `..._msal_angular_v6_is_listed` and `..._msal_browser_v5_is_listed`, carry a `Validates` line and are listed in `TRACED_FUNCTIONS` of `tests/test_repo_test_traceability.py`. `tests/test_issue_10_msal_init_sequence.py` and `tests/test_issue_6_entra_frontend_msal_wiring.py` are unchanged and still pin the init sequence: exactly one `initialize()` and one `handleRedirectPromise()` call site in the non-spec source, and the words `initialize` and `handleRedirectPromise`, in that order, in `app.config.ts`. The order test reads that text with `str.find` and matches the comment, not the calls in `auth.service.ts`.

## [0.6.0] - 2026-11-21

Python projects now keep their dependencies and their version in `pyproject.toml` and nowhere else. The first three changes below alter what a **newly scaffolded** FastAPI project contains; a project scaffolded earlier is not touched.

### Breaking changes for newly scaffolded projects

- **FastAPI scaffolds no longer ship `api/requirements.txt`.** `api/pyproject.toml` declares the dependencies: the application's in `[project] dependencies`, the test tooling (`pytest`, `pytest-asyncio`, `pytest-cov`, and `httpx` in the no-auth and token variants; the supabase and entra variants keep `httpx` at runtime, as before) in the `dev` extra. Install with `pip install ".[dev]"` in `api/`, not `pip install -r requirements.txt`. With `--async-db`, `asyncpg` and `sqlalchemy[asyncio]` join the dependencies and `aiosqlite` joins `dev`.
- **The application version comes from `[project] version` of `api/pyproject.toml`.** `Settings.version` is a read-only property over the installed project's metadata: the `version: str = "1.0.0"` field and the `VERSION` environment override are gone. After editing the number, run `pip install ".[dev]"` again; `tests/unit/test_version_source.py` fails when the installed metadata is stale.
- **The API Docker image no longer carries the test tooling.** Its builder stage runs `pip install .`, which leaves out the `dev` extra.

### Changed

- `project-initializer --version` reads the installed package metadata directly. A source tree that was never installed reports that it has no version to show.

### Removed

- **`project_initializer.__version__`.** It breaks code that imports it; read `importlib.metadata.version("project-initializer")` instead, which is what `--version` does.
- The `pyproject.toml` that every scaffold received at its root, NestJS and frontend-only ones included. It was a stale copy of this CLI's own metadata (name `project-initializer`, version 0.1.1).

### Repo tests

- `tests/test_python_metadata_single_source.py` fails on a `requirements*.txt` or a hardcoded version anywhere in the CLI package or the Python templates.
- `tests/test_fastapi_requirements.py` is now `tests/test_fastapi_dependencies.py`: it parses the three `api/pyproject.toml` files and keeps the exact-pin, token-stack and audited-`PyJWT` guards.

## [0.5.0] - 2026-11-21

The FastAPI and NestJS backend templates were reviewed against the code standard and reworked: secrets, error handling and logging, layering and ports, the database schema and its rollback, and the tests and tooling each scaffold ships. Everything below changes what a **newly scaffolded** project contains. A project scaffolded earlier is not touched.

### Breaking changes for newly scaffolded projects

Clients, scripts and `.env` files written against an earlier scaffold need these updates.

- **BAML and the whole chatbot/LLM feature are removed.** A new scaffold has no `/chat` endpoints in either backend (chat, stream, jobs and chat health), no `baml_src/` and no generated BAML client, no BAML dependency and no `baml-cli generate` step (Dockerfiles, VS Code tasks, CI), no chat page, route, navigation entry or service in the Angular frontend, and none of the LLM provider settings (`AZURE_OPENAI_*`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `OLLAMA_BASE_URL`, `BAML_LOG`). In NestJS, BullMQ, Redis and Bull Board went with it, because the chat jobs were their only user: there is no `redis` compose service, no `REDIS_HOST` or `REDIS_PORT`, no queue dashboard or `QUEUE_MONITOR_PASSWORD`, and no Redis readiness check. Nothing is migrated, and a project scaffolded earlier is not touched. A client that called a chat route must stop doing so, and a project that still needs a chatbot has to add its own endpoints and provider integration to the new scaffold; delete the removed keys from any `.env` copied from an older scaffold.
- **FastAPI: `GET /api/v1/users/me` is now `GET /api/v1/auth/me`**, in every auth variant. It returns `{id, email, username, roles, auth_method}`, with `roles` as an array. In the token variant, `GET /auth/me/jwt` returns the same shape and answers 401 for a deactivated account.
- **NestJS: the sample items moved from `/test/items` to `/items`** and persist in Postgres through Prisma (they were an in-memory map). Updates use `PUT /items/:id`. `/test/ping` and `/test/echo` stay.
- **NestJS: `GET /auth/me` returns `roles` (an array) instead of `role`.**
- **FastAPI: `GET /` now answers only `{"status": "operational", "api_version": "v1"}`**; the project name, version, environment and docs URLs are gone.
- **NestJS token variant: `AUTH_TOKEN` must have 32+ characters**, or the app refuses to start. The FastAPI token variant requires `AUTH_TOKEN` of 16+ and `JWT_SECRET_KEY` of 32+ characters (see the weak-secret entry below). Neither accepts `changeme`.
- **FastAPI hides the interactive docs and `/openapi.json` in production.** They are served in every other environment; `API_DOCS_ENABLED=true` or `false` overrides. `DEBUG` now defaults to `false`, and the app refuses to start with `DEBUG=true` outside `ENVIRONMENT=development`.
- **FastAPI: registering a duplicate email or username answers a generic 409** (it was a 400 that named the field). A wrong password, an unknown email and an inactive account all answer the same 401.
- **FastAPI: the in-memory rate limiter keys on the connection's peer address**, so behind a reverse proxy every caller shares one bucket unless the proxy is listed in `FORWARDED_ALLOW_IPS`. It is active only when `ENVIRONMENT` is `staging` or `production`, and each replica counts separately: use a gateway or an external shared store to scale out.
- **NestJS: Entra ids (`ENTRA_TENANT_ID`, `ENTRA_API_CLIENT_ID`, ...) must be GUID-shaped**, or the app refuses to start.
- **`SUPABASE_SECRET_KEY` is no longer read** by either backend: the service-role key bypasses Row Level Security and the services never need it.
- **FastAPI error responses use one envelope** (`{"error": {"code", "message", "timestamp", "request_id", "details"}}`). `details` is a list of `{field, message}` pairs and only appears for validation failures; it used to carry internal diagnostics.
- **FastAPI: the default page size stays 100** (maximum 100). `skip` is capped at 10000 and an out-of-range `skip` or `limit` is a 422.
- **FastAPI: item ids must be UUIDs.** A path id that is not one answers 422, not 404, and text fields reject a NUL character (422) instead of failing in the database driver with a 500.
- **FastAPI: the audit log line changed.** The free-text `audit action=... resource_id=...` message is now the event `audit.action` on the logger `app.audit` with the fields `action`, `resource_id` and `actor_id`, always at INFO whatever `LOG_LEVEL` is. Alerts that match the old text need the new event name.
- **FastAPI: `GET /health/ready` gains an `additional_databases` object** (empty unless a component such as the async overlay registered a probe), and a failing additional database turns the status to `degraded` with a 503.
- **FastAPI Entra: `email` comes from the `email` claim only.** It used to fall back to `preferred_username`, a mutable sign-in name that need not be an address; `username` now carries `preferred_username`. A client that read the address from `email` and relied on the fallback gets `null`.
- **Entra ids must be GUIDs in FastAPI too.** `ENTRA_TENANT_ID` and `ENTRA_API_CLIENT_ID` are validated at start-up (hyphenated GUIDs, stored lowercase), and `ENTRA_SPA_CLIENT_ID` is no longer a backend setting (it stays in `.env` for the frontend).
- **Supabase: anonymous users carry the role `anonymous`** instead of `authenticated` (both backends), so a guard for `authenticated` no longer admits an anonymous sign-in. A production-like start-up also refuses a Supabase key that starts with `sb_secret_` (FastAPI) and an `http` `SUPABASE_URL` (NestJS, `NODE_ENV=production`).
- **NestJS: JSON bodies above 512 KiB answer 413** (the Express default was 100 kB), and a malformed JSON body answers 400 `Malformed JSON request body`.
- **NestJS: `TRUST_PROXY_HOPS` defaults to 1** (the bundled nginx), so the rate limiter keys on the client address in `X-Forwarded-For`. An API exposed directly must set it to `0`, or a client can spoof the header.
- **Docker: the FastAPI server starts with `--no-access-log`** (the Dockerfile, both compose files and `python -m app.main`), because uvicorn's access line prints the client address and the query string unstructured. The structured `http.request` line replaces it.
- **Docker: both entrypoints wait for the database named in `DATABASE_URL`**, bounded by `DB_WAIT_TIMEOUT_SECONDS` (default 60), and exit with status 1 on timeout instead of waiting forever or on a hardcoded host.
- **FastAPI token variant: a non-empty weak secret is refused at every stage** (a placeholder, or `AUTH_TOKEN` under 16 and `JWT_SECRET_KEY` under 32 characters); only an empty secret is allowed outside `staging` and `production`. Login and `GET /auth/me/jwt` answer 503 while `JWT_SECRET_KEY` is empty, and emails are stored and matched in lower case.
- **NestJS token variant: `AUTH_TOKEN` must also be a valid bearer credential** (letters, digits and `- . _ ~ + /`, optional `=` padding).
- **Coverage is gated in the FastAPI scaffolds.** `pytest.ini` enforces 75% branch coverage of `app/`, so running a subset of the tests needs `--no-cov`.
- **FastAPI: `ENVIRONMENT=staging` and `production` refuse a database connection that is not TLS-protected.** `DATABASE_URL` and, when set, `DIRECT_DATABASE_URL` must resolve to `require`, `verify-ca` or `verify-full`: `DATABASE_SSL_MODE` when set (it wins over the URL), otherwise the `sslmode` of the URL. A deployment that connected in clear text now fails at start-up. Set `DATABASE_SSL_MODE`, or set `DATABASE_ALLOW_INSECURE_TRANSPORT=true` for a database on the same host or a private network that serves no TLS. The bundled compose `db` serves no TLS, so `ENVIRONMENT=production docker compose up` needs the opt-out. `development`, `test` and SQLite are exempt, the error never contains the URL, and the generated Supabase `.env` already meets the rule.
- **NestJS: `NODE_ENV=production` refuses a `DATABASE_URL` unless every `sslmode` in it is `require`, `verify-ca` or `verify-full`** (case-sensitive). `DB_ALLOW_INSECURE_TRANSPORT=true` (a boolean, default `false`) is the opt-out for a database on the same host or a private network without TLS. The message is fixed and names neither the URL nor the host. The compose stack runs `NODE_ENV=development` and is unaffected, the Supabase pooler URL passes, and `DIRECT_URL` is not checked because only migrations use it.
- **NestJS: `ItemsService.create`, `update` and `remove` take the actor id as their last argument** (`create(item, actorId)`, `update(id, changes, actorId)`, `remove(id, actorId)`), so the audit trail can name who made the change. Code that calls the service directly must pass `auditActorIdOf(user)` or its own opaque id.
- **FastAPI token variant: `AccessTokenDTO` gained a required `user_id`.** It is internal: `TokenResponse` does not expose it, so the `POST /auth/token` body is unchanged, but code that builds the DTO itself must pass it.

### Security
- **Secrets are generated at scaffold time.** `AUTH_TOKEN` and `JWT_SECRET_KEY` are random values (`secrets.token_urlsafe(32)`) written into the root `.env`; the committed `.env.example` leaves them blank, and re-scaffolding keeps the secrets an existing `.env` already holds. No scaffold ships `changeme` any more.
- **Debug tracebacks no longer reach clients**: `DEBUG=false` in the generated `.env`, and a generic 500 body whatever the settings.
- **Logs carry no personal data.** One `http.request` line per request holds the method, path, status and duration, with a request id; request and response bodies, query strings, client addresses, emails and tokens are never logged. SQL parameters are hidden from database error logs.
- **Error bodies are generic.** Domain errors carry a public message for the client and a separate log context; no exception text, connection string, SQL or service name is returned. Authentication failures never say which part was wrong.
- **The auth overlays are hardened.** Token comparison uses SHA-256 digests in constant time and an empty secret matches nothing. Entra accepts only `RS256`, requires `exp`, `iat`, `iss` and `aud`, pins the tenant and the scope, and bounds the key fetch with a timeout; a key endpoint outage answers 503, not 401. Supabase maps 429, 5xx and timeouts from Supabase Auth to 503, bounds the call with `SUPABASE_AUTH_TIMEOUT`, and refuses to start in production-like environments with a placeholder project. Login and registration inputs are length-bounded, and the bcrypt 72-byte limit is enforced.
- **Database TLS modes are honoured.** FastAPI passes `DATABASE_SSL_MODE` to the psycopg2 and asyncpg connections (the generated Supabase `.env` sets `require`). NestJS `sslmode=verify-ca` and `verify-full` now verify the server certificate; they used to encrypt without verifying it.
- **Supabase tables have Row Level Security enabled** in a migration in both stacks, so the Data API cannot read or write them with the publishable key: FastAPI `0003_enable_row_level_security` covers `items`, `profiles` and `alembic_version`, and the NestJS migration covers `profiles`, `items` and Prisma's `_prisma_migrations`.
- **Rollback backups no longer sit in `public`.** FastAPI and NestJS copy the rows of a dropped table into the PostgreSQL schema `migration_backup`, which the Supabase Data API does not serve, under a name with a microsecond timestamp so repeated rollbacks cannot collide.
- **Startup errors do not echo values.** The FastAPI settings use `hide_input_in_errors`, `DATABASE_ECHO` is refused outside development (SQLAlchemy writes bound parameters outside the structured formatter), and `CORS_ORIGINS=*` is refused in `staging` and `production`. CORS never allows credentials in FastAPI.
- **The FastAPI image keeps its code root-owned**, so the unprivileged process cannot rewrite what it runs.
- **The database connection is TLS-protected in deployed environments.** FastAPI (`staging`, `production`) and NestJS (`production`) refuse to start against a database whose transport is not `require`, `verify-ca` or `verify-full`, unless `DATABASE_ALLOW_INSECURE_TRANSPORT=true` / `DB_ALLOW_INSECURE_TRANSPORT=true` says the database sits on the same host or a private network (see Breaking changes). Neither error repeats the URL, which holds the password.
- **Role-based access control in NestJS.** `@Roles(...roles)` and the global `RolesGuard` (registered last: `[ThrottlerGuard, ...AUTH_GUARDS, RolesGuard]`) restrict a route to callers that hold one of the roles. A route without `@Roles` passes; no identity, an empty `@Roles()` or a mismatch is a 403 with a generic message that never lists the required roles. The base no-auth variant has no identity, so every `@Roles` route is denied (fail closed).
- **Audit trails name an actor by opaque id.** NestJS `AuditLogger` and the FastAPI token overlay record who changed what without an email or a username, and both trails are pinned to INFO, so a high `LOG_LEVEL` (`warn`, `error`, `silent` in NestJS) cannot silence them.

### Changed
- **NestJS dependency changes** (base, Supabase and Entra `package.json`, with regenerated locks): `uuid` and `@types/uuid` are removed (`randomUUID` from `node:crypto` replaces them); `dotenv` is added and `prisma` moves from devDependencies to dependencies because the production image runs `prisma migrate deploy` and `prisma.config.ts` imports `dotenv`; `typescript-eslint`, `@eslint/js`, `eslint-config-prettier`, `globals`, `prettier` and `@types/pg` are added as exact-pinned devDependencies for the new `lint`, `format` and `format:check` scripts. FastAPI: `passlib`, `psutil` and `prometheus-client` are removed (the token overlay uses `bcrypt` directly), `pytest-cov` is added, and the Entra overlay moves to `PyJWT[crypto]==2.15.1`.
- **Typed ports, DTOs and a unit of work.** FastAPI services depend on `ItemRepositoryPort`, `UnitOfWorkPort` and `TokenVerifierPort` (and, with `--async-db`, async twins), take commands and return DTOs, and commit only after a successful write. NestJS services depend on port tokens (`ITEM_REPOSITORY`, `DATABASE_HEALTH_PORT`, `ACCESS_TOKEN_VERIFIER`). `deps.py` (FastAPI) is the composition root, and the architecture test also bans `fastapi`, `starlette`, `sqlalchemy` and `pydantic` imports from the domain and application layers.
- **The auth overlays replace a seam instead of copying base files.** FastAPI overlays replace `app/api/auth_deps.py` and `app/infrastructure/auth_settings.py`; NestJS overlays replace `src/app.auth.ts`. A fix in the base now reaches every variant.
- **A circuit breaker guards database calls**, with thresholds and a half-open probe. An open circuit fails fast with 503 and `Retry-After`, and `GET /health/ready` (FastAPI) and `/health/readiness` (NestJS) report the database state. In FastAPI the readiness probe also reports the circuit, and a database outage at start-up no longer aborts the process.
- **One error envelope.** Every non-2xx response shares one shape, declared in OpenAPI through `responses=`, and carries the request id (see Breaking changes).
- **FastAPI request ids and structured logs.** A valid incoming `X-Request-ID` is reused, otherwise one is generated; it appears in the response header, every error body and every JSON log line. `LOG_FORMAT=text` gives a terminal format.
- **FastAPI settings are validated at start-up** (`ENVIRONMENT`, `LOG_LEVEL`, `LOG_FORMAT`, `DATABASE_SSL_MODE` and the numeric limits), and the CORS default is `http://localhost:4200` only.
- **The FastAPI middleware order is fixed:** CORS, request logging, security headers, `UnhandledErrorMiddleware`, rate limiting. CORS headers now appear on 429 and 500 responses, and preflight requests use no rate-limit quota. The catch-all answers an unhandled exception with the generic 500 envelope carrying the request id, security and CORS headers, and logs it once instead of twice. The `http.request` log field `path` is the matched route template, not the raw URL.
- **FastAPI database errors are classified.** A deadlock, a serialization failure or a lock timeout answers 409 (`ConflictError`, safe to retry) and never trips the circuit breaker; a database error that is not an outage answers 500 `DATABASE_ERROR`; the breaker counts connectivity failures only, and a request that never touched the database does not vote. Repositories flush through `flush_or_conflict`, so a uniqueness race is a 409 whichever moment the database rejects it.
- **A shutdown-hook and readiness-probe registry** (`register_shutdown_hook`, `register_readiness_probe`) lets the async overlay hook into the lifespan and `/health/ready` without editing `main.py`. `set_log_level()` changes the level of a running process; no route exposes it, and SIGHUP now drives it (see Added).
- **The FastAPI architecture test is an allowlist.** The domain imports the standard library and `app.domain` only, the application adds `app.application`, neither calls `importlib.import_module` or `__import__`, `infrastructure` never imports `app.api` or `app.main`, and `app/api` imports no repository, ORM model or `get_db` outside `deps.py` and `auth_deps.py`.
- **FastAPI Alembic setup.** `file_template = %%(rev)s` makes the revision id the file name (create revisions with `--rev-id 0003_add_widget`), `env.py` logs through the application's structured logger and honours an `embedded` config attribute, a drafted `op.drop_table` in a downgrade is rewritten to `preserve_and_drop_table`, and `preserve_and_drop_column` backs up a dropped column. The first migration creates `idx_items_created_at`.
- **The FastAPI token variant splits registration from login:** `RegistrationService` (`registration.py`) creates accounts and needs no signing key, `AuthService` handles login. The token response carries `Cache-Control: no-store`, a blank username means none, and `POST /auth/validate` logs each rejection.
- **FastAPI Entra key lookups are rate limited.** An unknown `kid` forces at most one reload of the key set per `ENTRA_JWKS_REFRESH_COOLDOWN` (default 30 seconds, at most 3600), a key endpoint failure of any kind answers 503, and `PyJWT` is pinned to 2.15.1.
- **FastAPI Supabase answers 503 for a malformed 200** from Supabase Auth, as it does for 429 and 5xx.
- **NestJS platform:** `configureApp` sets `TRUST_PROXY_HOPS` and a 512 KiB body limit, body-parser errors keep their 4xx status under a fixed message, the health controller answers an unhealthy probe with the Terminus result, `P2010` raw-query failures are judged by the driver error kind, the pino request serializer keeps only id, method and path, the throttler answers `Too many requests`, `DB_POOL_MAX` sets the pool size, the TLS parameters are stripped from the URL that reaches the pool, `API_DOCS_ENABLED` controls Swagger, the production image copies `prisma.config.ts`, and every handler, the demo routes included, declares `@ZodResponse`.
- **NestJS auth:** Supabase maps 429, timeouts and unparseable answers to 503 with a 5-second bound, Entra requires `exp` and `iat` with a 30-second tolerance and caches its JWKS for 24 hours, an `ENTRA_API_SCOPE` that reduces to nothing fails at start-up, and `email` is released only when it conforms to the HTML5 email grammar (otherwise `null`).
- **The generated NestJS `.env` keeps `NODE_ENV=development`**, which matches the compose `dev` target (devDependencies installed); a comment warns that the production image sets `NODE_ENV=production` itself and must not receive the file.
- **Entra scope accepts both forms.** `ENTRA_API_SCOPE` can be the bare name or the full `api://.../access_as_user` URI that MSAL needs, and it can never be empty. `ENTRA_AUTHORITY`, `ENTRA_JWKS_TIMEOUT` and `ENTRA_JWKS_REFRESH_COOLDOWN` are optional settings.
- **NestJS `ItemsService` records its changes.** After the repository call succeeds, `create`, `update` and `remove` write `item.create`, `item.update` and `item.delete` through `AuditLogger`, and their signatures gained `actorId` (see Breaking changes).
- **FastAPI token variant: `AuthService.authenticate` returns an `AccessTokenDTO` that carries `user_id`**, which the login route uses to write the `user.login` audit record. The DTO is internal and `TokenResponse` does not expose the field.
- **Docs are generated more fully.** The FastAPI `api/.claude/CLAUDE.md` gains the errors table, the auth seam, request ids and logging, resilience and readiness, the migration and rollback process, the test database, test traceability and the settings, including the proxy note for the rate limiter. The root docs no longer claim `.env.example` is identical to `.env`.

### Added
- **Alembic owns the FastAPI schema.** Runtime `create_all` is gone; `entrypoint.sh` runs `alembic upgrade head`. The Supabase migration `0002_create_users_table.py` creates `profiles` and keeps the base file's name on purpose, so it replaces the base migration instead of stacking.
- **Data-preserving rollbacks.** FastAPI downgrades go through `preserve_and_drop_table`, which copies a table to `<table>__rollback_<UTC timestamp>` before dropping it (`alembic downgrade -1`). Every NestJS migration ships a `down.sql` that does the same and un-records itself (`prisma db execute --file prisma/migrations/<dir>/down.sql`).
- **NestJS items on Prisma**, with an `items` model and migration (`20261121000000_create_items`).
- **Tooling and tests in every scaffold.** NestJS: ESLint (type-checked, no warnings), Prettier, a 75% coverage threshold, and e2e tests that run on in-memory fakes without Postgres. FastAPI: a pytest suite on in-memory SQLite with savepoint rollback, `pytest-cov` branch coverage gated at 75% on every full run, and registered `unit`, `integration` and `e2e` markers.
- **CI runs each scaffolded variant's own suites.** The `test-variant-suites` job scaffolds all nine variants and runs the FastAPI pytest suite or the NestJS lint, format, unit and e2e commands.
- **Test traceability is a convention only.** FastAPI tests carry a `Validates module.func()` docstring line and a registered `requirement` pytest marker; NestJS tests use a `[REQ-<AREA>-<NNN>]` title prefix. The templates ship no requirement IDs, because they have no requirements of their own: each generated project supplies its own, so the code standard's per-test requirement link stays unmet until it does.
- **SIGHUP reloads `LOG_LEVEL` in both stacks.** FastAPI: `app/infrastructure/log_level.py`, run by the lifespan; the `.env` file wins over the process environment on a reload, an invalid value is ignored with `log_level.reload_rejected`, an applied reload logs `log_level.reloaded`, an unexpected failure logs `log_level.reload_failed`, and the previous handler is restored on shutdown. NestJS: `src/config/log-level-reload.ts` reads `../.env` then `.env` with dotenv's parser without mutating `process.env`; a value the operator exported that differs from the file's start-up value wins, otherwise the edited file wins; an invalid value is ignored with one warning that names only the accepted set; nothing is installed on Windows and the listener is removed when the server closes. Use `kill -HUP <pid>` or `docker kill --signal=HUP <container>`. A terminal hang-up also sends SIGHUP, and without a `.env` file, as in Docker, a reload re-applies the start-up value.
- **NestJS `@Roles(...roles)` and `RolesGuard`** (`src/common/auth/roles.*`): no sample route uses them; handler-level metadata overrides class-level metadata, and a denial writes one warn with the opaque `actorId`.
- **NestJS `AuditLogger`** (`src/common/audit`): `record(action, resourceId, actorId)` writes one `audit.action` line through a pino child pinned to `info`. The items service uses it with the user id or the constant `anonymous` as actor.
- **FastAPI token overlay audit actions** `user.register` and `user.login`, queued as background tasks. Both name the account by id in `resource_id` and `actor_id` and carry no email or username.
- **Repo tests:** `tests/test_fastapi_migrations.py` (each FastAPI variant's merged migrations create exactly the tables its ORM maps to, every migration has a data-preserving downgrade, the Supabase 0002 file replaces the base one by name, 0003 exists only there and secures every table, and backups go to `migration_backup`), `tests/test_nestjs_migrations.py` (backups outside `public`, microsecond names, un-recording as the last statement, RLS on `_prisma_migrations`), `tests/test_nestjs_auth_seam.py` (the three `src/app.auth.ts` copies are byte-identical), `tests/test_fastapi_requirements.py`, `tests/test_env_generator_runtime_defaults.py` (`NODE_ENV` matches the compose target), `tests/test_docs_compliance_sync.py`, `tests/test_env_generator_secrets.py`, `tests/test_docs_nestjs_compliance.py` and `tests/test_template_packaging_complete.py`.
- **Repo test traceability.** The repo suite carries no requirement IDs (the project has no requirement tracker); each test of the new modules, and each test this change wrote or rewrote in an older module, ends its docstring with a `Validates <path or symbol>.` line naming the code it inspects, and `tests/test_repo_test_traceability.py` fails when a covered test lacks it. The untouched tests of the older modules are legacy and are annotated when next touched. The convention is written down in `CLAUDE.md` and `CONTRIBUTING.md`.

### Removed
- **BAML and the chatbot/LLM feature**, in both stacks and the shared frontend: the chat endpoints, services, ports, adapters, DTOs and tests, `baml_src/`, the generated BAML client and its dependency, the Angular chat page, and the LLM provider settings. NestJS also loses BullMQ, Redis and Bull Board (the queue dashboard, its credentials and the `redis` compose service). See Breaking changes.
- **FastAPI helpers nothing used:** the `RateLimiter` dependency, cursor pagination and `order_by`, `get_optional_user`, `get_user_id`, `DBSession`, `UserInDB`, `/users/me`, the empty `scripts/` package, and the unused settings `CACHE_TTL_*`, `ENABLE_METRICS`, `METRICS_PATH`, `CONNECTION_TIMEOUT`, `READ_TIMEOUT` and `DATABASE_POOL_RESET_ON_RETURN`. `passlib` is replaced by `bcrypt` called directly.
- **Per-overlay forks of base files:** the token, supabase and entra FastAPI overlays no longer ship their own `deps.py`, `settings.py`, `v1/router.py` or `.env.example`, and the entra overlay drops its copies of `entrypoint.sh` and `docker-compose.yml`.
- **The NestJS base `auth` module.** Authentication enters only through the overlay's `src/app.auth.ts`.
- **Unused FastAPI dependencies:** `psutil` and `prometheus-client` are gone from every FastAPI variant's `requirements.txt`; no template imported them.

### Fixed
- **A fresh FastAPI Supabase scaffold failed its own tests** (JSONB on SQLite), and the token and entra scaffolds failed 14 of their tests each because the shared tests wrote without credentials. The shared tests now override `get_current_user`, so they pass unchanged in every variant.
- **NestJS scaffolds failed their own checks:** `npm run lint` had no configuration, `npm run test:e2e` could not compile, and `npm test` failed in all four variants. All four now pass lint, format, unit and e2e.
- **The no-auth FastAPI variant honoured `X-User-Id` in every environment**, so anyone could act as any user. The header is now validated (422 on a bad value) and honoured only in development and test. The default principal needs no database access, so the first call no longer inserts an `admin@example.com` row, and the process-wide user cache is gone.

## [0.4.1] - 2026-09-14

### Fixed
- **Scaffolds from the PyPI package got a `.env` without working defaults.** The wheel and sdist left out `env_defaults.env`, so `project-initializer` installed from PyPI wrote a root `.env` and `.env.example` with an empty `DATABASE_URL`, `AUTH_TOKEN` and Entra IDs and a narrower `CORS_ORIGINS` for every api scope, and `docker compose up` did not run as-is. A scaffold from a checkout was unaffected. Every release published to PyPI up to 0.3.9 had this gap; 0.4.0 was tagged but not published. The file is now packaged, and `tests/test_package_data.py` builds a wheel and fails on any tracked package file missing from it.

## [0.4.0] - 2026-09-13

The Angular frontend template moves from Tailwind CSS to Angular Material 3 in every variant (base, token, supabase, entra).

### Changed
- **Frontend styling is Angular Material 3.** `@angular/material` and `@angular/cdk` 21.2 replace Tailwind: `mat.theme()` in `src/styles.scss` defines the `--mat-sys-*` tokens, light and dark switch through `color-scheme`, and there are no utility classes and no PostCSS config. Components are split into `.ts` + `.html` + `.css`, and component CSS uses tokens only (no color literals, `!important` or `::ng-deep`).
- **The navigation shell follows the M3 window size classes** (600 / 840 / 1200 / 1600px, never 768px): a top app bar and a navigation bar below 600px, whose actions button opens a bottom sheet with the theme and account actions; from 600px a collapsed rail docked in `mat-sidenav`, which a toggle expands from 840px and which starts expanded from 1600px. The rail choice is remembered in `localStorage`.
- **The theme choice is a selection, not a cycle.** The rail's Change theme button opens a menu of System, Light and Dark with the current mode checked; the compact sheet lists the same three as a single-selection list. Both share `THEME_OPTIONS` with the Settings page, and list items keep their focus overlay for keyboard focus only.

### Added
- Shared UI components on Material primitives and a `/components` catalog page.
- `tests/test_frontend_nginx_csp.py` checks every variant's layered `nginx.conf` against the nonce policy.

### Fixed
- **The Docker frontend blocked its own styles and scripts.** nginx sent `Content-Security-Policy: default-src 'self'` with no nonce, which blocks Angular's inline styles and scripts. nginx now replaces the `CSP_NONCE` placeholder in `index.html` with `$request_id` through `sub_filter`, allows that nonce in `script-src` and `style-src`, allows the `fonts.bunny.net` web fonts, and serves `index.html` without validators so a stored page never meets a newer nonce. The supabase and entra frontend overlays ship their own `nginx.conf` whose policy also allows their provider in `connect-src` (and `frame-src` for MSAL).
- **Entra sign-in could hang.** `AuthService.login()` dropped the promise from `loginRedirect()`, so a failure to start the redirect never reached the login page, which stayed busy with no message. `login()` now returns that promise.
- **Compact snackbars could cover the navigation bar** when enlarged text made the bar taller than 64px. The bar now publishes its rendered height as `--app-nav-bar-block-size`, which the snackbar offset reads.

### CI
- The `ruff` dev dependency is capped at `<0.16`: ruff 0.16 adds rules that report findings across the templates, which will be adopted in their own change.
- Component test helpers pick a component's `.ts` file by exact name instead of glob order, which differs between macOS and Linux.

## [0.3.9] - 2026-07-16

### Fixed
- **NestJS `GET /api/v1/test/items` always returned 500.** The handler returns an array but was decorated `@ZodSerializerDto(ItemResponseDto)`, whose schema is a single `z.object` — so the serializer rejected the response with "expected object, received array" before looking at any element, failing even for an empty list. List responses now use their own `ItemListResponseDto` (`z.array(ItemResponseSchema)`), which still strips unknown fields from every element, so the response whitelist is unchanged. The shipped `serialization.spec.ts` now covers the list path it previously missed.

## [0.3.8] - 2026-07-16

Every NestJS variant is now usable in Docker. Three chained bugs each hid the next: the API image would not build, so nothing reached the database; once it built, no migration existed so the database stayed empty; once the tables existed, every query still failed on TLS.

### Fixed
- **NestJS `/health/readiness` reported `database: down` against a perfectly healthy database.** `deriveSslOption` treated every host outside `{localhost, 127.0.0.1, [::1]}` as remote and forced TLS — but under Compose the API reaches Postgres at the *service name* (`db`), and `postgres:16-alpine` serves no TLS, so every query failed with `Error opening a TLS connection: The server does not support SSL connections`. (The util's own comment said the local Docker database "must stay plaintext"; the implementation just never accounted for the compose host.) TLS is now decided by an explicit `sslmode` when present, else by the host: loopback and single-label hostnames (`db`) stay plaintext, public DNS names get TLS. Supabase (`sslmode=require`, FQDN) is unaffected.
- **`PrismaService.isHealthy()` swallowed the driver error in a bare `catch {}`**, so a failing database surfaced only as `database: down` with no reason anywhere — which is what made the bug above invisible. It now logs the error before reporting down.
- **A scaffolded NestJS project came up with an empty database.** The template shipped a Prisma schema but no migrations (`prisma/migrations/` held only a `.gitkeep`), so the entrypoint's `prisma migrate deploy` logged "No migration found in prisma/migrations" and exited 0 — creating no tables. `/health/readiness` returned 503 `database: down`. An initial migration is now shipped for the base schema (`users`) and for the supabase overlay's differing schema (`profiles`). The supabase migration deliberately reuses the base migration's directory name so the overlay **overwrites** it rather than stacking — otherwise a supabase scaffold would also create a stray `users` table. Guarded by `tests/test_nestjs_migrations.py`, which ties each variant's migration to the tables its schema maps to.
- **No NestJS variant could build its API image.** The Dockerfile runs `npm ci` when a lock is present, and `npm ci` hard-fails on any drift between `package.json` and `package-lock.json` — so `docker-compose up` was broken for all four NestJS variants (half the matrix). Three separate causes:
  - The base lock never got the `@bull-board/*` + `express-basic-auth` deps that `package.json` declares (`Missing: @bull-board/api@8.0.0 from lock file`).
  - `templates-token-nestjs` shipped an empty stub lock (`{"packages": {}}`, committed by accident in a gitignore chore) that overwrote the good base lock. Removed — the overlay ships no `package.json`, so the base lock is the correct one.
  - `templates-entra-nestjs` added `jsonwebtoken` / `jwks-rsa` to `package.json` but shipped no lock, inheriting the base one. It now has its own.

  All four variants' locks are regenerated and verified in sync after layering, guarded by `tests/test_nestjs_lockfile_sync.py`.

## [0.3.7] - 2026-07-16

### Fixed
- **Two scaffolded projects could not run at the same time.** Two independent daemon-global collisions:
  - Every compose service pinned a fixed `container_name` (`app_db`, `app_api`, `app_frontend`, `app_adminer`, `app_redis`), so a second project — or any unrelated project already using those names — failed with `Conflict. The container name "/app_db" is already in use`. The `container_name` keys are dropped across all six compose files and the generated frontend-only compose; Compose now derives `<project>-<service>-1` from the project directory, which is unique per scaffold. The `app_db` **database** name is unchanged.
  - `adminer` published a literal `8080:8080` while every other service was already parametrized, so the second project died with `Bind for 0.0.0.0:8080 failed: port is already allocated`. Now `${ADMINER_HOST_PORT:-8080}`, emitted into the generated `.env` alongside the other topology vars.

  Verified by scaffolding two projects and running both stacks at once: eight containers healthy, each API backed by its own database. Guarded by `test_no_compose_file_hardcodes_container_names` and `test_every_published_host_port_is_parametrized`.

## [0.3.6] - 2026-07-16

### Added
- **Interactive wizard** (`wizard.py`) — `project-initializer` now prompts (via `questionary`) for any option not passed as a flag. A fully-flagged invocation still runs zero prompts, and `--yes` / piped stdin forces the previous non-interactive defaults, so CI and the `.vscode` tasks never block. Falls back to defaults when the terminal cannot host prompts (Git Bash / mintty, closed stdin, EOF).
- **`--framework fastapi|nestjs`** — explicit framework option; `--fastapi` / `--nestjs` remain as shorthands.
- **`--yes` / `-y`**, **`--verbose` / `-V`** flags, and a compact Rich scaffold output (config panel + summary tree).
- **`docs_generator.py`** — the six docs a scaffolded project ships (`README.md`, `CLAUDE.md`, `api/README.md`, `api/.claude/CLAUDE.md`, `frontend/README.md`, `frontend/.claude/CLAUDE.md`) are now built per-flag instead of copied from static overlay files, so a NestJS project never mentions SQLAlchemy and a no-auth project never documents Entra.
- **Architecture-fitness test** — `api/tests/unit/test_architecture.py` parses the inner layers with `ast` and fails the build on any outward import, so the hexagonal boundaries cannot erode silently.
- **Compose topology env vars** — `API_HOST_PORT`, `FRONTEND_HOST_PORT`, `DB_HOST_PORT` (omitted for supabase); unset vars fall back to the previous fixed ports.

### Fixed
- **Frontend container was permanently `unhealthy`.** Its `HEALTHCHECK` fetched `http://localhost/health`, which resolves to `::1` first, while `nginx.conf` listens on IPv4 only (`listen 80;`) — so the check failed forever even though nginx served correctly. Now pinned to `127.0.0.1`.
- **BAML client drift broke `docker-compose up` on both frameworks.** The checked-in `baml_client/` was generated by an older CLI (FastAPI 0.222.0, NestJS 0.220.0) than the pinned runtime (`baml-py==0.223.0` / `@boundaryml/baml@0.223.0`). The Dockerfile regenerates the client in-image, but compose bind-mounts the source tree over `/app`, shadowing it with the stale client — so a freshly scaffolded API container crashed at boot with `ImportError: baml-py is likely out of date`. Both clients are now regenerated at 0.223.0, matching `generators.baml` and the runtime pins.

### Changed
- **FastAPI template restructured to hexagonal (ports & adapters)**: `app/domain/` (entities, ports, exceptions), `app/application/` (services, dto, commands), `app/infrastructure/` (orm, repositories, database, settings, config, audit), `app/api/` (v1/endpoints, deps, schemas, handlers, middleware). Replaces the flat `app/models|services|repositories|core|utils` layout. All four overlays (token / supabase / entra / asyncdb) were re-pathed to match.
- The version now has a single source of truth in `pyproject.toml`; `__init__.py` reads it from the installed package metadata.
- Compose files no longer hardcode `.env`-owned config in their `environment` blocks.

### Removed
- 16 static per-overlay `README.md` / `CLAUDE.md` files, superseded by `docs_generator.py`.

## [0.3.5] - 2026-07-01

### Added
- **`--auth entra`** — Microsoft Entra ID (formerly Azure AD) OIDC auth mode, bringing the scaffolder to **8 variants** (2 frameworks × 4 auth modes):
  - FastAPI & NestJS: in-process RS256 JWT validation with JWKS auto-refresh and tenant/audience/scope checks; no client secret stored on the API.
  - Angular frontend: MSAL login, auth guard, and HTTP interceptor.
  - New `templates-entra-fastapi/`, `templates-entra-nestjs/`, and `templates-entra-frontend/` overlays, plus entra legs in the CI matrix.

### Fixed
- **BAML**: bumped the template generator to `0.223.0` to match the pinned `baml-py` / `@boundaryml/baml` package (BAML enforces a major/minor match), unblocking every backend CI job.
- **entra Docker**: override the host-facing `DATABASE_URL` / `DIRECT_URL` (`localhost:5433`) with the compose-network address (`db:5432`) so the API container can reach Postgres.
- **entra FastAPI**: added the missing `email-validator` dependency required by the base `EmailStr` user schemas.
- **entra NestJS**: fixed the `jwks-rsa` import (`import { JwksClient }` + `new`) that failed to compile under the template's tsconfig.

### CI
- Pinned `baml-py==0.223.0` in the FastAPI test-package legs (NestJS already pins via `package.json`) to prevent future version drift.

## [0.3.4] - 2026-06-18

### Fixed
- Repaired the frontend component catalog and rebuilt the chat input as a Gemini-style pill.

## [0.3.3] - 2026-06-18

### Added
- Angular UI component library with full test coverage.

## [0.3.2] - 2026-06-16

### Added
- Scope-aware layer selection and file transforms (`--scope api` / `--scope frontend`).
- `--async-db` opt-in async SQLAlchemy path for FastAPI, documented in the README.
- FastAPI template alignment with the official tutorial; hardened NestJS Prisma TLS with build-verification tests.
- Responsive frontend shell with theme toggle.
- GitHub Actions workflows for a green-gate CI.

### Fixed
- Forced LF on entrypoint scripts to stop CRLF `ENTRYPOINT` failures.
- NestJS user response schema whitelist and several CI pipeline repairs (BAML version, ruff path, frontend install resilience).

## [0.2.0] - 2026-02-13

### Added
- Early full-stack scaffolding across FastAPI and NestJS with token and Supabase auth overlays.

## [0.1.1] - 2026-01-25

### Added
- Initial public release of the `project-initializer` CLI.

[Unreleased]: https://github.com/SilvioBaratto/project-initializer/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/SilvioBaratto/project-initializer/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/SilvioBaratto/project-initializer/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/SilvioBaratto/project-initializer/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/SilvioBaratto/project-initializer/compare/v0.3.9...v0.4.0
[0.3.9]: https://github.com/SilvioBaratto/project-initializer/compare/v0.3.8...v0.3.9
[0.3.8]: https://github.com/SilvioBaratto/project-initializer/compare/v0.3.7...v0.3.8
[0.3.7]: https://github.com/SilvioBaratto/project-initializer/compare/v0.3.6...v0.3.7
[0.3.6]: https://github.com/SilvioBaratto/project-initializer/compare/v0.3.5...v0.3.6
[0.3.5]: https://github.com/SilvioBaratto/project-initializer/compare/v0.3.4...v0.3.5
[0.3.4]: https://github.com/SilvioBaratto/project-initializer/compare/v0.3.3...v0.3.4
[0.3.3]: https://github.com/SilvioBaratto/project-initializer/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/SilvioBaratto/project-initializer/compare/v0.2.0...v0.3.2
[0.2.0]: https://github.com/SilvioBaratto/project-initializer/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/SilvioBaratto/project-initializer/releases/tag/v0.1.1
