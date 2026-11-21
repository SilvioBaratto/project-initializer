import { Inject, Injectable, ServiceUnavailableException } from '@nestjs/common';
import { CHAT_UNAVAILABLE_MESSAGE } from './chat.constants';
import { CHAT_COMPLETION_PORT, ChatCompletionPort, ChatPrompt } from './chat-completion.port';
import { ChatRequest, ChatResponseDto, StreamChunkDto } from './dto/chat.dto';

function toChatPrompt(request: ChatRequest): ChatPrompt {
  return {
    question: request.user_question,
    history: request.conversation_history?.messages ?? [],
  };
}

function unavailable(cause: unknown): ServiceUnavailableException {
  return new ServiceUnavailableException(CHAT_UNAVAILABLE_MESSAGE, { cause });
}

/**
 * Answers chat questions through the {@link ChatCompletionPort}.
 *
 * Every failure follows one policy: the caller gets a generic {@link ServiceUnavailableException}
 * that carries the original error as its `cause`, and the service does not log it. The component
 * that ends the request logs the cause once: the HTTP exception filter for a plain request, the
 * stream controller for a stream and the queue processor for a job. No answer is ever returned
 * in-band on error, so clients, error-rate metrics and the queue's retry logic all see the failure.
 */
@Injectable()
export class ChatbotService {
  constructor(@Inject(CHAT_COMPLETION_PORT) private readonly completion: ChatCompletionPort) {}

  /**
   * Answers one question.
   *
   * @throws ServiceUnavailableException when the completion provider fails; the failure is its
   *   `cause`.
   */
  async chat(request: ChatRequest): Promise<ChatResponseDto> {
    try {
      return { answer: await this.completion.complete(toChatPrompt(request)) };
    } catch (error) {
      throw unavailable(error);
    }
  }

  /**
   * Streams the answer as it is generated.
   *
   * @param request - Validated question and history.
   * @param signal - Aborts the provider call, so an abandoned stream stops costing tokens.
   * @returns Chunks whose `content` is the answer so far; the generator ends without a terminal
   *   chunk, leaving that to the caller.
   * @throws ServiceUnavailableException from the iteration when the provider fails mid-stream or
   *   `signal` aborts; the failure is its `cause`.
   */
  async *streamChat(request: ChatRequest, signal?: AbortSignal): AsyncGenerator<StreamChunkDto> {
    try {
      for await (const answer of this.completion.streamAnswer(toChatPrompt(request), signal)) {
        yield { content: answer, done: false };
      }
    } catch (error) {
      throw unavailable(error);
    }
  }
}
