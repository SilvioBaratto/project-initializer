/**
 * Validates src/modules/items/items.service.ts.
 */
import { NotFoundException } from '@nestjs/common';
import type { AuditLogger } from '../../common/audit/audit-logger';
import type { Item } from './item.entity';
import { ITEM_AUDIT_ACTIONS, ITEM_NOT_FOUND_MESSAGE } from './item.constants';
import type { ItemRepository } from './item.repository';
import { ItemsService } from './items.service';

const ITEM_ID = 'f47ac10b-58cc-4372-a567-0e02b2c3d479';
const ACTOR_ID = 'actor-1';

const storedItem: Item = {
  id: ITEM_ID,
  name: 'widget',
  description: null,
  createdAt: new Date('2026-01-02T03:04:05.000Z'),
  updatedAt: new Date('2026-01-02T03:04:05.000Z'),
};

describe('ItemsService', () => {
  const repository: jest.Mocked<ItemRepository> = {
    findAll: jest.fn(),
    findById: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  };
  const audit = { record: jest.fn() };
  let service: ItemsService;

  beforeEach(() => {
    jest.resetAllMocks();
    service = new ItemsService(repository, audit as unknown as AuditLogger);
  });

  describe('findAll()', () => {
    it('when the repository holds items, then they are returned in the repository order', async () => {
      repository.findAll.mockResolvedValue([storedItem]);

      await expect(service.findAll()).resolves.toEqual([storedItem]);
    });
  });

  describe('findOne()', () => {
    it('when the item exists, then it is returned', async () => {
      repository.findById.mockResolvedValue(storedItem);

      await expect(service.findOne(ITEM_ID)).resolves.toBe(storedItem);
      expect(repository.findById).toHaveBeenCalledWith(ITEM_ID);
    });

    it('when the item does not exist, then NotFoundException carries the item message', async () => {
      repository.findById.mockResolvedValue(null);

      await expect(service.findOne(ITEM_ID)).rejects.toThrow(
        new NotFoundException(ITEM_NOT_FOUND_MESSAGE),
      );
    });

    it('when the repository fails, then the failure is not turned into a 404', async () => {
      const outage = new Error('connect ECONNREFUSED');
      repository.findById.mockRejectedValue(outage);

      await expect(service.findOne(ITEM_ID)).rejects.toBe(outage);
    });
  });

  describe('create()', () => {
    it('when an item is created, then the repository result is returned', async () => {
      repository.create.mockResolvedValue(storedItem);

      await expect(service.create({ name: 'widget' }, ACTOR_ID)).resolves.toBe(storedItem);
      expect(repository.create).toHaveBeenCalledWith({ name: 'widget' });
    });

    it('when an item is created, then one audit record names the new id and the actor', async () => {
      repository.create.mockResolvedValue(storedItem);

      await service.create({ name: 'widget' }, ACTOR_ID);

      expect(audit.record).toHaveBeenCalledTimes(1);
      expect(audit.record).toHaveBeenCalledWith(ITEM_AUDIT_ACTIONS.create, ITEM_ID, ACTOR_ID);
    });

    it('when the repository fails, then nothing is recorded', async () => {
      repository.create.mockRejectedValue(new Error('connect ECONNREFUSED'));

      await expect(service.create({ name: 'widget' }, ACTOR_ID)).rejects.toThrow('ECONNREFUSED');
      expect(audit.record).not.toHaveBeenCalled();
    });
  });

  describe('update()', () => {
    it('when the item exists, then the updated item is returned', async () => {
      const updated = { ...storedItem, name: 'renamed' };
      repository.update.mockResolvedValue(updated);

      await expect(service.update(ITEM_ID, { name: 'renamed' }, ACTOR_ID)).resolves.toBe(updated);
      expect(repository.update).toHaveBeenCalledWith(ITEM_ID, { name: 'renamed' });
    });

    it('when the item is updated, then one audit record names the id and the actor', async () => {
      repository.update.mockResolvedValue(storedItem);

      await service.update(ITEM_ID, { name: 'renamed' }, ACTOR_ID);

      expect(audit.record).toHaveBeenCalledTimes(1);
      expect(audit.record).toHaveBeenCalledWith(ITEM_AUDIT_ACTIONS.update, ITEM_ID, ACTOR_ID);
    });

    it('when the item does not exist, then NotFoundException carries the item message and nothing is recorded', async () => {
      repository.update.mockResolvedValue(null);

      await expect(service.update(ITEM_ID, { name: 'renamed' }, ACTOR_ID)).rejects.toThrow(
        new NotFoundException(ITEM_NOT_FOUND_MESSAGE),
      );
      expect(audit.record).not.toHaveBeenCalled();
    });
  });

  describe('remove()', () => {
    it('when the item exists, then it is deleted and nothing is returned', async () => {
      repository.delete.mockResolvedValue(true);

      await expect(service.remove(ITEM_ID, ACTOR_ID)).resolves.toBeUndefined();
      expect(repository.delete).toHaveBeenCalledWith(ITEM_ID);
    });

    it('when the item is deleted, then one audit record names the id and the actor', async () => {
      repository.delete.mockResolvedValue(true);

      await service.remove(ITEM_ID, ACTOR_ID);

      expect(audit.record).toHaveBeenCalledTimes(1);
      expect(audit.record).toHaveBeenCalledWith(ITEM_AUDIT_ACTIONS.delete, ITEM_ID, ACTOR_ID);
    });

    it('when the item does not exist, then NotFoundException carries the item message and nothing is recorded', async () => {
      repository.delete.mockResolvedValue(false);

      await expect(service.remove(ITEM_ID, ACTOR_ID)).rejects.toThrow(
        new NotFoundException(ITEM_NOT_FOUND_MESSAGE),
      );
      expect(audit.record).not.toHaveBeenCalled();
    });
  });
});
