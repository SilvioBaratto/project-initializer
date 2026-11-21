/** Validates src/common/filters/malformed-json.middleware.ts. */
import { BadRequestException } from '@nestjs/common';
import type { Request, Response } from 'express';
import { MALFORMED_JSON_MESSAGE, rejectMalformedJson } from './malformed-json.middleware';

describe('rejectMalformedJson', () => {
  const request = {} as Request;
  const response = {} as Response;

  it('when the JSON parser failed, then the next handler gets a 400 with the fixed message', () => {
    const next = jest.fn();
    const parserFailure = Object.assign(
      new SyntaxError('Unexpected token } in JSON at position 17'),
      {
        type: 'entity.parse.failed',
        statusCode: 400,
      },
    );

    rejectMalformedJson(parserFailure, request, response, next);

    expect(next).toHaveBeenCalledTimes(1);
    const [replacement] = next.mock.calls[0] as [BadRequestException];
    expect(replacement).toBeInstanceOf(BadRequestException);
    expect(replacement.message).toBe(MALFORMED_JSON_MESSAGE);
  });

  it.each([
    ['a syntax error from somewhere else', new SyntaxError('bad regex')],
    [
      'a body-parser size error',
      Object.assign(new Error('too large'), { type: 'entity.too.large' }),
    ],
    ['a non-error value', 'plain'],
  ])('when the failure is %s, then it is passed on unchanged', (_label, failure) => {
    const next = jest.fn();

    rejectMalformedJson(failure, request, response, next);

    expect(next).toHaveBeenCalledWith(failure);
  });
});
