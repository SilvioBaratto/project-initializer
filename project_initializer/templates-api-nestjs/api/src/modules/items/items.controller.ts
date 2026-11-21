import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  Post,
  Put,
} from '@nestjs/common';
import {
  ApiNoContentResponse,
  ApiNotFoundResponse,
  ApiOperation,
  ApiServiceUnavailableResponse,
  ApiTags,
} from '@nestjs/swagger';
import { ZodResponse } from 'nestjs-zod';
import { auditActorIdOf } from '../../common/audit/audit-logger';
import type { AuthenticatedUser } from '../../common/auth/authenticated-user';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { UuidParamDto } from '../../common/dto/uuid-param.dto';
import { SERVICE_UNAVAILABLE_MESSAGE } from '../../common/filters/error-body';
import { CreateItemDto, ItemResponseDto, UpdateItemDto, toItemResponse } from './dto/item.dto';
import { ITEM_NOT_FOUND_MESSAGE } from './item.constants';
import { ItemsService } from './items.service';

/** CRUD routes for the sample `items` resource, mounted at `/api/v1/items`. */
@ApiTags('Items')
@ApiServiceUnavailableResponse({ description: SERVICE_UNAVAILABLE_MESSAGE })
@Controller('items')
export class ItemsController {
  constructor(private readonly itemsService: ItemsService) {}

  /**
   * Lists the most recent items, newest first.
   *
   * @throws ServiceUnavailableException (503) when the database circuit is open.
   */
  @Get()
  @ZodResponse({ type: [ItemResponseDto] })
  @ApiOperation({ summary: 'List the most recent items, newest first' })
  async findAll(): Promise<ItemResponseDto[]> {
    const items = await this.itemsService.findAll();
    return items.map(toItemResponse);
  }

  /**
   * Creates an item.
   *
   * @throws BadRequestException (400) when the body fails validation.
   * @throws ServiceUnavailableException (503) when the database circuit is open.
   */
  @Post()
  @ZodResponse({ status: HttpStatus.CREATED, type: ItemResponseDto })
  @ApiOperation({ summary: 'Create an item' })
  async create(
    @Body() body: CreateItemDto,
    @CurrentUser() user?: AuthenticatedUser,
  ): Promise<ItemResponseDto> {
    return toItemResponse(await this.itemsService.create(body, auditActorIdOf(user)));
  }

  /**
   * Returns one item.
   *
   * @throws BadRequestException (400) when the id is not a UUID.
   * @throws NotFoundException (404) when no item has that id.
   * @throws ServiceUnavailableException (503) when the database circuit is open.
   */
  @Get(':id')
  @ZodResponse({ type: ItemResponseDto })
  @ApiOperation({ summary: 'Get an item by id' })
  @ApiNotFoundResponse({ description: ITEM_NOT_FOUND_MESSAGE })
  async findOne(@Param() params: UuidParamDto): Promise<ItemResponseDto> {
    return toItemResponse(await this.itemsService.findOne(params.id));
  }

  /**
   * Applies the given fields to an item and returns it.
   *
   * @throws BadRequestException (400) when the id is not a UUID or the body is empty or invalid.
   * @throws NotFoundException (404) when no item has that id.
   * @throws ServiceUnavailableException (503) when the database circuit is open.
   */
  @Put(':id')
  @ZodResponse({ type: ItemResponseDto })
  @ApiOperation({ summary: 'Update the given fields of an item' })
  @ApiNotFoundResponse({ description: ITEM_NOT_FOUND_MESSAGE })
  async update(
    @Param() params: UuidParamDto,
    @Body() body: UpdateItemDto,
    @CurrentUser() user?: AuthenticatedUser,
  ): Promise<ItemResponseDto> {
    return toItemResponse(await this.itemsService.update(params.id, body, auditActorIdOf(user)));
  }

  /**
   * Deletes an item.
   *
   * @throws BadRequestException (400) when the id is not a UUID.
   * @throws NotFoundException (404) when no item has that id.
   * @throws ServiceUnavailableException (503) when the database circuit is open.
   */
  @Delete(':id')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Delete an item' })
  @ApiNoContentResponse({ description: 'Item deleted' })
  @ApiNotFoundResponse({ description: ITEM_NOT_FOUND_MESSAGE })
  remove(@Param() params: UuidParamDto, @CurrentUser() user?: AuthenticatedUser): Promise<void> {
    return this.itemsService.remove(params.id, auditActorIdOf(user));
  }
}
