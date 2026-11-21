import {
  EchoParamSchema,
  EchoRequestSchema,
  MAX_ECHO_MESSAGE_LENGTH,
  PING_MESSAGE,
  PingResponseSchema,
} from './echo.dto';

/** Validates src/modules/test/dto/echo.dto.ts. */
describe.each([
  ['EchoRequestSchema', EchoRequestSchema],
  ['EchoParamSchema', EchoParamSchema],
])('%s', (_name, schema) => {
  it('when the message is exactly the maximum length, then it is accepted', () => {
    const message = 'm'.repeat(MAX_ECHO_MESSAGE_LENGTH);

    expect(schema.safeParse({ message }).success).toBe(true);
  });

  it('when the message is one character over the maximum, then it is rejected', () => {
    const message = 'm'.repeat(MAX_ECHO_MESSAGE_LENGTH + 1);

    expect(schema.safeParse({ message }).success).toBe(false);
  });

  it('when the message is empty, then it is rejected', () => {
    expect(schema.safeParse({ message: '' }).success).toBe(false);
  });
});

describe('PingResponseSchema', () => {
  it('when the message is the ping reply, then it is accepted', () => {
    expect(PingResponseSchema.safeParse({ message: PING_MESSAGE }).success).toBe(true);
  });

  it('when the message is anything else, then it is rejected', () => {
    expect(PingResponseSchema.safeParse({ message: 'pang' }).success).toBe(false);
  });
});
