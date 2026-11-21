/**
 * Validates src/config/log-level-reload.ts: reloadLogLevel, readLogLevelFromEnvFiles,
 * createLogLevelSink and installLogLevelReload.
 */
import { EventEmitter } from 'node:events';
import pino from 'pino';
import {
  createLogLevelSink,
  installLogLevelReload,
  type LogLevelReloadSink,
  type LogLevelSources,
  readLogLevelFromEnvFiles,
  reloadLogLevel,
} from './log-level-reload';
import type { LogLevel } from './logger.config';

function fakeSink(initialLevel: string): jest.Mocked<LogLevelReloadSink> {
  let level = initialLevel;
  return {
    currentLevel: jest.fn(() => level),
    applyLevel: jest.fn((next: LogLevel) => {
      level = next;
    }),
    log: jest.fn(),
    warn: jest.fn(),
  };
}

function sources(overrides: Partial<LogLevelSources> = {}): LogLevelSources {
  return {
    processValue: undefined,
    fileValue: undefined,
    startupFileValue: undefined,
    ...overrides,
  };
}

describe('reloadLogLevel', () => {
  it('when the file now says debug, then the loggers switch to debug and the change is logged', () => {
    const sink = fakeSink('info');

    const outcome = reloadLogLevel(
      sources({ fileValue: 'debug', processValue: 'info', startupFileValue: 'info' }),
      sink,
    );

    expect(outcome).toBe('applied');
    expect(sink.applyLevel).toHaveBeenCalledWith('debug');
    expect(sink.log).toHaveBeenCalledWith('Log level reloaded: info to debug');
    expect(sink.warn).not.toHaveBeenCalled();
  });

  it.each([
    ['info', 'error', ['log', 'applyLevel']],
    ['info', 'silent', ['log', 'applyLevel']],
    ['debug', 'info', ['log', 'applyLevel']],
    ['error', 'debug', ['applyLevel', 'log']],
    ['silent', 'warn', ['applyLevel', 'log']],
    ['info', 'trace', ['applyLevel', 'log']],
  ])(
    'when the level goes from %s to %s, then the change is logged in the order %j so some threshold passes it',
    (from, to, expectedOrder) => {
      const sink = fakeSink(from);

      reloadLogLevel(sources({ processValue: to }), sink);

      const order = [
        { name: 'log', at: sink.log.mock.invocationCallOrder[0] ?? 0 },
        { name: 'applyLevel', at: sink.applyLevel.mock.invocationCallOrder[0] ?? 0 },
      ]
        .sort((first, second) => first.at - second.at)
        .map((step) => step.name);
      expect(order).toEqual(expectedOrder);
    },
  );

  it('when the value is already in force, then nothing is applied', () => {
    const sink = fakeSink('warn');

    const outcome = reloadLogLevel(sources({ processValue: 'warn' }), sink);

    expect(outcome).toBe('unchanged');
    expect(sink.applyLevel).not.toHaveBeenCalled();
    expect(sink.log).toHaveBeenCalledWith('Log level reloaded: still warn');
  });

  it('when the value uses other casing and spaces, then it is normalised like at start-up', () => {
    const sink = fakeSink('info');

    reloadLogLevel(sources({ processValue: ' ERROR ' }), sink);

    expect(sink.applyLevel).toHaveBeenCalledWith('error');
  });

  it('when the operator exported a level that differs from the file, then the export wins', () => {
    const sink = fakeSink('info');

    reloadLogLevel(
      sources({ processValue: 'trace', fileValue: 'debug', startupFileValue: 'info' }),
      sink,
    );

    expect(sink.applyLevel).toHaveBeenCalledWith('trace');
  });

  it('when the process value is only the copy ConfigModule made of the file, then an edited file wins', () => {
    const sink = fakeSink('info');

    reloadLogLevel(
      sources({ processValue: 'info', fileValue: 'error', startupFileValue: 'info' }),
      sink,
    );

    expect(sink.applyLevel).toHaveBeenCalledWith('error');
  });

  it('when the key was removed from the file that set it, then the default level applies', () => {
    const sink = fakeSink('debug');

    reloadLogLevel(sources({ processValue: 'debug', startupFileValue: 'debug' }), sink);

    expect(sink.applyLevel).toHaveBeenCalledWith('info');
  });

  it('when the key is set nowhere, then the default level applies', () => {
    const sink = fakeSink('error');

    reloadLogLevel(sources(), sink);

    expect(sink.applyLevel).toHaveBeenCalledWith('info');
  });

  it('when the value is not a level, then it is ignored and one warning names only the accepted set', () => {
    const sink = fakeSink('info');

    const outcome = reloadLogLevel(sources({ processValue: 'loud-secret' }), sink);

    expect(outcome).toBe('rejected');
    expect(sink.applyLevel).not.toHaveBeenCalled();
    expect(sink.warn).toHaveBeenCalledTimes(1);
    expect(sink.warn).toHaveBeenCalledWith(
      'Log level not reloaded: LOG_LEVEL must be one of fatal, error, warn, info, debug, trace, silent',
    );
  });

  it('when the value is blank, then it is refused like at start-up', () => {
    const sink = fakeSink('info');

    expect(reloadLogLevel(sources({ fileValue: '' }), sink)).toBe('rejected');
  });
});

/** Reads from an in-memory map, failing like the file system for a path that is not in it. */
function readerOf(files: Record<string, string>): (path: string) => string {
  return (path) => {
    const content = files[path];
    if (content === undefined) {
      throw new Error('ENOENT');
    }
    return content;
  };
}

describe('readLogLevelFromEnvFiles', () => {
  const bothFiles = readerOf({
    '../.env': 'PORT=3000\nLOG_LEVEL="debug"\n',
    '.env': 'LOG_LEVEL=error\n',
  });

  it('when both files set the key, then the first file wins and quotes are removed', () => {
    expect(readLogLevelFromEnvFiles(['../.env', '.env'], bothFiles)).toBe('debug');
  });

  it('when the first file is missing, then the next one is used', () => {
    expect(readLogLevelFromEnvFiles(['missing/.env', '.env'], bothFiles)).toBe('error');
  });

  it('when a file does not set the key, then the next one is tried', () => {
    const reader = readerOf({ '../.env': 'PORT=3000\n', '.env': 'LOG_LEVEL=warn\n' });

    expect(readLogLevelFromEnvFiles(['../.env', '.env'], reader)).toBe('warn');
  });

  it('when no file sets the key, then it returns undefined', () => {
    expect(readLogLevelFromEnvFiles(['missing/.env'], bothFiles)).toBeUndefined();
  });

  it('when it reads files, then process.env is not modified', () => {
    const before = process.env.LOG_LEVEL;
    const reader = readerOf({ '.env': 'LOG_LEVEL=trace\nLOG_LEVEL_RELOAD_PROBE=1\n' });

    readLogLevelFromEnvFiles(['.env'], reader);

    expect(process.env.LOG_LEVEL).toBe(before);
    expect(process.env.LOG_LEVEL_RELOAD_PROBE).toBeUndefined();
  });
});

describe('createLogLevelSink', () => {
  it('when the level is applied, then every logger moves and the first is the reference', () => {
    const requestRoot = pino({ level: 'info' }, { write: () => undefined });
    const outOfContext = pino({ level: 'info' }, { write: () => undefined });
    const reporter = { log: jest.fn(), warn: jest.fn() };
    const sink = createLogLevelSink(() => [outOfContext, requestRoot], reporter);

    sink.applyLevel('error');

    expect(sink.currentLevel()).toBe('error');
    expect(requestRoot.level).toBe('error');
    expect(outOfContext.level).toBe('error');
  });

  it('when a message is logged or warned, then it reaches the reporter', () => {
    const reporter = { log: jest.fn(), warn: jest.fn() };
    const sink = createLogLevelSink(
      () => [pino({ level: 'info' }, { write: () => undefined })],
      reporter,
    );

    sink.log('changed');
    sink.warn('refused');

    expect(reporter.log).toHaveBeenCalledWith('changed');
    expect(reporter.warn).toHaveBeenCalledWith('refused');
  });
});

describe('installLogLevelReload', () => {
  function install(overrides: Partial<Parameters<typeof installLogLevelReload>[0]> = {}): {
    signals: EventEmitter;
    sink: jest.Mocked<LogLevelReloadSink>;
    remove: () => void;
  } {
    const signals = new EventEmitter();
    const sink = fakeSink('info');
    const remove = installLogLevelReload({
      envFilePaths: ['.env'],
      sink,
      processEnv: {},
      signals,
      platform: 'linux',
      readFile: () => 'LOG_LEVEL=info\n',
      ...overrides,
    });
    return { signals, sink, remove };
  }

  it('when SIGHUP arrives after the file changed, then the new level is applied', () => {
    let fileContent = 'LOG_LEVEL=info\n';
    const { signals, sink } = install({
      processEnv: { LOG_LEVEL: 'info' },
      readFile: () => fileContent,
    });

    fileContent = 'LOG_LEVEL=debug\n';
    signals.emit('SIGHUP');

    expect(sink.applyLevel).toHaveBeenCalledWith('debug');
  });

  it('when SIGHUP arrives and the file holds an invalid level, then the level stays and the process survives', () => {
    const { signals, sink } = install({ readFile: () => 'LOG_LEVEL=loud\n' });

    expect(() => signals.emit('SIGHUP')).not.toThrow();

    expect(sink.applyLevel).not.toHaveBeenCalled();
    expect(sink.warn).toHaveBeenCalledTimes(1);
  });

  it('when applying the level throws, then the failure is reported instead of escaping the handler', () => {
    const { signals, sink } = install({ readFile: () => 'LOG_LEVEL=debug\n' });
    sink.applyLevel.mockImplementation(() => {
      throw new Error('logger gone');
    });

    expect(() => signals.emit('SIGHUP')).not.toThrow();

    expect(sink.warn).toHaveBeenCalledWith(expect.stringContaining('logger gone'));
  });

  it('when the returned function is called, then SIGHUP no longer reloads', () => {
    const { signals, sink, remove } = install({ readFile: () => 'LOG_LEVEL=debug\n' });

    remove();
    signals.emit('SIGHUP');

    expect(signals.listenerCount('SIGHUP')).toBe(0);
    expect(sink.applyLevel).not.toHaveBeenCalled();
  });

  it('when the platform is Windows, then no handler is installed', () => {
    const { signals, remove } = install({ platform: 'win32' });

    expect(signals.listenerCount('SIGHUP')).toBe(0);
    expect(() => remove()).not.toThrow();
  });

  it('when the handler is installed, then exactly one SIGHUP listener is added', () => {
    const { signals } = install();

    expect(signals.listenerCount('SIGHUP')).toBe(1);
  });
});
