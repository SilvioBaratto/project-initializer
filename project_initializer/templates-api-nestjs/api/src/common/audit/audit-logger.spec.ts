import { Writable } from 'node:stream';
import { Test, type TestingModule } from '@nestjs/testing';
import { LoggerModule, PinoLogger } from 'nestjs-pino';
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

/** Validates src/common/audit/audit-logger.ts AuditLogger and auditActorIdOf. */
describe('AuditLogger', () => {
  // nestjs-pino builds one root logger per process, on the first boot of LoggerModule, and keeps
  // its destination and level from then on, so a second boot with other options would change
  // nothing. The real wiring is therefore booted once, and each test sets the level where
  // LOG_LEVEL and a runtime reload set it: on the root every application logger descends from.
  const sink = new CapturedLines();
  let moduleRef: TestingModule;
  let audit: AuditLogger;
  let appLogger: PinoLogger;

  beforeAll(async () => {
    moduleRef = await Test.createTestingModule({
      imports: [
        LoggerModule.forRoot(
          buildLoggerParams({ level: 'info', pretty: false, destination: sink }),
        ),
      ],
      providers: [AuditLogger],
    }).compile();
    await moduleRef.init();
    audit = moduleRef.get(AuditLogger);
    appLogger = await moduleRef.resolve(PinoLogger);
  });

  afterAll(async () => {
    await moduleRef.close();
  });

  beforeEach(() => {
    sink.lines.length = 0;
    PinoLogger.root.level = 'info';
  });

  it('when an action is recorded, then one structured line carries the event, action, resource and actor', () => {
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
    (level) => {
      PinoLogger.root.level = level;

      audit.record('item.delete', 'item-2', 'user-2');

      expect(sink.lines).toHaveLength(1);
      expect(sink.lines[0]).toMatchObject({ event: AUDIT_EVENT, action: 'item.delete' });
    },
  );

  it('when the application logs at the same level, then ordinary info lines are filtered but the audit line is not', () => {
    PinoLogger.root.level = 'warn';

    appLogger.info('ordinary');
    appLogger.warn('visible');
    audit.record('item.update', 'item-3', 'user-3');

    expect(sink.lines.map((line) => line.level)).toEqual([PINO_WARN, PINO_INFO]);
  });

  it('when the level of the application loggers changes at runtime, then the audit record is still written', () => {
    audit.record('item.create', 'item-4', 'user-4');

    PinoLogger.root.level = 'fatal';
    audit.record('item.create', 'item-4', 'user-4');

    expect(sink.lines).toHaveLength(2);
  });

  it('when an action is recorded, then the line holds only the audit fields and pino metadata', () => {
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
