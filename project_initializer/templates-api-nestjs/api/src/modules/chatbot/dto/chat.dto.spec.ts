/**
 * Validates src/modules/chatbot/dto/chat.dto.ts.
 */
import { MAX_REQUEST_BODY_BYTES } from '../../../config/http-limits';
import {
  MAX_CHAT_HISTORY_MESSAGE_LENGTH,
  MAX_CHAT_HISTORY_MESSAGES,
  MAX_CHAT_QUESTION_LENGTH,
} from '../chat.constants';
import {
  ChatJobAcceptedSchema,
  ChatJobDataSchema,
  ChatRequestSchema,
  StreamErrorSchema,
} from './chat.dto';

const JOB_ID = '5b0c5f52-3c0b-4d5e-9f6b-0f6c1f6d2a11';

function historyOf(count: number, messageLength = 1) {
  return { messages: Array.from({ length: count }, () => 'm'.repeat(messageLength)) };
}

describe('ChatRequestSchema', () => {
  it('when every bound is at its maximum, then the JSON body still fits the request body limit', () => {
    const body = JSON.stringify({
      user_question: 'q'.repeat(MAX_CHAT_QUESTION_LENGTH),
      conversation_history: historyOf(MAX_CHAT_HISTORY_MESSAGES, MAX_CHAT_HISTORY_MESSAGE_LENGTH),
    });

    expect(Buffer.byteLength(body)).toBeLessThan(MAX_REQUEST_BODY_BYTES);
  });

  it('when the question is trimmed to something, then it is accepted without its padding', () => {
    expect(ChatRequestSchema.parse({ user_question: '  hello  ' }).user_question).toBe('hello');
  });

  it('when the question is blank, then it is rejected', () => {
    expect(ChatRequestSchema.safeParse({ user_question: '   ' }).success).toBe(false);
  });

  it('when the question has the maximum length, then it is accepted', () => {
    const question = 'q'.repeat(MAX_CHAT_QUESTION_LENGTH);

    expect(ChatRequestSchema.safeParse({ user_question: question }).success).toBe(true);
  });

  it('when the question is one character too long, then it is rejected', () => {
    const question = 'q'.repeat(MAX_CHAT_QUESTION_LENGTH + 1);

    expect(ChatRequestSchema.safeParse({ user_question: question }).success).toBe(false);
  });

  it('when the history has the maximum number of messages, then it is accepted', () => {
    const body = {
      user_question: 'hi',
      conversation_history: historyOf(MAX_CHAT_HISTORY_MESSAGES),
    };

    expect(ChatRequestSchema.safeParse(body).success).toBe(true);
  });

  it('when the history has one message too many, then it is rejected', () => {
    const body = {
      user_question: 'hi',
      conversation_history: historyOf(MAX_CHAT_HISTORY_MESSAGES + 1),
    };

    expect(ChatRequestSchema.safeParse(body).success).toBe(false);
  });

  it('when a history message has the maximum length, then it is accepted', () => {
    const body = {
      user_question: 'hi',
      conversation_history: historyOf(1, MAX_CHAT_HISTORY_MESSAGE_LENGTH),
    };

    expect(ChatRequestSchema.safeParse(body).success).toBe(true);
  });

  it('when a history message is one character too long, then it is rejected', () => {
    const body = {
      user_question: 'hi',
      conversation_history: historyOf(1, MAX_CHAT_HISTORY_MESSAGE_LENGTH + 1),
    };

    expect(ChatRequestSchema.safeParse(body).success).toBe(false);
  });

  it('when the history is omitted, then the request is still valid', () => {
    expect(ChatRequestSchema.safeParse({ user_question: 'hi' }).success).toBe(true);
  });
});

describe('ChatJobAcceptedSchema', () => {
  it('when the job id is not a UUID, then it is rejected', () => {
    expect(ChatJobAcceptedSchema.safeParse({ jobId: '1' }).success).toBe(false);
  });

  it('when the job id is a UUID, then it is accepted', () => {
    expect(ChatJobAcceptedSchema.safeParse({ jobId: JOB_ID }).success).toBe(true);
  });
});

describe('ChatJobDataSchema', () => {
  it('when the owner is null, then the data is valid for an anonymous caller', () => {
    const data = { request: { user_question: 'hi' }, ownerId: null };

    expect(ChatJobDataSchema.safeParse(data).success).toBe(true);
  });

  it('when the owner key is missing, then the data is rejected', () => {
    expect(ChatJobDataSchema.safeParse({ request: { user_question: 'hi' } }).success).toBe(false);
  });
});

describe('StreamErrorSchema', () => {
  it('when the event is not terminal, then it is rejected', () => {
    expect(StreamErrorSchema.safeParse({ error: 'x', done: false }).success).toBe(false);
  });

  it('when the event is terminal, then it is accepted', () => {
    expect(StreamErrorSchema.safeParse({ error: 'x', done: true }).success).toBe(true);
  });
});
