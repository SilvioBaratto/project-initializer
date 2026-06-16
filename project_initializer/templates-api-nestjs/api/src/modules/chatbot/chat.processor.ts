import { OnWorkerEvent, Processor, WorkerHost } from '@nestjs/bullmq';
import { Logger } from '@nestjs/common';
import { Job } from 'bullmq';

@Processor('chat')
export class ChatProcessor extends WorkerHost {
  private readonly logger = new Logger(ChatProcessor.name);

  async process(job: Job): Promise<{ answer: string }> {
    const { user_question, conversation_history } = job.data;
    const { b } = await import('../../../baml_client');
    const result = await b.Chat(user_question, conversation_history);
    return { answer: result.answer };
  }

  @OnWorkerEvent('failed')
  onFailed(job: Job | undefined, error: Error): void {
    this.logger.error(`Chat job ${job?.id} failed: ${error.message}`, error.stack);
  }
}
