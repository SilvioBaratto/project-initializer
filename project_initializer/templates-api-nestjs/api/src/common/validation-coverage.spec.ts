/**
 * Validates the controller classes exported from the `*.controller.ts` files under src/: each
 * `@Body`, `@Param` and `@Query` of their own and inherited route handlers binds a schema.
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

/**
 * Names the route handlers of a controller, its own and the ones it inherits, because Nest's scanner
 * walks the prototype chain too: a handler declared on an undecorated base class is still a route.
 */
function handlerNamesOf(controller: Type<unknown>): string[] {
  const names = new Set<string>();
  let prototype = controller.prototype as object | null;
  while (prototype !== null && prototype !== Object.prototype) {
    const current: object = prototype;
    for (const name of Object.getOwnPropertyNames(current)) {
      const member: unknown = Object.getOwnPropertyDescriptor(current, name)?.value;
      if (typeof member === 'function' && Reflect.hasMetadata(METHOD_METADATA, member)) {
        names.add(name);
      }
    }
    prototype = Object.getPrototypeOf(current) as object | null;
  }
  return [...names];
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

/** The controller classes each `*.controller.ts` file under `src/` exports, keyed by file. */
async function discoverControllers(): Promise<Map<string, Type<unknown>[]>> {
  const files = readdirSync(SOURCE_ROOT, { recursive: true, encoding: 'utf8' }).filter((file) =>
    CONTROLLER_FILE.test(file),
  );
  const entries = await Promise.all(
    files.map(async (file): Promise<[string, Type<unknown>[]]> => {
      const exported = (await import(join(SOURCE_ROOT, file))) as Record<string, unknown>;
      return [file, Object.values(exported).filter(isController)];
    }),
  );
  return new Map(entries);
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

class ProbeBaseHandlers {
  @Get('search')
  search(@Query('term') term: string): string {
    return term;
  }
}

@Controller('probe')
class ProbeInheritingController extends ProbeBaseHandlers {}

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

  it('when a controller inherits a handler without a schema, then the check names it too', () => {
    expect(parametersWithoutSchema(ProbeInheritingController)).toEqual([
      'ProbeInheritingController.search: @Query at parameter 0',
    ]);
  });

  it('when the controller files under src are loaded, then each exports a controller and the health one is among them', async () => {
    const discovered = await discoverControllers();
    const filesWithoutController = [...discovered]
      .filter(([, controllers]) => controllers.length === 0)
      .map(([file]) => file);
    const names = [...discovered.values()].flat().map((controller) => controller.name);

    expect(filesWithoutController).toEqual([]);
    expect(names).toContain('HealthController');
  });

  it('when every controller under src is inspected, then each @Body, @Param and @Query passes a schema', async () => {
    const controllers = [...(await discoverControllers()).values()].flat();

    expect(controllers.flatMap(parametersWithoutSchema)).toEqual([]);
  });
});
