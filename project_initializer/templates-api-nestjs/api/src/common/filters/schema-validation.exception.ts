import {
  BadRequestException,
  StandardSchemaValidationPipe,
  type StandardSchemaValidationPipeOptions,
} from '@nestjs/common';

/** Message of every request-validation failure; the failing fields are listed separately. */
export const VALIDATION_FAILED_MESSAGE = 'Validation failed';

/**
 * Issues the native validation pipe reports. The type is read from the pipe's own options, so the
 * template does not depend directly on the Standard Schema package that defines it.
 */
export type SchemaIssues = Parameters<
  NonNullable<StandardSchemaValidationPipeOptions['exceptionFactory']>
>[0];

/**
 * Raised by the global `StandardSchemaValidationPipe` when a request parameter fails its schema.
 *
 * The pipe's default exception flattens the issues into message strings. This one keeps them, so
 * the error filter can report each failing field with its path, in the error body every other
 * failure uses.
 */
export class SchemaValidationException extends BadRequestException {
  /**
   * @param issues - Every issue the schema reported, in the order it reported them.
   */
  constructor(readonly issues: SchemaIssues) {
    super(VALIDATION_FAILED_MESSAGE);
  }
}

/**
 * Builds the validation pipe the application registers as `APP_PIPE`: Nest's
 * `StandardSchemaValidationPipe`, throwing {@link SchemaValidationException} so a failure keeps its
 * field detail. Specs that wire a pipe of their own use this too, so they test the production one.
 *
 * @returns A new pipe; it validates only parameters that pass `{ schema }`.
 */
export function createSchemaValidationPipe(): StandardSchemaValidationPipe {
  return new StandardSchemaValidationPipe({
    exceptionFactory: (issues) => new SchemaValidationException(issues),
  });
}
