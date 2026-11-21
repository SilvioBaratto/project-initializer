import { randomUUID } from 'node:crypto';
import request from 'supertest';
import { AUTH_GUARDS } from '../src/app.auth';
import { ANONYMOUS_ACTOR_ID, AuditLogger } from '../src/common/audit/audit-logger';
import { INSUFFICIENT_SCOPE_MESSAGE } from '../src/common/auth/auth-messages';
import {
  CHAT_UNAVAILABLE_MESSAGE,
  MAX_CHAT_QUESTION_LENGTH,
} from '../src/modules/chatbot/chat.constants';
import { ITEM_AUDIT_ACTIONS, ITEM_NOT_FOUND_MESSAGE } from '../src/modules/items/item.constants';
import { createE2eApp, E2eApp, httpServerOf } from './support/create-e2e-app';
import { RolesProbeController } from './support/roles-probe.controller';
import { FAKE_CHAT_ANSWER, TEST_BEARER_TOKEN, TEST_USER } from './support/test-doubles';

/**
 * Validates the HTTP surface that every auth variant shares: routing, validation, error bodies and
 * the chat and item flows, with a verifier that accepts `TEST_BEARER_TOKEN`.
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

  afterEach(() => {
    e2e.chatCompletion.failWith = undefined;
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

  describe('chat', () => {
    it('when a question is posted, then the answer comes back with 200', async () => {
      const response = await post('/api/v1/chat').send({ user_question: 'Hello' });

      expect(response.status).toBe(200);
      expect(response.body).toEqual({ answer: FAKE_CHAT_ANSWER });
    });

    it('when the completion provider fails, then 503 with a generic message and no internals', async () => {
      e2e.chatCompletion.failWith = new Error('upstream rejected key sk-secret-123');

      const response = await post('/api/v1/chat').send({ user_question: 'Hello' });

      expect(response.status).toBe(503);
      expect(response.body).toMatchObject({ statusCode: 503, message: CHAT_UNAVAILABLE_MESSAGE });
      expect(response.body).not.toHaveProperty('stack');
      expect(JSON.stringify(response.body)).not.toContain('sk-secret-123');
    });

    it('when the question exceeds the maximum length, then it answers 400', async () => {
      const response = await post('/api/v1/chat').send({
        user_question: 'x'.repeat(MAX_CHAT_QUESTION_LENGTH + 1),
      });

      expect(response.status).toBe(400);
    });

    it('when the question is blank, then it answers 400', async () => {
      const response = await post('/api/v1/chat').send({ user_question: '   ' });

      expect(response.status).toBe(400);
    });
  });

  describe('chat jobs', () => {
    it('when a job is enqueued, then 202 with an id whose status is waiting without a result', async () => {
      const accepted = await post('/api/v1/chat/jobs').send({ user_question: 'Hello' });
      expect(accepted.status).toBe(202);
      const { jobId } = accepted.body as { jobId: string };

      const status = await get(`/api/v1/chat/jobs/${jobId}`);

      expect(status.status).toBe(200);
      expect(status.body).toEqual({ jobId, state: 'waiting', result: null });
    });

    it('when the job has completed, then its status carries the answer', async () => {
      const accepted = await post('/api/v1/chat/jobs').send({ user_question: 'Hello' });
      const { jobId } = accepted.body as { jobId: string };
      const job = e2e.chatQueue.jobs.get(jobId);
      if (!job) {
        throw new Error('the enqueued job is missing from the fake queue');
      }
      job.state = 'completed';
      job.returnvalue = { answer: FAKE_CHAT_ANSWER };

      const status = await get(`/api/v1/chat/jobs/${jobId}`);

      expect(status.body).toEqual({
        jobId,
        state: 'completed',
        result: { answer: FAKE_CHAT_ANSWER },
      });
    });

    it('when the job id is unknown, then it answers 404', async () => {
      const response = await get(`/api/v1/chat/jobs/${randomUUID()}`);

      expect(response.status).toBe(404);
    });

    it('when the job id is not a UUID, then it answers 400', async () => {
      const response = await get('/api/v1/chat/jobs/not-a-uuid');

      expect(response.status).toBe(400);
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
