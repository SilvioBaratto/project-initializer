import type { Item, ItemChanges, NewItem } from './item.entity';

/** Injection token for the {@link ItemRepository} implementation. */
export const ITEM_REPOSITORY = Symbol('ITEM_REPOSITORY');

/** Storage port for items, so the service never depends on a database client. */
export interface ItemRepository {
  /** Returns the most recent items, newest first, capped at a fixed page size. */
  findAll(): Promise<Item[]>;
  /** Returns the item with that id, or `null` when none exists. */
  findById(id: string): Promise<Item | null>;
  /** Stores a new item and returns it with its generated id and timestamps. */
  create(item: NewItem): Promise<Item>;
  /** Applies the changes; returns the updated item, or `null` when the id does not exist. */
  update(id: string, changes: ItemChanges): Promise<Item | null>;
  /** Deletes the item; returns `false` when the id does not exist. */
  delete(id: string): Promise<boolean>;
}
