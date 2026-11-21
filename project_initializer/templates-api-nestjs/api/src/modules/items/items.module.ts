import { Module } from '@nestjs/common';
import { AuditModule } from '../../common/audit/audit.module';
import { PrismaModule } from '../../prisma/prisma.module';
import { ITEM_REPOSITORY } from './item.repository';
import { ItemsController } from './items.controller';
import { ItemsService } from './items.service';
import { PrismaItemRepository } from './prisma-item.repository';

/** Sample CRUD resource backed by Postgres; replace `PrismaItemRepository` to change the store. */
@Module({
  imports: [PrismaModule, AuditModule],
  controllers: [ItemsController],
  providers: [ItemsService, { provide: ITEM_REPOSITORY, useClass: PrismaItemRepository }],
})
export class ItemsModule {}
