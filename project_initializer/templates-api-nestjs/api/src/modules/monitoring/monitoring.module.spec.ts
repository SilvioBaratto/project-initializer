/**
 * Validates src/modules/monitoring/monitoring.module.ts: the chat queue is registered and the
 * dashboard is closed unless a password is configured.
 */
import type { Server } from 'node:http';
import { Global, INestApplication, Module } from '@nestjs/common';
import { getQueueToken } from '@nestjs/bullmq';
import { ConfigModule } from '@nestjs/config';
import { Test } from '@nestjs/testing';
import { createBullBoard } from '@bull-board/api';
import {
  BULL_BOARD_ADAPTER,
  BULL_BOARD_INSTANCE,
  BullBoardServerAdapter,
} from '@bull-board/nestjs';
import request from 'supertest';
import { CHAT_QUEUE_NAME } from '../chatbot/chat.constants';
import { MonitoringModule, QUEUE_DASHBOARD_ROUTE } from './monitoring.module';

// What Bull Board serves under its route besides the page itself: the JSON API that lists queues
// and job payloads, a state-changing job action, and the static assets.
const DASHBOARD_SUBPATHS: ReadonlyArray<readonly ['get' | 'put', string]> = [
  ['get', `${QUEUE_DASHBOARD_ROUTE}/api/queues`],
  ['put', `${QUEUE_DASHBOARD_ROUTE}/api/queues/${CHAT_QUEUE_NAME}/job-1/retry/failed`],
  ['get', `${QUEUE_DASHBOARD_ROUTE}/static/js/app.js`],
];

const DASHBOARD_USER = 'ops';
const DASHBOARD_PASSWORD = 'a-long-dashboard-secret';

// Bull Board's BullMQAdapter rejects a queue that reports no BullMQ version.
const fakeChatQueue = {
  name: CHAT_QUEUE_NAME,
  metaValues: { version: 'bullmq_test' },
};

let addQueue: jest.SpyInstance;

// The real queue comes from ChatbotModule's BullModule, which needs Redis; the feature module of
// Bull Board only looks the queue up by token, so a global provider is enough.
@Global()
@Module({
  providers: [{ provide: getQueueToken(CHAT_QUEUE_NAME), useValue: fakeChatQueue }],
  exports: [getQueueToken(CHAT_QUEUE_NAME)],
})
class FakeChatQueueModule {}

async function createApp(env: Record<string, string>): Promise<INestApplication> {
  const moduleRef = await Test.createTestingModule({
    imports: [
      FakeChatQueueModule,
      ConfigModule.forRoot({ isGlobal: true, ignoreEnvFile: true, load: [() => env] }),
      MonitoringModule,
    ],
  })
    .overrideProvider(BULL_BOARD_INSTANCE)
    .useFactory({
      inject: [BULL_BOARD_ADAPTER],
      // A real board keeps the dashboard router functional, the spy records what gets registered.
      factory: (serverAdapter: BullBoardServerAdapter) => {
        const board = createBullBoard({ queues: [], serverAdapter });
        addQueue = jest.spyOn(board, 'addQueue');
        return board;
      },
    })
    .compile();
  const app = moduleRef.createNestApplication();
  await app.init();
  return app;
}

describe('MonitoringModule', () => {
  let app: INestApplication | undefined;

  afterEach(async () => {
    await app?.close();
    app = undefined;
  });

  const server = () => (app as INestApplication).getHttpServer() as Server;

  it('when the module initialises, then the chat queue is registered once with Bull Board', async () => {
    app = await createApp({});

    expect(addQueue).toHaveBeenCalledTimes(1);
    const [adapter] = addQueue.mock.calls[0] as [{ getName(): string }];
    expect(adapter.getName()).toBe(CHAT_QUEUE_NAME);
  });

  it('when no dashboard password is configured, then the dashboard answers 404', async () => {
    app = await createApp({});

    const response = await request(server()).get(QUEUE_DASHBOARD_ROUTE);

    expect(response.status).toBe(404);
  });

  it('when a password is configured and none is sent, then the dashboard asks for basic auth', async () => {
    app = await createApp({
      QUEUE_MONITOR_USER: DASHBOARD_USER,
      QUEUE_MONITOR_PASSWORD: DASHBOARD_PASSWORD,
    });

    const response = await request(server()).get(QUEUE_DASHBOARD_ROUTE);

    expect(response.status).toBe(401);
    expect(response.headers['www-authenticate']).toMatch(/^Basic/);
  });

  it('when a password is configured and the wrong one is sent, then the dashboard answers 401', async () => {
    app = await createApp({
      QUEUE_MONITOR_USER: DASHBOARD_USER,
      QUEUE_MONITOR_PASSWORD: DASHBOARD_PASSWORD,
    });

    const response = await request(server())
      .get(QUEUE_DASHBOARD_ROUTE)
      .auth(DASHBOARD_USER, 'wrong-password');

    expect(response.status).toBe(401);
  });

  it('when the configured credentials are sent, then the request passes the gate', async () => {
    app = await createApp({
      QUEUE_MONITOR_USER: DASHBOARD_USER,
      QUEUE_MONITOR_PASSWORD: DASHBOARD_PASSWORD,
    });

    const response = await request(server())
      .get(QUEUE_DASHBOARD_ROUTE)
      .auth(DASHBOARD_USER, DASHBOARD_PASSWORD);

    expect(response.status).not.toBe(401);
    expect(response.status).not.toBe(404);
  });

  it.each(DASHBOARD_SUBPATHS)(
    'when a password is configured and none is sent, then %s %s answers 401',
    async (method, path) => {
      app = await createApp({
        QUEUE_MONITOR_USER: DASHBOARD_USER,
        QUEUE_MONITOR_PASSWORD: DASHBOARD_PASSWORD,
      });

      const response = await request(server())[method](path);

      expect(response.status).toBe(401);
    },
  );

  it.each(DASHBOARD_SUBPATHS)(
    'when no dashboard password is configured, then %s %s answers 404',
    async (method, path) => {
      app = await createApp({});

      const response = await request(server())[method](path);

      expect(response.status).toBe(404);
    },
  );
});
