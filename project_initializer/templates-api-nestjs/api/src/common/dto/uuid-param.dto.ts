import { z } from 'zod';

/**
 * Path parameter for routes that address one resource by its UUID, e.g. `GET /items/:id`. Bind it
 * with `@Param({ schema: UuidParamSchema })`: a malformed value is then a 400 with the shared error
 * body instead of reaching the database as an invalid UUID.
 */
export const UuidParamSchema = z.object({ id: z.uuid() });

/** Validated `id` path parameter, as {@link UuidParamSchema} returns it. */
export type UuidParamDto = z.infer<typeof UuidParamSchema>;
