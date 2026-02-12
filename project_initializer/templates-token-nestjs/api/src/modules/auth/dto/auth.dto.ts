import { z } from 'zod';
import { createZodDto } from 'nestjs-zod';

export const AuthRequestSchema = z.object({
  token: z.string().min(1, 'Token is required'),
});

export const AuthResponseSchema = z.object({
  authenticated: z.boolean(),
  message: z.string(),
});

export class AuthRequestDto extends createZodDto(AuthRequestSchema) {}
export class AuthResponseDto extends createZodDto(AuthResponseSchema) {}
