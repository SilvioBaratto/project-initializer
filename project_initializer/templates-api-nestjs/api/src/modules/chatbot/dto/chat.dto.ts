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

export const ChatJobAcceptedSchema = z.object({
  jobId: z.string(),
});

export const ChatJobStatusSchema = z.object({
  jobId: z.string(),
  state: z.string(),
  // nullish() accepts the response object, null (non-completed/failed jobs), or undefined.
  // .optional() alone rejects null, causing a ZodError → HTTP 500 for any state except completed.
  result: ChatResponseSchema.nullish(),
});

export class ChatRequestDto extends createZodDto(ChatRequestSchema) {}
export class ChatResponseDto extends createZodDto(ChatResponseSchema) {}
export class StreamChunkDto extends createZodDto(StreamChunkSchema) {}
export class ChatJobAcceptedDto extends createZodDto(ChatJobAcceptedSchema) {}
export class ChatJobStatusDto extends createZodDto(ChatJobStatusSchema) {}
