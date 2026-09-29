import { z } from 'zod';

export const EchoRequestSchema = z.object({
  message: z.string().min(1, 'Message is required'),
});

export const EchoResponseSchema = z.object({
  message: z.string(),
});

export type EchoRequestDto = z.infer<typeof EchoRequestSchema>;
export type EchoResponseDto = z.infer<typeof EchoResponseSchema>;
