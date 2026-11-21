import { z } from 'zod';
import { createZodDto } from 'nestjs-zod';
import {
  MAX_CHAT_HISTORY_MESSAGE_LENGTH,
  MAX_CHAT_HISTORY_MESSAGES,
  MAX_CHAT_QUESTION_LENGTH,
} from '../chat.constants';

/**
 * Body of every chat route. The snake_case keys are the wire contract the Angular app already
 * sends; the length limits bound LLM cost and keep untrusted input small.
 */
export const ChatRequestSchema = z.object({
  user_question: z.string().trim().min(1, 'Question is required').max(MAX_CHAT_QUESTION_LENGTH),
  conversation_history: z
    .object({
      messages: z
        .array(z.string().max(MAX_CHAT_HISTORY_MESSAGE_LENGTH))
        .max(MAX_CHAT_HISTORY_MESSAGES),
    })
    .optional(),
});

/** Answer returned by `POST /chat` and stored as the result of a completed job. */
export const ChatResponseSchema = z.object({
  answer: z.string(),
});

/** One `data:` event of the `POST /chat/stream` stream; `content` is the answer so far. */
export const StreamChunkSchema = z.object({
  content: z.string(),
  done: z.boolean(),
});

/** Terminal event of a stream that failed; the stream carries nothing after it. */
export const StreamErrorSchema = z.object({
  error: z.string(),
  done: z.literal(true),
});

/** Body of the 202 response to `POST /chat/jobs`. */
export const ChatJobAcceptedSchema = z.object({
  jobId: z.uuid(),
});

/** Every state BullMQ can report for a job, plus `unknown` for a job that vanished mid-read. */
export const CHAT_JOB_STATES = [
  'waiting',
  'active',
  'completed',
  'failed',
  'delayed',
  'prioritized',
  'waiting-children',
  'unknown',
] as const;

/**
 * Body of `GET /chat/jobs/:id`. `result` is null until the job completes: a nullable field keeps
 * the response serializer from throwing, which would turn every poll of a pending job into a 500.
 */
export const ChatJobStatusSchema = z.object({
  jobId: z.uuid(),
  state: z.enum(CHAT_JOB_STATES),
  result: ChatResponseSchema.nullable(),
});

/**
 * Payload stored on a chat job. `ownerId` is null for anonymous callers (the no-auth variant) and
 * is what a status read is compared against.
 */
export const ChatJobDataSchema = z.object({
  request: ChatRequestSchema,
  ownerId: z.string().nullable(),
});

/** Validated chat request, as the services and the queue consume it. */
export type ChatRequest = z.output<typeof ChatRequestSchema>;

/** Payload of a chat job, see {@link ChatJobDataSchema}. */
export type ChatJobData = z.output<typeof ChatJobDataSchema>;

/** Terminal event written to the stream when answering failed. */
export type StreamErrorEvent = z.output<typeof StreamErrorSchema>;

/** Status of a chat job as returned to its owner. */
export type ChatJobStatus = z.output<typeof ChatJobStatusSchema>;

/** Request body DTO of the chat routes, see {@link ChatRequestSchema}. */
export class ChatRequestDto extends createZodDto(ChatRequestSchema) {}

/** Response DTO of `POST /chat`, see {@link ChatResponseSchema}. */
export class ChatResponseDto extends createZodDto(ChatResponseSchema) {}

/** Event DTO of the chat stream, see {@link StreamChunkSchema}. */
export class StreamChunkDto extends createZodDto(StreamChunkSchema) {}

/** Response DTO of `POST /chat/jobs`, see {@link ChatJobAcceptedSchema}. */
export class ChatJobAcceptedDto extends createZodDto(ChatJobAcceptedSchema) {}

/** Response DTO of `GET /chat/jobs/:id`, see {@link ChatJobStatusSchema}. */
export class ChatJobStatusDto extends createZodDto(ChatJobStatusSchema) {}
