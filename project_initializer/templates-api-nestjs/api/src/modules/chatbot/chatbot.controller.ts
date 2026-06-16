import { Controller, Post, Get, Body, Param, Res } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { Response } from 'express';
import { ZodSerializerDto } from 'nestjs-zod';
import { ChatbotService } from './chatbot.service';
import { ChatJobService } from './chat-job.service';
import {
  ChatRequestDto,
  ChatResponseDto,
  ChatJobAcceptedDto,
  ChatJobStatusDto,
} from './dto/chat.dto';

@ApiTags('Chatbot')
@Controller('chat')
export class ChatbotController {
  constructor(
    private readonly chatbotService: ChatbotService,
    private readonly chatJobService: ChatJobService,
  ) {}

  @Post()
  @ZodSerializerDto(ChatResponseDto)
  @ApiOperation({ summary: 'Send a chat message' })
  async chat(@Body() chatRequest: ChatRequestDto): Promise<ChatResponseDto> {
    return this.chatbotService.chat(chatRequest);
  }

  @Post('stream')
  @ApiOperation({ summary: 'Stream a chat response (SSE)' })
  async streamChat(
    @Body() chatRequest: ChatRequestDto,
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
  @ZodSerializerDto(ChatJobAcceptedDto)
  @ApiOperation({ summary: 'Enqueue a chat job (async)' })
  async enqueueChat(@Body() chatRequest: ChatRequestDto): Promise<ChatJobAcceptedDto> {
    const jobId = await this.chatJobService.enqueueChat(chatRequest);
    return { jobId };
  }

  @Get('jobs/:id')
  @ZodSerializerDto(ChatJobStatusDto)
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
