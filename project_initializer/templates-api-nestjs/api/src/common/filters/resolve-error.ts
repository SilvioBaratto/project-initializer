import { STATUS_CODES } from 'node:http';
import { HttpException, HttpStatus, NotFoundException } from '@nestjs/common';
import { Prisma } from '@generated/prisma';
import type { Request } from 'express';
import { ZodValidationException } from 'nestjs-zod';
import { z } from 'zod';
import { CircuitOpenError } from '../resilience/circuit-breaker';
import {
  FieldError,
  INTERNAL_ERROR_MESSAGE,
  ROUTE_NOT_FOUND_MESSAGE,
  SERVICE_UNAVAILABLE_MESSAGE,
} from './error-body';

/** What a client is told about a failure: status, a message safe to show, optional field detail. */
export interface ResolvedError {
  status: number;
  message: string;
  errors?: readonly FieldError[];
}

type ErrorResolver = (exception: unknown, request: Request) => ResolvedError | undefined;

const FIELD_PATH_SEPARATOR = '.';
const FIRST_CLIENT_ERROR_STATUS = 400;
const FIRST_SERVER_ERROR_STATUS = 500;
const UNKNOWN_CLIENT_ERROR_MESSAGE = 'Bad Request';

function toFieldErrors(zodError: unknown): readonly FieldError[] | undefined {
  if (!(zodError instanceof z.core.$ZodError)) {
    return undefined;
  }
  return zodError.issues.map((issue) => ({
    path: issue.path.map((segment) => String(segment)).join(FIELD_PATH_SEPARATOR),
    message: issue.message,
  }));
}

/** Nest's router answers an unknown path with a 404 whose text is `Cannot <method> <full url>`. */
function isRouterNotFound(exception: HttpException, request: Request): boolean {
  return (
    exception instanceof NotFoundException &&
    exception.message === `Cannot ${request.method} ${request.originalUrl}`
  );
}

/**
 * Status of an error that Express middleware raised about the request itself, such as body-parser
 * rejecting an oversized, malformed or wrongly typed body.
 *
 * `http-errors` marks such an error `expose` when its status is a client error, meaning the text
 * is meant for the client. That text still is not sent: it can quote the offending input.
 */
function exposedClientErrorStatus(exception: unknown): number | undefined {
  if (typeof exception !== 'object' || exception === null) {
    return undefined;
  }
  if (!('expose' in exception) || exception.expose !== true) {
    return undefined;
  }
  if (!('statusCode' in exception) || typeof exception.statusCode !== 'number') {
    return undefined;
  }
  const { statusCode } = exception;
  return statusCode >= FIRST_CLIENT_ERROR_STATUS && statusCode < FIRST_SERVER_ERROR_STATUS
    ? statusCode
    : undefined;
}

const resolveValidationFailure: ErrorResolver = (exception) => {
  if (!(exception instanceof ZodValidationException)) {
    return undefined;
  }
  return {
    status: exception.getStatus(),
    message: exception.message,
    errors: toFieldErrors(exception.getZodError()),
  };
};

// A thrown HttpException keeps its status and message: the code that threw it chose both for the
// client.
const resolveHttpException: ErrorResolver = (exception, request) => {
  if (!(exception instanceof HttpException)) {
    return undefined;
  }
  const message = isRouterNotFound(exception, request)
    ? ROUTE_NOT_FOUND_MESSAGE
    : exception.message;
  return { status: exception.getStatus(), message };
};

const resolveUnavailableDependency: ErrorResolver = (exception) => {
  const unavailable =
    exception instanceof CircuitOpenError ||
    exception instanceof Prisma.PrismaClientInitializationError;
  return unavailable
    ? { status: HttpStatus.SERVICE_UNAVAILABLE, message: SERVICE_UNAVAILABLE_MESSAGE }
    : undefined;
};

const resolveRejectedRequest: ErrorResolver = (exception) => {
  const status = exposedClientErrorStatus(exception);
  if (status === undefined) {
    return undefined;
  }
  return { status, message: STATUS_CODES[status] ?? UNKNOWN_CLIENT_ERROR_MESSAGE };
};

const RESOLVERS: readonly ErrorResolver[] = [
  resolveValidationFailure,
  resolveHttpException,
  resolveUnavailableDependency,
  resolveRejectedRequest,
];

/**
 * Decides what the client is told about anything thrown while handling a request.
 *
 * Anything that is not recognised is an unexpected failure and gets a fixed 500 message, so the
 * cause stays in the server log only.
 *
 * @param exception - The thrown value.
 * @param request - The failed request; needed to recognise the router's own 404.
 * @returns The status, a client-safe message and, for validation failures, the failing fields.
 */
export function resolveError(exception: unknown, request: Request): ResolvedError {
  for (const resolver of RESOLVERS) {
    const resolved = resolver(exception, request);
    if (resolved !== undefined) {
      return resolved;
    }
  }
  return { status: HttpStatus.INTERNAL_SERVER_ERROR, message: INTERNAL_ERROR_MESSAGE };
}
