import {
  ArgumentsHost,
  Catch,
  ExceptionFilter,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { Prisma } from '@generated/prisma';
import type { Request, Response } from 'express';
import { inspect } from 'node:util';
import { CircuitOpenError } from '../resilience/circuit-breaker';
import { buildErrorBody, describeRequest, sendErrorBody } from './error-body';
import { resolveError } from './resolve-error';

const FIRST_SERVER_ERROR_STATUS: number = HttpStatus.INTERNAL_SERVER_ERROR;
const STACK_FRAME_PATTERN = /^\s+at\s+(.+)$/;
const DEPENDENCY_PATH_SEGMENT = 'node_modules';
const UNKNOWN_CALL_SITE = 'unknown call site';

/**
 * Stack frames of an error, taken from the end of the stack. The stack starts with the error's
 * message, so reading only the unbroken run of frames at its end keeps message text out even when
 * a line of it happens to look like a frame.
 */
function trailingFrames(stack: string): string[] {
  const lines = stack.split('\n');
  const frames: string[] = [];
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const frame = STACK_FRAME_PATTERN.exec(lines[index])?.[1];
    if (frame === undefined) {
      break;
    }
    frames.unshift(frame);
  }
  return frames;
}

/**
 * First stack frame that belongs to the application.
 *
 * A Prisma validation error carries the offending arguments in its message, and the stack starts
 * with that message, so the stack as a whole is not safe to log. The frames alone are.
 */
function callSiteOf(error: Error): string {
  const frames = trailingFrames(error.stack ?? '');
  return (
    frames.find((frame) => !frame.includes(DEPENDENCY_PATH_SEGMENT)) ??
    frames[0] ??
    UNKNOWN_CALL_SITE
  );
}

/**
 * Last line of defence: turns anything thrown while handling a request into the shared error
 * body.
 *
 * A thrown `HttpException` keeps its own status and message, because the code that threw it chose
 * both for the client. Express middleware rejections such as an oversized body keep their 4xx
 * status under a fixed message. A failing database answers 503. Anything else is an unexpected
 * failure, so the client gets a fixed message and the cause goes to the log only.
 *
 * Every 5xx is logged exactly once: unexpected errors at `error` with their stack, failures that
 * are expected to recur (database down, circuit open, a probe reporting unhealthy) at `warn` on a
 * single line.
 *
 * Nest tries global filters from the last registered to the first. Register this catch-all
 * first, so that the more specific filters registered after it get the first chance.
 */
@Catch()
export class HttpExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(HttpExceptionFilter.name);

  catch(exception: unknown, host: ArgumentsHost): void {
    const http = host.switchToHttp();
    const request = http.getRequest<Request>();
    const { status, message, errors } = resolveError(exception, request);
    if (status >= FIRST_SERVER_ERROR_STATUS) {
      this.logServerError(exception, request, status);
    }
    sendErrorBody(
      http.getResponse<Response>(),
      buildErrorBody({ status, message, request, errors }),
    );
  }

  private logServerError(exception: unknown, request: Request, status: number): void {
    const summary = `${describeRequest(request)} failed with ${status}`;
    if (
      exception instanceof CircuitOpenError ||
      exception instanceof Prisma.PrismaClientInitializationError
    ) {
      this.logger.warn(`${summary}: ${exception.name}`);
      return;
    }
    if (exception instanceof Prisma.PrismaClientValidationError) {
      this.logger.error(`${summary}: ${exception.name} raised at ${callSiteOf(exception)}`);
      return;
    }
    if (exception instanceof HttpException) {
      this.logHttpException(exception, summary);
      return;
    }
    // `{ err }` rather than a stack string: nestjs-pino keeps a second argument only when it
    // looks like a stack, so anything else would vanish from the log.
    this.logger.error(
      { err: exception instanceof Error ? exception : inspect(exception) },
      summary,
    );
  }

  private logHttpException(exception: HttpException, summary: string): void {
    if (exception.cause === undefined) {
      this.logger.warn(summary);
      return;
    }
    this.logger.error({ err: exception.cause }, summary);
  }
}
