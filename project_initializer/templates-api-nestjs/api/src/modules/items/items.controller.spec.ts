/**
 * Validates src/modules/items/items.controller.ts through real routing, validation and serialization.
 */
import type { Server } from 'node:http';
import { CanActivate, ExecutionContext, INestApplication, NotFoundException } from '@nestjs/common';
import { APP_GUARD, APP_INTERCEPTOR, APP_PIPE } from '@nestjs/core';
import { Test } from '@nestjs/testing';
import { ZodSerializerInterceptor, ZodValidationPipe } from 'nestjs-zod';
import request from 'supertest';
import { ANONYMOUS_ACTOR_ID } from '../../common/audit/audit-logger';
import type { AuthenticatedRequest } from '../../common/auth/authenticated-user';
import type { Item } from './item.entity';
import { ITEM_NOT_FOUND_MESSAGE, MAX_ITEM_NAME_LENGTH } from './item.constants';
import { ItemsController } from './items.controller';
import { ItemsService } from './items.service';

const ITEM_ID = 'f47ac10b-58cc-4372-a567-0e02b2c3d479';

const storedItem: Item = {
  id: ITEM_ID,
  name: 'widget',
  description: null,
  createdAt: new Date('2026-01-02T03:04:05.678Z'),
  updatedAt: new Date('2026-02-03T04:05:06.789Z'),
};

const widgetBody = {
  id: ITEM_ID,
  name: 'widget',
  description: null,
  created_at: '2026-01-02T03:04:05.678Z',
  updated_at: '2026-02-03T04:05:06.789Z',
};

const SUBJECT_ID = 'subject-1';
const SUBJECT_EMAIL = 'person@example.com';
const SUBJECT_HEADER = 'x-test-subject';

// Stands in for the authentication guard of an auth variant, which attaches the verified identity.
const identityStub: CanActivate = {
  canActivate(context: ExecutionContext): boolean {
    const request = context.switchToHttp().getRequest<AuthenticatedRequest>();
    if (request.headers[SUBJECT_HEADER] !== undefined) {
      request.user = { id: SUBJECT_ID, email: SUBJECT_EMAIL, roles: [] };
    }
    return true;
  },
};

describe('ItemsController', () => {
  const service = {
    findAll: jest.fn(),
    findOne: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    remove: jest.fn(),
  };
  let app: INestApplication;
  // Nest types the server as `any`; one cast here keeps every supertest call typed.
  const httpServer = (): Server => app.getHttpServer() as Server;

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({
      controllers: [ItemsController],
      providers: [
        { provide: ItemsService, useValue: service },
        { provide: APP_GUARD, useValue: identityStub },
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

  beforeEach(() => {
    jest.resetAllMocks();
  });

  describe('GET /items', () => {
    it('when items exist, then they are serialized with snake_case ISO timestamps', async () => {
      service.findAll.mockResolvedValue([storedItem]);

      const response = await request(httpServer()).get('/items').expect(200);

      expect(response.body).toEqual([widgetBody]);
    });

    it('when no items exist, then an empty array is returned', async () => {
      service.findAll.mockResolvedValue([]);

      const response = await request(httpServer()).get('/items').expect(200);

      expect(response.body).toEqual([]);
    });
  });

  describe('POST /items', () => {
    it('when the body is valid, then the item is created with 201', async () => {
      service.create.mockResolvedValue(storedItem);

      const response = await request(httpServer())
        .post('/items')
        .send({ name: '  widget  ' })
        .expect(201);

      expect(service.create).toHaveBeenCalledWith({ name: 'widget' }, ANONYMOUS_ACTOR_ID);
      expect(response.body).toEqual(widgetBody);
    });

    it('when the caller is authenticated, then the service gets the opaque subject id and never the email', async () => {
      service.create.mockResolvedValue(storedItem);

      await request(httpServer())
        .post('/items')
        .set(SUBJECT_HEADER, 'yes')
        .send({ name: 'widget' })
        .expect(201);

      expect(service.create).toHaveBeenCalledWith({ name: 'widget' }, SUBJECT_ID);
      expect(JSON.stringify(service.create.mock.calls)).not.toContain(SUBJECT_EMAIL);
    });

    it('when the name is over the maximum length, then it answers 400 and creates nothing', async () => {
      await request(httpServer())
        .post('/items')
        .send({ name: 'n'.repeat(MAX_ITEM_NAME_LENGTH + 1) })
        .expect(400);

      expect(service.create).not.toHaveBeenCalled();
    });

    it('when the service result carries an extra field, then it is stripped from the response', async () => {
      service.create.mockResolvedValue({ ...storedItem, password: 'leak' });

      const response = await request(httpServer())
        .post('/items')
        .send({ name: 'widget' })
        .expect(201);

      expect(response.body).not.toHaveProperty('password');
    });
  });

  describe('GET /items/:id', () => {
    it('when the item exists, then it is returned', async () => {
      service.findOne.mockResolvedValue(storedItem);

      const response = await request(httpServer()).get(`/items/${ITEM_ID}`).expect(200);

      expect(service.findOne).toHaveBeenCalledWith(ITEM_ID);
      expect(response.body).toEqual(widgetBody);
    });

    it('when the id is not a UUID, then it answers 400 and does not call the service', async () => {
      await request(httpServer()).get('/items/not-a-uuid').expect(400);

      expect(service.findOne).not.toHaveBeenCalled();
    });

    it('when the service reports the item missing, then the 404 passes through', async () => {
      service.findOne.mockRejectedValue(new NotFoundException(ITEM_NOT_FOUND_MESSAGE));

      const response = await request(httpServer()).get(`/items/${ITEM_ID}`).expect(404);

      expect(response.body).toMatchObject({ message: ITEM_NOT_FOUND_MESSAGE });
    });
  });

  describe('PUT /items/:id', () => {
    it('when only some fields are sent, then only those are passed to the service', async () => {
      service.update.mockResolvedValue({ ...storedItem, description: 'new' });

      const response = await request(httpServer())
        .put(`/items/${ITEM_ID}`)
        .send({ description: 'new' })
        .expect(200);

      expect(service.update).toHaveBeenCalledWith(
        ITEM_ID,
        { description: 'new' },
        ANONYMOUS_ACTOR_ID,
      );
      expect(response.body).toMatchObject({ description: 'new' });
    });

    it('when the caller is authenticated, then the update carries the subject id', async () => {
      service.update.mockResolvedValue(storedItem);

      await request(httpServer())
        .put(`/items/${ITEM_ID}`)
        .set(SUBJECT_HEADER, 'yes')
        .send({ name: 'renamed' })
        .expect(200);

      expect(service.update).toHaveBeenCalledWith(ITEM_ID, { name: 'renamed' }, SUBJECT_ID);
    });

    it('when the body is empty, then it answers 400', async () => {
      await request(httpServer()).put(`/items/${ITEM_ID}`).send({}).expect(400);

      expect(service.update).not.toHaveBeenCalled();
    });

    it('when the id is not a UUID, then it answers 400', async () => {
      await request(httpServer()).put('/items/42').send({ name: 'renamed' }).expect(400);

      expect(service.update).not.toHaveBeenCalled();
    });

    it('when the service reports the item missing, then the 404 passes through', async () => {
      service.update.mockRejectedValue(new NotFoundException(ITEM_NOT_FOUND_MESSAGE));

      await request(httpServer()).put(`/items/${ITEM_ID}`).send({ name: 'renamed' }).expect(404);
    });

    it('when PATCH is used instead, then the route does not exist', async () => {
      await request(httpServer()).patch(`/items/${ITEM_ID}`).send({ name: 'renamed' }).expect(404);
    });
  });

  describe('DELETE /items/:id', () => {
    it('when the item exists, then it answers 204 with no body', async () => {
      service.remove.mockResolvedValue(undefined);

      const response = await request(httpServer()).delete(`/items/${ITEM_ID}`).expect(204);

      expect(service.remove).toHaveBeenCalledWith(ITEM_ID, ANONYMOUS_ACTOR_ID);
      expect(response.body).toEqual({});
    });

    it('when the caller is authenticated, then the deletion carries the subject id', async () => {
      service.remove.mockResolvedValue(undefined);

      await request(httpServer())
        .delete(`/items/${ITEM_ID}`)
        .set(SUBJECT_HEADER, 'yes')
        .expect(204);

      expect(service.remove).toHaveBeenCalledWith(ITEM_ID, SUBJECT_ID);
    });

    it('when the service reports the item missing, then the 404 passes through', async () => {
      service.remove.mockRejectedValue(new NotFoundException(ITEM_NOT_FOUND_MESSAGE));

      await request(httpServer()).delete(`/items/${ITEM_ID}`).expect(404);
    });

    it('when the id is not a UUID, then it answers 400', async () => {
      await request(httpServer()).delete('/items/nope').expect(400);

      expect(service.remove).not.toHaveBeenCalled();
    });
  });
});
