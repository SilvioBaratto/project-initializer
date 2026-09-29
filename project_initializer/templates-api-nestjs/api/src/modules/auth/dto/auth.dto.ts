import { z } from 'zod';

export const AuthRequestSchema = z.object({
  token: z.string().min(1, 'Token is required'),
});

export const AuthResponseSchema = z.object({
  authenticated: z.boolean(),
  message: z.string(),
});

export type AuthRequestDto = z.infer<typeof AuthRequestSchema>;
export type AuthResponseDto = z.infer<typeof AuthResponseSchema>;
