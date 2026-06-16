import { Test, TestingModule } from '@nestjs/testing';
import { TestController } from './test.controller';
import { TestService } from './test.service';

const mockTestService = {
  findAll: jest.fn(),
  findOne: jest.fn(),
  create: jest.fn(),
  update: jest.fn(),
  remove: jest.fn(),
};

describe('TestController', () => {
  let controller: TestController;

  beforeEach(async () => {
    jest.clearAllMocks();

    const module: TestingModule = await Test.createTestingModule({
      controllers: [TestController],
      providers: [{ provide: TestService, useValue: mockTestService }],
    }).compile();

    controller = module.get<TestController>(TestController);
  });

  describe('ping()', () => {
    it('when ping is called, returns { message: "pong" }', () => {
      expect(controller.ping()).toEqual({ message: 'pong' });
    });
  });

  describe('findAll()', () => {
    it('when findAll is called, delegates to TestService.findAll and returns its result', () => {
      const items = [{ id: '1', name: 'a', created_at: '', updated_at: '' }];
      mockTestService.findAll.mockReturnValue(items);

      expect(controller.findAll()).toBe(items);
      expect(mockTestService.findAll).toHaveBeenCalledTimes(1);
    });
  });

  describe('findOne()', () => {
    it('when findOne is called with an id, delegates to TestService.findOne with that id', () => {
      const item = { id: 'abc', name: 'x', created_at: '', updated_at: '' };
      mockTestService.findOne.mockReturnValue(item);

      expect(controller.findOne('abc')).toBe(item);
      expect(mockTestService.findOne).toHaveBeenCalledWith('abc');
    });
  });

  describe('create()', () => {
    it('when create is called with a DTO, delegates to TestService.create with that DTO', () => {
      const dto = { name: 'widget' };
      const created = { id: '1', name: 'widget', created_at: '', updated_at: '' };
      mockTestService.create.mockReturnValue(created);

      expect(controller.create(dto as any)).toBe(created);
      expect(mockTestService.create).toHaveBeenCalledWith(dto);
    });
  });

  describe('update()', () => {
    it('when update is called with an id and DTO, delegates to TestService.update with those args', () => {
      const dto = { name: 'updated' };
      const updated = { id: 'abc', name: 'updated', created_at: '', updated_at: '' };
      mockTestService.update.mockReturnValue(updated);

      expect(controller.update('abc', dto as any)).toBe(updated);
      expect(mockTestService.update).toHaveBeenCalledWith('abc', dto);
    });
  });

  describe('remove()', () => {
    it('when remove is called with an id, delegates to TestService.remove with that id', () => {
      mockTestService.remove.mockReturnValue(undefined);

      controller.remove('abc');

      expect(mockTestService.remove).toHaveBeenCalledWith('abc');
    });
  });
});
