import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { INestApplication } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import type { NestExpressApplication } from '@nestjs/platform-express';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import helmet from 'helmet';
import { Logger } from 'nestjs-pino';
import { z } from 'zod';
import { HttpExceptionFilter } from './common/filters/http-exception.filter';
import { rejectMalformedJson } from './common/filters/malformed-json.middleware';
import { PrismaClientExceptionFilter } from './common/filters/prisma-exception.filter';
import type { BaseEnv } from './config/env.base';
import { MAX_REQUEST_BODY_BYTES } from './config/http-limits';

/** Path prefix of every route, which is also the API version a client pins to. */
export const API_PREFIX = 'api/v1';

/** Where the OpenAPI UI is served; it sits outside {@link API_PREFIX}. */
export const OPENAPI_PATH = 'docs';

/** HTTP methods a browser client may use cross-origin. */
export const CORS_METHODS: readonly string[] = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'];

/** Request headers a browser client may send cross-origin. */
export const CORS_ALLOWED_HEADERS: readonly string[] = [
  'Authorization',
  'Content-Type',
  'Accept',
  'X-Request-Id',
];

/** Response headers a browser client may read; the rate-limit ones let it back off by itself. */
export const CORS_EXPOSED_HEADERS: readonly string[] = [
  'X-Request-Id',
  'X-RateLimit-Limit',
  'X-RateLimit-Remaining',
  'X-RateLimit-Reset',
  'Retry-After',
];

/** How long a browser may cache a preflight answer. */
export const CORS_MAX_AGE_SECONDS = 3600;

const OPENAPI_TITLE = 'NestJS API Template';
const OPENAPI_DESCRIPTION = 'Modern API';
const BEARER_SECURITY_NAME = 'bearer';
const PACKAGE_MANIFEST_FILE = 'package.json';

const PackageManifestSchema = z.object({ version: z.string().min(1) });

/**
 * Applies everything about the HTTP surface that must be identical in production and in tests:
 * logger, shutdown hooks, proxy trust, security headers, CORS, the JSON body limit, the `api/v1`
 * prefix and the error filters.
 *
 * `main.ts` and the e2e harness both call it, so a test exercises the same pipeline a client
 * hits. Call it before `listen()` or `init()`: the body parser registered here replaces Nest's
 * default only when it is in place before initialisation. The application must run on the Express
 * platform and import `ConfigModule` (for `CORS_ORIGINS` and `TRUST_PROXY_HOPS`) and
 * `LoggerModule`.
 *
 * @param app - The application to configure.
 */
export function configureApp(app: INestApplication): void {
  const config = app.get<ConfigService, ConfigService<BaseEnv, true>>(ConfigService);
  const expressApp = app as NestExpressApplication;
  app.useLogger(app.get(Logger));
  app.enableShutdownHooks();
  // Behind the compose nginx every client arrives from the proxy's address, so without this the
  // rate limiter would count the whole user base as one caller.
  expressApp.set('trust proxy', config.get('TRUST_PROXY_HOPS', { infer: true }));
  app.use(helmet());
  app.enableCors({
    origin: config.get('CORS_ORIGINS', { infer: true }),
    credentials: true,
    methods: [...CORS_METHODS],
    allowedHeaders: [...CORS_ALLOWED_HEADERS],
    exposedHeaders: [...CORS_EXPOSED_HEADERS],
    maxAge: CORS_MAX_AGE_SECONDS,
  });
  // After CORS, so a 413 from the parser still carries the CORS headers and the browser can
  // read it instead of reporting an opaque network error.
  expressApp.useBodyParser('json', { limit: MAX_REQUEST_BODY_BYTES });
  app.use(rejectMalformedJson);
  app.setGlobalPrefix(API_PREFIX);
  // Nest tries global filters from the last registered to the first, so the catch-all goes in
  // first: the Prisma filter, registered after it, then gets to look at its own errors before
  // the catch-all turns them into a 500.
  app.useGlobalFilters(new HttpExceptionFilter(), new PrismaClientExceptionFilter());
}

/**
 * Decides whether the OpenAPI UI is published.
 *
 * @param env.API_DOCS_ENABLED - Explicit choice; wins over the environment default.
 * @param env.NODE_ENV - Runtime mode. Without an explicit choice the UI is published everywhere
 *   except production, where it would hand attackers a map of every route.
 * @returns `true` when {@link setupOpenApi} should run.
 */
export function isOpenApiEnabled(env: Pick<BaseEnv, 'API_DOCS_ENABLED' | 'NODE_ENV'>): boolean {
  return env.API_DOCS_ENABLED ?? env.NODE_ENV !== 'production';
}

/**
 * Publishes the OpenAPI document and its UI at {@link OPENAPI_PATH}. Request and response bodies
 * are documented from the zod schemas that `@Body({ schema })` and `@ResponseSchema` declare,
 * converted by the Swagger module itself.
 *
 * @param app - The configured application.
 * @param options.version - API version shown in the document.
 * @param options.bearerAuthRequired - Whether the variant protects its routes. When true the
 *   document declares a bearer requirement for every operation, so the UI sends the token;
 *   routes marked public can still be called without it.
 */
export function setupOpenApi(
  app: INestApplication,
  options: { version: string; bearerAuthRequired: boolean },
): void {
  const builder = new DocumentBuilder()
    .setTitle(OPENAPI_TITLE)
    .setDescription(OPENAPI_DESCRIPTION)
    .setVersion(options.version)
    .addBearerAuth(undefined, BEARER_SECURITY_NAME);
  if (options.bearerAuthRequired) {
    builder.addSecurityRequirements(BEARER_SECURITY_NAME);
  }
  const document = SwaggerModule.createDocument(app, builder.build());
  SwaggerModule.setup(OPENAPI_PATH, app, document);
}

/**
 * Reads the service version from `package.json`, so it is declared in one place.
 *
 * @param packageJsonPath - Manifest to read; defaults to the one in the working directory, which
 *   is the project root both under `nest start` and in the container.
 * @returns The `version` field.
 * @throws Error when the file is missing or is not JSON, or when `version` is absent or empty.
 */
export function readPackageVersion(
  packageJsonPath = join(process.cwd(), PACKAGE_MANIFEST_FILE),
): string {
  const manifest: unknown = JSON.parse(readFileSync(packageJsonPath, 'utf8'));
  return PackageManifestSchema.parse(manifest).version;
}
