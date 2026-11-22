/**
 * Validates every controller under src/: each `@Body`, `@Param` and `@Query` of a route handler
 * binds a schema.
 *
 * The global `StandardSchemaValidationPipe` validates only the parameters that pass `{ schema }`
 * and hands every other one to the handler unchanged, so a forgotten schema would switch input
 * validation off without any error. The controllers are discovered from the files at run time, so
 * a controller an auth variant adds, or one written later, is checked without editing this spec.
 */
import 'reflect-metadata';
import { readdirSync } from 'node:fs';
import { join } from 'node:path';
import { Body, Controller, Get, Param, Post, Query, Req, Type } from '@nestjs/common';
import {
  CONTROLLER_WATERMARK,
  METHOD_METADATA,
  ROUTE_ARGS_METADATA,
} from '@nestjs/common/constants';
import { RouteParamtypes } from '@nestjs/common/enums/route-paramtypes.enum';
import { z } from 'zod';
import { CurrentUser } from './decorators/current-user.decorator';

const SOURCE_ROOT = join(__dirname, '..');
const CONTROLLER_FILE = /\.controller\.ts$/;

/** The request-data decorators the global pipe validates only when they pass `{ schema }`. */
const VALIDATED_PARAMETERS: ReadonlyMap<number, string> = new Map([
  [RouteParamtypes.BODY, '@Body'],
  [RouteParamtypes.QUERY, '@Query'],
  [RouteParamtypes.PARAM, '@Param'],
]);

/** What Nest 12 stores per decorated parameter, keyed `<paramtype>:<index>`. */
interface RouteArgument {
  index: number;
  schema?: unknown;
}

function handlerNamesOf(controller: Type<unknown>): string[] {
  const prototype = controller.prototype as object;
  return Object.getOwnPropertyNames(prototype).filter((name) => {
    const member: unknown = Object.getOwnPropertyDescriptor(prototype, name)?.value;
    return typeof member === 'function' && Reflect.hasMetadata(METHOD_METADATA, member);
  });
}

/**
 * Lists the validated parameters of a controller's handlers that carry no schema. A custom
 * decorator such as `@CurrentUser()` is stored under a key whose paramtype is not a number, and
 * `@Req()` has its own paramtype, so neither is listed.
 */
function parametersWithoutSchema(controller: Type<unknown>): string[] {
  return handlerNamesOf(controller).flatMap((handler) => {
    const routeArguments = (Reflect.getMetadata(ROUTE_ARGS_METADATA, controller, handler) ??
      {}) as Record<string, RouteArgument>;
    return Object.entries(routeArguments)
      .sort(([, left], [, right]) => left.index - right.index)
      .flatMap(([key, argument]) => {
        const [paramtype] = key.split(':');
        const decorator = VALIDATED_PARAMETERS.get(Number(paramtype));
        return decorator !== undefined && argument.schema === undefined
          ? [`${controller.name}.${handler}: ${decorator} at parameter ${argument.index}`]
          : [];
      });
  });
}

function isController(candidate: unknown): candidate is Type<unknown> {
  return (
    typeof candidate === 'function' && Reflect.getMetadata(CONTROLLER_WATERMARK, candidate) === true
  );
}

async function discoverControllers(): Promise<Type<unknown>[]> {
  const files = readdirSync(SOURCE_ROOT, { recursive: true, encoding: 'utf8' }).filter((file) =>
    CONTROLLER_FILE.test(file),
  );
  const modules = await Promise.all(
    files.map((file) => import(join(SOURCE_ROOT, file)) as Promise<Record<string, unknown>>),
  );
  return modules.flatMap((exported) => Object.values(exported).filter(isController));
}

const ProbeSchema = z.object({ name: z.string() });

@Controller('probe')
class ProbeWithGapsController {
  @Post(':id')
  create(
    @Param('id') id: string,
    @Body() body: unknown,
    @Query({ schema: ProbeSchema }) query: unknown,
    @CurrentUser() user: unknown,
    @Req() request: unknown,
  ): unknown[] {
    return [id, body, query, user, request];
  }
}

@Controller('probe')
class ProbeCoveredController {
  @Get(':id')
  findOne(@Param({ schema: ProbeSchema }) params: unknown): unknown {
    return params;
  }
}

describe('Validation coverage of the controllers', () => {
  it('when a handler leaves a parameter without a schema, then the check names exactly that parameter', () => {
    expect(parametersWithoutSchema(ProbeWithGapsController)).toEqual([
      'ProbeWithGapsController.create: @Param at parameter 0',
      'ProbeWithGapsController.create: @Body at parameter 1',
    ]);
  });

  it('when every validated parameter passes a schema, then the check finds nothing', () => {
    expect(parametersWithoutSchema(ProbeCoveredController)).toEqual([]);
  });

  it('when the controllers under src are discovered, then the shared ones are among them', async () => {
    const names = (await discoverControllers()).map((controller) => controller.name);

    expect(names).toEqual(expect.arrayContaining(['ItemsController', 'TestController']));
  });

  it('when every controller under src is inspected, then each @Body, @Param and @Query passes a schema', async () => {
    const controllers = await discoverControllers();

    expect(controllers.flatMap(parametersWithoutSchema)).toEqual([]);
  });
});
