import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import { ChatbotController } from './chatbot.controller';
import { ChatbotService } from './chatbot.service';
import { ChatProcessor } from './chat.processor';
import { ChatJobService } from './chat-job.service';

@Module({
  imports: [
    BullModule.registerQueue({
      name: 'chat',
      defaultJobOptions: {
        attempts: 3,
        backoff: { type: 'exponential', delay: 1000 },
        removeOnComplete: { age: 3600, count: 1000 },
        removeOnFail: { age: 86400 },
      },
    }),
  ],
  controllers: [ChatbotController],
  providers: [ChatbotService, ChatJobService, ChatProcessor],
})
export class ChatbotModule {}
