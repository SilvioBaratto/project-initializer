import { HttpStatus } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import basicAuth from 'express-basic-auth';
import type { RequestHandler } from 'express';
import { buildErrorBody, sendErrorBody } from '../../common/filters/error-body';
import type { BaseEnv } from '../../config/env.base';

/** Message of the 404 a closed dashboard answers with. */
const DASHBOARD_CLOSED_MESSAGE = 'Not Found';

/** HTTP basic-auth credentials that unlock the queue dashboard. */
export interface QueueDashboardCredentials {
  readonly user: string;
  readonly password: string;
}

/**
 * Reads the dashboard credentials from validated configuration.
 *
 * @returns The credentials, or `undefined` when `QUEUE_MONITOR_PASSWORD` is not set, which
 *   leaves the dashboard closed.
 */
export function queueDashboardCredentials(
  config: ConfigService<BaseEnv, true>,
): QueueDashboardCredentials | undefined {
  const password = config.get('QUEUE_MONITOR_PASSWORD', { infer: true });
  if (!password) {
    return undefined;
  }
  return { user: config.get('QUEUE_MONITOR_USER', { infer: true }), password };
}

/**
 * Builds the middleware that gates the queue dashboard.
 *
 * Without credentials it answers every request with the shared 404 error body, as if the dashboard
 * did not exist: the dashboard shows job payloads, which are user conversations, and allows
 * retrying or removing jobs, so it must never be reachable by default. With credentials it demands
 * HTTP basic auth.
 */
export function createQueueDashboardMiddleware(
  credentials?: QueueDashboardCredentials,
): RequestHandler {
  if (!credentials) {
    return (request, response) => {
      sendErrorBody(
        response,
        buildErrorBody({
          status: HttpStatus.NOT_FOUND,
          message: DASHBOARD_CLOSED_MESSAGE,
          request,
        }),
      );
    };
  }
  return basicAuth({ users: { [credentials.user]: credentials.password }, challenge: true });
}
