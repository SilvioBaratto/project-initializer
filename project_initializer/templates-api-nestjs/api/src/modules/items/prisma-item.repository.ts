import { Inject, Injectable } from '@nestjs/common';
import { Prisma, type Item as ItemRow } from '@generated/prisma';
import { CircuitBreaker } from '../../common/resilience/circuit-breaker';
import { DATABASE_CIRCUIT_BREAKER } from '../../prisma/database-circuit-breaker';
import { PrismaService } from '../../prisma/prisma.service';
import type { Item, ItemChanges, NewItem } from './item.entity';
import { ITEM_LIST_LIMIT } from './item.constants';
import type { ItemRepository } from './item.repository';

/** Prisma code for "a record required by the operation was not found". */
const RECORD_NOT_FOUND_CODE = 'P2025';

/** Copies the row into the entity so a column added to the table later does not leak outward. */
function toItem(row: ItemRow): Item {
  return {
    id: row.id,
    name: row.name,
    description: row.description,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
  };
}

function isRecordNotFound(error: unknown): boolean {
  return (
    error instanceof Prisma.PrismaClientKnownRequestError && error.code === RECORD_NOT_FOUND_CODE
  );
}

/**
 * {@link ItemRepository} backed by Postgres through Prisma.
 *
 * Every call runs through the shared circuit breaker, so during a database outage requests fail
 * fast with a 503 instead of each waiting for a connection timeout.
 */
@Injectable()
export class PrismaItemRepository implements ItemRepository {
  constructor(
    private readonly prisma: PrismaService,
    @Inject(DATABASE_CIRCUIT_BREAKER) private readonly breaker: CircuitBreaker,
  ) {}

  async findAll(): Promise<Item[]> {
    const rows = await this.breaker.execute(() =>
      this.prisma.item.findMany({
        orderBy: [{ createdAt: 'desc' }, { id: 'asc' }],
        take: ITEM_LIST_LIMIT,
      }),
    );
    return rows.map(toItem);
  }

  async findById(id: string): Promise<Item | null> {
    const row = await this.breaker.execute(() => this.prisma.item.findUnique({ where: { id } }));
    return row === null ? null : toItem(row);
  }

  async create(item: NewItem): Promise<Item> {
    const row = await this.breaker.execute(() =>
      this.prisma.item.create({
        data: { name: item.name, description: item.description ?? null },
      }),
    );
    return toItem(row);
  }

  async update(id: string, changes: ItemChanges): Promise<Item | null> {
    try {
      const row = await this.breaker.execute(() =>
        this.prisma.item.update({ where: { id }, data: changes }),
      );
      return toItem(row);
    } catch (error) {
      if (isRecordNotFound(error)) {
        return null;
      }
      throw error;
    }
  }

  async delete(id: string): Promise<boolean> {
    try {
      await this.breaker.execute(() => this.prisma.item.delete({ where: { id } }));
      return true;
    } catch (error) {
      if (isRecordNotFound(error)) {
        return false;
      }
      throw error;
    }
  }
}
