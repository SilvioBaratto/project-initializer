import { randomUUID } from 'node:crypto';
import type { AccessTokenVerifier } from '../../src/common/auth/access-token-verifier';
import type { AuthenticatedUser } from '../../src/common/auth/authenticated-user';
import type { DatabaseHealthPort } from '../../src/modules/health/database-health.port';
import type { Item, ItemChanges, NewItem } from '../../src/modules/items/item.entity';
import type { ItemRepository } from '../../src/modules/items/item.repository';

/** Bearer token the shared e2e suite sends; only {@link acceptAllVerifier} gives it a meaning. */
export const TEST_BEARER_TOKEN = 'test-token';

/** Identity that {@link acceptAllVerifier} resolves for every token. */
export const TEST_USER: AuthenticatedUser = {
  id: '00000000-0000-4000-8000-000000000001',
  roles: ['user'],
};

/** Verifier that authenticates any token as {@link TEST_USER}, so a suite can ignore the variant. */
export const acceptAllVerifier: AccessTokenVerifier = {
  verify: () => Promise.resolve(TEST_USER),
};

/** In-memory stand-in for the Prisma-backed item repository, newest item first like the real one. */
export class InMemoryItemRepository implements ItemRepository {
  private readonly itemsById = new Map<string, Item>();

  findAll(): Promise<Item[]> {
    return Promise.resolve([...this.itemsById.values()].reverse());
  }

  findById(id: string): Promise<Item | null> {
    return Promise.resolve(this.itemsById.get(id) ?? null);
  }

  create(input: NewItem): Promise<Item> {
    const now = new Date();
    const item: Item = {
      id: randomUUID(),
      name: input.name,
      description: input.description ?? null,
      createdAt: now,
      updatedAt: now,
    };
    this.itemsById.set(item.id, item);
    return Promise.resolve(item);
  }

  update(id: string, changes: ItemChanges): Promise<Item | null> {
    const existing = this.itemsById.get(id);
    if (existing === undefined) {
      return Promise.resolve(null);
    }
    const updated: Item = {
      ...existing,
      name: changes.name ?? existing.name,
      description: changes.description === undefined ? existing.description : changes.description,
      updatedAt: new Date(),
    };
    this.itemsById.set(id, updated);
    return Promise.resolve(updated);
  }

  delete(id: string): Promise<boolean> {
    return Promise.resolve(this.itemsById.delete(id));
  }
}

/** Database health port that always reports a closed circuit and a reachable database. */
export const upDatabaseHealth: DatabaseHealthPort = {
  check: () => Promise.resolve({ up: true, circuit: 'closed' }),
};
