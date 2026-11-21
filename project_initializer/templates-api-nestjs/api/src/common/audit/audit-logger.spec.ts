import { Writable } from 'node:stream';
import { Test } from '@nestjs/testing';
import { LoggerModule, PinoLogger } from 'nestjs-pino';
import { __resetOutOfContextForTests } from 'nestjs-pino/PinoLogger';
import type { Logger } from 'pino';
import { buildLoggerParams, type LogLevel } from '../../config/logger.config';
import { ANONYMOUS_ACTOR_ID, AUDIT_EVENT, AuditLogger, auditActorIdOf } from './audit-logger';

interface LogLine {
  level: number;
  event?: string;
  [field: string]: unknown;
}

const PINO_INFO = 30;
const PINO_WARN = 40;

/** Collects what pino writes, parsed line by line. */
class CapturedLines extends Writable {
  readonly lines: LogLine[] = [];

  override _write(chunk: Buffer, _encoding: string, done: () => void): void {
    this.lines.push(JSON.parse(chunk.toString()) as LogLine);
    done();
  }
}

/** Boots the real pino wiring of the application at the given level, writing to `sink`. */
async function bootLogging(
  level: LogLevel,
  sink: CapturedLines,
): Promise<{ audit: AuditLogger; appLogger: Logger }> {
  const moduleRef = await Test.createTestingModule({
    imports: [LoggerModule.forRoot(buildLoggerParams({ level, pretty: false, destination: sink }))],
    providers: [AuditLogger],
  }).compile();
  await moduleRef.init();
  const pinoLogger = await moduleRef.resolve(PinoLogger);
  return { audit: moduleRef.get(AuditLogger), appLogger: pinoLogger.logger };
}

/** Validates src/common/audit/audit-logger.ts AuditLogger and auditActorIdOf. */
describe('AuditLogger', () => {
  let sink: CapturedLines;

  beforeEach(() => {
    __resetOutOfContextForTests();
    sink = new CapturedLines();
  });

  it('when an action is recorded, then one structured line carries the event, action, resource and actor', async () => {
    const { audit } = await bootLogging('info', sink);

    audit.record('item.create', 'item-1', 'user-1');

    expect(sink.lines).toHaveLength(1);
    expect(sink.lines[0]).toMatchObject({
      level: PINO_INFO,
      event: AUDIT_EVENT,
      action: 'item.create',
      resourceId: 'item-1',
      actorId: 'user-1',
    });
  });

  it.each<LogLevel>(['warn', 'error', 'fatal', 'silent'])(
    'when LOG_LEVEL is %s, then the audit record is still written',
    async (level) => {
      const { audit } = await bootLogging(level, sink);

      audit.record('item.delete', 'item-2', 'user-2');

      expect(sink.lines).toHaveLength(1);
      expect(sink.lines[0]).toMatchObject({ event: AUDIT_EVENT, action: 'item.delete' });
    },
  );

  it('when the application logs at the same level, then ordinary info lines are filtered but the audit line is not', async () => {
    const { audit, appLogger } = await bootLogging('warn', sink);

    appLogger.info('ordinary');
    appLogger.warn('visible');
    audit.record('item.update', 'item-3', 'user-3');

    expect(sink.lines.map((line) => line.level)).toEqual([PINO_WARN, PINO_INFO]);
  });

  it('when the level of the application loggers changes at runtime, then the audit record is still written', async () => {
    const { audit, appLogger } = await bootLogging('info', sink);

    appLogger.level = 'fatal';
    audit.record('item.create', 'item-4', 'user-4');

    expect(sink.lines).toHaveLength(1);
  });

  it('when an action is recorded, then the line holds only the audit fields and pino metadata', async () => {
    const { audit } = await bootLogging('info', sink);

    audit.record('item.create', 'item-5', 'user-5');

    expect(Object.keys(sink.lines[0] ?? {}).sort()).toEqual(
      [
        'action',
        'actorId',
        'context',
        'event',
        'hostname',
        'level',
        'pid',
        'resourceId',
        'time',
      ].sort(),
    );
  });
});

describe('auditActorIdOf', () => {
  it('when an identity is attached, then the opaque subject id is returned and not the email', () => {
    const actor = auditActorIdOf({ id: 'subject-1', email: 'person@example.com', roles: [] });

    expect(actor).toBe('subject-1');
    expect(actor).not.toContain('@');
  });

  it('when no identity is attached, then the constant anonymous actor is returned', () => {
    expect(auditActorIdOf(undefined)).toBe(ANONYMOUS_ACTOR_ID);
    expect(ANONYMOUS_ACTOR_ID).toBe('anonymous');
  });
});
