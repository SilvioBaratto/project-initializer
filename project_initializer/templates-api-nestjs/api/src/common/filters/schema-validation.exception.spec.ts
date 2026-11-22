/** Validates src/common/filters/schema-validation.exception.ts. */
import { BadRequestException, HttpStatus, StandardSchemaValidationPipe } from '@nestjs/common';
import { z } from 'zod';
import { SchemaValidationException } from './schema-validation.exception';

const NameSchema = z.object({ name: z.string().min(1) });

describe('SchemaValidationException', () => {
  it('when built from issues, then it is a 400 with the fixed message that keeps every issue', () => {
    const issues = [{ message: 'Required', path: ['name'] }];

    const exception = new SchemaValidationException(issues);

    expect(exception).toBeInstanceOf(BadRequestException);
    expect(exception.getStatus()).toBe(HttpStatus.BAD_REQUEST);
    expect(exception.message).toBe('Validation failed');
    expect(exception.issues).toBe(issues);
  });

  it('when the native pipe uses it as its exception factory, then a failing body throws it with the schema issues', async () => {
    const pipe = new StandardSchemaValidationPipe({
      exceptionFactory: (issues) => new SchemaValidationException(issues),
    });

    const rejection = pipe.transform({ name: '' }, { type: 'body', schema: NameSchema });

    await expect(rejection).rejects.toBeInstanceOf(SchemaValidationException);
    await expect(rejection).rejects.toMatchObject({
      issues: [expect.objectContaining({ path: ['name'] })],
    });
  });
});
