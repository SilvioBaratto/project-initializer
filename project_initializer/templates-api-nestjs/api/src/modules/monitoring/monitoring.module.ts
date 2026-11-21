import { Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { BullBoardModule } from '@bull-board/nestjs';
import { BullMQAdapter } from '@bull-board/api/bullMQAdapter';
import { ExpressAdapter } from '@bull-board/express';
import type { BaseEnv } from '../../config/env.base';
import { CHAT_QUEUE_NAME } from '../chatbot/chat.constants';
import { createQueueDashboardMiddleware, queueDashboardCredentials } from './queue-dashboard-auth';

/** Mount path of the Bull Board dashboard; Nest prepends the global prefix. */
export const QUEUE_DASHBOARD_ROUTE = '/admin/queues';

/** Serves the Bull Board dashboard for the chat queue, closed unless a password is configured. */
@Module({
  imports: [
    // Bull Board mounts as Express middleware, so APP_GUARD and the auth guard never see it. The
    // middleware from queue-dashboard-auth.ts is its only gate and it fails closed.
    BullBoardModule.forRootAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService<BaseEnv, true>) => ({
        route: QUEUE_DASHBOARD_ROUTE,
        adapter: ExpressAdapter,
        middleware: createQueueDashboardMiddleware(queueDashboardCredentials(config)),
      }),
    }),
    BullBoardModule.forFeature({ name: CHAT_QUEUE_NAME, adapter: BullMQAdapter }),
  ],
})
export class MonitoringModule {}
