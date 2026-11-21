import { Reflector } from '@nestjs/core';
import { Roles, ROLES_KEY } from './roles.decorator';

class ReportsController {
  @Roles('finance', 'admin')
  payroll(): void {}

  @Roles()
  sealed(): void {}

  open(): void {}
}

@Roles('admin')
class AdminController {
  handle(): void {}
}

/** Validates src/common/auth/roles.decorator.ts Roles. */
describe('Roles', () => {
  const reflector = new Reflector();

  it('when a handler is decorated, then its roles are stored under ROLES_KEY in order', () => {
    expect(reflector.get<string[]>(ROLES_KEY, ReportsController.prototype.payroll)).toEqual([
      'finance',
      'admin',
    ]);
  });

  it('when a handler is decorated with no role, then an empty list is stored', () => {
    expect(reflector.get<string[]>(ROLES_KEY, ReportsController.prototype.sealed)).toEqual([]);
  });

  it('when a handler is not decorated, then nothing is stored', () => {
    expect(
      reflector.get<string[] | undefined>(ROLES_KEY, ReportsController.prototype.open),
    ).toBeUndefined();
  });

  it('when a class is decorated, then its roles are stored on the class', () => {
    expect(reflector.get<string[]>(ROLES_KEY, AdminController)).toEqual(['admin']);
  });
});
