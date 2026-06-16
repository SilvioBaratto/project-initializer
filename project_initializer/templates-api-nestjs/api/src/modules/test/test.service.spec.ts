import { Test, TestingModule } from '@nestjs/testing';
import { NotFoundException } from '@nestjs/common';
import { TestService } from './test.service';

describe('TestService', () => {
  let service: TestService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [TestService],
    }).compile();
    service = module.get<TestService>(TestService);
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('create()', () => {
    it('when create is called with a name, returns an item with a non-empty string id', () => {
      const result = service.create({ name: 'widget' });
      expect(typeof result.id).toBe('string');
      expect(result.id.length).toBeGreaterThan(0);
    });

    it('when create is called, returns an item with a non-empty created_at ISO string', () => {
      const result = service.create({ name: 'widget' });
      expect(typeof result.created_at).toBe('string');
      expect(result.created_at.length).toBeGreaterThan(0);
    });

    it('when create is called, returns an item with a non-empty updated_at ISO string', () => {
      const result = service.create({ name: 'widget' });
      expect(typeof result.updated_at).toBe('string');
      expect(result.updated_at.length).toBeGreaterThan(0);
    });
  });

  describe('findAll()', () => {
    it('when no items have been created, findAll returns an empty array', () => {
      expect(service.findAll()).toEqual([]);
    });

    it('when two items have been created, findAll returns an array of length two', () => {
      service.create({ name: 'a' });
      service.create({ name: 'b' });
      expect(service.findAll()).toHaveLength(2);
    });
  });

  describe('findOne()', () => {
    it('when findOne is called with a valid id, returns the matching item', () => {
      const created = service.create({ name: 'widget' });
      expect(service.findOne(created.id)).toEqual(created);
    });

    it('when findOne is called with a non-existent id, throws NotFoundException with the item id in the message', () => {
      expect(() => service.findOne('no-such-id')).toThrow(
        new NotFoundException("Item with id 'no-such-id' not found"),
      );
    });
  });

  describe('update()', () => {
    it('when update is called with new fields, returns the item with those fields merged in', () => {
      const created = service.create({ name: 'old-name' });
      const result = service.update(created.id, { name: 'new-name' });
      expect(result.name).toBe('new-name');
      expect(result.id).toBe(created.id);
    });

    it('when update is called, created_at is preserved unchanged', () => {
      const created = service.create({ name: 'widget' });
      const result = service.update(created.id, { name: 'updated' });
      expect(result.created_at).toBe(created.created_at);
    });

    it('when update is called after a time advance, updated_at is later than the original value', () => {
      jest.useFakeTimers();
      const created = service.create({ name: 'widget' });
      jest.advanceTimersByTime(1000);
      const result = service.update(created.id, { name: 'updated' });
      expect(result.updated_at > created.updated_at).toBe(true);
    });
  });

  describe('remove()', () => {
    it('when remove is called with a valid id, does not throw', () => {
      const created = service.create({ name: 'widget' });
      expect(() => service.remove(created.id)).not.toThrow();
    });

    it('when remove is called with a non-existent id, throws NotFoundException with the item id in the message', () => {
      expect(() => service.remove('no-such-id')).toThrow(
        new NotFoundException("Item with id 'no-such-id' not found"),
      );
    });
  });
});
