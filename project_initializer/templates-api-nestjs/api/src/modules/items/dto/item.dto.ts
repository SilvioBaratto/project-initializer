import { createZodDto } from 'nestjs-zod';
import { z } from 'zod';
import type { Item } from '../item.entity';
import { MAX_ITEM_DESCRIPTION_LENGTH, MAX_ITEM_NAME_LENGTH } from '../item.constants';

/** Body of `POST /items`. A blank name is rejected after trimming. */
export const CreateItemSchema = z.object({
  name: z.string().trim().min(1).max(MAX_ITEM_NAME_LENGTH),
  description: z.string().max(MAX_ITEM_DESCRIPTION_LENGTH).nullish(),
});

/**
 * Body of `PUT /items/:id`. Every field is optional so a client may send only what changed, but an
 * empty object is rejected because it would be a silent no-op.
 */
export const UpdateItemSchema = CreateItemSchema.partial().refine(
  (changes) => Object.keys(changes).length > 0,
  { message: 'At least one field must be provided' },
);

/**
 * Response shape. Fields not listed here are dropped, so a column added to the table later cannot
 * leak through the API by accident. Timestamps are ISO 8601 strings.
 */
export const ItemResponseSchema = z.object({
  id: z.uuid(),
  name: z.string(),
  description: z.string().nullable(),
  created_at: z.iso.datetime(),
  updated_at: z.iso.datetime(),
});

/** Validated body of `POST /items`. */
export class CreateItemDto extends createZodDto(CreateItemSchema) {}
/** Validated body of `PUT /items/:id`. */
export class UpdateItemDto extends createZodDto(UpdateItemSchema) {}
/** Serialized item returned by every item route. */
export class ItemResponseDto extends createZodDto(ItemResponseSchema) {}

/**
 * Maps a stored item to its wire representation.
 *
 * @param item - the entity returned by the service.
 * @returns the response body, with timestamps rendered as ISO 8601 strings.
 */
export function toItemResponse(item: Item): ItemResponseDto {
  return {
    id: item.id,
    name: item.name,
    description: item.description,
    created_at: item.createdAt.toISOString(),
    updated_at: item.updatedAt.toISOString(),
  };
}
