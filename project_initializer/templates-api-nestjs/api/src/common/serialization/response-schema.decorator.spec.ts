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
const LIST_DESCRIPTION = 'Every widget';

class WidgetController {
  @ResponseSchema(HttpStatus.OK, WidgetSchema)
  findOne(): void {}

  @ResponseSchema(HttpStatus.OK, WidgetSchema, { many: true, description: LIST_DESCRIPTION })
  findAll(): void {}

  @HttpCode(HttpStatus.CREATED)
  @ResponseSchema(HttpStatus.CREATED, WidgetSchema)
  create(): void {}
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

  it('when it decorates a handler, then it leaves the HTTP status to the handler', () => {
    expect(Reflect.getMetadata(HTTP_CODE_METADATA, WidgetController.prototype.findOne)).toBe(
      undefined,
    );
    expect(Reflect.getMetadata(HTTP_CODE_METADATA, WidgetController.prototype.create)).toBe(
      HttpStatus.CREATED,
    );
  });
});
