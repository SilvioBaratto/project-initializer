import { CustomDecorator, SetMetadata } from '@nestjs/common';

/** Metadata key `RolesGuard` reads to find which roles may call a route. */
export const ROLES_KEY = 'roles';

/**
 * Restricts a route, or a whole controller, to callers that hold at least one of the given roles.
 *
 * Enforced by the global `RolesGuard`, which runs after the authentication guard and therefore
 * sees the verified identity. A route without this decorator is open to every authenticated
 * caller. A decorator on the handler replaces one on the controller; the two are not merged.
 * Role names are compared exactly, case included, against `AuthenticatedUser.roles`.
 *
 * The check fails closed: a caller without an identity (the base template wires no
 * authentication) and an empty role list both get 403, so a route cannot become open by mistake.
 *
 * @example
 * ```ts
 * @Controller('reports')
 * export class ReportsController {
 *   @Get('payroll')
 *   @Roles('finance', 'admin')
 *   payroll(): PayrollReport {
 *     return this.reportsService.payroll();
 *   }
 * }
 * ```
 *
 * @param roles - Role names that grant access; one match is enough.
 */
export const Roles = (...roles: string[]): CustomDecorator<string> => SetMetadata(ROLES_KEY, roles);
