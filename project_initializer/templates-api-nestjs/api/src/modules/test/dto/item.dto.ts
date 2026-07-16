import { z } from 'zod';
import { createZodDto } from 'nestjs-zod';

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

/**
 * List responses need their own schema: `ZodSerializerDto` parses the handler's
 * return value with the DTO's schema as-is, and `ItemResponseSchema` is an
 * object — handing it an array fails with "expected object, received array" and
 * the request 500s. Wrapping in `z.array` still strips unknown fields from every
 * element, so the response whitelist holds.
 */
export const ItemListResponseSchema = z.array(ItemResponseSchema);

export class CreateItemDto extends createZodDto(CreateItemSchema) {}
export class UpdateItemDto extends createZodDto(UpdateItemSchema) {}
export class ItemResponseDto extends createZodDto(ItemResponseSchema) {}
export class ItemListResponseDto extends createZodDto(ItemListResponseSchema) {}
