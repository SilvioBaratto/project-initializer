/**
 * Validates src/modules/items/prisma-item.repository.ts.
 */
import { Prisma } from '@generated/prisma';
import { Test } from '@nestjs/testing';
import { CircuitBreaker, CircuitOpenError } from '../../common/resilience/circuit-breaker';
import {
  DATABASE_CIRCUIT_BREAKER,
  isDatabaseUnavailableError,
} from '../../prisma/database-circuit-breaker';
import { PrismaService } from '../../prisma/prisma.service';
import { ITEM_LIST_LIMIT } from './item.constants';
import { PrismaItemRepository } from './prisma-item.repository';

const ITEM_ID = 'f47ac10b-58cc-4372-a567-0e02b2c3d479';
const FAILURE_THRESHOLD = 2;
const RESET_TIMEOUT_MS = 60_000;
const CLIENT_VERSION = 'test';

const row = {
  id: ITEM_ID,
  name: 'widget',
  description: 'a widget',
  createdAt: new Date('2026-01-02T03:04:05.000Z'),
  updatedAt: new Date('2026-01-02T03:04:05.000Z'),
};

const requestError = (code: string): Prisma.PrismaClientKnownRequestError =>
  new Prisma.PrismaClientKnownRequestError('request failed', {
    code,
    clientVersion: CLIENT_VERSION,
  });

describe('PrismaItemRepository', () => {
  const item = {
    findMany: jest.fn(),
    findUnique: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  };
  let repository: PrismaItemRepository;
  let breaker: CircuitBreaker;

  beforeEach(async () => {
    jest.resetAllMocks();
    breaker = new CircuitBreaker({
      failureThreshold: FAILURE_THRESHOLD,
      resetTimeoutMs: RESET_TIMEOUT_MS,
      isFailure: isDatabaseUnavailableError,
    });
    const moduleRef = await Test.createTestingModule({
      providers: [
        PrismaItemRepository,
        { provide: PrismaService, useValue: { item } },
        { provide: DATABASE_CIRCUIT_BREAKER, useValue: breaker },
      ],
    }).compile();
    repository = moduleRef.get(PrismaItemRepository);
  });

  describe('findAll()', () => {
    it('when called, then it asks for the newest items up to the list limit', async () => {
      item.findMany.mockResolvedValue([row]);

      await repository.findAll();

      expect(item.findMany).toHaveBeenCalledWith({
        orderBy: [{ createdAt: 'desc' }, { id: 'asc' }],
        take: ITEM_LIST_LIMIT,
      });
    });

    it('when rows come back, then they are mapped to entities', async () => {
      item.findMany.mockResolvedValue([{ ...row, secretColumn: 'leak' }]);

      const items = await repository.findAll();

      expect(items).toEqual([row]);
      expect(items[0]).not.toHaveProperty('secretColumn');
    });
  });

  describe('findById()', () => {
    it('when the row exists, then it is returned as an entity', async () => {
      item.findUnique.mockResolvedValue(row);

      await expect(repository.findById(ITEM_ID)).resolves.toEqual(row);
      expect(item.findUnique).toHaveBeenCalledWith({ where: { id: ITEM_ID } });
    });

    it('when no row exists, then null is returned', async () => {
      item.findUnique.mockResolvedValue(null);

      await expect(repository.findById(ITEM_ID)).resolves.toBeNull();
    });
  });

  describe('create()', () => {
    it('when no description is given, then it is stored as null', async () => {
      item.create.mockResolvedValue({ ...row, description: null });

      await repository.create({ name: 'widget' });

      expect(item.create).toHaveBeenCalledWith({ data: { name: 'widget', description: null } });
    });

    it('when a description is given, then it is stored', async () => {
      item.create.mockResolvedValue(row);

      await expect(repository.create({ name: 'widget', description: 'a widget' })).resolves.toEqual(
        row,
      );
      expect(item.create).toHaveBeenCalledWith({
        data: { name: 'widget', description: 'a widget' },
      });
    });
  });

  describe('update()', () => {
    it('when the row exists, then only the given changes are sent', async () => {
      item.update.mockResolvedValue({ ...row, name: 'renamed' });

      await expect(repository.update(ITEM_ID, { name: 'renamed' })).resolves.toMatchObject({
        name: 'renamed',
      });
      expect(item.update).toHaveBeenCalledWith({
        where: { id: ITEM_ID },
        data: { name: 'renamed' },
      });
    });

    it('when Prisma reports the record missing, then null is returned', async () => {
      item.update.mockRejectedValue(requestError('P2025'));

      await expect(repository.update(ITEM_ID, { name: 'renamed' })).resolves.toBeNull();
    });

    it('when Prisma reports another error, then it is rethrown', async () => {
      const duplicate = requestError('P2002');
      item.update.mockRejectedValue(duplicate);

      await expect(repository.update(ITEM_ID, { name: 'renamed' })).rejects.toBe(duplicate);
    });
  });

  describe('delete()', () => {
    it('when the row exists, then true is returned', async () => {
      item.delete.mockResolvedValue(row);

      await expect(repository.delete(ITEM_ID)).resolves.toBe(true);
      expect(item.delete).toHaveBeenCalledWith({ where: { id: ITEM_ID } });
    });

    it('when Prisma reports the record missing, then false is returned', async () => {
      item.delete.mockRejectedValue(requestError('P2025'));

      await expect(repository.delete(ITEM_ID)).resolves.toBe(false);
    });

    it('when Prisma reports another error, then it is rethrown', async () => {
      const outage = new Error('connect ECONNREFUSED');
      item.delete.mockRejectedValue(outage);

      await expect(repository.delete(ITEM_ID)).rejects.toBe(outage);
    });
  });

  describe('circuit breaker', () => {
    it('when the database keeps failing, then calls are rejected with CircuitOpenError without reaching Prisma', async () => {
      item.findUnique.mockRejectedValue(new Error('connect ECONNREFUSED'));
      for (let attempt = 0; attempt < FAILURE_THRESHOLD; attempt += 1) {
        await expect(repository.findById(ITEM_ID)).rejects.toThrow('connect ECONNREFUSED');
      }
      item.findUnique.mockClear();

      await expect(repository.findById(ITEM_ID)).rejects.toBeInstanceOf(CircuitOpenError);

      expect(item.findUnique).not.toHaveBeenCalled();
    });

    it('when Prisma keeps reporting missing records, then the circuit stays closed', async () => {
      item.update.mockRejectedValue(requestError('P2025'));

      for (let attempt = 0; attempt < FAILURE_THRESHOLD * 2; attempt += 1) {
        await repository.update(ITEM_ID, { name: 'renamed' });
      }

      expect(breaker.state).toBe('closed');
    });

    it.each([
      ['findAll', (): Promise<unknown> => repository.findAll()],
      ['create', (): Promise<unknown> => repository.create({ name: 'widget' })],
      ['update', (): Promise<unknown> => repository.update(ITEM_ID, { name: 'renamed' })],
      ['delete', (): Promise<unknown> => repository.delete(ITEM_ID)],
    ])('when the circuit is open, then %s is rejected', async (_method, call) => {
      item.findUnique.mockRejectedValue(new Error('connect ECONNREFUSED'));
      for (let attempt = 0; attempt < FAILURE_THRESHOLD; attempt += 1) {
        await repository.findById(ITEM_ID).catch(() => undefined);
      }

      await expect(call()).rejects.toBeInstanceOf(CircuitOpenError);
    });
  });
});
