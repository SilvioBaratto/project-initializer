import { TEST_ENTRA_API_AUDIENCE, TEST_ENTRA_API_SCOPE } from '../../test/support/auth-test-env';
import { requiredScopeName } from './entra-scope';

/** Validates src/config/entra-scope.ts requiredScopeName. */
describe('requiredScopeName', () => {
  it.each([
    [TEST_ENTRA_API_SCOPE, TEST_ENTRA_API_SCOPE],
    [`${TEST_ENTRA_API_AUDIENCE}/${TEST_ENTRA_API_SCOPE}`, TEST_ENTRA_API_SCOPE],
    [`  ${TEST_ENTRA_API_SCOPE}  `, TEST_ENTRA_API_SCOPE],
    [`${TEST_ENTRA_API_AUDIENCE}/`, ''],
    ['', ''],
  ])('when the configured scope is %j, then the bare name is %j', (configured, expected) => {
    expect(requiredScopeName(configured)).toBe(expected);
  });
});
