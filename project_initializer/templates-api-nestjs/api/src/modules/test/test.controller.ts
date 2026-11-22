import { Body, Controller, Get, HttpCode, HttpStatus, Param, Post } from '@nestjs/common';
import { ApiBadRequestResponse, ApiOperation, ApiTags } from '@nestjs/swagger';
import { ResponseSchema } from '../../common/serialization/response-schema.decorator';
import {
  EchoParamSchema,
  EchoRequestSchema,
  EchoResponseSchema,
  PING_MESSAGE,
  PingResponseSchema,
  type EchoParamDto,
  type EchoRequestDto,
  type EchoResponseDto,
  type PingResponseDto,
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
  @ResponseSchema(HttpStatus.OK, PingResponseSchema)
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
  @ResponseSchema(HttpStatus.OK, EchoResponseSchema)
  @ApiOperation({ summary: 'Echo a message (GET)' })
  @ApiBadRequestResponse({ description: VALIDATION_FAILED_DESCRIPTION })
  echoGet(@Param({ schema: EchoParamSchema }) params: EchoParamDto): EchoResponseDto {
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
  @ResponseSchema(HttpStatus.OK, EchoResponseSchema)
  @ApiOperation({ summary: 'Echo a message (POST)' })
  @ApiBadRequestResponse({ description: VALIDATION_FAILED_DESCRIPTION })
  echoPost(@Body({ schema: EchoRequestSchema }) body: EchoRequestDto): EchoResponseDto {
    return { message: body.message };
  }
}
