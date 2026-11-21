import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  Logger,
  Param,
  Post,
  Res,
} from '@nestjs/common';
import {
  ApiNotFoundResponse,
  ApiOkResponse,
  ApiOperation,
  ApiProduces,
  ApiServiceUnavailableResponse,
  ApiTags,
} from '@nestjs/swagger';
import { Throttle } from '@nestjs/throttler';
import type { Response } from 'express';
import { ZodResponse } from 'nestjs-zod';
import { AuthenticatedUser, ownerIdOf } from '../../common/auth/authenticated-user';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { UuidParamDto } from '../../common/dto/uuid-param.dto';
import { LLM_RATE_LIMIT } from '../../config/rate-limit';
import { CHAT_JOB_NOT_FOUND_MESSAGE, CHAT_UNAVAILABLE_MESSAGE } from './chat.constants';
import { describeChatFailure } from './chat-failure';
import { ChatJobService } from './chat-job.service';
import { ChatbotService } from './chatbot.service';
import {
  ChatJobAcceptedDto,
  ChatJobStatusDto,
  ChatRequestDto,
  ChatResponseDto,
  StreamChunkDto,
  StreamErrorEvent,
} from './dto/chat.dto';
import { applySseHeaders, writeSseEvent } from './sse';

const STREAM_DONE_EVENT: StreamChunkDto = { content: '', done: true };
const STREAM_ERROR_EVENT: StreamErrorEvent = { error: CHAT_UNAVAILABLE_MESSAGE, done: true };
const STREAM_CONTENT_TYPE = 'text/event-stream';
const STREAM_RESPONSE_DESCRIPTION =
  `${STREAM_CONTENT_TYPE}. The last event is {"content":"","done":true} on success, ` +
  'or {"error":"...","done":true} when answering failed.';

/** Chat endpoints: a synchronous answer, an SSE stream, and queued jobs polled by id. */
@ApiTags('Chatbot')
@Controller('chat')
export class ChatbotController {
  private readonly logger = new Logger(ChatbotController.name);

  constructor(
    private readonly chatbotService: ChatbotService,
    private readonly chatJobService: ChatJobService,
  ) {}

  /**
   * Answers one question in a single response.
   *
   * @returns The answer.
   * @throws BadRequestException (400) when the body fails validation.
   * @throws ServiceUnavailableException (503) when the assistant is unavailable.
   */
  @Post()
  @Throttle(LLM_RATE_LIMIT)
  @ZodResponse({ status: HttpStatus.OK, type: ChatResponseDto })
  @ApiOperation({ summary: 'Send a chat message' })
  @ApiServiceUnavailableResponse({ description: CHAT_UNAVAILABLE_MESSAGE })
  chat(@Body() chatRequest: ChatRequestDto): Promise<ChatResponseDto> {
    return this.chatbotService.chat(chatRequest);
  }

  /**
   * Streams the answer as server-sent events.
   *
   * The response is committed as 200 before the first chunk, so a failure cannot change the status
   * code: the stream ends with exactly one terminal event, `{ content: '', done: true }` on
   * success or `{ error, done: true }` on failure. When the client disconnects, the provider call
   * is aborted and nothing more is written.
   *
   * @throws BadRequestException (400) when the body fails validation, before the stream opens.
   */
  @Post('stream')
  @HttpCode(HttpStatus.OK)
  @Throttle(LLM_RATE_LIMIT)
  @ApiOperation({ summary: 'Stream a chat response (SSE)' })
  @ApiProduces(STREAM_CONTENT_TYPE)
  @ApiOkResponse({ type: StreamChunkDto, description: STREAM_RESPONSE_DESCRIPTION })
  async streamChat(@Body() chatRequest: ChatRequestDto, @Res() res: Response): Promise<void> {
    applySseHeaders(res);
    const clientGone = new AbortController();
    res.on('close', () => clientGone.abort());
    try {
      for await (const chunk of this.chatbotService.streamChat(chatRequest, clientGone.signal)) {
        if (clientGone.signal.aborted) {
          return;
        }
        writeSseEvent(res, chunk);
      }
      writeSseEvent(res, STREAM_DONE_EVENT);
    } catch (error) {
      this.endFailedStream(res, error, clientGone.signal);
    } finally {
      res.end();
    }
  }

  /**
   * Queues a question for the background worker.
   *
   * @returns The id to poll with {@link ChatbotController.getJobStatus}.
   * @throws BadRequestException (400) when the body fails validation.
   */
  @Post('jobs')
  @Throttle(LLM_RATE_LIMIT)
  @ZodResponse({ status: HttpStatus.ACCEPTED, type: ChatJobAcceptedDto })
  @ApiOperation({ summary: 'Enqueue a chat job (async)' })
  async enqueueChat(
    @Body() chatRequest: ChatRequestDto,
    @CurrentUser() user?: AuthenticatedUser,
  ): Promise<ChatJobAcceptedDto> {
    const jobId = await this.chatJobService.enqueue(chatRequest, ownerIdOf(user));
    return { jobId };
  }

  /**
   * Reports the state of a queued job, and its answer once it has completed.
   *
   * @returns The job state; `result` is null until the job completes.
   * @throws BadRequestException (400) when the id is not a UUID.
   * @throws NotFoundException (404) when the job does not exist, has expired, or belongs to
   *   another caller.
   */
  @Get('jobs/:id')
  @ZodResponse({ status: HttpStatus.OK, type: ChatJobStatusDto })
  @ApiOperation({ summary: 'Poll chat job status' })
  @ApiNotFoundResponse({ description: CHAT_JOB_NOT_FOUND_MESSAGE })
  getJobStatus(
    @Param() { id }: UuidParamDto,
    @CurrentUser() user?: AuthenticatedUser,
  ): Promise<ChatJobStatusDto> {
    return this.chatJobService.getStatus(id, ownerIdOf(user));
  }

  // A stream whose client left has nobody to tell, and the abort it caused is no failure to log.
  private endFailedStream(res: Response, error: unknown, clientGone: AbortSignal): void {
    if (clientGone.aborted) {
      return;
    }
    // The stream bypasses the exception filter, so this is the one place the cause is logged.
    this.logger.error('Chat stream failed', describeChatFailure(error));
    writeSseEvent(res, STREAM_ERROR_EVENT);
  }
}
