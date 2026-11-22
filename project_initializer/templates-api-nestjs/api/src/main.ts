import { ConsoleLogger, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { NestFactory } from '@nestjs/core';
import type { NestExpressApplication } from '@nestjs/platform-express';
import { PinoLogger } from 'nestjs-pino';
import { AUTH_GUARDS } from './app.auth';
import { AppModule } from './app.module';
import {
  answerUnmatchedRequests,
  configureApp,
  isOpenApiEnabled,
  readPackageVersion,
  setupOpenApi,
} from './app.setup';
import type { BaseEnv } from './config/env.base';
import { ENV_FILE_PATHS } from './config/env-files';
import { createLogLevelSink, installLogLevelReload } from './config/log-level-reload';

const BOOTSTRAP_LOG_CONTEXT = 'Bootstrap';
const LOG_LEVEL_RELOAD_LOG_CONTEXT = 'LogLevelReload';
const PRODUCTION_ENV = 'production';
const FAILED_START_EXIT_DELAY_MS = 10_000;

// Until the pino logger takes over, Nest writes its own start-up lines, coloured and unstructured
// by default. A log collector in production needs them as JSON like every other line. The mode is
// read from the process environment because the validated configuration does not exist yet.
function createStartupLogger(): ConsoleLogger | undefined {
  return process.env.NODE_ENV === PRODUCTION_ENV ? new ConsoleLogger({ json: true }) : undefined;
}

// `PinoLogger.root` alone is enough: request loggers are its children and lines written outside a
// request go to it directly, so moving it moves the whole application.
function enableLogLevelReload(app: NestExpressApplication): void {
  const removeHandler = installLogLevelReload({
    envFilePaths: ENV_FILE_PATHS,
    sink: createLogLevelSink(() => [PinoLogger.root], new Logger(LOG_LEVEL_RELOAD_LOG_CONTEXT)),
  });
  app.getHttpServer().once('close', removeHandler);
}

async function startApplication(app: NestExpressApplication): Promise<void> {
  const config = app.get<ConfigService, ConfigService<BaseEnv, true>>(ConfigService);
  configureApp(app);
  const docsEnabled = isOpenApiEnabled({
    API_DOCS_ENABLED: config.get('API_DOCS_ENABLED', { infer: true }),
    NODE_ENV: config.get('NODE_ENV', { infer: true }),
  });
  if (docsEnabled) {
    setupOpenApi(app, {
      version: readPackageVersion(),
      bearerAuthRequired: AUTH_GUARDS.length > 0,
    });
  }
  // init() registers the routes, so the unmatched-request handler can go in after all of them.
  await app.init();
  answerUnmatchedRequests(app);
  await app.listen(config.get('PORT', { infer: true }));
  enableLogLevelReload(app);
}

async function failStartup(app: NestExpressApplication, error: unknown): Promise<void> {
  // For an HTTP app Nest prints the buffered start-up logs only once `listen` succeeds, so after
  // a failed start the fatal line below would stay in the buffer and the process would die
  // without a word.
  app.flushLogs();
  Logger.fatal(error instanceof Error ? error : new Error(String(error)), BOOTSTRAP_LOG_CONTEXT);
  process.exitCode = 1;
  // The database pool is already open; closing it lets the process exit with the code set above.
  // Closing can hang while the database is unreachable, and a container that never exits is never
  // restarted, so the exit is also forced after a delay.
  setTimeout(() => process.exit(1), FAILED_START_EXIT_DELAY_MS).unref();
  // A failure to close must not hide the start-up error that caused it.
  await app.close().catch((closeError: unknown) => {
    Logger.error(
      { err: closeError },
      'Closing after a failed start-up also failed',
      BOOTSTRAP_LOG_CONTEXT,
    );
  });
}

async function bootstrap(): Promise<void> {
  // Without abortOnError: false, Nest calls process.abort() on a start-up error, which skips the
  // handling in `failStartup` and leaves a core dump instead of one fatal log line and an exit
  // code.
  const app = await NestFactory.create<NestExpressApplication>(AppModule, {
    bufferLogs: true,
    abortOnError: false,
    logger: createStartupLogger(),
  });
  try {
    await startApplication(app);
  } catch (error) {
    await failStartup(app, error);
  }
}

// Nest has already logged a failure of `NestFactory.create`, so only the exit code is set here.
bootstrap().catch(() => {
  process.exitCode = 1;
});
