# Frontend

This project was generated using [Angular CLI](https://github.com/angular/angular-cli) version 20.3.3.

## Installing dependencies

Install packages with the `--legacy-peer-deps` flag:

```bash
npm install --legacy-peer-deps
```

> **Why `--legacy-peer-deps`?** `@angular/build` declares an optional peer dependency on
> `vitest@^4`, but this project pins `vitest@^3`. npm 7+ treats this mismatch as a hard
> `ERESOLVE` error and aborts a plain `npm install`. `--legacy-peer-deps` skips npm's
> peer-dependency check and installs anyway. Safe here: `vitest` is a test-only devDependency and
> Angular's build only optionally peers it, so app build/serve are unaffected.

## Development server

To start a local development server, run:

```bash
ng serve
```

Once the server is running, open your browser and navigate to `http://localhost:4200/`. The application will automatically reload whenever you modify any of the source files.

## Code scaffolding

Angular CLI includes powerful code scaffolding tools. To generate a new component, run:

```bash
ng generate component component-name
```

For a complete list of available schematics (such as `components`, `directives`, or `pipes`), run:

```bash
ng generate --help
```

## Building

To build the project run:

```bash
ng build
```

This will compile your project and store the build artifacts in the `dist/` directory. By default, the production build optimizes your application for performance and speed.

## Running unit tests

To execute unit tests with the [Karma](https://karma-runner.github.io) test runner, use the following command:

```bash
ng test
```

## Running end-to-end tests

For end-to-end (e2e) testing, run:

```bash
ng e2e
```

Angular CLI does not come with an end-to-end testing framework by default. You can choose one that suits your needs.

## Router features

The scaffold enables two `provideRouter` features in `app.config.ts`:

| Feature | What it does |
|---|---|
| **`withComponentInputBinding()`** | Binds route parameters, query params, and data directly to signal `input()` properties on routed components — no `ActivatedRoute` injection needed. |
| **`withViewTransitions()`** | Wraps route navigations in the [View Transitions API](https://developer.mozilla.org/en-US/docs/Web/API/View_Transitions_API), producing smooth cross-page animations in supporting browsers (gracefully no-ops in others). |

### Using `withComponentInputBinding`

```typescript
// In a routed component — no ActivatedRoute needed
export class ItemDetailComponent {
  readonly id = input<string>();   // bound from :id route param automatically
}
```

### Using `withViewTransitions`

Navigations automatically use the browser's default cross-fade. To customise the transition, add CSS `view-transition-name` rules and a `@keyframes` block for `::view-transition-*` pseudo-elements.

## Production security hardening — CSP nonces

The scaffold ships a `Content-Security-Policy: default-src 'self'` baseline from nginx. For production, tighten the policy with per-request nonces so inline scripts injected by third-party libraries are blocked unless they carry the server-issued nonce.

### Options

| Approach | Where to configure |
|---|---|
| **`autoCsp: true`** in `angular.json` build options | Instructs the Angular build to inject `ngCspNonce` meta tags automatically during SSR/server rendering. |
| **`ngCspNonce` attribute** on the `<app-root>` element | Pass a unique, unpredictable nonce per request from your server template into the bootstrap token `CSP_NONCE`. Angular reads this token and stamps it on all inline styles/scripts it generates. |
| **`CSP_NONCE` injection token** | Provide the token in `app.config.ts`: `{ provide: CSP_NONCE, useValue: getRequestNonce() }`. Angular uses it for runtime-generated inline elements. |

### Rules

- Nonces **must be unique and unpredictable per HTTP response** — a static nonce is equivalent to no nonce.
- Generate nonces server-side (e.g. `secrets.token_hex(16)`) and pass them in both the `Content-Security-Policy` header and the HTML template.
- Update the nginx `add_header Content-Security-Policy` line to include `'nonce-<VALUE>'` in `script-src` and `style-src`.

Reference: [angular.dev/best-practices/security](https://angular.dev/best-practices/security)

## Additional Resources

For more information on using the Angular CLI, including detailed command references, visit the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.
