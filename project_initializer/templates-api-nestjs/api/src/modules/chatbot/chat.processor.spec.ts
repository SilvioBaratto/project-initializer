import { Test, TestingModule } from '@nestjs/testing';
import { Logger } from '@nestjs/common';
import { ChatProcessor } from './chat.processor';
import { Job } from 'bullmq';

// Variables prefixed with 'mock' are hoisted alongside jest.mock() by Jest's transform.
const mockBChat = jest.fn();

jest.mock('../../../baml_client', () => ({
  b: {
    Chat: (...args: unknown[]) => mockBChat(...args),
  },
}));

function makeJob(data: Record<string, unknown>, id = 'job-1'): Job {
  return { data, id } as unknown as Job;
}

describe('ChatProcessor', () => {
  let processor: ChatProcessor;

  beforeEach(async () => {
    jest.clearAllMocks();

    const module: TestingModule = await Test.createTestingModule({
      providers: [ChatProcessor],
    }).compile();

    processor = module.get<ChatProcessor>(ChatProcessor);
  });

  describe('process()', () => {
    it('when b.Chat resolves, returns { answer } from BAML', async () => {
      mockBChat.mockResolvedValue({ answer: 'Hello from BAML' });

      const result = await processor.process(
        makeJob({ user_question: 'Hi', conversation_history: undefined }),
      );

      expect(result).toEqual({ answer: 'Hello from BAML' });
    });

    it('when b.Chat rejects, process() propagates the error so BullMQ marks the job failed', async () => {
      mockBChat.mockRejectedValue(new Error('BAML unavailable'));

      await expect(
        processor.process(makeJob({ user_question: 'Hi', conversation_history: undefined })),
      ).rejects.toThrow('BAML unavailable');
    });

    it('when conversation_history is provided, passes it to b.Chat', async () => {
      const history = { messages: ['hello'] };
      mockBChat.mockResolvedValue({ answer: 'ok' });

      await processor.process(
        makeJob({ user_question: 'follow-up', conversation_history: history }),
      );

      expect(mockBChat).toHaveBeenCalledWith('follow-up', history);
    });
  });

  describe('onFailed()', () => {
    it('when a job fails, logs the error via Logger.error', () => {
      const loggerSpy = jest.spyOn(Logger.prototype, 'error').mockImplementation(() => undefined);
      const error = new Error('transient LLM failure');

      processor.onFailed(makeJob({ user_question: 'Hi' }), error);

      expect(loggerSpy).toHaveBeenCalledWith(
        expect.stringContaining('job-1'),
        error.stack,
      );
    });

    it('when job is undefined (BullMQ may pass undefined on certain failures), logs without throwing', () => {
      const loggerSpy = jest.spyOn(Logger.prototype, 'error').mockImplementation(() => undefined);
      const error = new Error('unknown failure');

      expect(() => processor.onFailed(undefined, error)).not.toThrow();
      expect(loggerSpy).toHaveBeenCalled();
    });
  });
});
