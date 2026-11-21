/** Injection token for the {@link ChatCompletionPort} implementation. */
export const CHAT_COMPLETION_PORT = Symbol('CHAT_COMPLETION_PORT');

/** What the assistant is asked, independent of any LLM provider. */
export interface ChatPrompt {
  readonly question: string;
  /** Earlier conversation turns, oldest first; empty for a first question. */
  readonly history: readonly string[];
}

/** Boundary to the LLM provider, so services and the queue processor never import a vendor client. */
export interface ChatCompletionPort {
  /**
   * Produces the full answer.
   *
   * @throws Error when the provider cannot be reached or rejects the request.
   */
  complete(prompt: ChatPrompt): Promise<string>;

  /**
   * Streams the answer as it is generated.
   *
   * @param prompt - What to ask.
   * @param signal - Aborts the provider call when the consumer no longer wants the answer, so the
   *   tokens it would still generate are not paid for.
   * @returns An iterable whose every element is the answer accumulated so far, not a delta.
   * @throws Error from the iteration when the provider fails mid-stream or `signal` aborts.
   */
  streamAnswer(prompt: ChatPrompt, signal?: AbortSignal): AsyncIterable<string>;
}
