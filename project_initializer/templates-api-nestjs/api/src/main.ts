import { NestFactory, HttpAdapterHost } from '@nestjs/core';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { cleanupOpenApiDoc } from 'nestjs-zod';
import helmet from 'helmet';
import { AppModule } from './app.module';
import { HttpExceptionFilter } from './common/filters/http-exception.filter';
import { PrismaClientExceptionFilter } from './common/filters/prisma-exception.filter';
import { TransformInterceptor } from './common/interceptors/transform.interceptor';

async function bootstrap() {
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
    .setVersion('1.0.0')
    .addBearerAuth()
    .build();
  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('docs', app, cleanupOpenApiDoc(document));

  // Health endpoint at root (outside /api/v1 prefix)
  const expressApp = app.getHttpAdapter().getInstance();
  expressApp.get('/', (_req: any, res: any) => {
    res.json({
      message: 'Welcome to the NestJS API Template!',
      version: '1.0.0',
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
  console.log(`Application is running on: http://localhost:${port}`);
  console.log(`Swagger docs: http://localhost:${port}/docs`);
}
bootstrap();
