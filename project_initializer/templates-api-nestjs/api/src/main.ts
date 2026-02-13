import { NestFactory, HttpAdapterHost } from '@nestjs/core';
import { Logger } from '@nestjs/common';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { cleanupOpenApiDoc } from 'nestjs-zod';
import helmet from 'helmet';
import { AppModule } from './app.module';
import { HttpExceptionFilter } from './common/filters/http-exception.filter';
import { PrismaClientExceptionFilter } from './common/filters/prisma-exception.filter';
import { TransformInterceptor } from './common/interceptors/transform.interceptor';

import { join } from 'path';
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { version } = require(join(process.cwd(), 'package.json'));

async function bootstrap() {
  const logger = new Logger('Bootstrap');
  const app = await NestFactory.create(AppModule);

  // Enable graceful shutdown hooks (for Prisma disconnect)
  app.enableShutdownHooks();

  // Security
  app.use(helmet());

  // CORS
  const corsOrigins = process.env.CORS_ORIGINS?.split(',').map((o) => o.trim()) || [
    'http://localhost:4200',
    'http://localhost:4300',
  ];
  app.enableCors({
    origin: corsOrigins,
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
    allowedHeaders: [
      'Authorization',
      'Content-Type',
      'Accept',
      'Origin',
      'User-Agent',
      'X-Requested-With',
      'X-Client-Info',
      'X-Dev-User',
    ],
    exposedHeaders: ['X-Total-Count', 'X-Rate-Limit-Remaining'],
    maxAge: 3600,
  });

  // Global prefix
  app.setGlobalPrefix('api/v1');

  // Global filters (ZodValidationPipe is registered in AppModule)
  const { httpAdapter } = app.get(HttpAdapterHost);
  app.useGlobalFilters(
    new HttpExceptionFilter(),
    new PrismaClientExceptionFilter(httpAdapter),
  );

  // Global interceptors
  app.useGlobalInterceptors(new TransformInterceptor());

  // Swagger documentation
  const config = new DocumentBuilder()
    .setTitle('NestJS API Template')
    .setDescription('Modern API')
    .setVersion(version)
    .addBearerAuth()
    .build();
  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('docs', app, cleanupOpenApiDoc(document));

  // Health endpoint at root (outside /api/v1 prefix)
  const expressApp = app.getHttpAdapter().getInstance();
  expressApp.get('/', (_req: any, res: any) => {
    res.json({
      message: 'Welcome to the NestJS API Template!',
      version,
      status: 'operational',
      environment: process.env.NODE_ENV || 'development',
      api_version: 'v1',
      docs_url: '/docs',
    });
  });
  expressApp.get('/health', (_req: any, res: any) => {
    res.json({ status: 'ok' });
  });

  const port = process.env.PORT || 3000;
  await app.listen(port);
  logger.log(`Application is running on: http://localhost:${port}`);
  logger.log(`Swagger docs: http://localhost:${port}/docs`);
}
bootstrap();
