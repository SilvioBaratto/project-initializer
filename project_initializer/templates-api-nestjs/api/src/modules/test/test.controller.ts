import {
  Controller,
  Get,
  Post,
  Put,
  Delete,
  Body,
  Param,
  HttpCode,
  HttpStatus,
  SerializeOptions,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { TestService } from './test.service';
import {
  CreateItemSchema,
  UpdateItemSchema,
  ItemResponseSchema,
  CreateItemDto,
  UpdateItemDto,
  ItemResponseDto,
} from './dto/item.dto';
import {
  EchoRequestSchema,
  EchoResponseSchema,
  EchoRequestDto,
  EchoResponseDto,
} from './dto/echo.dto';

/** Demo CRUD and echo endpoints exercising native request validation and response serialization. */
@ApiTags('Test')
@Controller('test')
export class TestController {
  constructor(private readonly testService: TestService) {}

  @Get('ping')
  @ApiOperation({ summary: 'Ping endpoint' })
  ping() {
    return { message: 'pong' };
  }

  @Get('echo/:message')
  @SerializeOptions({ schema: EchoResponseSchema })
  @ApiOperation({ summary: 'Echo a message (GET)' })
  echoGet(@Param('message') message: string): EchoResponseDto {
    return { message };
  }

  @Post('echo')
  @SerializeOptions({ schema: EchoResponseSchema })
  @ApiOperation({ summary: 'Echo a message (POST)' })
  echoPost(
    @Body({ schema: EchoRequestSchema }) body: EchoRequestDto,
  ): EchoResponseDto {
    return { message: body.message };
  }

  // findAll returns an array; StandardSchemaSerializerInterceptor applies the schema to
  // each element, so pass the single-item ItemResponseSchema, not a z.array wrapper.
  @Get('items')
  @SerializeOptions({ schema: ItemResponseSchema })
  @ApiOperation({ summary: 'List all items' })
  findAll(): ItemResponseDto[] {
    return this.testService.findAll();
  }

  @Post('items')
  @HttpCode(HttpStatus.CREATED)
  @SerializeOptions({ schema: ItemResponseSchema })
  @ApiOperation({ summary: 'Create an item' })
  @ApiResponse({ status: 201, description: 'Item created' })
  create(
    @Body({ schema: CreateItemSchema }) createItemDto: CreateItemDto,
  ): ItemResponseDto {
    return this.testService.create(createItemDto);
  }

  @Get('items/:id')
  @SerializeOptions({ schema: ItemResponseSchema })
  @ApiOperation({ summary: 'Get an item by ID' })
  findOne(@Param('id') id: string): ItemResponseDto {
    return this.testService.findOne(id);
  }

  @Put('items/:id')
  @SerializeOptions({ schema: ItemResponseSchema })
  @ApiOperation({ summary: 'Update an item' })
  update(
    @Param('id') id: string,
    @Body({ schema: UpdateItemSchema }) updateItemDto: UpdateItemDto,
  ): ItemResponseDto {
    return this.testService.update(id, updateItemDto);
  }

  @Delete('items/:id')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Delete an item' })
  remove(@Param('id') id: string): void {
    this.testService.remove(id);
  }
}
