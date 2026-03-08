## Code Cleanup Notes

This version uses direct multi-provider LLM access (OpenAI, Anthropic, Google Gemini) with a unified `LLMProvider` ABC interface. Each provider has its own SDK and API key.

### Architecture Decisions

1. **Multi-provider support** — OpenAI, Anthropic, and Gemini each have dedicated provider classes with native SDK access
2. **Unified interface** — All providers implement the same `LLMProvider` ABC (`is_available()`, `generate()`, `generate_stream_tokens()`)
3. **Adaptive model routing** — The pipeline selects the best available model based on complexity tier, speed, and tags
4. **Fallback logic** — If a provider/model fails, the pipeline falls back to alternatives across providers
