/**
 * Validates src/modules/chatbot/chat-failure.ts.
 */
import { ServiceUnavailableException } from '@nestjs/common';
import { describeChatFailure } from './chat-failure';

describe('describeChatFailure', () => {
  it('when the error wraps a cause, then the stack of the cause is described', () => {
    const cause = new Error('provider rejected the key');

    const description = describeChatFailure(new ServiceUnavailableException('down', { cause }));

    expect(description).toBe(cause.stack);
  });

  it('when the error has no cause, then its own stack is described', () => {
    const error = new Error('socket exploded');

    expect(describeChatFailure(error)).toBe(error.stack);
  });

  it('when the cause is not an Error, then it is described as text', () => {
    const error = new ServiceUnavailableException('down', { cause: 'plain cause' });

    expect(describeChatFailure(error)).toBe('plain cause');
  });

  it('when the failure is not an Error, then it is described as text', () => {
    expect(describeChatFailure('plain failure')).toBe('plain failure');
  });
});
