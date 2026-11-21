/**
 * Validates src/modules/chatbot/chatbot.module.ts.
 */
import 'reflect-metadata';
import { BamlChatCompletionAdapter } from './baml-chat-completion.adapter';
import { CHAT_COMPLETION_PORT } from './chat-completion.port';
import {
  CHAT_JOB_BACKOFF_DELAY_MS,
  COMPLETED_CHAT_JOB_TTL_SECONDS,
  COMPLETED_CHAT_JOBS_KEPT,
  FAILED_CHAT_JOB_TTL_SECONDS,
} from './chat.constants';
import { CHAT_JOB_OPTIONS, ChatbotModule } from './chatbot.module';

describe('CHAT_JOB_OPTIONS', () => {
  it('when a job fails, then it is retried with exponential backoff', () => {
    expect(CHAT_JOB_OPTIONS.attempts).toBeGreaterThan(1);
    expect(CHAT_JOB_OPTIONS.backoff).toEqual({
      type: 'exponential',
      delay: CHAT_JOB_BACKOFF_DELAY_MS,
    });
  });

  it('when a job completes, then it stays readable for a bounded window', () => {
    expect(CHAT_JOB_OPTIONS.removeOnComplete).toEqual({
      age: COMPLETED_CHAT_JOB_TTL_SECONDS,
      count: COMPLETED_CHAT_JOBS_KEPT,
    });
  });

  it('when a job fails for good, then it is kept for a bounded window', () => {
    expect(CHAT_JOB_OPTIONS.removeOnFail).toEqual({ age: FAILED_CHAT_JOB_TTL_SECONDS });
  });
});

describe('ChatbotModule', () => {
  it('when the module is inspected, then the completion port is bound to the BAML adapter', () => {
    const providers = Reflect.getMetadata('providers', ChatbotModule) as unknown[];

    expect(providers).toContainEqual({
      provide: CHAT_COMPLETION_PORT,
      useClass: BamlChatCompletionAdapter,
    });
  });
});
