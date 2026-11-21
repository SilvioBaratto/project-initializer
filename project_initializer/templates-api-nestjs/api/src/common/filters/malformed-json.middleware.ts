import { BadRequestException } from '@nestjs/common';
import type { NextFunction, Request, Response } from 'express';

/** Message of the 400 answer for a request body that is not valid JSON. */
export const MALFORMED_JSON_MESSAGE = 'Malformed JSON request body';

const JSON_PARSE_FAILURE_TYPE = 'entity.parse.failed';

function isJsonParseFailure(error: unknown): boolean {
  return error instanceof SyntaxError && 'type' in error && error.type === JSON_PARSE_FAILURE_TYPE;
}

/**
 * Express error middleware that replaces the JSON body parser's failure with a fixed message.
 *
 * Nest turns every `SyntaxError` coming out of the middleware chain into a `BadRequestException`
 * carrying the parser's own text, which quotes the input ("Unexpected token ... in JSON at
 * position 17"). Register it directly after the body parser, so that Nest sees this exception
 * instead.
 *
 * @param error - whatever an earlier middleware passed on.
 * @param _request - unused; Express recognises error middleware by its four parameters.
 * @param _response - unused, as above.
 * @param next - continues with the replacement for a JSON parse failure and with the original
 *   error for anything else.
 */
export function rejectMalformedJson(
  error: unknown,
  _request: Request,
  _response: Response,
  next: NextFunction,
): void {
  next(isJsonParseFailure(error) ? new BadRequestException(MALFORMED_JSON_MESSAGE) : error);
}
