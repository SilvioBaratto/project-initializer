import { randomUUID } from 'node:crypto';
import request from 'supertest';
import { AUTH_GUARDS } from '../src/app.auth';
import { ANONYMOUS_ACTOR_ID, AuditLogger } from '../src/common/audit/audit-logger';
import { INSUFFICIENT_SCOPE_MESSAGE } from '../src/common/auth/auth-messages';
import { INTERNAL_ERROR_MESSAGE, ROUTE_NOT_FOUND_MESSAGE } from '../src/common/filters/error-body';
import { VALIDATION_FAILED_MESSAGE } from '../src/common/filters/schema-validation.exception';
import {
  ITEM_AUDIT_ACTIONS,
  ITEM_NOT_FOUND_MESSAGE,
  MAX_ITEM_DESCRIPTION_LENGTH,
} from '../src/modules/items/item.constants';
import { createE2eApp, E2eApp, httpServerOf } from './support/create-e2e-app';
import { sendRawRequest } from './support/raw-request';
import { RolesProbeController } from './support/roles-probe.controller';
import { TEST_BEARER_TOKEN, TEST_USER } from './support/test-doubles';

/** Every field the shared error body may carry; a 404 carries no `errors`. */
const ERROR_BODY_KEYS = ['statusCode', 'error', 'message', 'path', 'timestamp', 'requestId'];

/**
 * Validates the HTTP surface that every auth variant shares: routing, validation, error bodies and
 * the item flow, with a verifier that accepts `TEST_BEARER_TOKEN`.
 */
describe('API (e2e)', () => {
  let e2e: E2eApp;

  const authorization = `Bearer ${TEST_BEARER_TOKEN}`;
  const get = (path: string) =>
    request(httpServerOf(e2e.app)).get(path).set('Authorization', authorization);
  const post = (path: string) =>
    request(httpServerOf(e2e.app)).post(path).set('Authorization', authorization);
  const put = (path: string) =>
    request(httpServerOf(e2e.app)).put(path).set('Authorization', authorization);
  const del = (path: string) =>
    request(httpServerOf(e2e.app)).delete(path).set('Authorization', authorization);

  // Audit lines are written at info whatever LOG_LEVEL says, so a run would print them; the spy
  // keeps the output clean and shows which records the routes ask for.
  let auditRecord: jest.SpyInstance;

  beforeAll(async () => {
    auditRecord = jest.spyOn(AuditLogger.prototype, 'record').mockImplementation();
    e2e = await createE2eApp({ controllers: [RolesProbeController] });
  });

  afterAll(async () => {
    await e2e.app.close();
    auditRecord.mockRestore();
  });

  describe('health and ping', () => {
    it('when liveness is called without an Authorization header, then it answers 200', async () => {
      const response = await request(httpServerOf(e2e.app)).get('/api/v1/health/liveness');

      expect(response.status).toBe(200);
      expect(response.body).toMatchObject({ status: 'ok' });
    });

    it('when ping is called, then it answers pong', async () => {
      const response = await get('/api/v1/test/ping');

      expect(response.status).toBe(200);
      expect(response.body).toEqual({ message: 'pong' });
    });
  });

  describe('items', () => {
    it('when an item is created, read, updated and deleted, then each step reflects the previous one', async () => {
      const created = await post('/api/v1/items').send({ name: ' Widget ', description: 'first' });
      expect(created.status).toBe(201);
      expect(created.body).toMatchObject({ name: 'Widget', description: 'first' });
      const itemPath = `/api/v1/items/${(created.body as { id: string }).id}`;

      const fetched = await get(itemPath);
      expect(fetched.body).toEqual(created.body);

      const listed = await get('/api/v1/items');
      expect(listed.status).toBe(200);
      expect(listed.body).toEqual(expect.arrayContaining([created.body]));

      const renamed = await put(itemPath).send({ name: 'Renamed' });
      expect(renamed.status).toBe(200);
      expect(renamed.body).toMatchObject({ name: 'Renamed', description: 'first' });

      expect((await del(itemPath)).status).toBe(204);
      const afterDelete = await get(itemPath);
      expect(afterDelete.status).toBe(404);
      expect(afterDelete.body).toMatchObject({ message: ITEM_NOT_FOUND_MESSAGE });
    });

    it('when an item is created, updated and deleted, then each action reaches the audit trail with the caller id', async () => {
      const actorId = AUTH_GUARDS.length > 0 ? TEST_USER.id : ANONYMOUS_ACTOR_ID;
      auditRecord.mockClear();

      const created = await post('/api/v1/items').send({ name: 'audited' });
      const itemId = (created.body as { id: string }).id;
      await put(`/api/v1/items/${itemId}`).send({ name: 'audited again' });
      await del(`/api/v1/items/${itemId}`);

      expect(auditRecord.mock.calls).toEqual([
        [ITEM_AUDIT_ACTIONS.create, itemId, actorId],
        [ITEM_AUDIT_ACTIONS.update, itemId, actorId],
        [ITEM_AUDIT_ACTIONS.delete, itemId, actorId],
      ]);
    });

    it('when the item id is not a UUID, then it answers 400', async () => {
      const response = await get('/api/v1/items/not-a-uuid');

      expect(response.status).toBe(400);
    });

    it('when the item id is an unknown UUID, then it answers 404', async () => {
      const response = await get(`/api/v1/items/${randomUUID()}`);

      expect(response.status).toBe(404);
    });
  });

  describe('error envelope', () => {
    it('when no route matches, then 404 with the fixed message and the shared error shape', async () => {
      const response = await get('/api/v1/missing?token=secret');

      expect(response.status).toBe(404);
      expect(response.body).toMatchObject({
        statusCode: 404,
        error: 'Not Found',
        message: ROUTE_NOT_FOUND_MESSAGE,
        path: '/api/v1/missing',
      });
      expect(JSON.stringify(response.body)).not.toContain('secret');
    });

    it.each([
      ['get', '/nope?token=secret', '/nope'],
      ['get', '/', '/'],
      ['post', '/nope', '/nope'],
      ['delete', '/nope', '/nope'],
      ['get', '/docs-x', '/docs-x'],
      ['get', '/api/v1x/foo', '/api/v1x/foo'],
      ['get', '/api/v1/missing', '/api/v1/missing'],
      ['post', '/api/v1/missing?token=secret', '/api/v1/missing'],
    ] as const)(
      'when %s %s matches no route, then it answers the JSON 404 body whether or not the path is under the prefix',
      async (method, url, path) => {
        const response = await request(httpServerOf(e2e.app))[method](url);
        const body = response.body as Record<string, unknown>;

        expect(response.status).toBe(404);
        expect(response.headers['content-type']).toMatch(/^application\/json/);
        expect(body).toMatchObject({
          statusCode: 404,
          error: 'Not Found',
          message: ROUTE_NOT_FOUND_MESSAGE,
          path,
        });
        expect(typeof body.timestamp).toBe('string');
        expect(ERROR_BODY_KEYS).toEqual(expect.arrayContaining(Object.keys(body)));
        expect(response.text).not.toContain('secret');
      },
    );

    it('when an absolute-form request target carries credentials, then the 404 body names only the path', async () => {
      const raw = await sendRawRequest(
        e2e.app,
        'GET http://user:hunter2@localhost/api/v1/missing?token=secret HTTP/1.1',
      );

      expect(raw).toMatch(/^HTTP\/1\.1 404 /);
      expect(raw).toContain('"path":"/api/v1/missing"');
      expect(raw).not.toMatch(/hunter2|secret/);
    });

    it('when an item body is invalid, then 400 names the rejected field', async () => {
      const response = await post('/api/v1/items').send({ name: '   ' });

      expect(response.status).toBe(400);
      expect(response.body).toMatchObject({
        statusCode: 400,
        error: 'Bad Request',
        message: VALIDATION_FAILED_MESSAGE,
        errors: [{ path: 'name', message: 'Too small: expected string to have >=1 characters' }],
      });
    });

    it('when several fields of a body are invalid, then 400 lists each of them once, in order', async () => {
      const response = await post('/api/v1/items').send({
        name: 5,
        description: 'd'.repeat(MAX_ITEM_DESCRIPTION_LENGTH + 1),
      });

      expect(response.status).toBe(400);
      expect((response.body as { errors: unknown }).errors).toEqual([
        { path: 'name', message: 'Invalid input: expected string, received number' },
        {
          path: 'description',
          message: `Too big: expected string to have <=${MAX_ITEM_DESCRIPTION_LENGTH} characters`,
        },
      ]);
    });

    it('when a path parameter is invalid, then 400 names it like a body field', async () => {
      const response = await get('/api/v1/items/not-a-uuid');

      expect(response.status).toBe(400);
      expect((response.body as { errors: unknown }).errors).toEqual([
        { path: 'id', message: 'Invalid UUID' },
      ]);
    });

    it('when the whole update body is rejected, then the field error has an empty path', async () => {
      const response = await put(`/api/v1/items/${randomUUID()}`).send({});

      expect(response.status).toBe(400);
      expect((response.body as { errors: unknown }).errors).toEqual([
        { path: '', message: 'At least one field must be provided' },
      ]);
    });

    it('when the repository fails unexpectedly, then 500 with a generic message and no internals', async () => {
      const findAll = jest
        .spyOn(e2e.items, 'findAll')
        .mockRejectedValueOnce(new Error('connection to db.internal refused, key sk-secret-123'));

      const response = await get('/api/v1/items');
      findAll.mockRestore();

      expect(response.status).toBe(500);
      expect(response.body).toMatchObject({ statusCode: 500, message: INTERNAL_ERROR_MESSAGE });
      expect(response.body).not.toHaveProperty('stack');
      expect(JSON.stringify(response.body)).not.toContain('sk-secret-123');
    });
  });

  describe('role-protected routes', () => {
    // The base variant wires no authentication, so no caller has an identity and every @Roles
    // route stays closed; an auth variant resolves TEST_USER, who holds the role `user`.
    const callerIsIdentified = AUTH_GUARDS.length > 0;

    it('when a route has no @Roles, then the caller passes', async () => {
      const response = await get('/api/v1/roles-probe/open');

      expect(response.status).toBe(200);
    });

    it('when a route requires a role the caller holds, then it passes exactly when the variant identifies callers', async () => {
      const response = await get('/api/v1/roles-probe/member');

      expect(response.status).toBe(callerIsIdentified ? 200 : 403);
    });

    it('when a route requires a role the caller lacks, then 403 with the generic message that names no role', async () => {
      const response = await get('/api/v1/roles-probe/admin');

      expect(response.status).toBe(403);
      expect(response.body).toMatchObject({ message: INSUFFICIENT_SCOPE_MESSAGE });
    });
  });
});
