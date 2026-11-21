class ChatTurn {
  role "user" | "assistant"
  content string
}

class ChatResponse {
  answer string @description("The chatbot's answer to the user's question")
}

// History is rendered as real user/assistant messages after the system block.
// Inlining it in the system prompt would let a crafted "previous message" carry
// system-level authority.
function Chat(user_question: string, history: ChatTurn[]) -> ChatResponse {
  client AzureOpenAI

  prompt #"
    {{ _.role("system") }}
    You are a helpful AI assistant. Answer questions clearly and concisely.

    {{ ctx.output_format }}

    {% for turn in history %}
    {{ _.role(turn.role) }}
    {{ turn.content }}
    {% endfor %}

    {{ _.role("user") }}
    {{ user_question }}
  "#
}
