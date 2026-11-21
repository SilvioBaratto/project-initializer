import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { AuditLogger } from '../../common/audit/audit-logger';
import type { Item, ItemChanges, NewItem } from './item.entity';
import { ITEM_AUDIT_ACTIONS, ITEM_NOT_FOUND_MESSAGE } from './item.constants';
import { ITEM_REPOSITORY, type ItemRepository } from './item.repository';

/**
 * Item use cases; storage is reached only through the {@link ItemRepository} port. Every change
 * that succeeds is written to the audit trail with the id of the actor who made it.
 */
@Injectable()
export class ItemsService {
  constructor(
    @Inject(ITEM_REPOSITORY) private readonly items: ItemRepository,
    private readonly audit: AuditLogger,
  ) {}

  /** Returns the most recent items, newest first. */
  findAll(): Promise<Item[]> {
    return this.items.findAll();
  }

  /**
   * Returns one item.
   *
   * @throws NotFoundException when no item has that id.
   */
  async findOne(id: string): Promise<Item> {
    const item = await this.items.findById(id);
    if (item === null) {
      throw new NotFoundException(ITEM_NOT_FOUND_MESSAGE);
    }
    return item;
  }

  /**
   * Creates an item; the id and timestamps are assigned by the store.
   *
   * @param actorId - Opaque id of the caller, for the audit trail.
   */
  async create(item: NewItem, actorId: string): Promise<Item> {
    const created = await this.items.create(item);
    this.audit.record(ITEM_AUDIT_ACTIONS.create, created.id, actorId);
    return created;
  }

  /**
   * Applies the given changes to an item.
   *
   * @param actorId - Opaque id of the caller, for the audit trail.
   * @returns the item after the update.
   * @throws NotFoundException when no item has that id.
   */
  async update(id: string, changes: ItemChanges, actorId: string): Promise<Item> {
    const item = await this.items.update(id, changes);
    if (item === null) {
      throw new NotFoundException(ITEM_NOT_FOUND_MESSAGE);
    }
    this.audit.record(ITEM_AUDIT_ACTIONS.update, id, actorId);
    return item;
  }

  /**
   * Deletes an item.
   *
   * @param actorId - Opaque id of the caller, for the audit trail.
   * @throws NotFoundException when no item has that id.
   */
  async remove(id: string, actorId: string): Promise<void> {
    const deleted = await this.items.delete(id);
    if (!deleted) {
      throw new NotFoundException(ITEM_NOT_FOUND_MESSAGE);
    }
    this.audit.record(ITEM_AUDIT_ACTIONS.delete, id, actorId);
  }
}
