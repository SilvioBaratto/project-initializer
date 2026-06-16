import { Test, TestingModule } from '@nestjs/testing';
import { getQueueToken } from '@nestjs/bullmq';
import { BULL_BOARD_INSTANCE } from '@bull-board/nestjs';
import { BullBoardModule } from '@bull-board/nestjs';
import { ExpressAdapter } from '@bull-board/express';
import { MonitoringModule } from './monitoring.module';

// Minimal mock queue — BullBoardFeatureModule resolves the queue token on init.
// BullMQAdapter constructor checks `queue.metaValues?.version?.startsWith('bullmq')` or
// `queue instanceof Queue`; the metaValues shim is simpler than a real Queue prototype stub.
const mockQueue = {
  name: 'chat',
  add: jest.fn(),
  getJob: jest.fn(),
  metaValues: { version: 'bullmq_mock' },
};

// Mock Bull Board instance — the real instance does not expose getBullBoardQueues.
// We spy on addQueue to verify the chat queue was registered.
const mockAddQueue = jest.fn();
const mockBoard = {
  addQueue: mockAddQueue,
  setQueues: jest.fn(),
  replaceQueues: jest.fn(),
  removeQueue: jest.fn(),
};

describe('MonitoringModule', () => {
  let moduleRef: TestingModule;

  beforeEach(async () => {
    jest.clearAllMocks();

    // BullBoardModule.forRoot is global and provides BULL_BOARD_INSTANCE.
    // We override BULL_BOARD_INSTANCE with a mock so we can assert addQueue() calls.
    moduleRef = await Test.createTestingModule({
      imports: [
        BullBoardModule.forRoot({ route: '/admin/queues', adapter: ExpressAdapter }),
        MonitoringModule,
      ],
    })
      .overrideProvider(getQueueToken('chat'))
      .useValue(mockQueue)
      .overrideProvider(BULL_BOARD_INSTANCE)
      .useValue(mockBoard)
      .compile();
  });

  afterEach(async () => {
    await moduleRef.close();
  });

  it('when MonitoringModule is compiled, then it initialises without error', () => {
    expect(moduleRef).toBeDefined();
  });

  it('when MonitoringModule is compiled, then the Bull Board instance provider is registered', () => {
    const board = moduleRef.get(BULL_BOARD_INSTANCE, { strict: false });
    expect(board).toBeDefined();
  });

  it('when MonitoringModule initialises, then addQueue is called once for the chat queue', () => {
    // BullBoardFeatureModule.onModuleInit wraps the chat queue in a BullMQAdapter
    // and calls board.addQueue(adapter). One call per registered queue feature.
    expect(mockAddQueue).toHaveBeenCalledTimes(1);
    // The adapter's getName() returns the queue name it wraps.
    const [adapter] = mockAddQueue.mock.calls[0];
    expect(adapter.getName()).toBe('chat');
  });
});
