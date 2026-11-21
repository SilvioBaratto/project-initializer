/**
 * Validates src/modules/chatbot/chatbot.service.ts.
 */
import { HttpStatus, Logger, ServiceUnavailableException } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { CHAT_UNAVAILABLE_MESSAGE } from './chat.constants';
import { CHAT_COMPLETION_PORT, ChatCompletionPort, ChatPrompt } from './chat-completion.port';
import { ChatbotService } from './chatbot.service';
import { StreamChunkDto } from './dto/chat.dto';

const PROVIDER_SECRET = 'provider said: key sk-secret rejected';

class StubChatCompletion implements ChatCompletionPort {
  readonly prompts: ChatPrompt[] = [];
  readonly signals: Array<AbortSignal | undefined> = [];
  answers: string[] = ['Hello'];
  /** Thrown by `complete`, and by `streamAnswer` once every answer has been yielded. */
  private failure?: { readonly reason: unknown };

  failWith(reason: unknown): void {
    this.failure = { reason };
  }

  async complete(prompt: ChatPrompt): Promise<string> {
    this.prompts.push(prompt);
    await Promise.resolve();
    if (this.failure !== undefined) {
      throw this.failure.reason;
    }
    return this.answers.join('');
  }

  async *streamAnswer(prompt: ChatPrompt, signal?: AbortSignal): AsyncGenerator<string> {
    this.prompts.push(prompt);
    this.signals.push(signal);
    for (const answer of this.answers) {
      yield await Promise.resolve(answer);
    }
    if (this.failure !== undefined) {
      throw this.failure.reason;
    }
  }
}

function rejectionOf(promise: Promise<unknown>): Promise<unknown> {
  return promise.then(
    () => undefined,
    (error: unknown) => error,
  );
}

async function collect(chunks: AsyncIterable<StreamChunkDto>): Promise<StreamChunkDto[]> {
  const collected: StreamChunkDto[] = [];
  for await (const chunk of chunks) {
    collected.push(chunk);
  }
  return collected;
}

describe('ChatbotService', () => {
  let service: ChatbotService;
  let completion: StubChatCompletion;
  let errorLog: jest.SpyInstance;

  beforeEach(async () => {
    completion = new StubChatCompletion();
    errorLog = jest.spyOn(Logger.prototype, 'error').mockImplementation(() => undefined);
    const moduleRef = await Test.createTestingModule({
      providers: [ChatbotService, { provide: CHAT_COMPLETION_PORT, useValue: completion }],
    }).compile();
    service = moduleRef.get(ChatbotService);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('chat()', () => {
    it('when the port answers, then it returns the answer', async () => {
      completion.answers = ['Hello from the model'];

      await expect(service.chat({ user_question: 'Hi' })).resolves.toEqual({
        answer: 'Hello from the model',
      });
    });

    it('when a history is given, then the prompt carries question and history', async () => {
      await service.chat({
        user_question: 'Next',
        conversation_history: { messages: ['one', 'two'] },
      });

      expect(completion.prompts).toEqual([{ question: 'Next', history: ['one', 'two'] }]);
    });

    it('when no history is given, then the prompt history is empty', async () => {
      await service.chat({ user_question: 'First' });

      expect(completion.prompts).toEqual([{ question: 'First', history: [] }]);
    });

    it('when the port fails, then it throws a generic 503 that exposes no cause in its message', async () => {
      completion.failWith(new Error(PROVIDER_SECRET));

      const failure = await rejectionOf(service.chat({ user_question: 'Hi' }));

      expect(failure).toBeInstanceOf(ServiceUnavailableException);
      expect(failure).toHaveProperty('message', CHAT_UNAVAILABLE_MESSAGE);
      expect(failure).toHaveProperty('status', HttpStatus.SERVICE_UNAVAILABLE);
    });

    it('when the port fails, then the original error travels as the cause and nothing is logged here', async () => {
      const cause = new Error(PROVIDER_SECRET);
      completion.failWith(cause);

      const failure = await rejectionOf(service.chat({ user_question: 'Hi' }));

      expect(failure).toHaveProperty('cause', cause);
      expect(errorLog).not.toHaveBeenCalled();
    });

    it('when the port rejects with a non-Error value, then it is the cause of the 503', async () => {
      completion.failWith('plain string failure');

      const failure = await rejectionOf(service.chat({ user_question: 'Hi' }));

      expect(failure).toBeInstanceOf(ServiceUnavailableException);
      expect(failure).toHaveProperty('cause', 'plain string failure');
    });
  });

  describe('streamChat()', () => {
    it('when the port streams answers, then each becomes a non-final chunk', async () => {
      completion.answers = ['Hel', 'Hello'];

      await expect(collect(service.streamChat({ user_question: 'Hi' }))).resolves.toEqual([
        { content: 'Hel', done: false },
        { content: 'Hello', done: false },
      ]);
    });

    it('when the port streams nothing, then no chunk is produced', async () => {
      completion.answers = [];

      await expect(collect(service.streamChat({ user_question: 'Hi' }))).resolves.toEqual([]);
    });

    it('when the stream fails midway, then earlier chunks are delivered and a 503 is thrown', async () => {
      completion.answers = ['Hel'];
      completion.failWith(new Error(PROVIDER_SECRET));
      const received: StreamChunkDto[] = [];

      const iteration = (async () => {
        for await (const chunk of service.streamChat({ user_question: 'Hi' })) {
          received.push(chunk);
        }
      })();

      await expect(iteration).rejects.toThrow(ServiceUnavailableException);
      expect(received).toEqual([{ content: 'Hel', done: false }]);
    });

    it('when the stream fails, then the original error travels as the cause and nothing is logged here', async () => {
      const cause = new Error(PROVIDER_SECRET);
      completion.failWith(cause);

      const failure = await rejectionOf(collect(service.streamChat({ user_question: 'Hi' })));

      expect(failure).toBeInstanceOf(ServiceUnavailableException);
      expect(failure).toHaveProperty('cause', cause);
      expect(errorLog).not.toHaveBeenCalled();
    });

    it('when a signal is given, then the port receives the same signal', async () => {
      const abort = new AbortController();

      await collect(service.streamChat({ user_question: 'Hi' }, abort.signal));

      expect(completion.signals).toEqual([abort.signal]);
    });
  });
});
