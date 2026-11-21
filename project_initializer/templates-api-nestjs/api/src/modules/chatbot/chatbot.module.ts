import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import type { DefaultJobOptions } from 'bullmq';
import { BamlChatCompletionAdapter } from './baml-chat-completion.adapter';
import { CHAT_COMPLETION_PORT } from './chat-completion.port';
import {
  CHAT_JOB_BACKOFF_DELAY_MS,
  CHAT_QUEUE_NAME,
  COMPLETED_CHAT_JOB_TTL_SECONDS,
  COMPLETED_CHAT_JOBS_KEPT,
  FAILED_CHAT_JOB_TTL_SECONDS,
} from './chat.constants';
import { ChatJobService } from './chat-job.service';
import { ChatProcessor } from './chat.processor';
import { ChatbotController } from './chatbot.controller';
import { ChatbotService } from './chatbot.service';
import { QueueErrorReporter } from './queue-error-reporter';

/**
 * Options applied to every chat job.
 *
 * Retries with exponential backoff absorb transient LLM failures and rate limiting. Completed jobs
 * stay readable for the window a client has to poll for its answer, `count` caps Redis growth
 * under load, and failed jobs stay longer for diagnosis.
 *
 * Every attempt runs the BAML client's own retry policy (`Exponential` in `baml_src/clients.baml`,
 * 1 call plus 2 retries), so a job that keeps failing costs up to 3 x 3 provider calls.
 */
export const CHAT_JOB_OPTIONS: DefaultJobOptions = {
  attempts: 3,
  backoff: { type: 'exponential', delay: CHAT_JOB_BACKOFF_DELAY_MS },
  removeOnComplete: { age: COMPLETED_CHAT_JOB_TTL_SECONDS, count: COMPLETED_CHAT_JOBS_KEPT },
  removeOnFail: { age: FAILED_CHAT_JOB_TTL_SECONDS },
};

/** Chat endpoints, the queue behind the asynchronous ones, and the LLM adapter they share. */
@Module({
  imports: [
    BullModule.registerQueue({
      name: CHAT_QUEUE_NAME,
      defaultJobOptions: CHAT_JOB_OPTIONS,
    }),
  ],
  controllers: [ChatbotController],
  providers: [
    ChatbotService,
    ChatJobService,
    ChatProcessor,
    QueueErrorReporter,
    { provide: CHAT_COMPLETION_PORT, useClass: BamlChatCompletionAdapter },
  ],
})
export class ChatbotModule {}
