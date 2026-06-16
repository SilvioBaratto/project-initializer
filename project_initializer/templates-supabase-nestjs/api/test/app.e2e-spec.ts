import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/prisma/prisma.service';
import { AuthService } from '../src/modules/auth/auth.service';
import { getQueueToken } from '@nestjs/bullmq';

// Satisfy ConfigModule env validation without a live database or Supabase connection.
process.env.DATABASE_URL = 'postgresql://localhost:5432/test';
process.env.DIRECT_URL = 'postgresql://localhost:5432/test';
process.env.SUPABASE_URL = 'https://test.supabase.co';
process.env.SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_test_e2e';

const mockPrismaService = {
  $connect: jest.fn().mockResolvedValue(undefined),
  $disconnect: jest.fn().mockResolvedValue(undefined),
  onModuleInit: jest.fn().mockResolvedValue(undefined),
  onModuleDestroy: jest.fn().mockResolvedValue(undefined),
  isHealthy: jest.fn().mockResolvedValue(true),
};

// Override AuthService so the guard does not make live Supabase network calls.
const mockAuthService = {
  getUser: jest.fn().mockResolvedValue({
    id: 'e2e-user-id',
    email: 'e2e@test.com',
    role: 'authenticated',
  }),
};

const mockChatQueue = {
  add: jest.fn().mockResolvedValue({ id: 'e2e-job-1' }),
  getJob: jest.fn().mockResolvedValue({
    getState: jest.fn().mockResolvedValue('completed'),
    returnvalue: { answer: 'stub answer' },
  }),
  close: jest.fn().mockResolvedValue(undefined),
};

describe('AppModule supabase (e2e)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const module: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    })
      .overrideProvider(PrismaService)
      .useValue(mockPrismaService)
      .overrideProvider(AuthService)
      .useValue(mockAuthService)
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

  // Protected route — SupabaseAuthGuard calls AuthService.getUser which is mocked to succeed
  it('when GET /api/v1/test/ping is called with a Bearer token, returns 200 with { message: "pong" }', () => {
    return request(app.getHttpServer())
      .get('/api/v1/test/ping')
      .set('Authorization', 'Bearer valid-supabase-jwt')
      .expect(200)
      .expect((res) => {
        expect(res.body).toHaveProperty('message', 'pong');
      });
  });

  // Protected route — missing auth header must be rejected (guard still checks header existence)
  it('when GET /api/v1/test/ping is called without an Authorization header, returns 401', () => {
    return request(app.getHttpServer())
      .get('/api/v1/test/ping')
      .expect(401);
  });

  // Protected route — enqueue a chat job with a valid (mocked) token
  it('when POST /api/v1/chat/jobs is called with a Bearer token and body, returns 201 with { jobId }', () => {
    return request(app.getHttpServer())
      .post('/api/v1/chat/jobs')
      .set('Authorization', 'Bearer valid-supabase-jwt')
      .send({ user_question: 'Hello' })
      .expect(201)
      .expect((res) => {
        expect(res.body).toHaveProperty('jobId');
        expect(typeof res.body.jobId).toBe('string');
      });
  });

  // Protected route — poll job status with valid (mocked) token
  it('when GET /api/v1/chat/jobs/:id is called with a Bearer token, returns 200 with jobId, state and result', () => {
    return request(app.getHttpServer())
      .get('/api/v1/chat/jobs/e2e-job-1')
      .set('Authorization', 'Bearer valid-supabase-jwt')
      .expect(200)
      .expect((res) => {
        expect(res.body).toHaveProperty('jobId', 'e2e-job-1');
        expect(res.body).toHaveProperty('state');
        expect(res.body).toHaveProperty('result');
      });
  });
});
