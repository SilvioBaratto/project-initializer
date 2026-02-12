export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isError?: boolean;
}

export interface ChatRequest {
  user_question: string;
  conversation_history: { messages: string[] };
}

export interface ChatResponse {
  answer: string;
}
