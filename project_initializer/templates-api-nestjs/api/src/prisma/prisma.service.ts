import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { PrismaClient } from '@generated/prisma';
import { PrismaPg } from '@prisma/adapter-pg';
import { deriveSslOption } from './prisma-ssl.util';

@Injectable()
export class PrismaService extends PrismaClient implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(PrismaService.name);

  constructor() {
    super({ adapter: PrismaService.buildAdapter() });
  }

  private static buildAdapter(): PrismaPg {
    const connectionString = process.env.DATABASE_URL;
    const ssl = deriveSslOption(connectionString);
    return new PrismaPg({ connectionString, ssl });
  }

  async onModuleInit() {
    await this.$connect();
    this.logger.log('Database connection established');
  }

  async onModuleDestroy() {
    await this.$disconnect();
    this.logger.log('Database connection closed');
  }

  async isHealthy(): Promise<boolean> {
    try {
      await this.$queryRaw`SELECT 1`;
      return true;
    } catch (error) {
      // Log before swallowing: this only reports up as `database: down` in the
      // readiness probe, so without the reason a failure here is undiagnosable
      // from the outside. The driver error carries no credentials.
      this.logger.error(
        `Database health check failed: ${(error as Error).message}`,
      );
      return false;
    }
  }
}
