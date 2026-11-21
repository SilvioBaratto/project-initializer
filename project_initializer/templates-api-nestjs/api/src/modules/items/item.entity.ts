/** A persisted item as the application sees it, independent of the ORM row it is stored in. */
export interface Item {
  readonly id: string;
  name: string;
  description: string | null;
  createdAt: Date;
  updatedAt: Date;
}

/** What a caller supplies to create an item; identifiers and timestamps are assigned on save. */
export interface NewItem {
  name: string;
  description?: string | null;
}

/** Fields to change on an existing item; an omitted field keeps its value, `null` clears the description. */
export type ItemChanges = Partial<NewItem>;
