import { emailAddressSchema, toOptionalEmail } from './optional-email';

/** Validates src/common/auth/optional-email.ts toOptionalEmail. */
describe('toOptionalEmail', () => {
  it.each([
    'ada@example.com',
    'first!last@example.com',
    'a#b@example.com',
    'dev@localhost',
    'x@xn--bcher-kva.de',
  ])('when the claim is the valid address %j, then it is returned unchanged', (address) => {
    expect(toOptionalEmail(address)).toBe(address);
  });

  it.each([
    ['absent', undefined],
    ['empty', ''],
    ['a display name', 'Ada Lovelace'],
    ['a phone number', '+15550100'],
    ['an address without a domain', 'ada@'],
    ['an internationalised domain in Unicode form', 'müller@bücher.de'],
  ])('when the claim is %s, then there is no email', (_label, raw) => {
    expect(toOptionalEmail(raw)).toBeUndefined();
  });

  it('when an address is accepted, then the response schema accepts it too', () => {
    const address = 'first!last@example.com';

    expect(emailAddressSchema.safeParse(toOptionalEmail(address)).success).toBe(true);
  });
});
