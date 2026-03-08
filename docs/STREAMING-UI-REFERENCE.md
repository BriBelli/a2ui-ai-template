# Streaming UI Code Reference

Complete reference to all streaming UI implementation code in the A2UI chat application.

---

## Overview

The A2UI chat application uses **Server-Sent Events (SSE)** for real-time streaming of:

- **Pipeline progress** (`step` events) — shown in the thinking indicator
- **Token streaming** (`token` events) — progressive text display with typing cursor
- **Final response** (`complete` event) — full A2UI JSON with components
- **Location requests** (`need_location` event) — geolocation acquisition
- **Errors** (`error` event) — error handling

---

## Frontend Streaming Implementation

### Core Streaming Service

**File:** `apps/a2ui-chat/src/services/chat-service.ts`

#### SSE Event Types

```71:79:apps/a2ui-chat/src/services/chat-service.ts
/** SSE event from the backend pipeline stream. */
export interface StreamEvent {
  id: string;
  status: 'start' | 'done';
  label: string;
  detail?: string;
  reasoning?: string;
  result?: Record<string, unknown>;
}
```

#### ChatMessage Interface (Streaming Flag)

```38:40:apps/a2ui-chat/src/services/chat-service.ts
  /** True while the response is still streaming tokens (text only, no A2UI yet) */
  streaming?: boolean;
```

#### SSE Request Setup

```301:302:apps/a2ui-chat/src/services/chat-service.ts
      const headers = this.getHeaders();
      headers['Accept'] = 'text/event-stream';
```

#### SSE Stream Consumption

```424:516:apps/a2ui-chat/src/services/chat-service.ts
  private async consumeSSE(
    response: Response,
    onProgress?: (
      phase: 'stream-event' | 'token',
      detail?: string,
      streamEvent?: StreamEvent,
    ) => void,
  ): Promise<ChatResponse> {
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalResponse: ChatResponse | null = null;
    // Accumulate raw token deltas for streaming text extraction
    let tokenBuffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';

      for (const part of parts) {
        if (!part.trim()) continue;

        let eventType = 'message';
        let dataStr = '';
        for (const line of part.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7);
          } else if (line.startsWith('data: ')) {
            dataStr += line.slice(6);
          }
        }
        if (!dataStr) continue;

        try {
          const payload = JSON.parse(dataStr);
          if (eventType === 'complete') {
            if (!isValidChatResponse(payload)) {
              console.warn('[SSE] Invalid complete payload structure, skipping');
              continue;
            }
            finalResponse = ChatService.recoverA2UIResponse(payload as Record<string, any>);
            if (finalResponse?.a2ui) {
              console.log('[A2UI] SSE response a2ui:', JSON.stringify(finalResponse.a2ui, null, 2));
            }
          } else if (eventType === 'token') {
            // Accumulate token deltas and extract readable text
            const delta = (payload as Record<string, string>).delta || '';
            tokenBuffer += delta;
            const streamedText = ChatService.extractStreamingText(tokenBuffer);
            if (streamedText) {
              onProgress?.('token', streamedText);
            }
          } else if (eventType === 'need_location') {
            // Backend analyzer wants location — get it and POST it back.
            // The pipeline is paused waiting for our response.
            const requestId = (payload as Record<string, unknown>).request_id as string;
            if (requestId) {
              this.handleLocationRequest(requestId);
            }
          } else if (eventType === 'step') {
            if (!isValidStepEvent(payload)) {
              console.warn('[SSE] Invalid step payload, skipping');
              continue;
            }
            onProgress?.('stream-event', undefined, payload);
          } else if (eventType === 'error') {
            throw new Error(payload.message || 'Stream error');
          }
        } catch (e) {
          if (e instanceof SyntaxError) {
            console.warn('[SSE] Invalid JSON:', dataStr.slice(0, 100));
          } else {
            throw e;
          }
        }
      }

      // Once we have the final response, stop reading — don't wait for connection close
      if (finalResponse) {
        reader.cancel();
        break;
      }
    }

    if (!finalResponse) {
      throw new Error('Stream ended without a complete event');
    }
    return finalResponse;
  }
```

#### Token Streaming Text Extraction

```376:415:apps/a2ui-chat/src/services/chat-service.ts
  static extractStreamingText(partialJson: string): string {
    // Find the "text" field value start
    const marker = /"text"\s*:\s*"/;
    const match = marker.exec(partialJson);
    if (!match) return '';

    const valueStart = match.index + match[0].length;
    let result = '';
    let i = valueStart;

    while (i < partialJson.length) {
      const ch = partialJson[i];
      if (ch === '\\' && i + 1 < partialJson.length) {
        // Handle JSON escape sequences
        const next = partialJson[i + 1];
        if (next === '"') { result += '"'; i += 2; }
        else if (next === '\\') { result += '\\'; i += 2; }
        else if (next === 'n') { result += '\n'; i += 2; }
        else if (next === 'r') { result += '\r'; i += 2; }
        else if (next === 't') { result += '\t'; i += 2; }
        else if (next === '/') { result += '/'; i += 2; }
        else if (next === 'u' && i + 5 < partialJson.length) {
          const hex = partialJson.slice(i + 2, i + 6);
          result += String.fromCharCode(parseInt(hex, 16));
          i += 6;
        } else {
          // Incomplete escape at end of buffer — stop here
          break;
        }
      } else if (ch === '"') {
        // End of the text value
        break;
      } else {
        result += ch;
        i++;
      }
    }

    return result;
  }
```

#### Location Request Handler

```182:214:apps/a2ui-chat/src/services/chat-service.ts
  /**
   * Handle a `need_location` SSE event from the backend.
   * Gets browser geolocation and POSTs it to the backend to unblock
   * the paused pipeline.  Runs async (fire-and-forget) so the SSE
   * reader keeps consuming events.
   */
  private handleLocationRequest(requestId: string): void {
    getUserLocation()
      .then(async (loc) => {
        const body = loc
          ? { lat: loc.lat, lng: loc.lng, label: loc.label ?? null, denied: false }
          : { denied: true };
        try {
          await fetch(`${this.baseUrl}/provide-location/${requestId}`, {
            method: 'POST',
            headers: this.getHeaders(),
            body: JSON.stringify(body),
          });
          console.log('[Geo] Location provided to backend:', loc ? `${loc.lat}, ${loc.lng}` : 'denied');
        } catch (err) {
          console.warn('[Geo] Failed to POST location to backend:', err);
        }
      })
      .catch((err) => {
        console.warn('[Geo] getUserLocation failed:', err);
        // Tell the backend we couldn't get it
        fetch(`${this.baseUrl}/provide-location/${requestId}`, {
          method: 'POST',
          headers: this.getHeaders(),
          body: JSON.stringify({ denied: true }),
        }).catch(() => {});
      });
  }
```

---

### App Component — Streaming State Management

**File:** `apps/a2ui-chat/src/components/a2ui-app.ts`

#### Core Send Logic with Streaming

```1095:1295:apps/a2ui-chat/src/components/a2ui-app.ts
  /**
   * Core chat send logic shared by all contexts (main chat, alert-detail, etc.).
   * Handles: user message push, thinking steps, SSE streaming, token streaming,
   * final response assembly, error handling.
   */
  private async _sendChatMessage(
    userMessage: string,
    opts: {
      messages: 'messages' | 'alertDetailMessages';
      loading: 'isLoading' | 'alertDetailLoading';
      thinkingSteps: 'thinkingSteps' | 'alertDetailThinkingSteps';
      contextPrefix?: string;
      contentStyleOverride?: string;
      toolOverrides?: ChatToolOverrides;
      manageThreads?: boolean;
    },
  ) {
    // ── Helpers to read/write the correct state property ──
    const getMessages = (): ChatMessage[] => this[opts.messages];
    const setMessages = (msgs: ChatMessage[]) => { (this as any)[opts.messages] = msgs; };
    const setLoading = (v: boolean) => { (this as any)[opts.loading] = v; };
    const setThinkingSteps = (s: ThinkingStep[]) => { (this as any)[opts.thinkingSteps] = s; };

    const isFirstMessage = opts.manageThreads && getMessages().length === 0;

    // Start a new thread on first message (main chat only)
    if (isFirstMessage) {
      this.activeThreadId = crypto.randomUUID();
    }

    // Add user message
    setMessages([
      ...getMessages(),
      {
        id: crypto.randomUUID(),
        role: 'user',
        content: userMessage,
        timestamp: Date.now(),
        avatarUrl: this.user?.picture || undefined,
        avatarInitials: this.getInitials(this.user!),
      },
    ]);

    // Push history entry on first message so back clears the conversation
    if (isFirstMessage) {
      history.pushState({ a2ui: 'chat', threadId: this.activeThreadId }, '');
    }

    if (opts.manageThreads) {
      this.persistThread();
      this.refreshThreadList();
    }

    setLoading(true);
    const startTime = performance.now();

    // Thinking steps built from SSE stream events.
    const steps: ThinkingStep[] = [];
    const stepIndexByTool = new Map<string, number>();

    const push = (label: string, detail?: string, tool?: string, reasoning?: string) => {
      const idx = steps.length;
      steps.push({ label, done: false, detail, tool, reasoning });
      if (tool) stepIndexByTool.set(tool, idx);
      setThinkingSteps([...steps]);
      return idx;
    };
    const done = (index: number, label?: string, detail?: string, reasoning?: string) => {
      steps[index] = {
        ...steps[index],
        done: true,
        ...(label && { label }),
        ...(detail && { detail }),
        ...(reasoning && { reasoning }),
      };
      setThinkingSteps([...steps]);
    };

    const handleStreamEvent = (evt: StreamEvent) => {
      const existing = stepIndexByTool.get(evt.id);
      if (evt.status === 'start') {
        if (existing !== undefined) {
          steps[existing] = {
            ...steps[existing],
            label: evt.label,
            detail: evt.detail,
            ...(evt.reasoning && { reasoning: evt.reasoning }),
          };
          setThinkingSteps([...steps]);
        } else {
          push(evt.label, evt.detail, evt.id, evt.reasoning);
        }
      } else if (evt.status === 'done') {
        if (existing !== undefined) {
          done(existing, evt.label, evt.detail, evt.reasoning);
        }
      }
    };

    // ── Streaming message state ──
    const streamingMsgId = crypto.randomUUID();
    let streamingMsgPushed = false;

    try {
      const smartRouting = this.isAutoModel || aiConfig.smartRouting;
      const messageToSend = (opts.contextPrefix ?? '') + userMessage;

      const response = await this.chatService.sendMessage(
        messageToSend,
        this.resolvedProvider,
        this.resolvedModel,
        getMessages(),
        smartRouting,
        (phase, detail, streamEvent?) => {
          if (phase === 'token' && detail != null && uiConfig.streamingText) {
            if (!streamingMsgPushed) {
              streamingMsgPushed = true;
              setThinkingSteps([]);
              setMessages([
                ...getMessages(),
                {
                  id: streamingMsgId,
                  role: 'assistant',
                  content: detail,
                  timestamp: Date.now(),
                  streaming: true,
                },
              ]);
            } else {
              setMessages(
                getMessages().map((m) =>
                  m.id === streamingMsgId ? { ...m, content: detail } : m,
                ),
              );
            }
          } else if (streamEvent) {
            handleStreamEvent(streamEvent);
          }
        },
        opts.contentStyleOverride,
        opts.toolOverrides,
      );

      steps.forEach((_, i) => done(i));

      // Resolve actual model/provider from response
      const actualProviderId = response._provider || this.selectedProvider;
      const actualModelId = response._model || this.selectedModel;
      const actualProvider = this.providers.find((p) => p.id === actualProviderId);
      const fallbackProvider = this.providers.find((p) => p.id === this.selectedProvider);
      const actualModel =
        actualProvider?.models.find((m) => m.id === actualModelId) ||
        fallbackProvider?.models.find((m) => m.id === actualModelId);
      const modelLabel = actualModel?.name || actualModelId;
      const wasUpgraded = !!response._model_upgraded_from;
      const elapsed = (performance.now() - startTime) / 1000;

      const finalMessage = {
        id: streamingMsgPushed ? streamingMsgId : crypto.randomUUID(),
        role: 'assistant' as const,
        content: response.text || '',
        a2ui: response.a2ui,
        timestamp: Date.now(),
        model: modelLabel,
        provider: actualProviderId,
        modelUpgraded: wasUpgraded,
        suggestions: response.suggestions,
        duration: Math.round(elapsed * 10) / 10,
        images: response._images,
        style: response._style,
        sources: response._sources,
        streaming: false,
      };

      if (streamingMsgPushed) {
        setMessages(getMessages().map((m) => (m.id === streamingMsgId ? finalMessage : m)));
      } else {
        setMessages([...getMessages(), finalMessage]);
      }

      // Update Data Sources panel — show which sources the AI used
      dataSourceRegistry.updateActiveFromMessage(finalMessage.sources);

      if (opts.manageThreads) {
        this.persistThread();
        this.refreshThreadList();
      }
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        id: streamingMsgPushed ? streamingMsgId : crypto.randomUUID(),
        role: 'assistant' as const,
        content: 'Sorry, there was an error processing your request.',
        timestamp: Date.now(),
        streaming: false,
      };
      if (streamingMsgPushed) {
        setMessages(getMessages().map((m) => (m.id === streamingMsgId ? errorMessage : m)));
      } else {
        setMessages([...getMessages(), errorMessage]);
      }
```

**Key streaming logic:**

- **Line 1194-1196:** Creates unique streaming message ID and tracks push state
- **Line 1208-1232:** Progress callback handles `token` events (updates message content) and `stream-event` events (updates thinking steps)
- **Line 1209:** Checks `uiConfig.streamingText` flag before enabling token streaming
- **Line 1269-1273:** Replaces streaming message with final message on completion

---

### Chat Message Component — Streaming UI Rendering

**File:** `apps/a2ui-chat/src/components/chat/a2ui-chat-message.ts`

#### Streaming State Tracking

```949:964:apps/a2ui-chat/src/components/chat/a2ui-chat-message.ts
  /**
   * Track whether the message just transitioned from streaming to complete.
   * Used to apply the staggered A2UI component entrance animation.
   */
  @state() private _wasStreaming = false;

  willUpdate(changed: Map<string, unknown>) {
    super.willUpdate(changed);
    if (changed.has("message")) {
      const prev = changed.get("message") as ChatMessage | undefined;
      // Detect transition: was streaming → now complete (has a2ui)
      if (prev?.streaming && !this.message.streaming && this.message.a2ui) {
        this._wasStreaming = true;
      }
    }
  }
```

#### Streaming Cursor CSS Animation

```889:903:apps/a2ui-chat/src/components/chat/a2ui-chat-message.ts
    /* ── Streaming cursor animation ────────────── */

    .streaming-text::after {
      content: '▊';
      display: inline;
      animation: blink 0.7s steps(2) infinite;
      color: var(--a2ui-accent);
      font-weight: var(--a2ui-font-normal, 400);
      margin-left: 1px;
    }

    @keyframes blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0; }
    }
```

#### Staggered Component Entrance Animation

```905:933:apps/a2ui-chat/src/components/chat/a2ui-chat-message.ts
    /* ── Staggered A2UI component entrance ─────── */
    /* Applied when the message transitions from streaming → complete.
       Targets the direct children of .a2ui-root (the flex container with
       gap:16px) so component spacing is preserved.  Each child gets an
       increasing animation-delay via nth-child for a cascading effect. */

    .a2ui-content.staggered .a2ui-root > * {
      opacity: 0;
      transform: translateY(8px);
      animation: componentSlideIn 0.35s cubic-bezier(0.22, 1, 0.36, 1) forwards;
    }
    .a2ui-content.staggered .a2ui-root > :nth-child(1) { animation-delay: 0ms; }
    .a2ui-content.staggered .a2ui-root > :nth-child(2) { animation-delay: 120ms; }
    .a2ui-content.staggered .a2ui-root > :nth-child(3) { animation-delay: 240ms; }
    .a2ui-content.staggered .a2ui-root > :nth-child(4) { animation-delay: 360ms; }
    .a2ui-content.staggered .a2ui-root > :nth-child(5) { animation-delay: 480ms; }
    .a2ui-content.staggered .a2ui-root > :nth-child(6) { animation-delay: 600ms; }
    .a2ui-content.staggered .a2ui-root > :nth-child(n+7) { animation-delay: 720ms; }

    @keyframes componentSlideIn {
      from {
        opacity: 0;
        transform: translateY(8px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
```

#### Streaming State Rendering Logic

```1420:1443:apps/a2ui-chat/src/components/chat/a2ui-chat-message.ts
            : this.message.streaming
              ? html`
                  <!-- Streaming state: text only, with blinking cursor -->
                  <div class="response-layout pos-${uiConfig.sourcesPosition}">
                    <div class="response-main">
                      <div class="bubble">
                        ${content
                          ? html`<div class="text-content streaming-text">${md(content)}</div>`
                          : html`<div class="text-content streaming-text">&nbsp;</div>`}
                      </div>
                    </div>
                  </div>
                `
              : html`
                <div class="response-layout pos-${uiConfig.sourcesPosition}">
                  <div class="response-main">
                    <div class="bubble">
                      ${content
                        ? html` <div class="text-content">${md(content)}</div> `
                        : ""}
                      ${a2ui
                        ? html`
                            <div class="a2ui-content${this._wasStreaming ? " staggered" : ""}">
                              ${A2UIRenderer.render(a2ui)}
                            </div>
```

**Key rendering logic:**

- **Line 1420:** Checks `message.streaming` flag
- **Line 1427:** Applies `streaming-text` class for cursor animation
- **Line 1442:** Applies `staggered` class when transitioning from streaming to complete

---

### UI Configuration — Streaming Toggle

**File:** `apps/a2ui-chat/src/config/ui-config.ts`

#### Streaming Text Config

```66:73:apps/a2ui-chat/src/config/ui-config.ts
  /**
   * Show progressive token streaming in chat while the AI generates.
   * When enabled, response text streams character-by-character with a typing cursor.
   * When disabled, the thinking indicator stays visible until the full response arrives.
   * Backend SSE streaming always runs regardless — this only controls the UX.
   * Default: true.
   */
  streamingText: boolean;
```

#### Settings Panel Toggle

**File:** `apps/a2ui-chat/src/components/a2ui-settings-panel.ts`

```716:716:apps/a2ui-chat/src/components/a2ui-settings-panel.ts
  @state() private streamingText = uiConfig.streamingText;
```

```961:963:apps/a2ui-chat/src/components/a2ui-settings-panel.ts
  private handleStreamingText() {
    this.streamingText = !this.streamingText;
    setUIConfig({ streamingText: this.streamingText });
```

```1598:1599:apps/a2ui-chat/src/components/a2ui-settings-panel.ts
                .checked=${this.streamingText}
                @change=${this.handleStreamingText}
```

---

## Backend Streaming Implementation

### SSE Endpoint Handler

**File:** `apps/a2ui-agent/src/main.py`

#### SSE Response Generator

```363:400:apps/a2ui-agent/src/main.py
    # ── SSE streaming path ──
    if wants_sse:
        async def _sse_generator():
            try:
                async for event in llm_service.generate_stream(
                    body.message,
                    body.provider,
                    body.model,
                    history=history_dicts,
                    user_location=location_dict,
                    content_style=body.contentStyle,
                    performance_mode=body.performanceMode,
                    smart_routing=body.smartRouting,
                    enable_web_search=body.enableWebSearch,
                    enable_geolocation=body.enableGeolocation,
                    enable_data_sources=body.enableDataSources,
                    data_context=data_context_dicts,
                    temperature=body.temperature,
                    data_source_overrides=body.dataSourceOverrides,
                    data_source_disabled=body.dataSourceDisabled,
                ):
                    etype = event.get("event", "message")
                    payload = _json.dumps(event.get("data", {}), default=str)
                    yield f"event: {etype}\ndata: {payload}\n\n"
            except Exception as exc:
                logger.exception("SSE stream error")
                err = _json.dumps({"message": "Something went wrong. Please try again."})
                yield f"event: error\ndata: {err}\n\n"

        return StreamingResponse(
            _sse_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
```

**Key backend streaming:**

- **Line 367:** Calls `llm_service.generate_stream()` async generator
- **Line 384-386:** Formats SSE events: `event: {type}\ndata: {json}\n\n`
- **Line 392-399:** Returns `StreamingResponse` with proper SSE headers

---

## SSE Event Types Reference

### Event: `step`

Pipeline progress updates shown in the thinking indicator.

**Format:**

```json
{
  "id": "analyzer",
  "status": "start" | "done",
  "label": "Analyzing intent",
  "detail": "style=analytical search=false",
  "reasoning": "User asked about claims metrics"
}
```

**Frontend handling:** `apps/a2ui-chat/src/services/chat-service.ts:487-492`

### Event: `token`

Progressive text streaming (character-by-character).

**Format:**

```json
{
  "delta": "{\"text\":\"Hello world\"}"
}
```

**Frontend handling:** `apps/a2ui-chat/src/services/chat-service.ts:472-479`

### Event: `complete`

Final A2UI response with full JSON payload.

**Format:**

```json
{
  "text": "Response text",
  "a2ui": { "version": "1.0", "components": [...] },
  "_search": {...},
  "_sources": [...],
  "_model": "claude-sonnet-4",
  ...
}
```

**Frontend handling:** `apps/a2ui-chat/src/services/chat-service.ts:463-471`

### Event: `need_location`

Backend requests browser geolocation.

**Format:**

```json
{
  "request_id": "uuid-here"
}
```

**Frontend handling:** `apps/a2ui-chat/src/services/chat-service.ts:480-486`

### Event: `error`

Error during processing.

**Format:**

```json
{
  "message": "Error description"
}
```

**Frontend handling:** `apps/a2ui-chat/src/services/chat-service.ts:493-494`

---

## Streaming Flow Diagram

```
User sends message
  |
  v
Frontend: POST /api/chat (Accept: text/event-stream)
  |
  v
Backend: llm_service.generate_stream() → async generator
  |
  ├── yield {"event": "step", "data": {...}}     → Thinking indicator updates
  ├── yield {"event": "token", "data": {...}}    → Text streams (if enabled)
  ├── yield {"event": "need_location", ...}      → Geolocation request
  └── yield {"event": "complete", "data": {...}} → Final response
  |
  v
Frontend: consumeSSE() parses stream
  |
  ├── Token events → Update message.content (if streamingText enabled)
  ├── Step events → Update thinking steps
  ├── Complete event → Replace streaming message with final message
  └── Transition: streaming=true → streaming=false → Staggered animation
```

---

## Key Files Summary

| File                                                      | Purpose                                                      |
| --------------------------------------------------------- | ------------------------------------------------------------ |
| `apps/a2ui-chat/src/services/chat-service.ts`             | SSE stream consumption, token extraction, location handling  |
| `apps/a2ui-chat/src/components/a2ui-app.ts`               | Streaming state management, progress callbacks               |
| `apps/a2ui-chat/src/components/chat/a2ui-chat-message.ts` | Streaming UI rendering, cursor animation, staggered entrance |
| `apps/a2ui-chat/src/config/ui-config.ts`                  | Streaming text toggle configuration                          |
| `apps/a2ui-chat/src/components/a2ui-settings-panel.ts`    | User toggle for streaming text                               |
| `apps/a2ui-agent/src/main.py`                             | SSE endpoint handler, stream generator                       |
| `apps/a2ui-agent/src/llm_providers.py`                    | `generate_stream()` async generator implementation           |

---

## Related Documentation

- **[frontend-guide.md](frontend-guide.md)** — Complete frontend architecture and rendering pipeline
- **[agent-development.md](agent-development.md)** — Backend pipeline and SSE event types
- **[pipeline-workflow.md](pipeline-workflow.md)** — Backend pipeline phases and streaming integration
