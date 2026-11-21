/**
 * Validates src/modules/chatbot/chat.processor.ts.
 */
import { Logger, ServiceUnavailableException } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { Job, UnrecoverableError } from 'bullmq';
import { ChatProcessor } from './chat.processor';
import { ChatbotService } from './chatbot.service';
import type { ChatJobData, ChatResponseDto } from './dto/chat.dto';
import { QueueErrorReporter } from './queue-error-reporter';

type ChatJob = Job<ChatJobData, ChatResponseDto>;

const REQUEST = {
  user_question: 'follow-up',
  conversation_history: { messages: ['hello'] },
};

// The processor reads only id, data and attemptsMade, and a real Job needs a live queue.
function makeJob(data: unknown, id = 'job-1', attemptsMade = 3): ChatJob {
  return { id, data, attemptsMade } as unknown as ChatJob;
}

describe('ChatProcessor', () => {
  let processor: ChatProcessor;
  const chatbotService = { chat: jest.fn() };
  const queueErrors = { report: jest.fn() };
  let warnLog: jest.SpyInstance;
  let errorLog: jest.SpyInstance;

  beforeEach(async () => {
    jest.resetAllMocks();
    warnLog = jest.spyOn(Logger.prototype, 'warn').mockImplementation(() => undefined);
    errorLog = jest.spyOn(Logger.prototype, 'error').mockImplementation(() => undefined);
    const moduleRef = await Test.createTestingModule({
      providers: [
        ChatProcessor,
        { provide: ChatbotService, useValue: chatbotService },
        { provide: QueueErrorReporter, useValue: queueErrors },
      ],
    }).compile();
    processor = moduleRef.get(ChatProcessor);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('process()', () => {
    it('when the service answers, then the answer is the job result', async () => {
      chatbotService.chat.mockResolvedValue({ answer: 'Hello from BAML' });

      await expect(
        processor.process(makeJob({ request: REQUEST, ownerId: null })),
      ).resolves.toEqual({
        answer: 'Hello from BAML',
      });
    });

    it('when a request with history is queued, then the service receives it unchanged', async () => {
      chatbotService.chat.mockResolvedValue({ answer: 'ok' });

      await processor.process(makeJob({ request: REQUEST, ownerId: 'user-a' }));

      expect(chatbotService.chat).toHaveBeenCalledWith(REQUEST);
    });

    it('when the service fails, then process() rejects so BullMQ retries the job', async () => {
      chatbotService.chat.mockRejectedValue(new ServiceUnavailableException('down'));

      await expect(processor.process(makeJob({ request: REQUEST, ownerId: null }))).rejects.toThrow(
        ServiceUnavailableException,
      );
    });

    it('when the job data has no request, then process() rejects without a retry and without calling the service', async () => {
      await expect(processor.process(makeJob({ ownerId: null }))).rejects.toThrow(
        UnrecoverableError,
      );

      expect(chatbotService.chat).not.toHaveBeenCalled();
    });

    it('when the job data is malformed, then the error names the invalid field', async () => {
      const data = { request: { user_question: 42 }, ownerId: null };

      const failure = await processor.process(makeJob(data)).catch((error: unknown) => error);

      expect(failure).toBeInstanceOf(UnrecoverableError);
      expect((failure as Error).message).toContain('user_question');
    });
  });

  describe('onFailed()', () => {
    it('when the assistant failed, then it logs one record naming the job and attempt, with the cause stack', () => {
      const cause = new Error('provider rejected the key');

      processor.onFailed(makeJob({}), new ServiceUnavailableException('down', { cause }));

      expect(errorLog).toHaveBeenCalledTimes(1);
      expect(errorLog).toHaveBeenCalledWith('Chat job job-1 (attempt 3) failed', cause.stack);
      expect(warnLog).not.toHaveBeenCalled();
    });

    it('when the failure has no cause, then its own stack is logged', () => {
      const error = new UnrecoverableError('malformed job');

      processor.onFailed(makeJob({}), error);

      expect(errorLog).toHaveBeenCalledTimes(1);
      expect(errorLog).toHaveBeenCalledWith(expect.stringContaining('job-1'), error.stack);
    });

    it('when BullMQ passes no job, then the log line has no placeholder for it', () => {
      processor.onFailed(undefined, new Error('unknown failure'));

      expect(errorLog).toHaveBeenCalledTimes(1);
      expect(errorLog).toHaveBeenCalledWith('Chat job failed', expect.any(String));
    });
  });

  describe('onWorkerError()', () => {
    it('when the worker emits an error, then it goes to the queue error reporter as a worker error', () => {
      const error = new Error('connection lost');

      processor.onWorkerError(error);

      expect(queueErrors.report).toHaveBeenCalledWith('worker', error);
    });
  });
});
