import {
  Controller,
  Post,
  Get,
  Body,
  Param,
  Res,
  SerializeOptions,
} from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { Response } from 'express';
import { ChatbotService } from './chatbot.service';
import { ChatJobService } from './chat-job.service';
import {
  ChatRequestSchema,
  ChatResponseSchema,
  ChatJobAcceptedSchema,
  ChatJobStatusSchema,
  ChatRequestDto,
  ChatResponseDto,
  ChatJobAcceptedDto,
  ChatJobStatusDto,
} from './dto/chat.dto';

/** Chatbot HTTP surface: synchronous chat, SSE streaming, and async job enqueue/poll. */
@ApiTags('Chatbot')
@Controller('chat')
export class ChatbotController {
  constructor(
    private readonly chatbotService: ChatbotService,
    private readonly chatJobService: ChatJobService,
  ) {}

  @Post()
  @SerializeOptions({ schema: ChatResponseSchema })
  @ApiOperation({ summary: 'Send a chat message' })
  async chat(
    @Body({ schema: ChatRequestSchema }) chatRequest: ChatRequestDto,
  ): Promise<ChatResponseDto> {
    return this.chatbotService.chat(chatRequest);
  }

  // No @SerializeOptions: this handler writes an SSE stream via @Res() directly, so the
  // serializer interceptor must not run its schema over the event stream.
  @Post('stream')
  @ApiOperation({ summary: 'Stream a chat response (SSE)' })
  async streamChat(
    @Body({ schema: ChatRequestSchema }) chatRequest: ChatRequestDto,
    @Res() res: Response,
  ): Promise<void> {
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    try {
      for await (const chunk of this.chatbotService.streamChat(chatRequest)) {
        res.write(`data: ${JSON.stringify(chunk)}\n\n`);
      }
      res.write(`data: ${JSON.stringify({ content: '', done: true })}\n\n`);
      res.end();
    } catch (error) {
      res.write(
        `data: ${JSON.stringify({ content: 'Error generating response', done: true })}\n\n`,
      );
      res.end();
    }
  }

  @Post('jobs')
  @SerializeOptions({ schema: ChatJobAcceptedSchema })
  @ApiOperation({ summary: 'Enqueue a chat job (async)' })
  async enqueueChat(
    @Body({ schema: ChatRequestSchema }) chatRequest: ChatRequestDto,
  ): Promise<ChatJobAcceptedDto> {
    const jobId = await this.chatJobService.enqueueChat(chatRequest);
    return { jobId };
  }

  @Get('jobs/:id')
  @SerializeOptions({ schema: ChatJobStatusSchema })
  @ApiOperation({ summary: 'Poll chat job status' })
  async getJobStatus(@Param('id') id: string): Promise<ChatJobStatusDto> {
    const { state, result } = await this.chatJobService.getJobStatus(id);
    return { jobId: id, state, result: result as ChatJobStatusDto['result'] };
  }

  @Get('health')
  @ApiOperation({ summary: 'Chatbot health check' })
  health() {
    return { status: 'ok', service: 'chatbot' };
  }
}
