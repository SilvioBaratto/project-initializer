import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/prisma/prisma.service';
import { getQueueToken } from '@nestjs/bullmq';

// Satisfy ConfigModule env validation without a live database
process.env.DATABASE_URL = 'postgresql://localhost:5432/test';
process.env.DIRECT_URL = 'postgresql://localhost:5432/test';

const mockPrismaService = {
  $connect: jest.fn().mockResolvedValue(undefined),
  $disconnect: jest.fn().mockResolvedValue(undefined),
  onModuleInit: jest.fn().mockResolvedValue(undefined),
  onModuleDestroy: jest.fn().mockResolvedValue(undefined),
  isHealthy: jest.fn().mockResolvedValue(true),
};

// Stub the chat queue so no live Redis connection is required.
const mockChatQueue = {
  add: jest.fn().mockResolvedValue({ id: 'e2e-job-1' }),
  getJob: jest.fn().mockResolvedValue({
    getState: jest.fn().mockResolvedValue('completed'),
    returnvalue: { answer: 'stub answer' },
  }),
  // ioredis lifecycle methods expected by BullMQ internals
  close: jest.fn().mockResolvedValue(undefined),
};

describe('AppModule (e2e)', () => {
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

  it('when GET /api/v1/test/ping is called, returns 200 with { message: "pong" }', () => {
    return request(app.getHttpServer())
      .get('/api/v1/test/ping')
      .expect(200)
      .expect({ message: 'pong' });
  });

  it('when POST /api/v1/chat/jobs is called with a valid body, returns 201 with { jobId }', () => {
    return request(app.getHttpServer())
      .post('/api/v1/chat/jobs')
      .send({ user_question: 'Hello' })
      .expect(201)
      .expect((res) => {
        expect(res.body).toHaveProperty('jobId');
        expect(typeof res.body.jobId).toBe('string');
      });
  });

  it('when GET /api/v1/chat/jobs/:id is called, returns 200 with jobId, state and result', () => {
    return request(app.getHttpServer())
      .get('/api/v1/chat/jobs/e2e-job-1')
      .expect(200)
      .expect((res) => {
        expect(res.body).toHaveProperty('jobId', 'e2e-job-1');
        expect(res.body).toHaveProperty('state');
        expect(res.body).toHaveProperty('result');
      });
  });
});
