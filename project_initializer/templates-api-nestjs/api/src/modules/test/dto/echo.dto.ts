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
export type EchoRequestDto = z.infer<typeof EchoRequestSchema>;

/** Validated path parameter of `GET /test/echo/:message`. */
export type EchoParamDto = z.infer<typeof EchoParamSchema>;

/** Serialized reply of the echo routes. */
export type EchoResponseDto = z.infer<typeof EchoResponseSchema>;

/** Serialized reply of the ping route. */
export type PingResponseDto = z.infer<typeof PingResponseSchema>;
