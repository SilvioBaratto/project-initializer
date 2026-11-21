import { UuidParamSchema } from './uuid-param.dto';

/** Validates src/common/dto/uuid-param.dto.ts. */
describe('UuidParamSchema', () => {
  it('when the id is a UUID, then it is accepted', () => {
    const id = 'f47ac10b-58cc-4372-a567-0e02b2c3d479';

    expect(UuidParamSchema.parse({ id })).toEqual({ id });
  });

  it.each(['', '1', 'not-a-uuid', 'f47ac10b-58cc-4372-a567-0e02b2c3d47', "' OR 1=1 --"])(
    'when the id is %p, then it is rejected',
    (id) => {
      expect(UuidParamSchema.safeParse({ id }).success).toBe(false);
    },
  );

  it('when the id is missing, then it is rejected', () => {
    expect(UuidParamSchema.safeParse({}).success).toBe(false);
  });
});
