import {
  ArgumentsHost,
  Catch,
  ExceptionFilter,
  Logger,
  ServiceUnavailableException,
} from '@nestjs/common';
import type { Request, Response } from 'express';
import { describeRequest } from '../../common/filters/error-body';

const NO_FAILING_INDICATOR = 'none';

function failingIndicatorsOf(responseBody: string | object): string {
  if (typeof responseBody === 'string' || !('error' in responseBody)) {
    return NO_FAILING_INDICATOR;
  }
  const { error } = responseBody;
  if (typeof error !== 'object' || error === null) {
    return NO_FAILING_INDICATOR;
  }
  return Object.keys(error).join(', ') || NO_FAILING_INDICATOR;
}

/**
 * Answers a failed health probe with the Terminus result itself.
 *
 * Terminus signals an unhealthy probe by throwing a 503 `ServiceUnavailableException` whose
 * response object lists every indicator and its details, including the circuit breaker state. The
 * app-wide error filter would reduce that to the exception's generic message, and an operator
 * reading the probe would lose which dependency is down. Apply it to the health controller only.
 *
 * Terminus' own logging is switched off in `HealthModule`, so this filter writes the one log line
 * a failed probe produces, at `warn` because an orchestrator polls the probe for as long as the
 * dependency stays down.
 */
@Catch(ServiceUnavailableException)
export class HealthCheckExceptionFilter implements ExceptionFilter<ServiceUnavailableException> {
  private readonly logger = new Logger(HealthCheckExceptionFilter.name);

  catch(exception: ServiceUnavailableException, host: ArgumentsHost): void {
    const http = host.switchToHttp();
    const request = http.getRequest<Request>();
    const responseBody = exception.getResponse();
    this.logger.warn(
      `${describeRequest(request)} reported unhealthy: ${failingIndicatorsOf(responseBody)}`,
    );
    http.getResponse<Response>().status(exception.getStatus()).json(responseBody);
  }
}
