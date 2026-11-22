import type { Server } from 'node:http';
import {
  INestApplication,
  StandardSchemaSerializerInterceptor,
  StandardSchemaValidationPipe,
} from '@nestjs/common';
import { APP_INTERCEPTOR, APP_PIPE } from '@nestjs/core';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import {
  documentedStatusesOf,
  openApiDocumentOf,
  requestBodySchemaOf,
  responseSchemaOf,
} from '../../../test/support/openapi-document';
import { MAX_ECHO_MESSAGE_LENGTH, PING_MESSAGE } from './dto/echo.dto';
import { TestController } from './test.controller';

// A response schema is documented closed, because the serializer drops every unlisted field.
const ECHO_REPLY_SCHEMA = {
  type: 'object',
  properties: { message: { type: 'string' } },
  required: ['message'],
  additionalProperties: false,
};

/** Validates src/modules/test/test.controller.ts through real routing, validation and serialization. */
describe('TestController', () => {
  let app: INestApplication;
  // Nest types the server as `any`; one cast here keeps every supertest call typed.
  const httpServer = (): Server => app.getHttpServer() as Server;

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({
      controllers: [TestController],
      providers: [
        { provide: APP_PIPE, useClass: StandardSchemaValidationPipe },
        { provide: APP_INTERCEPTOR, useClass: StandardSchemaSerializerInterceptor },
      ],
    }).compile();
    app = moduleRef.createNestApplication();
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  describe('GET /test/ping', () => {
    it('when called, then it answers pong', async () => {
      const response = await request(httpServer()).get('/test/ping').expect(200);

      expect(response.body).toEqual({ message: 'pong' });
    });
  });

  describe('GET /test/echo/:message', () => {
    it('when a message is given, then it is echoed back', async () => {
      const response = await request(httpServer()).get('/test/echo/hello').expect(200);

      expect(response.body).toEqual({ message: 'hello' });
    });

    it('when the message is over the maximum length, then it answers 400', async () => {
      const message = 'm'.repeat(MAX_ECHO_MESSAGE_LENGTH + 1);

      await request(httpServer()).get(`/test/echo/${message}`).expect(400);
    });
  });

  describe('POST /test/echo', () => {
    it('when a message is posted, then it is echoed back with 200 because nothing is created', async () => {
      const response = await request(httpServer())
        .post('/test/echo')
        .send({ message: 'hello' })
        .expect(200);

      expect(response.body).toEqual({ message: 'hello' });
    });

    it('when the message is missing, then it answers 400', async () => {
      await request(httpServer()).post('/test/echo').send({}).expect(400);
    });

    it('when the message is over the maximum length, then it answers 400', async () => {
      await request(httpServer())
        .post('/test/echo')
        .send({ message: 'm'.repeat(MAX_ECHO_MESSAGE_LENGTH + 1) })
        .expect(400);
    });
  });

  describe('OpenAPI document', () => {
    it('when GET /test/ping is documented, then its 200 body is the fixed pong reply', () => {
      expect(responseSchemaOf(openApiDocumentOf(app), '/test/ping', 'get', '200')).toEqual({
        type: 'object',
        properties: { message: { type: 'string', enum: [PING_MESSAGE] } },
        required: ['message'],
        additionalProperties: false,
      });
    });

    it.each([
      ['/test/echo/{message}', 'get'],
      ['/test/echo', 'post'],
    ] as const)('when %s %s is documented, then its 200 body is the echo reply', (path, method) => {
      expect(responseSchemaOf(openApiDocumentOf(app), path, method, '200')).toEqual(
        ECHO_REPLY_SCHEMA,
      );
    });

    it('when the POST echo route is documented, then its request body comes from the request schema', () => {
      expect(requestBodySchemaOf(openApiDocumentOf(app), '/test/echo', 'post')).toEqual({
        type: 'object',
        properties: {
          message: { type: 'string', minLength: 1, maxLength: MAX_ECHO_MESSAGE_LENGTH },
        },
        required: ['message'],
      });
    });

    it('when the POST echo route is documented, then it does not claim a 201 because nothing is created', () => {
      expect(documentedStatusesOf(openApiDocumentOf(app), '/test/echo', 'post')).not.toContain(
        '201',
      );
    });

    it.each([
      ['/test/echo/{message}', 'get'],
      ['/test/echo', 'post'],
    ] as const)(
      'when %s %s is documented, then it declares its 400 validation failure',
      (path, method) => {
        expect(documentedStatusesOf(openApiDocumentOf(app), path, method)).toContain('400');
      },
    );
  });
});
