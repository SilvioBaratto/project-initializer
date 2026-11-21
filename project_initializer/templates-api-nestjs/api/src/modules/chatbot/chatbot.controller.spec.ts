/**
 * Validates src/modules/chatbot/chatbot.controller.ts.
 */
import 'reflect-metadata';
import type { Server } from 'node:http';
import {
  INestApplication,
  Logger,
  NotFoundException,
  ServiceUnavailableException,
} from '@nestjs/common';
import { APP_INTERCEPTOR, APP_PIPE } from '@nestjs/core';
import { Throttle } from '@nestjs/throttler';
import { Test } from '@nestjs/testing';
import type { Response } from 'express';
import { ZodSerializerInterceptor, ZodValidationPipe } from 'nestjs-zod';
import request from 'supertest';
import { LLM_RATE_LIMIT } from '../../config/rate-limit';
import {
  CHAT_JOB_NOT_FOUND_MESSAGE,
  CHAT_UNAVAILABLE_MESSAGE,
  MAX_CHAT_HISTORY_MESSAGE_LENGTH,
  MAX_CHAT_HISTORY_MESSAGES,
  MAX_CHAT_QUESTION_LENGTH,
} from './chat.constants';
import { ChatJobService } from './chat-job.service';
import { ChatbotController } from './chatbot.controller';
import { ChatbotService } from './chatbot.service';
import type { StreamChunkDto } from './dto/chat.dto';

const SSE_FRAME_END = '\n\n';
const SSE_DATA_PREFIX = 'data: ';
const PROVIDER_SECRET = 'provider said: key sk-secret rejected';
const JOB_ID = '5b0c5f52-3c0b-4d5e-9f6b-0f6c1f6d2a11';
const QUESTION = { user_question: 'Hello' };
const SIGNED_IN_USER = { id: 'user-a', roles: ['user'] };

const chatbotService = { chat: jest.fn(), streamChat: jest.fn() };
const chatJobService = { enqueue: jest.fn(), getStatus: jest.fn() };

async function* chunksOf(...chunks: StreamChunkDto[]): AsyncGenerator<StreamChunkDto> {
  await Promise.resolve();
  yield* chunks;
}

async function* failingAfter(
  chunks: StreamChunkDto[],
  reason: unknown,
): AsyncGenerator<StreamChunkDto> {
  yield* chunksOf(...chunks);
  throw reason;
}

function throttleMetadataOf(handler: object): Map<unknown, unknown> {
  const keys = Reflect.getMetadataKeys(handler).filter((key: unknown) =>
    String(key).startsWith('THROTTLER:'),
  ) as unknown[];
  return new Map(keys.map((key) => [key, Reflect.getMetadata(key as string, handler) as unknown]));
}

class ReferenceThrottle {
  @Throttle(LLM_RATE_LIMIT)
  handler(): void {}
}

describe('ChatbotController', () => {
  let app: INestApplication;
  let controller: ChatbotController;

  beforeEach(async () => {
    jest.resetAllMocks();
    jest.spyOn(Logger.prototype, 'error').mockImplementation(() => undefined);
    const moduleRef = await Test.createTestingModule({
      controllers: [ChatbotController],
      providers: [
        { provide: ChatbotService, useValue: chatbotService },
        { provide: ChatJobService, useValue: chatJobService },
        { provide: APP_PIPE, useClass: ZodValidationPipe },
        { provide: APP_INTERCEPTOR, useClass: ZodSerializerInterceptor },
      ],
    }).compile();
    app = moduleRef.createNestApplication();
    await app.init();
    controller = moduleRef.get(ChatbotController);
  });

  afterEach(async () => {
    await app.close();
    jest.restoreAllMocks();
  });

  const server = () => app.getHttpServer() as Server;

  describe('POST /chat', () => {
    it('when the service answers, then it responds 200 with the answer', async () => {
      chatbotService.chat.mockResolvedValue({ answer: 'Hello from BAML' });

      const response = await request(server()).post('/chat').send(QUESTION);

      expect(response.status).toBe(200);
      expect(response.body).toEqual({ answer: 'Hello from BAML' });
    });

    it('when the service is unavailable, then it responds 503 without a stack', async () => {
      chatbotService.chat.mockRejectedValue(
        new ServiceUnavailableException(CHAT_UNAVAILABLE_MESSAGE),
      );

      const response = await request(server()).post('/chat').send(QUESTION);

      expect(response.status).toBe(503);
      expect(JSON.stringify(response.body)).not.toContain('stack');
    });

    it.each([
      ['an empty question', { user_question: '   ' }],
      ['an oversize question', { user_question: 'q'.repeat(MAX_CHAT_QUESTION_LENGTH + 1) }],
      [
        'too many history messages',
        {
          ...QUESTION,
          conversation_history: {
            messages: Array.from({ length: MAX_CHAT_HISTORY_MESSAGES + 1 }, () => 'm'),
          },
        },
      ],
      [
        'an oversize history message',
        {
          ...QUESTION,
          conversation_history: { messages: ['m'.repeat(MAX_CHAT_HISTORY_MESSAGE_LENGTH + 1)] },
        },
      ],
    ])(
      'when the body has %s, then it responds 400 and never calls the service',
      async (_name, body) => {
        const response = await request(server()).post('/chat').send(body);

        expect(response.status).toBe(400);
        expect(chatbotService.chat).not.toHaveBeenCalled();
      },
    );
  });

  describe('POST /chat/jobs', () => {
    it('when a request is queued, then it responds 202 with the job id for an anonymous owner', async () => {
      chatJobService.enqueue.mockResolvedValue(JOB_ID);

      const response = await request(server()).post('/chat/jobs').send(QUESTION);

      expect(response.status).toBe(202);
      expect(response.body).toEqual({ jobId: JOB_ID });
      expect(chatJobService.enqueue).toHaveBeenCalledWith(QUESTION, null);
    });

    it('when a signed-in user queues a request, then the job is owned by that user', async () => {
      chatJobService.enqueue.mockResolvedValue(JOB_ID);

      await controller.enqueueChat(QUESTION, SIGNED_IN_USER);

      expect(chatJobService.enqueue).toHaveBeenCalledWith(QUESTION, SIGNED_IN_USER.id);
    });
  });

  describe('GET /chat/jobs/:id', () => {
    it('when the job is pending, then it responds 200 with a null result', async () => {
      chatJobService.getStatus.mockResolvedValue({ jobId: JOB_ID, state: 'waiting', result: null });

      const response = await request(server()).get(`/chat/jobs/${JOB_ID}`);

      expect(response.status).toBe(200);
      expect(response.body).toEqual({ jobId: JOB_ID, state: 'waiting', result: null });
    });

    it('when the job is completed, then the answer is part of the body', async () => {
      chatJobService.getStatus.mockResolvedValue({
        jobId: JOB_ID,
        state: 'completed',
        result: { answer: 'Hello from BAML' },
      });

      const response = await request(server()).get(`/chat/jobs/${JOB_ID}`);

      expect(response.body).toEqual({
        jobId: JOB_ID,
        state: 'completed',
        result: { answer: 'Hello from BAML' },
      });
    });

    it('when the id is not a UUID, then it responds 400 and never reaches the queue', async () => {
      const response = await request(server()).get('/chat/jobs/42');

      expect(response.status).toBe(400);
      expect(chatJobService.getStatus).not.toHaveBeenCalled();
    });

    it('when the service reports no such job, then it responds 404', async () => {
      chatJobService.getStatus.mockRejectedValue(new NotFoundException(CHAT_JOB_NOT_FOUND_MESSAGE));

      const response = await request(server()).get(`/chat/jobs/${JOB_ID}`);

      expect(response.status).toBe(404);
    });

    it('when a signed-in user polls, then the lookup is scoped to that user', async () => {
      chatJobService.getStatus.mockResolvedValue({ jobId: JOB_ID, state: 'waiting', result: null });

      await controller.getJobStatus({ id: JOB_ID }, SIGNED_IN_USER);

      expect(chatJobService.getStatus).toHaveBeenCalledWith(JOB_ID, SIGNED_IN_USER.id);
    });
  });

  describe('GET /chat/health', () => {
    it('when it is requested, then the route no longer exists', async () => {
      const response = await request(server()).get('/chat/health');

      expect(response.status).toBe(404);
    });
  });

  describe('rate limiting', () => {
    it.each(['chat', 'streamChat', 'enqueueChat'] as const)(
      'when %s is inspected, then it carries the LLM rate limit',
      (handlerName) => {
        const expected = throttleMetadataOf(ReferenceThrottle.prototype.handler);

        expect(expected.size).toBeGreaterThan(0);
        expect(throttleMetadataOf(ChatbotController.prototype[handlerName])).toEqual(expected);
      },
    );
  });

  describe('POST /chat/stream over HTTP', () => {
    function collectText(
      res: request.Response,
      callback: (error: Error | null, body: string) => void,
    ): void {
      let text = '';
      res.setEncoding('utf8');
      res.on('data', (piece: string) => (text += piece));
      res.on('end', () => callback(null, text));
    }

    function eventsOf(response: request.Response): unknown[] {
      return (response.body as string)
        .split(SSE_FRAME_END)
        .filter((frame) => frame !== '')
        .map((frame) => JSON.parse(frame.slice(SSE_DATA_PREFIX.length)) as unknown);
    }

    function postStream(body: object): request.Test {
      return request(server()).post('/chat/stream').send(body).buffer(true).parse(collectText);
    }

    it('when the stream succeeds, then it responds 200 as text/event-stream ending with the done event', async () => {
      chatbotService.streamChat.mockReturnValue(
        chunksOf({ content: 'Hel', done: false }, { content: 'Hello', done: false }),
      );

      const response = await postStream(QUESTION);

      expect(response.status).toBe(200);
      expect(response.headers['content-type']).toContain('text/event-stream');
      expect(eventsOf(response)).toEqual([
        { content: 'Hel', done: false },
        { content: 'Hello', done: false },
        { content: '', done: true },
      ]);
    });

    it('when the stream fails midway, then the status stays 200 and one error event ends it', async () => {
      chatbotService.streamChat.mockReturnValue(
        failingAfter(
          [{ content: 'Hel', done: false }],
          new ServiceUnavailableException(CHAT_UNAVAILABLE_MESSAGE, {
            cause: new Error(PROVIDER_SECRET),
          }),
        ),
      );

      const response = await postStream(QUESTION);

      expect(response.status).toBe(200);
      expect(eventsOf(response)).toEqual([
        { content: 'Hel', done: false },
        { error: CHAT_UNAVAILABLE_MESSAGE, done: true },
      ]);
      expect(response.body).not.toContain(PROVIDER_SECRET);
    });

    it('when the body is invalid, then it responds 400 before any stream opens', async () => {
      const response = await postStream({ user_question: '   ' });

      expect(response.status).toBe(400);
      expect(response.headers['content-type']).not.toContain('text/event-stream');
      expect(chatbotService.streamChat).not.toHaveBeenCalled();
    });
  });

  describe('POST /chat/stream handler', () => {
    function makeResponse() {
      const written: string[] = [];
      const closeListeners: Array<() => void> = [];
      const fake = {
        headers: new Map<string, string>(),
        setHeader(name: string, value: string) {
          this.headers.set(name, value);
        },
        write(frame: string) {
          written.push(frame);
          return true;
        },
        on(event: string, listener: () => void) {
          if (event === 'close') {
            closeListeners.push(listener);
          }
          return this;
        },
        end: jest.fn(),
      };
      const disconnect = () => closeListeners.forEach((listener) => listener());
      // The handler touches only these members, so the rest of the Express response is not faked.
      return { fake, written, disconnect, response: fake as unknown as Response };
    }

    it('when the stream succeeds, then the events end with exactly one done event', async () => {
      chatbotService.streamChat.mockReturnValue(
        chunksOf({ content: 'Hel', done: false }, { content: 'Hello', done: false }),
      );
      const { fake, written, response } = makeResponse();

      await controller.streamChat(QUESTION, response);

      expect(written).toEqual([
        'data: {"content":"Hel","done":false}\n\n',
        'data: {"content":"Hello","done":false}\n\n',
        'data: {"content":"","done":true}\n\n',
      ]);
      expect(fake.end).toHaveBeenCalledTimes(1);
    });

    it('when the response is opened, then it carries the SSE headers', async () => {
      chatbotService.streamChat.mockReturnValue(chunksOf());
      const { fake, response } = makeResponse();

      await controller.streamChat(QUESTION, response);

      expect(fake.headers.get('Content-Type')).toBe('text/event-stream');
      expect(fake.headers.get('X-Accel-Buffering')).toBe('no');
    });

    it('when the stream fails midway, then exactly one terminal error event follows the chunks', async () => {
      chatbotService.streamChat.mockReturnValue(
        failingAfter(
          [{ content: 'Hel', done: false }],
          new ServiceUnavailableException(CHAT_UNAVAILABLE_MESSAGE),
        ),
      );
      const { fake, written, response } = makeResponse();

      await controller.streamChat(QUESTION, response);

      expect(written).toEqual([
        'data: {"content":"Hel","done":false}\n\n',
        `data: {"error":"${CHAT_UNAVAILABLE_MESSAGE}","done":true}\n\n`,
      ]);
      expect(fake.end).toHaveBeenCalledTimes(1);
    });

    it('when the assistant is unavailable, then the cause behind the 503 is logged once with its stack', async () => {
      const errorLog = jest.spyOn(Logger.prototype, 'error');
      const cause = new Error(PROVIDER_SECRET);
      chatbotService.streamChat.mockReturnValue(
        failingAfter([], new ServiceUnavailableException(CHAT_UNAVAILABLE_MESSAGE, { cause })),
      );
      const { written, response } = makeResponse();

      await controller.streamChat(QUESTION, response);

      expect(errorLog).toHaveBeenCalledTimes(1);
      expect(errorLog).toHaveBeenCalledWith(expect.any(String), cause.stack);
      expect(written.join('')).not.toContain(PROVIDER_SECRET);
    });

    it('when the failure is not the service outage, then its own stack is logged and the client still gets the generic event', async () => {
      const errorLog = jest.spyOn(Logger.prototype, 'error');
      const failure = new Error('socket exploded');
      chatbotService.streamChat.mockReturnValue(failingAfter([], failure));
      const { written, response } = makeResponse();

      await controller.streamChat(QUESTION, response);

      expect(errorLog).toHaveBeenCalledWith(expect.any(String), failure.stack);
      expect(written).toEqual([`data: {"error":"${CHAT_UNAVAILABLE_MESSAGE}","done":true}\n\n`]);
    });

    it('when the failure is not an Error object, then it is logged as text and the client still gets the generic event', async () => {
      const errorLog = jest.spyOn(Logger.prototype, 'error');
      chatbotService.streamChat.mockReturnValue(failingAfter([], 'plain failure'));
      const { written, response } = makeResponse();

      await controller.streamChat(QUESTION, response);

      expect(errorLog).toHaveBeenCalledWith(expect.any(String), 'plain failure');
      expect(written).toEqual([`data: {"error":"${CHAT_UNAVAILABLE_MESSAGE}","done":true}\n\n`]);
    });

    it('when the client disconnects, then the provider call is aborted and later chunks are not written', async () => {
      const { fake, written, disconnect, response } = makeResponse();
      let signalAbortedAfterDisconnect = false;
      chatbotService.streamChat.mockImplementation(async function* (
        _request: unknown,
        signal: AbortSignal,
      ) {
        yield await Promise.resolve({ content: 'Hel', done: false });
        disconnect();
        signalAbortedAfterDisconnect = signal.aborted;
        yield { content: 'Hello', done: false };
      });

      await controller.streamChat(QUESTION, response);

      expect(signalAbortedAfterDisconnect).toBe(true);
      expect(written).toEqual(['data: {"content":"Hel","done":false}\n\n']);
      expect(fake.end).toHaveBeenCalledTimes(1);
    });

    it('when the abort makes the stream throw, then nothing more is logged or written for a client that left', async () => {
      const errorLog = jest.spyOn(Logger.prototype, 'error');
      const { fake, written, disconnect, response } = makeResponse();
      chatbotService.streamChat.mockImplementation(async function* () {
        yield await Promise.resolve({ content: 'Hel', done: false });
        disconnect();
        throw new ServiceUnavailableException(CHAT_UNAVAILABLE_MESSAGE, {
          cause: new Error('aborted'),
        });
      });

      await controller.streamChat(QUESTION, response);

      expect(written).toEqual(['data: {"content":"Hel","done":false}\n\n']);
      expect(errorLog).not.toHaveBeenCalled();
      expect(fake.end).toHaveBeenCalledTimes(1);
    });
  });
});
