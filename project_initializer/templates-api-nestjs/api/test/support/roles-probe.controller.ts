import { Controller, Get } from '@nestjs/common';
import { Roles } from '../../src/common/auth/roles.decorator';
import { TEST_USER } from './test-doubles';

/** Role that {@link TEST_USER}, the identity of the shared test verifier, holds. */
const [TEST_USER_ROLE = ''] = TEST_USER.roles;

/** Answer of every probe route that lets the caller through. */
const PROBE_ANSWER = { ok: true };

/**
 * Routes that exist only in tests, to show that `RolesGuard` is wired into the whole application
 * and not just into a unit test: one without `@Roles`, one the test user may call and one it may
 * not. Nothing in the application's own controllers carries `@Roles`.
 */
@Controller('roles-probe')
export class RolesProbeController {
  @Get('open')
  open(): typeof PROBE_ANSWER {
    return PROBE_ANSWER;
  }

  @Get('member')
  @Roles(TEST_USER_ROLE)
  member(): typeof PROBE_ANSWER {
    return PROBE_ANSWER;
  }

  @Get('admin')
  @Roles('admin')
  admin(): typeof PROBE_ANSWER {
    return PROBE_ANSWER;
  }
}
