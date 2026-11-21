/**
 * Validates src/modules/items/dto/item.dto.ts.
 */
import { CreateItemSchema, ItemResponseSchema, UpdateItemSchema, toItemResponse } from './item.dto';
import type { Item } from '../item.entity';
import { MAX_ITEM_DESCRIPTION_LENGTH, MAX_ITEM_NAME_LENGTH } from '../item.constants';

const ITEM_ID = 'f47ac10b-58cc-4372-a567-0e02b2c3d479';

const storedItem: Item = {
  id: ITEM_ID,
  name: 'widget',
  description: null,
  createdAt: new Date('2026-01-02T03:04:05.678Z'),
  updatedAt: new Date('2026-02-03T04:05:06.789Z'),
};

describe('CreateItemSchema', () => {
  it('when the name has surrounding spaces, then it is trimmed', () => {
    expect(CreateItemSchema.parse({ name: '  widget  ' }).name).toBe('widget');
  });

  it('when the name is blank after trimming, then it is rejected', () => {
    expect(CreateItemSchema.safeParse({ name: '   ' }).success).toBe(false);
  });

  it('when the name is exactly the maximum length, then it is accepted', () => {
    const name = 'n'.repeat(MAX_ITEM_NAME_LENGTH);

    expect(CreateItemSchema.safeParse({ name }).success).toBe(true);
  });

  it('when the name is one character over the maximum, then it is rejected', () => {
    const name = 'n'.repeat(MAX_ITEM_NAME_LENGTH + 1);

    expect(CreateItemSchema.safeParse({ name }).success).toBe(false);
  });

  it('when the description is exactly the maximum length, then it is accepted', () => {
    const description = 'd'.repeat(MAX_ITEM_DESCRIPTION_LENGTH);

    expect(CreateItemSchema.safeParse({ name: 'widget', description }).success).toBe(true);
  });

  it('when the description is one character over the maximum, then it is rejected', () => {
    const description = 'd'.repeat(MAX_ITEM_DESCRIPTION_LENGTH + 1);

    expect(CreateItemSchema.safeParse({ name: 'widget', description }).success).toBe(false);
  });

  it.each([undefined, null])('when the description is %s, then it is accepted', (description) => {
    expect(CreateItemSchema.safeParse({ name: 'widget', description }).success).toBe(true);
  });
});

describe('UpdateItemSchema', () => {
  it('when only the description is sent, then the name stays absent from the result', () => {
    const changes = UpdateItemSchema.parse({ description: 'new' });

    expect(changes).toEqual({ description: 'new' });
  });

  it('when the description is null, then it is kept so the stored value can be cleared', () => {
    expect(UpdateItemSchema.parse({ description: null })).toEqual({ description: null });
  });

  it('when the body is empty, then it is rejected as a no-op', () => {
    expect(UpdateItemSchema.safeParse({}).success).toBe(false);
  });

  it('when the name is over the maximum length, then it is rejected', () => {
    const name = 'n'.repeat(MAX_ITEM_NAME_LENGTH + 1);

    expect(UpdateItemSchema.safeParse({ name }).success).toBe(false);
  });

  it('when only unknown fields are sent, then it is rejected as a no-op', () => {
    expect(UpdateItemSchema.safeParse({ unknown: 1 }).success).toBe(false);
  });
});

describe('ItemResponseSchema', () => {
  it('when an unknown field is present, then it is stripped from the result', () => {
    const response = ItemResponseSchema.parse({ ...toItemResponse(storedItem), password: 'leak' });

    expect(response).not.toHaveProperty('password');
  });

  it('when a timestamp is not ISO 8601, then it is rejected', () => {
    const response = { ...toItemResponse(storedItem), created_at: '02/01/2026' };

    expect(ItemResponseSchema.safeParse(response).success).toBe(false);
  });

  it('when the id is not a UUID, then it is rejected', () => {
    const response = { ...toItemResponse(storedItem), id: '1' };

    expect(ItemResponseSchema.safeParse(response).success).toBe(false);
  });
});

describe('toItemResponse', () => {
  it('when an item is mapped, then timestamps are rendered as ISO 8601 and names are snake_case', () => {
    expect(toItemResponse(storedItem)).toEqual({
      id: ITEM_ID,
      name: 'widget',
      description: null,
      created_at: '2026-01-02T03:04:05.678Z',
      updated_at: '2026-02-03T04:05:06.789Z',
    });
  });

  it('when an item is mapped, then the result satisfies the response schema', () => {
    expect(ItemResponseSchema.safeParse(toItemResponse(storedItem)).success).toBe(true);
  });
});
