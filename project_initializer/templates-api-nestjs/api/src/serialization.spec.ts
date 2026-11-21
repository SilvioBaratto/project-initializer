import 'reflect-metadata';
import { ZodSerializerDto } from 'nestjs-zod';
import { EchoResponseDto, PingResponseDto } from './modules/test/dto/echo.dto';
import { ItemResponseDto, ItemResponseSchema } from './modules/items/dto/item.dto';
import { ChatbotController } from './modules/chatbot/chatbot.controller';
import { ItemsController } from './modules/items/items.controller';
import { TestController } from './modules/test/test.controller';

/** Validates the response whitelist: schemas strip unknown fields and JSON handlers are serialized. */
const validItem = {
  id: 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
  name: 'test item',
  description: 'desc',
  created_at: '2024-01-01T00:00:00.000Z',
  updated_at: '2024-01-01T00:00:00.000Z',
};

/**
 * Reads the key `ZodSerializerDto` stores its DTO under by decorating a probe, so the spec follows
 * the library instead of repeating its private metadata key.
 */
function serializerMetadataKey(): string {
  class Probe {
    @ZodSerializerDto(EchoResponseDto)
    handler(): void {}
  }
  const [key] = Reflect.getMetadataKeys(Probe.prototype.handler) as string[];
  return key;
}

const serializerDtoOf = (handler: object): unknown =>
  Reflect.getMetadata(serializerMetadataKey(), handler);

describe('Response serialization', () => {
  it('when the item schema parses an object with an extra secret field, then the secret is stripped', () => {
    const result = ItemResponseSchema.parse({ ...validItem, password: 'leak' });

    expect(result).not.toHaveProperty('password');
    expect(result).toMatchObject({ id: validItem.id, name: validItem.name });
  });

  it('when a list is serialized, then every element is stripped of extra secret fields', () => {
    const result = ItemResponseDto.schema.array().parse([{ ...validItem, password: 'leak' }]);

    expect(result).toHaveLength(1);
    expect(result[0]).not.toHaveProperty('password');
  });

  it('when the item schema is handed an array, then it rejects it', () => {
    // Pins why the list route must declare an array DTO instead of reusing the single-item one.
    expect(() => ItemResponseSchema.parse([validItem])).toThrow();
  });

  it.each(['findOne', 'create', 'update'] as const)(
    'when the %s handler is inspected, then its serializer DTO is the item DTO',
    (handler) => {
      expect(serializerDtoOf(ItemsController.prototype[handler])).toBe(ItemResponseDto);
    },
  );

  it('when the findAll handler is inspected, then its serializer DTO is the array of the item DTO', () => {
    expect(serializerDtoOf(ItemsController.prototype.findAll)).toEqual([ItemResponseDto]);
  });

  it.each([
    ['ping', TestController.prototype.ping, PingResponseDto],
    ['echoGet', TestController.prototype.echoGet, EchoResponseDto],
    ['echoPost', TestController.prototype.echoPost, EchoResponseDto],
  ])('when the %s handler is inspected, then it has a serializer DTO', (_name, handler, dto) => {
    expect(serializerDtoOf(handler)).toBe(dto);
  });

  it('when the streamChat handler is inspected, then no serializer DTO is attached', () => {
    // The SSE handler writes to the raw response, so a serializer would parse a stream it never sees.
    expect(serializerDtoOf(ChatbotController.prototype.streamChat)).toBeUndefined();
  });
});
