import { Injectable, Logger } from '@nestjs/common';
import { ChatRequestDto, ChatResponseDto, StreamChunkDto } from './dto/chat.dto';

@Injectable()
export class ChatbotService {
  private readonly logger = new Logger(ChatbotService.name);

  async chat(request: ChatRequestDto): Promise<ChatResponseDto> {
    try {
      // Import BAML client dynamically
      const { b } = await import('../../../baml_client');
      const result = await b.Chat(request.user_question, request.conversation_history);
      return { answer: result.answer };
    } catch (error) {
      this.logger.error(`Chat error: ${error}`);
      return { answer: 'Sorry, I encountered an error processing your request.' };
    }
  }

  async *streamChat(
    request: ChatRequestDto,
  ): AsyncGenerator<StreamChunkDto> {
    try {
      const { b } = await import('../../../baml_client');
      const stream = b.stream.StreamChat(
        request.user_question,
        request.conversation_history,
      );

      for await (const event of stream) {
        if (event?.answer) {
          yield { content: event.answer, done: false };
        }
      }
    } catch (error) {
      this.logger.error(`Stream chat error: ${error}`);
      yield { content: 'Sorry, I encountered an error.', done: true };
    }
  }
}
