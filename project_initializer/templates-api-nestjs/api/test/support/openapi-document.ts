import type { INestApplication } from '@nestjs/common';
import {
  DocumentBuilder,
  OpenAPIObject,
  ReferenceObject,
  RequestBodyObject,
  ResponseObject,
  SwaggerModule,
} from '@nestjs/swagger';

const JSON_MEDIA_TYPE = 'application/json';

/** Lower-case HTTP method, as the OpenAPI document keys its operations. */
export type HttpMethod = 'get' | 'post' | 'put' | 'delete';

/**
 * Builds the OpenAPI document of an initialised application, with the same scan and schema
 * conversion as `setupOpenApi`, so a spec reads the contract a client would download.
 */
export function openApiDocumentOf(app: INestApplication): OpenAPIObject {
  return SwaggerModule.createDocument(app, new DocumentBuilder().build());
}

/** Status codes an operation documents, or none when the operation is absent. */
export function documentedStatusesOf(
  document: OpenAPIObject,
  path: string,
  method: HttpMethod,
): string[] {
  return Object.keys(document.paths[path]?.[method]?.responses ?? {});
}

/** JSON schema of one documented response, or `undefined` when it has no JSON body. */
export function responseSchemaOf(
  document: OpenAPIObject,
  path: string,
  method: HttpMethod,
  status: string,
): unknown {
  return jsonSchemaOf(document.paths[path]?.[method]?.responses[status]);
}

/** JSON schema of an operation's request body, or `undefined` when it documents none. */
export function requestBodySchemaOf(
  document: OpenAPIObject,
  path: string,
  method: HttpMethod,
): unknown {
  return jsonSchemaOf(document.paths[path]?.[method]?.requestBody);
}

function jsonSchemaOf(
  holder: ResponseObject | RequestBodyObject | ReferenceObject | undefined,
): unknown {
  return holder !== undefined && 'content' in holder
    ? holder.content?.[JSON_MEDIA_TYPE]?.schema
    : undefined;
}
