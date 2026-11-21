import { randomUUID } from 'node:crypto';
import type { AccessTokenVerifier } from '../../src/common/auth/access-token-verifier';
import type { AuthenticatedUser } from '../../src/common/auth/authenticated-user';
import type {
  ChatCompletionPort,
  ChatPrompt,
} from '../../src/modules/chatbot/chat-completion.port';
import { CHAT_QUEUE_NAME } from '../../src/modules/chatbot/chat.constants';
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

/** Answer every {@link FakeChatCompletion} call returns unless it is set to fail. */
export const FAKE_CHAT_ANSWER = 'stub answer';

/** Chat completion port that never reaches an LLM; set `failWith` to simulate a provider outage. */
export class FakeChatCompletion implements ChatCompletionPort {
  failWith?: Error;
  readonly prompts: ChatPrompt[] = [];

  complete(prompt: ChatPrompt): Promise<string> {
    this.prompts.push(prompt);
    return this.failWith ? Promise.reject(this.failWith) : Promise.resolve(FAKE_CHAT_ANSWER);
  }

  async *streamAnswer(prompt: ChatPrompt): AsyncGenerator<string> {
    this.prompts.push(prompt);
    if (this.failWith) {
      throw this.failWith;
    }
    yield await Promise.resolve(FAKE_CHAT_ANSWER);
  }
}

/** A queued job as the chat job service reads it back from BullMQ. */
export interface FakeChatJob {
  readonly id: string;
  readonly name: string;
  readonly data: unknown;
  returnvalue: unknown;
  state: string;
  getState(): Promise<string>;
}

/** Chat queue double: just enough of the BullMQ `Queue` surface for the service and Bull Board. */
export interface FakeChatQueue {
  readonly name: string;
  /** Bull Board's adapter reads the queue version and rejects a queue that has none. */
  readonly metaValues: { readonly version: string };
  readonly jobs: Map<string, FakeChatJob>;
  add: jest.Mock<Promise<FakeChatJob>, [name: string, data: unknown, options: { jobId: string }]>;
  getJob: jest.Mock<Promise<FakeChatJob | undefined>, [jobId: string]>;
  /** Accepts the `error` listener the chat job service registers; the fake never emits. */
  on: jest.Mock<void, [event: string, listener: (error: Error) => void]>;
  close: jest.Mock<Promise<void>, []>;
}

const FAKE_QUEUE_VERSION = 'bullmq_test';
const FRESH_JOB_STATE = 'waiting';

/** Creates a queue whose jobs stay `waiting` until a test changes `state` and `returnvalue`. */
export function createFakeChatQueue(): FakeChatQueue {
  const jobs = new Map<string, FakeChatJob>();
  return {
    name: CHAT_QUEUE_NAME,
    metaValues: { version: FAKE_QUEUE_VERSION },
    jobs,
    add: jest.fn((name: string, data: unknown, options: { jobId: string }) => {
      const job: FakeChatJob = {
        id: options.jobId,
        name,
        data,
        returnvalue: null,
        state: FRESH_JOB_STATE,
        getState() {
          return Promise.resolve(this.state);
        },
      };
      jobs.set(job.id, job);
      return Promise.resolve(job);
    }),
    getJob: jest.fn((jobId: string) => Promise.resolve(jobs.get(jobId))),
    on: jest.fn<void, [event: string, listener: (error: Error) => void]>(),
    close: jest.fn(() => Promise.resolve()),
  };
}

/** Database health port that always reports a closed circuit and a reachable database. */
export const upDatabaseHealth: DatabaseHealthPort = {
  check: () => Promise.resolve({ up: true, circuit: 'closed' }),
};
