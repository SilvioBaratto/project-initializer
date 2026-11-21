import { Injectable } from '@nestjs/common';
import { setLogLevel } from '@boundaryml/baml/logging';
import { b } from '../../../baml_client';
import type { ConversationHistory } from '../../../baml_client';
import type { ChatCompletionPort, ChatPrompt } from './chat-completion.port';

// BAML logs every prompt and raw model reply to stdout at its default level. That output carries
// user questions and answers, bypasses the application logger and its redaction, and cannot be
// filtered later.
setLogLevel('OFF');

function toBamlHistory(history: readonly string[]): ConversationHistory | undefined {
  return history.length === 0 ? undefined : { messages: [...history] };
}

/** {@link ChatCompletionPort} backed by the generated BAML client (`baml_src/chatbot.baml`). */
@Injectable()
export class BamlChatCompletionAdapter implements ChatCompletionPort {
  /** {@inheritDoc ChatCompletionPort.complete} */
  async complete(prompt: ChatPrompt): Promise<string> {
    const response = await b.Chat(prompt.question, toBamlHistory(prompt.history));
    return response.answer;
  }

  /** {@inheritDoc ChatCompletionPort.streamAnswer} */
  async *streamAnswer(prompt: ChatPrompt, signal?: AbortSignal): AsyncGenerator<string> {
    const stream = b.stream.Chat(prompt.question, toBamlHistory(prompt.history), { signal });
    for await (const partial of stream) {
      // The first events arrive before any answer text has been parsed.
      if (partial.answer) {
        yield partial.answer;
      }
    }
  }
}
