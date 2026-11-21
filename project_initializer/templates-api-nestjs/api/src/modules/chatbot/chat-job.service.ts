import { randomUUID } from 'node:crypto';
import { Injectable, NotFoundException, OnModuleInit } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { CHAT_JOB_NAME, CHAT_JOB_NOT_FOUND_MESSAGE, CHAT_QUEUE_NAME } from './chat.constants';
import {
  ChatJobData,
  ChatJobStatus,
  ChatRequest,
  ChatResponseDto,
  ChatResponseSchema,
} from './dto/chat.dto';
import { QueueErrorReporter } from './queue-error-reporter';

/** Enqueues chat requests for the background worker and reports their progress to their owner. */
@Injectable()
export class ChatJobService implements OnModuleInit {
  constructor(
    @InjectQueue(CHAT_QUEUE_NAME)
    private readonly chatQueue: Queue<ChatJobData, ChatResponseDto, typeof CHAT_JOB_NAME>,
    private readonly queueErrors: QueueErrorReporter,
  ) {}

  /** Starts reporting the connection errors the queue emits, so BullMQ does not print them raw. */
  onModuleInit(): void {
    this.chatQueue.on('error', (error) => this.queueErrors.report('producer', error));
  }

  /**
   * Queues a chat request.
   *
   * @param request - Validated request the worker will answer.
   * @param ownerId - Caller the job belongs to, `null` for an anonymous caller.
   * @returns The job id, a random UUID so that ids of other callers' jobs cannot be guessed.
   */
  async enqueue(request: ChatRequest, ownerId: string | null): Promise<string> {
    const jobId = randomUUID();
    await this.chatQueue.add(CHAT_JOB_NAME, { request, ownerId }, { jobId });
    return jobId;
  }

  /**
   * Reads the current state of a job.
   *
   * @param jobId - Id returned by {@link ChatJobService.enqueue}.
   * @param ownerId - Caller asking; must equal the owner the job was queued for.
   * @returns The state, plus the answer once the job is `completed` and `null` before that.
   * @throws NotFoundException when the job does not exist, has expired, or belongs to another
   *   caller. The three cases are indistinguishable on purpose. A job queued before owners were
   *   recorded has no `ownerId` and counts as another caller's.
   * @throws ZodError when a completed job's stored result is not a chat answer.
   */
  async getStatus(jobId: string, ownerId: string | null): Promise<ChatJobStatus> {
    const job = await this.chatQueue.getJob(jobId);
    if (!job || job.data.ownerId !== ownerId) {
      throw new NotFoundException(CHAT_JOB_NOT_FOUND_MESSAGE);
    }
    const state = await job.getState();
    const result = state === 'completed' ? ChatResponseSchema.parse(job.returnvalue) : null;
    return { jobId, state, result };
  }
}
