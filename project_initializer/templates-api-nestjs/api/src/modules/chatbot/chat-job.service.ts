import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { ChatRequestDto } from './dto/chat.dto';

@Injectable()
export class ChatJobService {
  constructor(@InjectQueue('chat') private readonly chatQueue: Queue) {}

  async enqueueChat(request: ChatRequestDto): Promise<string> {
    const job = await this.chatQueue.add('chat', request);
    return job.id as string;
  }

  async getJobStatus(id: string): Promise<{ state: string; result: unknown }> {
    const job = await this.chatQueue.getJob(id);
    if (!job) {
      throw new NotFoundException(`Job ${id} not found`);
    }
    const state = await job.getState();
    return { state, result: job.returnvalue ?? null };
  }
}
