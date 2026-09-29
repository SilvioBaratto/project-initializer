import 'reflect-metadata';
import { ItemResponseSchema } from './dto/item.dto';
import { TestController } from './test.controller';
import { ChatbotController } from '../chatbot/chatbot.controller';

// The metadata key @SerializeOptions writes under (from @nestjs/common's class-serializer).
// StandardSchemaSerializerInterceptor reads the { schema } stored here to shape the response.
const CLASS_SERIALIZER_OPTIONS = 'class_serializer:options';

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

  // findAll returns an array and StandardSchemaSerializerInterceptor applies the single-item
  // schema to each element, so element-level whitelisting is what protects list responses.
  it('when a list element carries an extra secret field, parsing it with the item schema strips it', () => {
    const items = [{ ...validItem, password: 'leak' }].map((i) =>
      ItemResponseSchema.parse(i),
    );

    expect(items[0]).not.toHaveProperty('password');
    expect(items[0]).toMatchObject({ id: validItem.id, name: validItem.name });
  });

  it('when findOne is inspected, its response schema is ItemResponseSchema', () => {
    const options = Reflect.getMetadata(
      CLASS_SERIALIZER_OPTIONS,
      TestController.prototype.findOne,
    );

    expect(options?.schema).toBe(ItemResponseSchema);
  });

  it('when findAll is inspected, its response schema is the single-item ItemResponseSchema', () => {
    const options = Reflect.getMetadata(
      CLASS_SERIALIZER_OPTIONS,
      TestController.prototype.findAll,
    );

    expect(options?.schema).toBe(ItemResponseSchema);
  });

  it('when the SSE streamChat handler is inspected, it carries no serializer schema', () => {
    // The SSE handler writes to the response stream directly; running the interceptor's
    // schema over an event stream would corrupt it, so it must not be decorated.
    const options = Reflect.getMetadata(
      CLASS_SERIALIZER_OPTIONS,
      ChatbotController.prototype.streamChat,
    );

    expect(options).toBeUndefined();
  });
});
