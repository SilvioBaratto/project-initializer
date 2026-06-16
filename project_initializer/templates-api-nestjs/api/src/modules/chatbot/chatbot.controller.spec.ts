import { Test, TestingModule } from '@nestjs/testing';
import { ChatbotController } from './chatbot.controller';
import { ChatbotService } from './chatbot.service';
import { ChatJobService } from './chat-job.service';

const mockChatbotService = {
  chat: jest.fn(),
  streamChat: jest.fn(),
};

const mockChatJobService = {
  enqueueChat: jest.fn(),
  getJobStatus: jest.fn(),
};

describe('ChatbotController', () => {
  let controller: ChatbotController;

  beforeEach(async () => {
    jest.clearAllMocks();

    const module: TestingModule = await Test.createTestingModule({
      controllers: [ChatbotController],
      providers: [
        { provide: ChatbotService, useValue: mockChatbotService },
        { provide: ChatJobService, useValue: mockChatJobService },
      ],
    }).compile();

    controller = module.get<ChatbotController>(ChatbotController);
  });

  describe('enqueueChat()', () => {
    it('when POST /chat/jobs is called, returns { jobId } from enqueueChat', async () => {
      mockChatJobService.enqueueChat.mockResolvedValue('job-abc');

      const result = await controller.enqueueChat({ user_question: 'Hello' });

      expect(mockChatJobService.enqueueChat).toHaveBeenCalledWith({ user_question: 'Hello' });
      expect(result).toEqual({ jobId: 'job-abc' });
    });
  });

  describe('getJobStatus()', () => {
    it('when GET /chat/jobs/:id is called with a completed job, returns jobId, state and result', async () => {
      mockChatJobService.getJobStatus.mockResolvedValue({
        state: 'completed',
        result: { answer: 'Hello from BAML' },
      });

      const result = await controller.getJobStatus('job-abc');

      expect(mockChatJobService.getJobStatus).toHaveBeenCalledWith('job-abc');
      expect(result).toEqual({
        jobId: 'job-abc',
        state: 'completed',
        result: { answer: 'Hello from BAML' },
      });
    });

    it('when GET /chat/jobs/:id is called with an active job, returns jobId, state and null result', async () => {
      mockChatJobService.getJobStatus.mockResolvedValue({
        state: 'active',
        result: null,
      });

      const result = await controller.getJobStatus('job-xyz');

      expect(result).toEqual({ jobId: 'job-xyz', state: 'active', result: null });
    });
  });
});
