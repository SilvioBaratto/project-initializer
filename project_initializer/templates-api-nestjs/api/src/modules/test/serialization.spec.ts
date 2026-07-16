import 'reflect-metadata';
import {
  ItemResponseSchema,
  ItemListResponseSchema,
  ItemListResponseDto,
} from './dto/item.dto';
import { TestController } from './test.controller';

const ZOD_SERIALIZER_DTO_OPTIONS = 'ZOD_SERIALIZER_DTO_OPTIONS';

const validItem = {
  id: 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
  name: 'test item',
  description: 'desc',
  created_at: '2024-01-01T00:00:00.000Z',
  updated_at: '2024-01-01T00:00:00.000Z',
};

describe('Response serialization', () => {
  it('when ItemResponseSchema parses an object with an extra secret field, the secret field is stripped', () => {
    const result = ItemResponseSchema.parse({ ...validItem, password: 'leak' });

    expect(result).not.toHaveProperty('password');
    expect(result).toMatchObject({ id: validItem.id, name: validItem.name });
  });

  it('when findOne handler is inspected, ZodSerializerDto metadata is present', () => {
    const metadata = Reflect.getMetadata(
      ZOD_SERIALIZER_DTO_OPTIONS,
      TestController.prototype.findOne,
    );

    expect(metadata).toBeDefined();
  });

  it('when streamChat handler is inspected, ZodSerializerDto metadata is absent', () => {
    // SSE handler bypasses the interceptor and must not carry the decorator
    const ChatbotControllerModule = require('../chatbot/chatbot.controller');
    const { ChatbotController } = ChatbotControllerModule;
    const metadata = Reflect.getMetadata(
      ZOD_SERIALIZER_DTO_OPTIONS,
      ChatbotController.prototype.streamChat,
    );

    expect(metadata).toBeUndefined();
  });

  // findAll returns an array, so its serializer DTO must wrap the item schema in
  // z.array. Decorating it with the single-object ItemResponseDto made every
  // GET /test/items 500 with "expected object, received array" — even for an
  // empty list, since the shape is wrong before any element is looked at.
  it('when ItemListResponseSchema parses a list, it succeeds', () => {
    const result = ItemListResponseSchema.parse([validItem]);

    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({ id: validItem.id, name: validItem.name });
  });

  it('when ItemListResponseSchema parses an empty list, it succeeds', () => {
    expect(ItemListResponseSchema.parse([])).toEqual([]);
  });

  it('when a list element carries an extra secret field, it is stripped', () => {
    const result = ItemListResponseSchema.parse([{ ...validItem, password: 'leak' }]);

    expect(result[0]).not.toHaveProperty('password');
  });

  it('when the item schema is handed an array, it rejects it', () => {
    // Pins the reason findAll needs its own DTO rather than reusing ItemResponseDto.
    expect(() => ItemResponseSchema.parse([validItem])).toThrow();
  });

  it('when findAll handler is inspected, its serializer DTO is the list DTO', () => {
    const metadata = Reflect.getMetadata(
      ZOD_SERIALIZER_DTO_OPTIONS,
      TestController.prototype.findAll,
    );

    expect(metadata).toBe(ItemListResponseDto);
  });
});
