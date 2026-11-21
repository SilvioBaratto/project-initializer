import type { Server } from 'node:http';
import { INestApplication } from '@nestjs/common';
import { APP_INTERCEPTOR, APP_PIPE } from '@nestjs/core';
import { Test } from '@nestjs/testing';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { cleanupOpenApiDoc, ZodSerializerInterceptor, ZodValidationPipe } from 'nestjs-zod';
import request from 'supertest';
import { MAX_ECHO_MESSAGE_LENGTH } from './dto/echo.dto';
import { TestController } from './test.controller';

/** Validates src/modules/test/test.controller.ts through real routing, validation and serialization. */
describe('TestController', () => {
  let app: INestApplication;
  // Nest types the server as `any`; one cast here keeps every supertest call typed.
  const httpServer = (): Server => app.getHttpServer() as Server;

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({
      controllers: [TestController],
      providers: [
        { provide: APP_PIPE, useClass: ZodValidationPipe },
        { provide: APP_INTERCEPTOR, useClass: ZodSerializerInterceptor },
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
    function responseCodesOf(path: string, method: 'get' | 'post'): string[] {
      const document = cleanupOpenApiDoc(
        SwaggerModule.createDocument(app, new DocumentBuilder().build()),
      );
      return Object.keys(document.paths[path]?.[method]?.responses ?? {});
    }

    it.each([
      ['/test/ping', 'get'],
      ['/test/echo/{message}', 'get'],
      ['/test/echo', 'post'],
    ] as const)(
      'when %s %s is documented, then it declares its 200 success response',
      (path, method) => {
        expect(responseCodesOf(path, method)).toContain('200');
      },
    );

    it('when the POST echo route is documented, then it does not claim a 201 because nothing is created', () => {
      expect(responseCodesOf('/test/echo', 'post')).not.toContain('201');
    });

    it.each([
      ['/test/echo/{message}', 'get'],
      ['/test/echo', 'post'],
    ] as const)(
      'when %s %s is documented, then it declares its 400 validation failure',
      (path, method) => {
        expect(responseCodesOf(path, method)).toContain('400');
      },
    );
  });
});
