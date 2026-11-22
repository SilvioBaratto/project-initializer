import 'reflect-metadata';
import { Controller, Get, HttpStatus } from '@nestjs/common';
import request from 'supertest';
import { createE2eApp, E2eApp, httpServerOf } from '../test/support/create-e2e-app';
import { TEST_BEARER_TOKEN } from '../test/support/test-doubles';
import { INTERNAL_ERROR_MESSAGE } from './common/filters/error-body';
import { ResponseSchema } from './common/serialization/response-schema.decorator';
import { ItemResponseSchema } from './modules/items/dto/item.dto';

/**
 * Validates the response whitelist of src/modules/items/dto/item.dto.ts and the serializer that
 * src/app.module.ts registers for every route.
 */
const validItem = {
  id: 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
  name: 'test item',
  description: 'desc',
  created_at: '2024-01-01T00:00:00.000Z',
  updated_at: '2024-01-01T00:00:00.000Z',
};

const MALFORMED_ID = 'not-a-uuid';
const LEAKED_SECRET = 'leaked-password';

@Controller('serialization-probe')
class SerializationProbeController {
  @Get('violating')
  @ResponseSchema(HttpStatus.OK, ItemResponseSchema)
  violating(): unknown {
    return { ...validItem, id: MALFORMED_ID, password: LEAKED_SECRET };
  }
}

describe('Response serialization', () => {
  it('when the item schema parses an object with an extra secret field, then the secret is stripped', () => {
    const result = ItemResponseSchema.parse({ ...validItem, password: 'leak' });

    expect(result).not.toHaveProperty('password');
    expect(result).toMatchObject({ id: validItem.id, name: validItem.name });
  });

  it('when a list is serialized, then every element is stripped of extra secret fields', () => {
    const result = ItemResponseSchema.array().parse([{ ...validItem, password: 'leak' }]);

    expect(result).toHaveLength(1);
    expect(result[0]).not.toHaveProperty('password');
  });

  it('when the item schema is handed an array, then it rejects it', () => {
    // Pins why a list route passes the single-item schema with `many`: the serializer applies it
    // to each element, never to the array as a whole.
    expect(() => ItemResponseSchema.parse([validItem])).toThrow();
  });

  describe('through the application pipeline', () => {
    let e2e: E2eApp;

    beforeAll(async () => {
      e2e = await createE2eApp({ controllers: [SerializationProbeController] });
    });

    afterAll(async () => {
      await e2e.app.close();
    });

    it('when a handler returns data that violates its response schema, then the client gets the generic 500 without fields', async () => {
      const response = await request(httpServerOf(e2e.app))
        .get('/api/v1/serialization-probe/violating')
        .set('Authorization', `Bearer ${TEST_BEARER_TOKEN}`);

      expect(response.status).toBe(HttpStatus.INTERNAL_SERVER_ERROR);
      expect(response.body).toMatchObject({ statusCode: 500, message: INTERNAL_ERROR_MESSAGE });
      expect(response.body).not.toHaveProperty('errors');
      expect(JSON.stringify(response.body)).not.toContain(MALFORMED_ID);
      expect(JSON.stringify(response.body)).not.toContain(LEAKED_SECRET);
    });
  });
});
