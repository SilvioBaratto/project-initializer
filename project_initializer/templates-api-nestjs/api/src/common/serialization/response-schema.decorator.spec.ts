/** Validates src/common/serialization/response-schema.decorator.ts. */
import 'reflect-metadata';
import {
  CallHandler,
  HttpCode,
  HttpStatus,
  StandardSchemaSerializerInterceptor,
} from '@nestjs/common';
import { HTTP_CODE_METADATA } from '@nestjs/common/constants';
import { Reflector } from '@nestjs/core';
import { ExecutionContextHost } from '@nestjs/core/helpers/execution-context-host';
import { DECORATORS } from '@nestjs/swagger';
import { firstValueFrom, of } from 'rxjs';
import { z } from 'zod';
import { ResponseSchema } from './response-schema.decorator';

const WidgetSchema = z.object({ name: z.string() });
type Widget = z.infer<typeof WidgetSchema>;
const LIST_DESCRIPTION = 'Every widget';
const GEAR: Widget = { name: 'gear' };

class WidgetController {
  @ResponseSchema(HttpStatus.OK, WidgetSchema)
  findOne(): Widget {
    return GEAR;
  }

  @ResponseSchema(HttpStatus.OK, WidgetSchema, { many: true, description: LIST_DESCRIPTION })
  findAll(): Promise<Widget[]> {
    return Promise.resolve([GEAR]);
  }

  @HttpCode(HttpStatus.CREATED)
  @ResponseSchema(HttpStatus.CREATED, WidgetSchema)
  create(): Promise<Widget> {
    return Promise.resolve(GEAR);
  }
}

// Compiled with the specs, so a decorator that stopped checking return types fails the run: each
// directive below must meet the error it announces.
class MismatchedController {
  // @ts-expect-error a handler that returns a number cannot declare the widget schema
  @ResponseSchema(HttpStatus.OK, WidgetSchema)
  count(): number {
    return 1;
  }

  // @ts-expect-error a list declared with many must be returned as an array
  @ResponseSchema(HttpStatus.OK, WidgetSchema, { many: true })
  first(): Widget {
    return GEAR;
  }

  // @ts-expect-error a single-object schema rejects a handler that returns an array
  @ResponseSchema(HttpStatus.OK, WidgetSchema)
  all(): Widget[] {
    return [GEAR];
  }
}

type WidgetHandler = keyof WidgetController;

function serialize(handler: WidgetHandler, returned: unknown): Promise<unknown> {
  const interceptor = new StandardSchemaSerializerInterceptor(new Reflector());
  const context = new ExecutionContextHost(
    [],
    WidgetController,
    WidgetController.prototype[handler],
  );
  context.setType('http');
  const next: CallHandler = { handle: () => of(returned) };
  return firstValueFrom(interceptor.intercept(context, next));
}

function documentedResponsesOf(handler: WidgetHandler): Record<string, Record<string, unknown>> {
  return Reflect.getMetadata(
    DECORATORS.API_RESPONSE,
    WidgetController.prototype[handler],
  ) as Record<string, Record<string, unknown>>;
}

describe('ResponseSchema', () => {
  it('when it decorates a handler, then the serializer strips every field outside the schema', async () => {
    await expect(serialize('findOne', { name: 'gear', secret: 'leak' })).resolves.toEqual({
      name: 'gear',
    });
  });

  it('when it decorates a handler, then the OpenAPI response of the status carries the schema', () => {
    expect(Object.keys(documentedResponsesOf('findOne'))).toEqual([String(HttpStatus.OK)]);
    expect(documentedResponsesOf('findOne')[HttpStatus.OK]).toMatchObject({
      standardSchema: WidgetSchema,
    });
  });

  it('when it decorates a handler with many, then the OpenAPI response is an array of the schema', () => {
    expect(documentedResponsesOf('findAll')[HttpStatus.OK]).toMatchObject({
      standardSchema: WidgetSchema,
      isArray: true,
      description: LIST_DESCRIPTION,
    });
  });

  it('when it decorates a handler with many, then the serializer strips each element of the array', async () => {
    await expect(serialize('findAll', [{ name: 'gear', secret: 'leak' }])).resolves.toEqual([
      { name: 'gear' },
    ]);
  });

  it('when the handler returns data that violates the schema, then serialization fails', async () => {
    await expect(serialize('findOne', { name: 42 })).rejects.toThrow(Error);
  });

  it('when a handler returns another type than its schema, then only the compiler objects', () => {
    // The @ts-expect-error directives on MismatchedController are the assertion; at run time the
    // decorator is applied as usual.
    expect(
      Reflect.getMetadata(DECORATORS.API_RESPONSE, MismatchedController.prototype.count),
    ).toBeDefined();
  });

  it('when it decorates a handler, then it leaves the HTTP status to the handler', () => {
    expect(Reflect.getMetadata(HTTP_CODE_METADATA, WidgetController.prototype.findOne)).toBe(
      undefined,
    );
    expect(Reflect.getMetadata(HTTP_CODE_METADATA, WidgetController.prototype.create)).toBe(
      HttpStatus.CREATED,
    );
  });
});
