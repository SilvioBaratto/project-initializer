import { ArgumentsHost, Catch, ExceptionFilter, HttpStatus, Logger } from '@nestjs/common';
import { Prisma } from '@generated/prisma';
import type { Request, Response } from 'express';
import { isDatabaseUnavailableError } from '../../prisma/database-circuit-breaker';
import {
  buildErrorBody,
  describeRequest,
  INTERNAL_ERROR_MESSAGE,
  sendErrorBody,
  SERVICE_UNAVAILABLE_MESSAGE,
} from './error-body';

interface PrismaErrorMapping {
  status: HttpStatus;
  message: string;
}

/**
 * Client-facing answer for each Prisma error code that a caller can cause.
 *
 * The messages are fixed on purpose. Prisma's own text and `meta` name constraint columns, which
 * would let a client enumerate the schema or probe for existing values.
 */
export const PRISMA_ERROR_MAP: Readonly<Record<string, PrismaErrorMapping>> = {
  P2002: { status: HttpStatus.CONFLICT, message: 'Resource already exists' },
  P2003: { status: HttpStatus.BAD_REQUEST, message: 'Related resource does not exist' },
  P2025: { status: HttpStatus.NOT_FOUND, message: 'Resource not found' },
};

function findMapping(code: string): PrismaErrorMapping | undefined {
  // An own-property check, so a code such as "constructor" cannot resolve to an inherited member.
  return Object.hasOwn(PRISMA_ERROR_MAP, code) ? PRISMA_ERROR_MAP[code] : undefined;
}

/**
 * Maps known Prisma request errors to the shared error body.
 *
 * Codes in {@link PRISMA_ERROR_MAP} are caller mistakes and log one warning line carrying only
 * the code. Errors that mean the database cannot take the work (unreachable, timed out, out of
 * connections, refusing sessions while it restarts, as {@link isDatabaseUnavailableError}
 * defines) answer 503, exactly as a call rejected by the open circuit does, so a client sees one
 * answer for one outage; they log one warning line. Any other code is an unexpected database
 * failure: it answers 500 with a fixed message and logs the error with its stack.
 */
@Catch(Prisma.PrismaClientKnownRequestError)
export class PrismaClientExceptionFilter implements ExceptionFilter<Prisma.PrismaClientKnownRequestError> {
  private readonly logger = new Logger(PrismaClientExceptionFilter.name);

  catch(exception: Prisma.PrismaClientKnownRequestError, host: ArgumentsHost): void {
    const http = host.switchToHttp();
    const request = http.getRequest<Request>();
    const { status, message } = this.resolve(exception, request);
    sendErrorBody(http.getResponse<Response>(), buildErrorBody({ status, message, request }));
  }

  private resolve(
    exception: Prisma.PrismaClientKnownRequestError,
    request: Request,
  ): PrismaErrorMapping {
    const mapping = findMapping(exception.code);
    if (mapping) {
      this.logger.warn(`Prisma error ${exception.code} on ${describeRequest(request)}`);
      return mapping;
    }
    if (isDatabaseUnavailableError(exception)) {
      this.logger.warn(
        `Prisma error ${exception.code} on ${describeRequest(request)}: database unavailable`,
      );
      return { status: HttpStatus.SERVICE_UNAVAILABLE, message: SERVICE_UNAVAILABLE_MESSAGE };
    }
    this.logger.error(
      { err: exception },
      `Unmapped Prisma error ${exception.code} on ${describeRequest(request)}`,
    );
    return { status: HttpStatus.INTERNAL_SERVER_ERROR, message: INTERNAL_ERROR_MESSAGE };
  }
}
