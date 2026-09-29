import { z } from 'zod';

export const CreateItemSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  description: z.string().optional(),
});

export const UpdateItemSchema = CreateItemSchema.partial();

export const ItemResponseSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  description: z.string().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

export type CreateItemDto = z.infer<typeof CreateItemSchema>;
export type UpdateItemDto = z.infer<typeof UpdateItemSchema>;
export type ItemResponseDto = z.infer<typeof ItemResponseSchema>;
