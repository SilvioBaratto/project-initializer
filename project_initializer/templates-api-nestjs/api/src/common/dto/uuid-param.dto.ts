import { createZodDto } from 'nestjs-zod';
import { z } from 'zod';

/** Path parameter for routes that address one resource by its UUID, e.g. `GET /items/:id`. */
export const UuidParamSchema = z.object({ id: z.uuid() });

/**
 * Validates the `id` path parameter before a handler runs: a malformed value is a 400 with the
 * shared error body instead of reaching the database as an invalid UUID.
 */
export class UuidParamDto extends createZodDto(UuidParamSchema) {}
