import { z } from 'zod';
import { createZodDto } from 'nestjs-zod';

export const ChatRequestSchema = z.object({
  user_question: z.string().min(1, 'Question is required'),
  conversation_history: z.object({ messages: z.array(z.string()) }).optional(),
});

export const ChatResponseSchema = z.object({
  answer: z.string(),
});

export const StreamChunkSchema = z.object({
  content: z.string(),
  done: z.boolean(),
});

export class ChatRequestDto extends createZodDto(ChatRequestSchema) {}
export class ChatResponseDto extends createZodDto(ChatResponseSchema) {}
export class StreamChunkDto extends createZodDto(StreamChunkSchema) {}
