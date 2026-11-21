/**
 * Validates src/modules/chatbot/baml-chat-completion.adapter.ts.
 */
import { setLogLevel } from '@boundaryml/baml/logging';
import { b } from '../../../baml_client';
import { BamlChatCompletionAdapter } from './baml-chat-completion.adapter';

// The adapter is the one place that talks to the vendor client, so this is the one spec that
// replaces it by module path.
jest.mock('../../../baml_client', () => ({
  b: { Chat: jest.fn(), stream: { Chat: jest.fn() } },
}));
jest.mock('@boundaryml/baml/logging', () => ({ setLogLevel: jest.fn() }));

// The adapter switches the log level when its module loads, before any test runs.
const logLevelCallsAtLoad = jest.mocked(setLogLevel).mock.calls.slice();

type PartialAnswer = { answer?: string | null };
type BamlStreamStub = ReturnType<typeof b.stream.Chat>;

function streamOf(...partials: PartialAnswer[]): BamlStreamStub {
  async function* emit() {
    await Promise.resolve();
    yield* partials;
  }
  // The adapter only iterates the stream, so a bare async generator stands in for BamlStream.
  return emit() as unknown as BamlStreamStub;
}

async function collect(answers: AsyncIterable<string>): Promise<string[]> {
  const collected: string[] = [];
  for await (const answer of answers) {
    collected.push(answer);
  }
  return collected;
}

describe('BamlChatCompletionAdapter', () => {
  it('when the module loads, then BAML logging is switched off so prompts never reach stdout', () => {
    expect(logLevelCallsAtLoad).toEqual([['OFF']]);
  });

  const adapter = new BamlChatCompletionAdapter();
  const chatMock = jest.mocked(b.Chat);
  const streamChatMock = jest.mocked(b.stream.Chat);

  beforeEach(() => {
    jest.resetAllMocks();
  });

  describe('complete()', () => {
    it('when the model answers, then it returns the answer text', async () => {
      chatMock.mockResolvedValue({ answer: 'Hello from BAML' });

      await expect(adapter.complete({ question: 'Hi', history: [] })).resolves.toBe(
        'Hello from BAML',
      );
    });

    it('when history is given, then it is passed as a messages object', async () => {
      chatMock.mockResolvedValue({ answer: 'ok' });

      await adapter.complete({ question: 'Next', history: ['one', 'two'] });

      expect(chatMock).toHaveBeenCalledWith('Next', { messages: ['one', 'two'] });
    });

    it('when history is empty, then no history argument is passed', async () => {
      chatMock.mockResolvedValue({ answer: 'ok' });

      await adapter.complete({ question: 'First', history: [] });

      expect(chatMock).toHaveBeenCalledWith('First', undefined);
    });

    it('when the client rejects, then the error propagates', async () => {
      chatMock.mockRejectedValue(new Error('BAML unavailable'));

      await expect(adapter.complete({ question: 'Hi', history: [] })).rejects.toThrow(
        'BAML unavailable',
      );
    });
  });

  describe('streamAnswer()', () => {
    it('when the stream emits partial answers, then each non-empty one is yielded as is', async () => {
      streamChatMock.mockReturnValue(
        streamOf({ answer: null }, { answer: 'Hel' }, { answer: '' }, { answer: 'Hello' }, {}),
      );

      await expect(collect(adapter.streamAnswer({ question: 'Hi', history: [] }))).resolves.toEqual(
        ['Hel', 'Hello'],
      );
    });

    it('when history is given, then it is passed as a messages object', async () => {
      streamChatMock.mockReturnValue(streamOf());

      await collect(adapter.streamAnswer({ question: 'Next', history: ['one'] }));

      expect(streamChatMock).toHaveBeenCalledWith(
        'Next',
        { messages: ['one'] },
        { signal: undefined },
      );
    });

    it('when a signal is given, then it is handed to the BAML stream so the call can be aborted', async () => {
      streamChatMock.mockReturnValue(streamOf());
      const abort = new AbortController();

      await collect(adapter.streamAnswer({ question: 'Hi', history: [] }, abort.signal));

      expect(streamChatMock).toHaveBeenCalledWith('Hi', undefined, { signal: abort.signal });
    });

    it('when the stream fails, then the error propagates from the iteration', async () => {
      async function* failing(): AsyncGenerator<PartialAnswer> {
        yield await Promise.resolve({ answer: 'partial' });
        throw new Error('stream broke');
      }
      streamChatMock.mockReturnValue(failing() as unknown as BamlStreamStub);

      await expect(collect(adapter.streamAnswer({ question: 'Hi', history: [] }))).rejects.toThrow(
        'stream broke',
      );
    });
  });
});
