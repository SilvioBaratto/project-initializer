/** Longest accepted item name; matches the `VARCHAR(100)` column. */
export const MAX_ITEM_NAME_LENGTH = 100;

/** Longest accepted item description; matches the `VARCHAR(500)` column. */
export const MAX_ITEM_DESCRIPTION_LENGTH = 500;

/** Most items `GET /items` returns, so the list stays bounded as the table grows. */
export const ITEM_LIST_LIMIT = 100;

/** Message of the 404 returned for an unknown item id. */
export const ITEM_NOT_FOUND_MESSAGE = 'Item not found';

/** Names under which item changes are written to the audit trail. */
export const ITEM_AUDIT_ACTIONS = {
  create: 'item.create',
  update: 'item.update',
  delete: 'item.delete',
} as const;
