import { Module } from '@nestjs/common';
import { BullBoardModule } from '@bull-board/nestjs';
import { BullMQAdapter } from '@bull-board/api/bullMQAdapter';

// Auth / guard interaction — Bull Board mounts via Express middleware, NOT a Nest controller.
// The global APP_GUARD (ThrottlerGuard / AuthGuard / SupabaseAuthGuard) only covers Nest routes
// and does NOT protect middleware-mounted paths such as the dashboard.
//
// Security decision per variant (configured in each variant's AppModule):
//   - Base template (no auth): open to local operators — intentional for local dev;
//     protect with a reverse-proxy allowlist in any internet-exposed environment.
//   - Token / Supabase overlays: use express-basic-auth middleware in BullBoardModule.forRoot
//     driven by QUEUE_MONITOR_USER / QUEUE_MONITOR_PASSWORD env vars (see each overlay's
//     AppModule for the wiring).
//
// Resolved path: BullBoardModule.forRoot uses route '/admin/queues'. With setGlobalPrefix('api/v1')
// in main.ts the full path becomes /api/v1/admin/queues (the root module prepends the global prefix).

/**
 * Registers the chat queue with the Bull Board instance.
 *
 * BullBoardModule.forRoot (with route and ExpressAdapter) is declared in each variant's
 * AppModule so each variant can configure auth middleware independently.
 * This module adds only the forFeature registration for the chat queue.
 */
@Module({
  imports: [
    BullBoardModule.forFeature({
      name: 'chat',
      adapter: BullMQAdapter,
    }),
  ],
})
export class MonitoringModule {}
