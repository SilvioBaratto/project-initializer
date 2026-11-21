/**
 * Validates src/modules/monitoring/queue-dashboard-auth.ts.
 */
import type { Server } from 'node:http';
import { Controller, Get, INestApplication } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import type { BaseEnv } from '../../config/env.base';
import {
  createQueueDashboardMiddleware,
  QueueDashboardCredentials,
  queueDashboardCredentials,
} from './queue-dashboard-auth';

const CREDENTIALS: QueueDashboardCredentials = { user: 'ops', password: 'a-long-dashboard-secret' };

@Controller()
class DashboardProbeController {
  @Get()
  probe(): string {
    return 'dashboard';
  }
}

async function createApp(credentials?: QueueDashboardCredentials): Promise<INestApplication> {
  const moduleRef = await Test.createTestingModule({
    controllers: [DashboardProbeController],
  }).compile();
  const app = moduleRef.createNestApplication();
  app.use(createQueueDashboardMiddleware(credentials));
  await app.init();
  return app;
}

function configWith(values: Record<string, string>): ConfigService<BaseEnv, true> {
  return new ConfigService<BaseEnv, true>(values);
}

describe('queueDashboardCredentials', () => {
  it('when a password is configured, then the user and password are returned', () => {
    const config = configWith({
      QUEUE_MONITOR_USER: 'ops',
      QUEUE_MONITOR_PASSWORD: CREDENTIALS.password,
    });

    expect(queueDashboardCredentials(config)).toEqual(CREDENTIALS);
  });

  it('when no password is configured, then there are no credentials', () => {
    expect(queueDashboardCredentials(configWith({ QUEUE_MONITOR_USER: 'ops' }))).toBeUndefined();
  });

  it('when the password is an empty string, then there are no credentials', () => {
    const config = configWith({ QUEUE_MONITOR_USER: 'ops', QUEUE_MONITOR_PASSWORD: '' });

    expect(queueDashboardCredentials(config)).toBeUndefined();
  });
});

describe('createQueueDashboardMiddleware', () => {
  let app: INestApplication | undefined;

  afterEach(async () => {
    await app?.close();
    app = undefined;
  });

  const server = () => (app as INestApplication).getHttpServer() as Server;

  describe('without credentials', () => {
    beforeEach(async () => {
      app = await createApp();
    });

    it('when the dashboard is requested, then it answers 404 as if it did not exist', async () => {
      const response = await request(server()).get('/');

      expect(response.status).toBe(404);
      expect(response.text).not.toContain('dashboard');
    });

    it('when the dashboard is requested, then the 404 uses the shared JSON error body', async () => {
      const response = await request(server()).get('/');

      expect(response.headers['content-type']).toContain('application/json');
      expect(response.body).toMatchObject({
        statusCode: 404,
        error: 'Not Found',
        message: 'Not Found',
      });
    });

    it('when basic auth is presented anyway, then it still answers 404', async () => {
      const response = await request(server()).get('/').auth('admin', 'admin');

      expect(response.status).toBe(404);
    });
  });

  describe('with credentials', () => {
    beforeEach(async () => {
      app = await createApp(CREDENTIALS);
    });

    it('when no Authorization header is sent, then it answers 401 with a basic challenge', async () => {
      const response = await request(server()).get('/');

      expect(response.status).toBe(401);
      expect(response.headers['www-authenticate']).toMatch(/^Basic/);
    });

    it('when the password is wrong, then it answers 401', async () => {
      const response = await request(server()).get('/').auth(CREDENTIALS.user, 'wrong-password');

      expect(response.status).toBe(401);
    });

    it('when the user is wrong, then it answers 401', async () => {
      const response = await request(server()).get('/').auth('intruder', CREDENTIALS.password);

      expect(response.status).toBe(401);
    });

    it('when the credentials match, then the request reaches the dashboard', async () => {
      const response = await request(server())
        .get('/')
        .auth(CREDENTIALS.user, CREDENTIALS.password);

      expect(response.status).toBe(200);
      expect(response.text).toBe('dashboard');
    });
  });
});
