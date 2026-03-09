import type { A2UIResponse } from '@a2ui/core';
import { aiConfig } from '../config/ui-config';
import { getCachedLocation, getUserLocation } from './geolocation-service';
import { toast } from './toast-service';

export interface SourceCitation {
  title: string;
  url: string;
  type?: 'web' | 'data';
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  a2ui?: A2UIResponse;
  timestamp: number;
  model?: string;
  /** Okta user avatar URL (user messages only) */
  avatarUrl?: string;
  /** Initials fallback when no avatar image (user messages only) */
  avatarInitials?: string;
  /** Follow-up suggestions shown below assistant responses */
  suggestions?: string[];
  /** Generation duration in seconds */
  duration?: number;
  /** Search result images rendered as a visual strip */
  images?: string[];
  /** Content style used for this response (e.g. "content", "analytical") */
  style?: string;
  /** Source citations (web search results + data sources) */
  sources?: SourceCitation[];
  /** Provider ID (e.g. "openai", "anthropic", "google") */
  provider?: string;
  /** True when model was dynamically upgraded by adaptive routing */
  modelUpgraded?: boolean;
  /** True while the response is still streaming tokens (text only, no A2UI yet) */
  streaming?: boolean;
}

/** Simplified message format for API history */
export interface HistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  text?: string;
  a2ui?: A2UIResponse;
  suggestions?: string[];
  _search?: {
    searched: boolean;
    success?: boolean;
    results_count?: number;
    images_count?: number;
    error?: string;
    query?: string;
  };
  _location?: boolean;
  _images?: string[];
  _style?: string;
  _sources?: SourceCitation[];
  _data_sources?: Record<string, unknown>;
  _model?: string;
  _provider?: string;
  _model_upgraded_from?: string;
  _provider_upgraded_from?: string;
}

/** SSE event from the backend pipeline stream. */
export interface StreamEvent {
  id: string;
  status: 'start' | 'done';
  label: string;
  detail?: string;
  reasoning?: string;
  result?: Record<string, unknown>;
}

export interface LLMModel {
  id: string;
  name: string;
}

export interface LLMProvider {
  id: string;
  name: string;
  models: LLMModel[];
}

export interface ProvidersResponse {
  providers: LLMProvider[];
}

function isValidStepEvent(payload: unknown): payload is StreamEvent {
  if (!payload || typeof payload !== 'object') return false;
  const p = payload as Record<string, unknown>;
  return (
    typeof p.id === 'string' &&
    (p.status === 'start' || p.status === 'done') &&
    typeof p.label === 'string'
  );
}

function isValidChatResponse(data: unknown): data is Record<string, unknown> {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  if (d.text !== undefined && typeof d.text !== 'string') return false;
  if (d.a2ui !== undefined && typeof d.a2ui !== 'object') return false;
  return true;
}


export class ChatService {
  private baseUrl = '/api';

  /**
   * Recover a structured A2UI response when the backend returns the raw
   * LLM JSON inside the `text` field (i.e. parse_llm_json fell through).
   *
   * Detects the pattern: { text: '{"text":"...","a2ui":{...}}' } and
   * re-parses the embedded JSON so the UI gets proper components.
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  static recoverA2UIResponse(data: Record<string, any>): Record<string, any> {
    // Already has structured a2ui — nothing to recover
    if (data.a2ui) return data;

    const text = data.text;
    if (typeof text !== 'string') return data;

    // Quick heuristic: if text looks like it contains a JSON object with
    // "a2ui" or "text" keys, try to parse it.
    const jsonStart = text.indexOf('{');
    if (jsonStart === -1) return data;

    try {
      const candidate = text.slice(jsonStart);
      const parsed = JSON.parse(candidate);
      if (parsed && typeof parsed === 'object' && (parsed.a2ui || parsed.text)) {
        console.warn('[A2UI] Recovered double-encoded response from text field');
        // Merge parsed fields into the response, preserving metadata (_search, etc.)
        return { ...data, ...parsed };
      }
    } catch {
      // Not valid JSON — leave the response as-is
    }

    return data;
  }

  /**
   * Build request headers, including optional API key auth.
   * Set VITE_A2UI_API_KEY in your .env to enable.
   */
  private getHeaders(json = true): Record<string, string> {
    const headers: Record<string, string> = {};
    if (json) {
      headers['Content-Type'] = 'application/json';
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const apiKey = (import.meta as any).env?.VITE_A2UI_API_KEY;
    if (apiKey) {
      headers['X-API-Key'] = apiKey;
    }
    return headers;
  }

  async getProviders(): Promise<LLMProvider[]> {
    try {
      const response = await fetch(`${this.baseUrl}/providers`, {
        headers: this.getHeaders(false),
      });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data: ProvidersResponse = await response.json();
      return data.providers;
    } catch (error) {
      console.error('Failed to fetch providers:', error);
      return [];
    }
  }

  /**
   * Send a message to the backend via SSE stream for real-time pipeline events.
   * Falls back to regular JSON if the stream fails.
   *
   * If location was previously resolved and cached, it's included in the
   * request so the backend can use it immediately. Otherwise the backend
   * analyzer decides whether location is needed and requests it mid-stream
   * via a ``need_location`` SSE event — the frontend then resolves the
   * browser Geolocation API and POSTs the result back.
   */
  async sendMessage(
    message: string,
    provider?: string,
    model?: string,
    history?: ChatMessage[],
    smartRouting?: boolean,
    onProgress?: (
      phase: 'stream-event' | 'token',
      detail?: string,
      streamEvent?: StreamEvent,
    ) => void,
    contentStyleOverride?: string,
    toolOverrides?: Record<string, unknown>,
  ): Promise<ChatResponse> {
    try {
      const location = aiConfig.geolocation ? getCachedLocation() : null;

      const body: Record<string, unknown> = {
        message,
        provider,
        model,
        enableWebSearch: aiConfig.webSearch,
        enableGeolocation: aiConfig.geolocation,
        enableDataSources: aiConfig.dataSources,
        contentStyle: aiConfig.contentStyle,
        performanceMode: aiConfig.performanceMode,
        smartRouting: smartRouting ?? aiConfig.smartRouting,
        ...(location && { userLocation: location }),
      };

      if (aiConfig.conversationHistory && history && history.length > 0) {
        const historyMessages: HistoryMessage[] = history
          .slice(-aiConfig.maxHistoryMessages)
          .map((msg) => ({ role: msg.role, content: msg.content }));
        body.history = historyMessages;
      }

      const headers = this.getHeaders();
      headers['Accept'] = 'text/event-stream';

      const response = await fetch(`${this.baseUrl}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const raw = data?.text || data?.error || '';
        const isRateLimit = response.status === 429;
        const errMsg = isRateLimit
          ? 'Too many requests. Please wait a moment and try again.'
          : raw || 'Something went wrong. Please try again.';
        return {
          text: errMsg,
          a2ui: {
            version: '1.0',
            components: [{
              id: 'err', type: 'alert',
              props: {
                variant: isRateLimit ? 'warning' : 'error',
                title: isRateLimit ? 'Rate Limited' : 'Error',
                description: errMsg,
              },
            }],
          },
        };
      }

      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('text/event-stream') && response.body) {
        return await this.consumeSSE(response, onProgress);
      }

      // Fallback: regular JSON response
      const data = await response.json();
      const result = ChatService.recoverA2UIResponse(data);
      if (result.a2ui) {
        console.log('[A2UI] API response a2ui:', JSON.stringify(result.a2ui, null, 2));
      }
      return result;
    } catch (error) {
      console.error('Chat API error:', error);
      const isTimeout = error instanceof DOMException && error.name === 'AbortError';
      const userMsg = isTimeout
        ? 'The request took too long. Please try again or use a faster model.'
        : 'Something went wrong. Please try again in a moment.';
      toast.error(userMsg);
      return {
        text: userMsg,
        a2ui: {
          version: '1.0',
          components: [{
            id: 'err', type: 'alert',
            props: {
              variant: 'error',
              title: isTimeout ? 'Request Timeout' : 'Something Went Wrong',
              description: userMsg,
            },
          }],
        },
      };
    }
  }

  /**
   * Handle a `need_location` SSE event from the backend.
   * Gets browser geolocation and POSTs it to the backend to unblock
   * the paused pipeline.  Runs async (fire-and-forget) so the SSE
   * reader keeps consuming events.
   */
  private resolveLocationRequest(requestId: string): void {
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
        fetch(`${this.baseUrl}/provide-location/${requestId}`, {
          method: 'POST',
          headers: this.getHeaders(),
          body: JSON.stringify({ denied: true }),
        }).catch(() => {});
      });
  }

  /**
   * Extract readable text from a partial JSON token buffer.
   * Finds the "text" field value and unescapes JSON string content.
   */
  static extractStreamingText(partialJson: string): string {
    const marker = /"text"\s*:\s*"/;
    const match = marker.exec(partialJson);
    if (!match) return '';

    const valueStart = match.index + match[0].length;
    let result = '';
    let i = valueStart;

    while (i < partialJson.length) {
      const ch = partialJson[i];
      if (ch === '\\' && i + 1 < partialJson.length) {
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
          break;
        }
      } else if (ch === '"') {
        break;
      } else {
        result += ch;
        i++;
      }
    }

    return result;
  }

  /**
   * Parse an SSE stream from the backend, emitting events and returning the
   * final response from the ``complete`` event.
   */
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
            const delta = (payload as Record<string, string>).delta || '';
            tokenBuffer += delta;
            const streamedText = ChatService.extractStreamingText(tokenBuffer);
            if (streamedText) {
              onProgress?.('token', streamedText);
            }
          } else if (eventType === 'need_location') {
            const reqId = payload.request_id;
            if (reqId) {
              this.resolveLocationRequest(reqId);
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
}
