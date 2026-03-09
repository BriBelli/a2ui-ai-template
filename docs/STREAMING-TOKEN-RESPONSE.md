
## Streaming Token Response — Engineering Game Plan

### Current Architecture

```
User types → Frontend POST (SSE) → Backend generate_stream()
                                      │
                                      ├─ yield step events (search, analyze, etc.)
                                      │
                                      ├─ await provider.generate() ← BLOCKS HERE (entire response)
                                      │
                                      └─ yield "complete" event (full JSON response)
```

The SSE pipe already exists and works well for pipeline step events. The **only blocking point** is line 1867:

```1867:1869:a2ui-agent/llm_providers.py
        response = await effective_provider.generate(
            augmented_message, effective_model, effective_history, system_prompt=system_prompt,
        )
```

This calls `_call_llm()`, which does a non-streaming `chat.completions.create()` and waits for the entire response. For GPT-5, that's ~50-60 seconds of dead silence.

### What Needs to Change

**5 layers, bottom to top:**

---

#### Layer 1: Provider `_call_llm_stream()` methods (Backend — Medium effort)

Add a streaming variant to each provider. OpenAI, Anthropic, and Gemini all support `stream=True`.

```python
# OpenAI example
async def _call_llm_stream(self, message, model, history, system_prompt):
    messages = _build_messages(message, history, system_prompt=system_prompt)
    stream = await self.client.chat.completions.create(
        model=model, messages=messages,
        response_format={"type": "json_object"},
        stream=True, **extra,
    )
    full_content = ""
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        full_content += delta
        yield delta  # Each token as it arrives
    return full_content  # Final assembled string
```

**Files:** `llm_providers.py` — 4 providers × ~30 lines each
**Effort:** ~2 hours

---

#### Layer 2: `generate_stream()` yields token chunks (Backend — Medium effort)

Instead of `await provider.generate()`, iterate the stream and yield a new SSE event type:

```python
# New event type: "token"
yield {"event": "step", "data": {"id": "llm", "status": "start", ...}}

full_content = ""
async for delta in effective_provider._call_llm_stream(...):
    full_content += delta
    yield {"event": "token", "data": {"delta": delta}}

# Parse the full JSON once complete
response = parse_llm_json(full_content)
yield {"event": "complete", "data": response}
```

**Key decision:** You still need the full JSON to parse the A2UI component tree. Streaming gives UX feedback, but the actual A2UI render still happens on `complete`. The streaming tokens would show the raw text being typed out in a temporary "generating..." state.

**Files:** `llm_providers.py` — `generate_stream()` method
**Effort:** ~1-2 hours

---

#### Layer 3: Frontend `consumeSSE()` handles `token` events (Frontend — Low effort)

The SSE parser already handles multiple event types. Add `token`:

```typescript
// In consumeSSE()
} else if (eventType === 'token') {
    partialText += payload.delta;
    onProgress?.('token', partialText);
}
```

**Files:** `chat-service.ts`
**Effort:** ~30 min

---

#### Layer 4: `a2ui-app.ts` shows streaming text (Frontend — Medium effort)

The `sendMessage` call currently returns only after the full response. For streaming, you'd show a temporary message that updates as tokens arrive:

```typescript
// Before sendMessage resolves, show a temporary streaming message
let streamingContent = '';

const response = await this.chatService.sendMessage(
    message, provider, model, history,
    (phase, detail, streamEvent?) => {
        // ... existing step handling ...
        if (phase === 'token') {
            streamingContent = detail!;
            // Update the last message's content reactively
            this.updateStreamingMessage(streamingContent);
        }
    },
);
// On complete, replace the streaming message with the full A2UI response
```

**Files:** `a2ui-app.ts`
**Effort:** ~2-3 hours (reactive updates, cleanup, loading states)

---

#### Layer 5: Chat message component streaming state (Frontend — Low effort)

`a2ui-chat-message.ts` would need a `streaming` boolean property. When true, it renders the raw markdown text (no A2UI components yet). When the `complete` event arrives, it swaps to the full A2UI render.

**Files:** `a2ui-chat-message.ts`
**Effort:** ~1 hour

---

### Effort Summary

| Layer | What | Where | Effort |
|---|---|---|---|
| 1 | Provider stream methods | `llm_providers.py` | ~2h |
| 2 | Pipeline yields tokens | `llm_providers.py` | ~1-2h |
| 3 | SSE parser handles tokens | `chat-service.ts` | ~30min |
| 4 | App shows streaming text | `a2ui-app.ts` | ~2-3h |
| 5 | Message streaming state | `a2ui-chat-message.ts` | ~1h |
| — | Testing + edge cases | All | ~2h |
| **Total** | | | **~8-10 hours** |

### What You Get

- **No more timeouts** — the connection stays alive as long as tokens are flowing
- **Perceived speed** — users see text appearing in ~1-2 seconds, even for slow models
- **GPT-5 becomes usable** — 50 seconds of typing looks fine; 50 seconds of nothing looks broken
- **Every model feels faster** — even GPT-4.1 goes from 8s of blank to instant text

### Important Tradeoff

Since the LLM outputs JSON (not plain text), the streaming tokens are raw JSON fragments — not pretty markdown. Two approaches:

**A. Simple (recommended first):** Show a typing indicator / "Generating..." animation while tokens stream in the background. Replace with full A2UI render on `complete`. Users see instant feedback without partial JSON weirdness.

**B. Advanced (later):** Parse the `"text"` field incrementally from the JSON stream and render markdown in real-time. More complex but gives the ChatGPT-style typing effect.

Option A gets you 80% of the UX improvement with 40% of the effort. Option B is a polish pass later.

---

Switch to Agent mode if you want me to start building it.