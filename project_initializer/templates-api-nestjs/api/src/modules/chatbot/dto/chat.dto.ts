import { IsString, IsNotEmpty, IsOptional, IsArray } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class ChatRequestDto {
  @ApiProperty({ description: 'User question' })
  @IsString()
  @IsNotEmpty()
  user_question: string;

  @ApiPropertyOptional({
    description: 'Conversation history as list of messages',
    type: [String],
  })
  @IsArray()
  @IsString({ each: true })
  @IsOptional()
  conversation_history?: string[];
}

export class ChatResponseDto {
  @ApiProperty({ description: 'Chatbot answer' })
  answer: string;
}

export class StreamChunkDto {
  @ApiProperty({ description: 'Content chunk' })
  content: string;

  @ApiProperty({ description: 'Whether the stream is done' })
  done: boolean;
}
