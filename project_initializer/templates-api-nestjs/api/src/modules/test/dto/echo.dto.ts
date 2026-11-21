import { createZodDto } from 'nestjs-zod';
import { z } from 'zod';

/** Longest message the echo routes accept. */
export const MAX_ECHO_MESSAGE_LENGTH = 500;

/** Reply of `GET /test/ping`. */
export const PING_MESSAGE = 'pong';

const echoMessageSchema = z.string().min(1, 'Message is required').max(MAX_ECHO_MESSAGE_LENGTH);

/** Body of `POST /test/echo`. */
export const EchoRequestSchema = z.object({ message: echoMessageSchema });

/** Path parameter of `GET /test/echo/:message`. */
export const EchoParamSchema = z.object({ message: echoMessageSchema });

/** Reply of both echo routes. */
export const EchoResponseSchema = z.object({ message: z.string() });

/** Reply of `GET /test/ping`. */
export const PingResponseSchema = z.object({ message: z.literal(PING_MESSAGE) });

/** Validated body of `POST /test/echo`. */
export class EchoRequestDto extends createZodDto(EchoRequestSchema) {}

/** Validated path parameter of `GET /test/echo/:message`. */
export class EchoParamDto extends createZodDto(EchoParamSchema) {}

/** Serialized reply of the echo routes. */
export class EchoResponseDto extends createZodDto(EchoResponseSchema) {}

/** Serialized reply of the ping route. */
export class PingResponseDto extends createZodDto(PingResponseSchema) {}
