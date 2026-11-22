import { applyDecorators, HttpStatus, SerializeOptions } from '@nestjs/common';
import { ApiResponse } from '@nestjs/swagger';
import type { z } from 'zod';

/** Options of {@link ResponseSchema}. */
export interface ResponseSchemaOptions {
  /** The handler returns an array whose every element matches the schema. */
  many?: boolean;
  /** Text shown for the response in the OpenAPI document. */
  description?: string;
}

/**
 * Declares the body a handler answers with, once for both readers of that contract: the global
 * serializer, which validates the returned value and drops every field the schema does not list,
 * and the OpenAPI document, which shows the same schema under `status`. Declaring it once is what
 * keeps the published document and the wire format from drifting apart.
 *
 * It does not change the HTTP status. A handler that answers anything other than its method's
 * default keeps its own `@HttpCode`, so the status sent and the status documented are both
 * written out where a reader sees them.
 *
 * @param status - Status the response is documented under.
 * @param schema - Schema of the body. For a list, the schema of one element: the serializer checks
 *   each element of a returned array on its own and would reject an array schema.
 * @param options - `many` documents the body as an array of `schema`; `description` labels it.
 * @returns A decorator for a route handler.
 */
export function ResponseSchema(
  status: HttpStatus,
  schema: z.ZodType,
  options: ResponseSchemaOptions = {},
): MethodDecorator {
  return applyDecorators(
    SerializeOptions({ schema }),
    ApiResponse({
      status,
      standardSchema: schema,
      isArray: options.many,
      description: options.description,
    }),
  );
}
