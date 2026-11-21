import { Module } from '@nestjs/common';
import { AuditLogger } from './audit-logger';

/**
 * Provides {@link AuditLogger} to feature modules. It relies on the global `LoggerModule` that
 * `AppModule` registers for the pino logger it writes to.
 */
@Module({ providers: [AuditLogger], exports: [AuditLogger] })
export class AuditModule {}
