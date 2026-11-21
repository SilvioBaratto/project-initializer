import { Injectable } from '@nestjs/common';
import { PinoLogger } from 'nestjs-pino';
import type { AuthenticatedUser } from '../auth/authenticated-user';

/** Value of the `event` field of every audit record, so a collector can filter on one string. */
export const AUDIT_EVENT = 'audit.action';

/** Actor id recorded where no authentication is wired and the caller is unknown. */
export const ANONYMOUS_ACTOR_ID = 'anonymous';

/**
 * Level audit records are written at, and the threshold of the logger that writes them. It is set
 * on the logger itself, not inherited, so `LOG_LEVEL` can neither silence the trail nor be the
 * reason it is missing when someone needs it.
 */
const AUDIT_LOG_LEVEL = 'info';
const AUDIT_LOG_CONTEXT = 'Audit';

/**
 * Names the actor of a request for the audit trail.
 *
 * @param user - Identity the authentication guard attached, or `undefined` when none is wired.
 * @returns The caller's opaque subject id, or {@link ANONYMOUS_ACTOR_ID}. Never an email, a
 *   username or a token, so the trail cannot be traced back to a person by reading it.
 */
export function auditActorIdOf(user?: AuthenticatedUser): string {
  return user?.id ?? ANONYMOUS_ACTOR_ID;
}

/**
 * Writes the audit trail: one structured line per state-changing action on data that may be
 * privacy relevant, to answer who did what to which record.
 *
 * Each line carries `event` ({@link AUDIT_EVENT}), `action`, `resourceId` and `actorId`, plus the
 * correlation id of the request it was written in. Pino's `info` threshold is fixed on a child
 * logger, so `LOG_LEVEL=warn`, `error` or `silent`, and a runtime level change, leave the trail
 * on. Route it to a retained store in the log collector by filtering on `event`.
 */
@Injectable()
export class AuditLogger {
  constructor(private readonly pinoLogger: PinoLogger) {}

  /**
   * Records that an action happened. Call it after the action succeeded, so the trail lists what
   * changed and not what was attempted.
   *
   * @param action - Stable dotted name of the action, for example `item.create`.
   * @param resourceId - Identifier of the record it acted on.
   * @param actorId - Opaque identifier of who did it, see {@link auditActorIdOf}.
   */
  record(action: string, resourceId: string, actorId: string): void {
    // Taken from the request logger when there is one, so the line carries the request id.
    this.pinoLogger.logger
      .child({ context: AUDIT_LOG_CONTEXT }, { level: AUDIT_LOG_LEVEL })
      .info({ event: AUDIT_EVENT, action, resourceId, actorId });
  }
}
