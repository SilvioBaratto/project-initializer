import { Test, TestingModule } from '@nestjs/testing';
import { NotFoundException } from '@nestjs/common';
import { getQueueToken } from '@nestjs/bullmq';
import { ChatJobService } from './chat-job.service';
import { ChatJobStatusSchema } from './dto/chat.dto';

const mockAdd = jest.fn();
const mockGetJob = jest.fn();

const mockQueue = {
  add: mockAdd,
  getJob: mockGetJob,
};

describe('ChatJobService', () => {
  let service: ChatJobService;

  beforeEach(async () => {
    jest.clearAllMocks();

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ChatJobService,
        { provide: getQueueToken('chat'), useValue: mockQueue },
      ],
    }).compile();

    service = module.get<ChatJobService>(ChatJobService);
  });

  describe('enqueueChat()', () => {
    it('when called, adds a job to the queue and returns the job id', async () => {
      mockAdd.mockResolvedValue({ id: 'job-123' });

      const id = await service.enqueueChat({ user_question: 'Hello' });

      expect(mockAdd).toHaveBeenCalledWith('chat', { user_question: 'Hello' });
      expect(id).toBe('job-123');
    });
  });

  describe('getJobStatus()', () => {
    it('when job exists and is completed, returns state and result', async () => {
      const mockJob = {
        getState: jest.fn().mockResolvedValue('completed'),
        returnvalue: { answer: 'done' },
      };
      mockGetJob.mockResolvedValue(mockJob);

      const result = await service.getJobStatus('job-123');

      expect(result).toEqual({ state: 'completed', result: { answer: 'done' } });
    });

    it('when job exists but has no returnvalue, result is null', async () => {
      const mockJob = {
        getState: jest.fn().mockResolvedValue('active'),
        returnvalue: undefined,
      };
      mockGetJob.mockResolvedValue(mockJob);

      const result = await service.getJobStatus('job-456');

      expect(result).toEqual({ state: 'active', result: null });
    });

    it('when job does not exist, throws NotFoundException', async () => {
      mockGetJob.mockResolvedValue(null);

      await expect(service.getJobStatus('missing-id')).rejects.toThrow(NotFoundException);
    });

    it.each(['waiting', 'active', 'delayed', 'failed'])(
      'when job state is %s, returns null result without throwing',
      async (state) => {
        const mockJob = {
          getState: jest.fn().mockResolvedValue(state),
          returnvalue: undefined,
        };
        mockGetJob.mockResolvedValue(mockJob);

        const result = await service.getJobStatus('job-pending');

        expect(result).toEqual({ state, result: null });
      },
    );
  });
});

// Serializer contract: ZodSerializerInterceptor runs ChatJobStatusSchema.parse() on the
// outgoing response body — a plain controller unit test bypasses this interceptor.
// These tests exercise the schema directly to lock the fix in chat.dto.ts.
describe('ChatJobStatusSchema (serializer contract)', () => {
  it('when result is null, parse does not throw', () => {
    expect(() =>
      ChatJobStatusSchema.parse({ jobId: 'j', state: 'failed', result: null }),
    ).not.toThrow();
  });

  it('when result is undefined (key absent), parse does not throw', () => {
    expect(() =>
      ChatJobStatusSchema.parse({ jobId: 'j', state: 'waiting' }),
    ).not.toThrow();
  });

  it('when result is the answer object, parse does not throw and returns answer', () => {
    const parsed = ChatJobStatusSchema.parse({
      jobId: 'j',
      state: 'completed',
      result: { answer: 'Hello' },
    });

    expect(parsed.result).toEqual({ answer: 'Hello' });
  });
});
