/**
 * Validates src/modules/chatbot/chat-job.service.ts and the ChatJobStatusSchema it returns.
 */
import { NotFoundException } from '@nestjs/common';
import { getQueueToken } from '@nestjs/bullmq';
import { Test } from '@nestjs/testing';
import { ZodError } from 'zod';
import { CHAT_JOB_NAME, CHAT_JOB_NOT_FOUND_MESSAGE, CHAT_QUEUE_NAME } from './chat.constants';
import { ChatJobService } from './chat-job.service';
import { ChatJobStatusSchema } from './dto/chat.dto';
import { QueueErrorReporter } from './queue-error-reporter';

const JOB_ID = '5b0c5f52-3c0b-4d5e-9f6b-0f6c1f6d2a11';
const OWNER_ID = 'user-a';
const REQUEST = { user_question: 'Hello' };

interface StubJob {
  data: { request: typeof REQUEST; ownerId?: string | null };
  returnvalue: unknown;
  getState: jest.Mock<Promise<string>, []>;
}

function makeJob(state: string, overrides: Partial<StubJob> = {}): StubJob {
  return {
    data: { request: REQUEST, ownerId: OWNER_ID },
    returnvalue: undefined,
    getState: jest.fn<Promise<string>, []>(() => Promise.resolve(state)),
    ...overrides,
  };
}

describe('ChatJobService', () => {
  let service: ChatJobService;
  const queue = { add: jest.fn(), getJob: jest.fn(), on: jest.fn() };
  const queueErrors = { report: jest.fn() };

  beforeEach(async () => {
    jest.resetAllMocks();
    const moduleRef = await Test.createTestingModule({
      providers: [
        ChatJobService,
        { provide: getQueueToken(CHAT_QUEUE_NAME), useValue: queue },
        { provide: QueueErrorReporter, useValue: queueErrors },
      ],
    }).compile();
    service = moduleRef.get(ChatJobService);
  });

  describe('onModuleInit()', () => {
    it('when the queue emits an error, then it is reported as a producer error', () => {
      service.onModuleInit();
      const [event, listener] = queue.on.mock.calls[0] as [string, (error: Error) => void];
      const error = new Error('connection lost');

      listener(error);

      expect(event).toBe('error');
      expect(queueErrors.report).toHaveBeenCalledWith('producer', error);
    });
  });

  describe('enqueue()', () => {
    it('when a request is queued, then the job carries the request and its owner under a UUID id', async () => {
      const jobId = await service.enqueue(REQUEST, OWNER_ID);

      expect(jobId).toMatch(
        /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
      );
      expect(queue.add).toHaveBeenCalledWith(
        CHAT_JOB_NAME,
        { request: REQUEST, ownerId: OWNER_ID },
        { jobId },
      );
    });

    it('when the caller is anonymous, then the owner is stored as null', async () => {
      await service.enqueue(REQUEST, null);

      expect(queue.add).toHaveBeenCalledWith(
        CHAT_JOB_NAME,
        { request: REQUEST, ownerId: null },
        expect.anything(),
      );
    });

    it('when two requests are queued, then their ids differ', async () => {
      const first = await service.enqueue(REQUEST, OWNER_ID);
      const second = await service.enqueue(REQUEST, OWNER_ID);

      expect(first).not.toBe(second);
    });
  });

  describe('getStatus()', () => {
    it('when the job is completed, then it returns the answer as result', async () => {
      queue.getJob.mockResolvedValue(makeJob('completed', { returnvalue: { answer: 'done' } }));

      await expect(service.getStatus(JOB_ID, OWNER_ID)).resolves.toEqual({
        jobId: JOB_ID,
        state: 'completed',
        result: { answer: 'done' },
      });
    });

    it.each(['waiting', 'active', 'delayed', 'failed'])(
      'when the job is %s, then result is null without throwing',
      async (state) => {
        queue.getJob.mockResolvedValue(makeJob(state));

        await expect(service.getStatus(JOB_ID, OWNER_ID)).resolves.toEqual({
          jobId: JOB_ID,
          state,
          result: null,
        });
      },
    );

    it('when a completed job has a malformed return value, then it rejects instead of returning it', async () => {
      queue.getJob.mockResolvedValue(makeJob('completed', { returnvalue: { unexpected: true } }));

      await expect(service.getStatus(JOB_ID, OWNER_ID)).rejects.toThrow(ZodError);
    });

    it('when the job was queued before owners were recorded, then it answers like a missing job', async () => {
      queue.getJob.mockResolvedValue(makeJob('waiting', { data: { request: REQUEST } }));

      await expect(service.getStatus(JOB_ID, null)).rejects.toThrow(
        new NotFoundException(CHAT_JOB_NOT_FOUND_MESSAGE),
      );
    });

    it('when the job does not exist, then it throws NotFoundException', async () => {
      queue.getJob.mockResolvedValue(undefined);

      await expect(service.getStatus(JOB_ID, OWNER_ID)).rejects.toThrow(
        new NotFoundException(CHAT_JOB_NOT_FOUND_MESSAGE),
      );
    });

    it('when the job belongs to another caller, then it answers exactly like a missing job', async () => {
      queue.getJob.mockResolvedValue(makeJob('completed', { returnvalue: { answer: 'secret' } }));

      await expect(service.getStatus(JOB_ID, 'user-b')).rejects.toThrow(
        new NotFoundException(CHAT_JOB_NOT_FOUND_MESSAGE),
      );
    });

    it('when an anonymous caller asks for an owned job, then it throws NotFoundException', async () => {
      queue.getJob.mockResolvedValue(makeJob('waiting'));

      await expect(service.getStatus(JOB_ID, null)).rejects.toThrow(NotFoundException);
    });

    it('when an authenticated caller asks for an anonymous job, then it throws NotFoundException', async () => {
      queue.getJob.mockResolvedValue(
        makeJob('waiting', { data: { request: REQUEST, ownerId: null } }),
      );

      await expect(service.getStatus(JOB_ID, OWNER_ID)).rejects.toThrow(NotFoundException);
    });

    it('when an anonymous caller asks for an anonymous job, then it is returned', async () => {
      queue.getJob.mockResolvedValue(
        makeJob('waiting', { data: { request: REQUEST, ownerId: null } }),
      );

      await expect(service.getStatus(JOB_ID, null)).resolves.toMatchObject({ state: 'waiting' });
    });
  });
});

describe('ChatJobStatusSchema (serializer contract)', () => {
  it('when result is null, then parse does not throw', () => {
    expect(() =>
      ChatJobStatusSchema.parse({ jobId: JOB_ID, state: 'failed', result: null }),
    ).not.toThrow();
  });

  it('when result is the answer object, then parse returns the answer', () => {
    const parsed = ChatJobStatusSchema.parse({
      jobId: JOB_ID,
      state: 'completed',
      result: { answer: 'Hello' },
    });

    expect(parsed.result).toEqual({ answer: 'Hello' });
  });

  it('when result is absent, then parse rejects so the service must always send null', () => {
    expect(() => ChatJobStatusSchema.parse({ jobId: JOB_ID, state: 'waiting' })).toThrow();
  });

  it('when the state is not a BullMQ state, then parse rejects', () => {
    expect(() =>
      ChatJobStatusSchema.parse({ jobId: JOB_ID, state: 'exploded', result: null }),
    ).toThrow();
  });

  it('when the job id is not a UUID, then parse rejects', () => {
    expect(() =>
      ChatJobStatusSchema.parse({ jobId: '42', state: 'waiting', result: null }),
    ).toThrow();
  });
});
