import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/prisma/prisma.service';
import { getQueueToken } from '@nestjs/bullmq';

// Satisfy ConfigModule env validation without a live database or Redis.
const E2E_AUTH_TOKEN = 'e2e-test-token-min16chars';
process.env.DATABASE_URL = 'postgresql://localhost:5432/test';
process.env.DIRECT_URL = 'postgresql://localhost:5432/test';
process.env.AUTH_TOKEN = E2E_AUTH_TOKEN;

const mockPrismaService = {
  $connect: jest.fn().mockResolvedValue(undefined),
  $disconnect: jest.fn().mockResolvedValue(undefined),
  onModuleInit: jest.fn().mockResolvedValue(undefined),
  onModuleDestroy: jest.fn().mockResolvedValue(undefined),
  isHealthy: jest.fn().mockResolvedValue(true),
};

const mockChatQueue = {
  add: jest.fn().mockResolvedValue({ id: 'e2e-job-1' }),
  getJob: jest.fn().mockResolvedValue({
    getState: jest.fn().mockResolvedValue('completed'),
    returnvalue: { answer: 'stub answer' },
  }),
  close: jest.fn().mockResolvedValue(undefined),
};

describe('AppModule token (e2e)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const module: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    })
      .overrideProvider(PrismaService)
      .useValue(mockPrismaService)
      .overrideProvider(getQueueToken('chat'))
      .useValue(mockChatQueue)
      .compile();

    app = module.createNestApplication();
    app.setGlobalPrefix('api/v1');
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  // Public route — no auth required (health endpoints carry @Public())
  it('when GET /api/v1/health/liveness is called without auth, returns 200', () => {
    return request(app.getHttpServer())
      .get('/api/v1/health/liveness')
      .expect(200);
  });

  // Protected route — must supply the correct Bearer token
  it('when GET /api/v1/test/ping is called with valid Bearer token, returns 200 with { message: "pong" }', () => {
    return request(app.getHttpServer())
      .get('/api/v1/test/ping')
      .set('Authorization', `Bearer ${E2E_AUTH_TOKEN}`)
      .expect(200)
      .expect((res) => {
        expect(res.body).toHaveProperty('message', 'pong');
      });
  });

  // Protected route — wrong token must be rejected
  it('when GET /api/v1/test/ping is called with an invalid Bearer token, returns 401', () => {
    return request(app.getHttpServer())
      .get('/api/v1/test/ping')
      .set('Authorization', 'Bearer wrong-token')
      .expect(401);
  });

  // Protected route — missing auth header must be rejected
  it('when GET /api/v1/test/ping is called without an Authorization header, returns 401', () => {
    return request(app.getHttpServer())
      .get('/api/v1/test/ping')
      .expect(401);
  });

  // Protected route — enqueue a chat job with valid token
  it('when POST /api/v1/chat/jobs is called with a valid Bearer token and body, returns 201 with { jobId }', () => {
    return request(app.getHttpServer())
      .post('/api/v1/chat/jobs')
      .set('Authorization', `Bearer ${E2E_AUTH_TOKEN}`)
      .send({ user_question: 'Hello' })
      .expect(201)
      .expect((res) => {
        expect(res.body).toHaveProperty('jobId');
        expect(typeof res.body.jobId).toBe('string');
      });
  });

  // Protected route — poll job status with valid token
  it('when GET /api/v1/chat/jobs/:id is called with a valid Bearer token, returns 200 with jobId, state and result', () => {
    return request(app.getHttpServer())
      .get('/api/v1/chat/jobs/e2e-job-1')
      .set('Authorization', `Bearer ${E2E_AUTH_TOKEN}`)
      .expect(200)
      .expect((res) => {
        expect(res.body).toHaveProperty('jobId', 'e2e-job-1');
        expect(res.body).toHaveProperty('state');
        expect(res.body).toHaveProperty('result');
      });
  });
});
