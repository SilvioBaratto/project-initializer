import { Body, Controller, Get, HttpCode, HttpStatus, Param, Post } from '@nestjs/common';
import { ApiBadRequestResponse, ApiOperation, ApiTags } from '@nestjs/swagger';
import { ZodResponse } from 'nestjs-zod';
import {
  EchoParamDto,
  EchoRequestDto,
  EchoResponseDto,
  PING_MESSAGE,
  PingResponseDto,
} from './dto/echo.dto';

const VALIDATION_FAILED_DESCRIPTION = 'The message is missing or longer than the limit';

/** Smoke-test routes that touch no database, mounted at `/api/v1/test`. */
@ApiTags('Test')
@Controller('test')
export class TestController {
  /**
   * Proves the server is up and the serialization pipeline runs.
   *
   * @returns the fixed `pong` message.
   */
  @Get('ping')
  @ZodResponse({ status: HttpStatus.OK, type: PingResponseDto })
  @ApiOperation({ summary: 'Ping endpoint' })
  ping(): PingResponseDto {
    return { message: PING_MESSAGE };
  }

  /**
   * Returns the path parameter unchanged.
   *
   * @param params - the validated path parameter.
   * @returns the message that was sent.
   */
  @Get('echo/:message')
  @ZodResponse({ status: HttpStatus.OK, type: EchoResponseDto })
  @ApiOperation({ summary: 'Echo a message (GET)' })
  @ApiBadRequestResponse({ description: VALIDATION_FAILED_DESCRIPTION })
  echoGet(@Param() params: EchoParamDto): EchoResponseDto {
    return { message: params.message };
  }

  /**
   * Returns the request body's message unchanged. Answers 200 rather than 201 because nothing is
   * created.
   *
   * @param body - the validated request body.
   * @returns the message that was sent.
   */
  @Post('echo')
  @HttpCode(HttpStatus.OK)
  @ZodResponse({ status: HttpStatus.OK, type: EchoResponseDto })
  @ApiOperation({ summary: 'Echo a message (POST)' })
  @ApiBadRequestResponse({ description: VALIDATION_FAILED_DESCRIPTION })
  echoPost(@Body() body: EchoRequestDto): EchoResponseDto {
    return { message: body.message };
  }
}
