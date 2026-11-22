import { readFileSync } from 'node:fs';
import { parse } from 'dotenv';
import { describeError } from '../common/describe-error';
import { baseEnvShape } from './env.base';
import { LOG_LEVELS, type LogLevel } from './logger.config';

const LOG_LEVEL_KEY = 'LOG_LEVEL';
const RELOAD_SIGNAL = 'SIGHUP' as const;
const WINDOWS_PLATFORM = 'win32';

/** Where a log level can be read from at the moment of a reload. */
export interface LogLevelSources {
  /** `LOG_LEVEL` in the process environment right now. */
  readonly processValue: string | undefined;
  /** `LOG_LEVEL` in the first dotenv file that sets it, read right now. */
  readonly fileValue: string | undefined;
  /**
   * What `fileValue` was when the process started. `ConfigModule` copies a file's `LOG_LEVEL` into
   * the process environment at start-up, so a `processValue` equal to this one was never exported
   * by the operator and must not shadow an edit to the file.
   */
  readonly startupFileValue: string | undefined;
}

/** Receives what a reload decides; the application backs it with the pino loggers. */
export interface LogLevelReloadSink {
  /** The level the loggers use now. */
  currentLevel(): string;
  /** Switches every logger to the given level. */
  applyLevel(level: LogLevel): void;
  /** Informational line about a reload that went through. */
  log(message: string): void;
  /** Warning about a reload that was refused. */
  warn(message: string): void;
}

/** What {@link reloadLogLevel} did. */
export type LogLevelReloadOutcome = 'applied' | 'unchanged' | 'rejected';

// Quietest last: a higher rank lets fewer lines through.
const LEVELS_BY_QUIETNESS: readonly string[] = [
  ...LOG_LEVELS.filter((level) => level !== 'silent').reverse(),
  'silent',
];

function isQuieter(next: string, previous: string): boolean {
  return LEVELS_BY_QUIETNESS.indexOf(next) > LEVELS_BY_QUIETNESS.indexOf(previous);
}

/**
 * Picks the raw `LOG_LEVEL` a reload should use, with the precedence start-up has: a value the
 * operator exported beats a file, and among files the first one wins.
 */
function selectRawLevel(sources: LogLevelSources): string | undefined {
  const exportedByOperator =
    sources.processValue !== undefined && sources.processValue !== sources.startupFileValue;
  return exportedByOperator ? sources.processValue : sources.fileValue;
}

/**
 * Re-evaluates `LOG_LEVEL` and switches the loggers to it, so a level can be raised or lowered on
 * a running process without a restart.
 *
 * The value is validated with the same schema as the start-up check, so the vocabulary and the
 * casing rule are the same. A key that is set nowhere means the default level, as at start-up. A
 * value that is not a level is refused and the current level is kept; the warning names only the
 * accepted set, never the value, which may have been pasted into the wrong key. The change is
 * logged once, on whichever side of the switch the line can pass the threshold.
 *
 * @param sources - The values to choose from, see {@link LogLevelSources}.
 * @param sink - Applies the level and reports the result.
 * @returns `applied` when the level changed, `unchanged` when it was already in force, `rejected`
 *   when the value was not a level.
 */
export function reloadLogLevel(
  sources: LogLevelSources,
  sink: LogLevelReloadSink,
): LogLevelReloadOutcome {
  const parsed = baseEnvShape.LOG_LEVEL.safeParse(selectRawLevel(sources));
  if (!parsed.success) {
    sink.warn(`Log level not reloaded: ${LOG_LEVEL_KEY} must be one of ${LOG_LEVELS.join(', ')}`);
    return 'rejected';
  }
  const previous = sink.currentLevel();
  if (parsed.data === previous) {
    sink.log(`Log level reloaded: still ${previous}`);
    return 'unchanged';
  }
  const message = `Log level reloaded: ${previous} to ${parsed.data}`;
  // The line has to pass the threshold of one of the two levels to be seen at all: before the
  // switch when it gets quieter, after it when it gets louder.
  if (isQuieter(parsed.data, previous)) {
    sink.log(message);
    sink.applyLevel(parsed.data);
  } else {
    sink.applyLevel(parsed.data);
    sink.log(message);
  }
  return 'applied';
}

/**
 * Reads `LOG_LEVEL` from dotenv files without touching `process.env`.
 *
 * @param paths - Files to try in order; one that is missing or unreadable is skipped.
 * @param readFile - Reads a file as UTF-8 text; replaceable in tests.
 * @returns The value in the first file that sets the key, as written, or `undefined`.
 */
export function readLogLevelFromEnvFiles(
  paths: readonly string[],
  readFile: (path: string) => string = (path) => readFileSync(path, 'utf8'),
): string | undefined {
  for (const path of paths) {
    try {
      const value = parse(readFile(path))[LOG_LEVEL_KEY];
      if (value !== undefined) {
        return value;
      }
    } catch {
      // A file that does not exist is the normal case (in Docker no file is read), and one that
      // cannot be read must not stop the process from reloading the rest.
    }
  }
  return undefined;
}

/** A logger whose threshold can be changed at runtime; every pino logger is one. */
export interface LevelledLogger {
  level: string;
}

/** Where a reload reports its result. */
export interface LogLevelReporter {
  log(message: string): void;
  warn(message: string): void;
}

/**
 * Builds the sink that moves a set of pino loggers to a new level together.
 *
 * `nestjs-pino` has one root logger, `PinoLogger.root`, that every other logger descends from:
 * request loggers are its children and lines written outside a request go to it directly, so the
 * application passes the root alone. Loggers already created for in-flight requests keep the
 * level they were created with; the next request picks up the new one. A child logger created
 * with an explicit level, such as the audit logger's, is not touched.
 *
 * @param loggers - Returns the loggers to keep in step, evaluated at every reload because the
 *   root logger only exists once the logging module has been built. The first one is the
 *   reference for the current level.
 * @param reporter - Receives the result lines.
 * @returns The sink to pass to {@link installLogLevelReload}.
 */
export function createLogLevelSink(
  loggers: () => readonly [LevelledLogger, ...LevelledLogger[]],
  reporter: LogLevelReporter,
): LogLevelReloadSink {
  return {
    currentLevel: () => loggers()[0].level,
    applyLevel: (level) => {
      for (const logger of loggers()) {
        logger.level = level;
      }
    },
    log: (message) => reporter.log(message),
    warn: (message) => reporter.warn(message),
  };
}

/** The part of `process` that {@link installLogLevelReload} uses to listen for the signal. */
export interface SignalSource {
  on(signal: 'SIGHUP', listener: () => void): unknown;
  off(signal: 'SIGHUP', listener: () => void): unknown;
}

/** Everything {@link installLogLevelReload} needs from its surroundings. */
export interface LogLevelReloadInstall {
  /** Dotenv files to re-read, see `ENV_FILE_PATHS`. */
  readonly envFilePaths: readonly string[];
  /** Applies levels and reports results. */
  readonly sink: LogLevelReloadSink;
  /** The process environment; replaceable in tests. */
  readonly processEnv?: NodeJS.ProcessEnv;
  /** Signal source; defaults to the current process. */
  readonly signals?: SignalSource;
  /** Defaults to the current platform. */
  readonly platform?: NodeJS.Platform;
  /** Reads a file as text; replaceable in tests. */
  readonly readFile?: (path: string) => string;
}

/**
 * Makes `SIGHUP` reload the log level, the way daemons re-read their configuration: edit the
 * `.env` file or export a new value, then `kill -HUP <pid>`.
 *
 * Nothing is installed on Windows, where `SIGHUP` means the console window closed. The handler is
 * installed with the file's start-up value as the baseline, see {@link LogLevelSources}.
 *
 * @param install - See {@link LogLevelReloadInstall}.
 * @returns A function that removes the handler; call it when the application closes. It is a
 *   no-op when nothing was installed.
 */
export function installLogLevelReload(install: LogLevelReloadInstall): () => void {
  const platform = install.platform ?? process.platform;
  if (platform === WINDOWS_PLATFORM) {
    return () => undefined;
  }
  const processEnv = install.processEnv ?? process.env;
  const signals = install.signals ?? process;
  const startupFileValue = readLogLevelFromEnvFiles(install.envFilePaths, install.readFile);
  const handler = (): void => {
    try {
      reloadLogLevel(
        {
          processValue: processEnv[LOG_LEVEL_KEY],
          fileValue: readLogLevelFromEnvFiles(install.envFilePaths, install.readFile),
          startupFileValue,
        },
        install.sink,
      );
    } catch (error) {
      // An exception escaping a signal handler would take the whole process down.
      install.sink.warn(`Log level not reloaded: ${describeError(error)}`);
    }
  };
  signals.on(RELOAD_SIGNAL, handler);
  return () => {
    signals.off(RELOAD_SIGNAL, handler);
  };
}
