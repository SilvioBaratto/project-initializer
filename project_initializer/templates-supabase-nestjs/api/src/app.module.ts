import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import { BullBoardModule } from '@bull-board/nestjs';
import { ExpressAdapter } from '@bull-board/express';
import { ConfigModule } from '@nestjs/config';
import { validate } from './config/env.validation';
import { ThrottlerModule, ThrottlerGuard } from '@nestjs/throttler';
import { APP_GUARD, APP_PIPE, APP_INTERCEPTOR } from '@nestjs/core';
import { ZodValidationPipe, ZodSerializerInterceptor } from 'nestjs-zod';
import { LoggerModule } from 'nestjs-pino';
import { PrismaModule } from './prisma/prisma.module';
import { HealthModule } from './modules/health/health.module';
import { TestModule } from './modules/test/test.module';
import { ChatbotModule } from './modules/chatbot/chatbot.module';
import { AuthModule } from './modules/auth/auth.module';
import { SupabaseAuthGuard } from './modules/auth/auth.guard';
import { MonitoringModule } from './modules/monitoring/monitoring.module';
import { loggerConfig } from './config/logger.config';
import basicAuth from 'express-basic-auth';

// Bull Board auth guard note (IMPORTANT):
// The dashboard at /api/v1/admin/queues is mounted as Express middleware — it does
// NOT pass through the NestJS APP_GUARD pipeline (SupabaseAuthGuard only covers Nest routes).
// Gate the dashboard with HTTP Basic auth via QUEUE_MONITOR_USER / QUEUE_MONITOR_PASSWORD
// env vars. If QUEUE_MONITOR_PASSWORD is unset the dashboard is open; set it in .env
// for any internet-exposed deployment.
function buildMonitoringMiddleware() {
  const user = process.env.QUEUE_MONITOR_USER ?? 'admin';
  const pass = process.env.QUEUE_MONITOR_PASSWORD ?? '';
  if (!pass) return undefined;
  return basicAuth({ challenge: true, users: { [user]: pass } });
}

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      // The project .env lives at the repo root (one level above api/). Check it
      // first, then a local api/.env fallback. In Docker no file is read — compose
      // env_file injects the vars as real environment variables (validate() reads
      // process.env either way).
      envFilePath: ['../.env', '.env'],
      validate: validate,
    }),
    BullModule.forRoot({
      connection: {
        host: process.env.REDIS_HOST ?? 'localhost',
        port: Number(process.env.REDIS_PORT ?? 6379),
      },
    }),
    BullBoardModule.forRoot({
      route: '/admin/queues',
      adapter: ExpressAdapter,
      middleware: buildMonitoringMiddleware(),
    }),
    LoggerModule.forRoot(loggerConfig),
    PrismaModule,
    ThrottlerModule.forRoot([
      {
        ttl: 60000,
        limit: 100,
      },
    ]),
    HealthModule,
    TestModule,
    ChatbotModule,
    AuthModule,
    MonitoringModule,
  ],
  providers: [
    {
      provide: APP_GUARD,
      useClass: ThrottlerGuard,
    },
    {
      provide: APP_GUARD,
      useClass: SupabaseAuthGuard,
    },
    {
      provide: APP_PIPE,
      useClass: ZodValidationPipe,
    },
    {
      provide: APP_INTERCEPTOR,
      useClass: ZodSerializerInterceptor,
    },
  ],
})
export class AppModule {}
