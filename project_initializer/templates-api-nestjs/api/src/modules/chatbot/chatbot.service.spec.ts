import { Test, TestingModule } from '@nestjs/testing';
import { ChatbotService } from './chatbot.service';

// Variables prefixed with 'mock' are hoisted alongside jest.mock() by Jest's transform.
const mockBChat = jest.fn();
const mockBStreamChat = jest.fn();

jest.mock('../../../baml_client', () => ({
  b: {
    Chat: (...args: unknown[]) => mockBChat(...args),
    stream: {
      StreamChat: (...args: unknown[]) => mockBStreamChat(...args),
    },
  },
}));

describe('ChatbotService', () => {
  let service: ChatbotService;

  beforeEach(async () => {
    jest.clearAllMocks();

    const module: TestingModule = await Test.createTestingModule({
      providers: [ChatbotService],
    }).compile();

    service = module.get<ChatbotService>(ChatbotService);
  });

  describe('chat()', () => {
    it('when b.Chat resolves, returns the BAML answer', async () => {
      mockBChat.mockResolvedValue({ answer: 'Hello from BAML' });

      const result = await service.chat({ user_question: 'Hi' });

      expect(result).toEqual({ answer: 'Hello from BAML' });
    });

    it('when b.Chat rejects, returns the fallback message', async () => {
      mockBChat.mockRejectedValue(new Error('BAML unavailable'));

      const result = await service.chat({ user_question: 'Hi' });

      expect(result).toEqual({
        answer: 'Sorry, I encountered an error processing your request.',
      });
    });
  });

  describe('streamChat()', () => {
    it('when StreamChat yields events with answer, yields { content, done: false } per event', async () => {
      async function* fakeStream() {
        yield { answer: 'chunk one' };
        yield { answer: 'chunk two' };
      }
      mockBStreamChat.mockReturnValue(fakeStream());

      const chunks: { content: string; done: boolean }[] = [];
      for await (const chunk of service.streamChat({ user_question: 'stream me' })) {
        chunks.push(chunk);
      }

      expect(chunks).toEqual([
        { content: 'chunk one', done: false },
        { content: 'chunk two', done: false },
      ]);
    });
  });
});
