// Conversation history for context
class ConversationHistory {
  messages string[] @description("List of previous messages in the conversation")
}

// Simple response with just the answer
class ChatResponse {
  answer string @description("The chatbot's answer to the user's question")
}

// Non-streaming chat function
function Chat(
  user_question: string,
  conversation_history: ConversationHistory?
) -> ChatResponse {
  client CustomSonnet45

  prompt #"
    {{ _.role("system") }}
    You are a helpful AI assistant. Answer questions clearly and concisely.

    {% if conversation_history %}
    ## Previous Conversation:
    {% for msg in conversation_history.messages %}
    {{ msg }}
    {% endfor %}
    {% endif %}

    {{ _.role("user") }}
    {{ user_question }}

    {{ ctx.output_format }}
  "#
}

// Streaming chat function for real-time responses
function StreamChat(
  user_question: string,
  conversation_history: ConversationHistory?
) -> ChatResponse {
  client CustomSonnet45

  prompt #"
    {{ _.role("system") }}
    You are a helpful AI assistant. Answer questions clearly and concisely.

    {% if conversation_history %}
    ## Previous Conversation:
    {% for msg in conversation_history.messages %}
    {{ msg }}
    {% endfor %}
    {% endif %}

    {{ _.role("user") }}
    {{ user_question }}

    {{ ctx.output_format }}
  "#
}
