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
 * Decorator for a route handler whose result, awaited or not, must be a `Body`. Decorating a handler
 * that returns anything else is a compile error (TS1241), so a handler cannot drift from the schema
 * it declares without the build noticing.
 */
export type ResponseSchemaDecorator<Body> = <
  Handler extends (...args: never[]) => Body | Promise<Body>,
>(
  target: object,
  propertyKey: string | symbol,
  descriptor: TypedPropertyDescriptor<Handler>,
) => void;

/**
 * Declares the body a handler answers with, once for both readers of that contract: the global
 * serializer, which validates the returned value and drops every field the schema does not list,
 * and the OpenAPI document, which shows the same schema under `status`. Declaring it once is what
 * keeps the published document and the wire format from drifting apart, and the decorator's type
 * makes the handler's return type follow the schema as well.
 *
 * It does not change the HTTP status. A handler that answers anything other than its method's
 * default keeps its own `@HttpCode`, so the status sent and the status documented are both
 * written out where a reader sees them.
 *
 * @param status - Status the response is documented under.
 * @param schema - Schema of the body. For a list, the schema of one element: the serializer checks
 *   each element of a returned array on its own and would reject an array schema.
 * @param options - `many` documents the body as an array of `schema` and expects the handler to
 *   return an array; `description` labels the response.
 * @returns A decorator for a route handler.
 */
export function ResponseSchema<Schema extends z.ZodType>(
  status: HttpStatus,
  schema: Schema,
  options: ResponseSchemaOptions & { many: true },
): ResponseSchemaDecorator<z.input<Schema>[]>;
/**
 * Declares a single-object body; see the overload above for the contract.
 *
 * @param status - Status the response is documented under.
 * @param schema - Schema of the body.
 * @param options - `description` labels the response.
 * @returns A decorator for a handler that returns one `schema` value.
 */
export function ResponseSchema<Schema extends z.ZodType>(
  status: HttpStatus,
  schema: Schema,
  options?: ResponseSchemaOptions & { many?: false },
): ResponseSchemaDecorator<z.input<Schema>>;
/**
 * Implementation shared by both overloads: sets the serializer schema and the OpenAPI response.
 *
 * @param status - Status the response is documented under.
 * @param schema - Schema of the body, or of one element of it.
 * @param options - See {@link ResponseSchemaOptions}.
 * @returns The combined decorator.
 */
export function ResponseSchema(
  status: HttpStatus,
  schema: z.ZodType,
  options: ResponseSchemaOptions = {},
): ResponseSchemaDecorator<unknown> {
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
