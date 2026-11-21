// Only AzureOpenAI is wired to a function (see chatbot.baml). The others are
// ready-made alternatives: point a function's `client` at one and set its key.

client<llm> CustomGPT5 {
  provider openai
  options {
    model "gpt-5.2"
    api_key env.OPENAI_API_KEY
  }
}

client<llm> Gemini {
  provider google-ai
  options {
    model "gemini-3-pro-preview"
    api_key env.GOOGLE_API_KEY
    generationConfig {
      maxOutputTokens 16000
    }
  }
}

client<llm> CustomOpus45 {
  provider anthropic
  options {
    model "claude-opus-4-5-20251101"
    api_key env.ANTHROPIC_API_KEY
    max_tokens 16000
  }
}

client<llm> CustomSonnet45 {
  provider anthropic
  options {
    model "claude-sonnet-4-5-20250929"
    api_key env.ANTHROPIC_API_KEY
    max_tokens 16000
  }
}

client<llm> AzureOpenAI {
  provider azure-openai
  retry_policy Exponential
  options {
    base_url env.AZURE_OPENAI_BASE_URL
    api_version env.AZURE_OPENAI_API_VERSION
    api_key env.AZURE_OPENAI_API_KEY
    // No output cap is sent, so the deployment's own default applies and models that reject
    // `max_tokens` keep working. Set `max_completion_tokens` here to bound the cost of a reply.
    max_tokens null
  }
}

// Local model; OLLAMA_BASE_URL overrides the localhost default when the API
// runs in Docker. Low temperature and a small token cap keep replies fast.
client<llm> Ollama {
  provider "openai-generic"
  retry_policy Constant
  options {
    base_url env.OLLAMA_BASE_URL ?? "http://localhost:11434/v1"
    model qwen3:4b
    temperature 0.3
    max_tokens 100
  }
}

client<llm> OpenaiFallback {
  provider fallback
  options {
    strategy [AzureOpenAI, CustomGPT5]
  }
}

retry_policy Constant {
  max_retries 3
  strategy {
    type constant_delay
    delay_ms 200
  }
}

// Each call is tried up to 3 times. A chat job on the NestJS queue is also attempted 3 times
// (CHAT_JOB_OPTIONS), so a job that keeps failing reaches the provider up to 9 times.
retry_policy Exponential {
  max_retries 2
  strategy {
    type exponential_backoff
    delay_ms 300
    multiplier 1.5
    max_delay_ms 10000
  }
}
