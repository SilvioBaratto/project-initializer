import { OnWorkerEvent, Processor, WorkerHost } from '@nestjs/bullmq';
import { Logger } from '@nestjs/common';
import { Job, UnrecoverableError } from 'bullmq';
import { CHAT_QUEUE_NAME } from './chat.constants';
import { describeChatFailure } from './chat-failure';
import { ChatbotService } from './chatbot.service';
import { ChatJobData, ChatJobDataSchema, ChatResponseDto } from './dto/chat.dto';
import { QueueErrorReporter } from './queue-error-reporter';

type ChatJob = Job<ChatJobData, ChatResponseDto>;

function parseJobData(data: unknown): ChatJobData {
  const parsed = ChatJobDataSchema.safeParse(data);
  if (!parsed.success) {
    throw new UnrecoverableError(`Malformed chat job data: ${parsed.error.message}`);
  }
  return parsed.data;
}

/** Worker that answers queued chat jobs. */
@Processor(CHAT_QUEUE_NAME)
export class ChatProcessor extends WorkerHost {
  private readonly logger = new Logger(ChatProcessor.name);

  constructor(
    private readonly chatbotService: ChatbotService,
    private readonly queueErrors: QueueErrorReporter,
  ) {
    super();
  }

  /**
   * Answers one job.
   *
   * @throws UnrecoverableError when the job data is malformed. Retrying cannot repair it, so the
   *   job fails at once.
   * @throws ServiceUnavailableException when the assistant fails. It is rethrown, never swallowed
   *   into an answer, so BullMQ retries the job and finally records it as failed.
   */
  async process(job: ChatJob): Promise<ChatResponseDto> {
    const { request } = parseJobData(job.data);
    return this.chatbotService.chat(request);
  }

  /**
   * Logs a failed attempt, with the stack of its cause. BullMQ emits this for every failed
   * attempt, not only the last one, and with no job when the job was removed before the event
   * fired. The worker has no exception filter, so this is the one place the cause is logged.
   */
  @OnWorkerEvent('failed')
  onFailed(job: ChatJob | undefined, error: Error): void {
    const subject = job ? `Chat job ${job.id} (attempt ${job.attemptsMade})` : 'Chat job';
    this.logger.error(`${subject} failed`, describeChatFailure(error));
  }

  /** Reports a worker-level error, such as a lost Redis connection, without a stack dump. */
  @OnWorkerEvent('error')
  onWorkerError(error: Error): void {
    this.queueErrors.report('worker', error);
  }
}
