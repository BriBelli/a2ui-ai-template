import type { A2UIResponse } from '@a2ui/core';
import { aiConfig } from '../config/ui-config';
import { getUserLocation } from './geolocation-service';
import { toast } from './toast-service';

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
  /** Backend metadata about search/tools used (for thinking indicator). */
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
   * Lightweight check — mirrors backend's should_search().
   * Used to predict whether the backend will search so the
   * thinking indicator can show the right steps immediately.
   */
  willSearch(message: string): boolean {
    const m = message.toLowerCase();
    const indicators = [
      'current',
      'latest',
      'today',
      'now',
      'recent',
      'right now',
      'these days',
      'nowadays',
      'trending',
      'popular',
      'getting noticed',
      'going viral',
      'price',
      'stock',
      'market',
      'trading',
      'bitcoin',
      'crypto',
      'weather',
      'forecast',
      'temperature',
      'news',
      'headlines',
      'score',
      'game',
      'what is',
      'what are',
      'how much',
      'who won',
      'who is',
      'compare',
      'vs',
      'versus',
      'show me',
      'pictures of',
      'photos of',
      'images of',
      'artwork',
      'art',
      'design',
      '2024',
      '2025',
      '2026',
    ];
    return indicators.some((i) => m.includes(i));
  }

  /**
   * Check if a message would benefit from the user's location.
   * Only local queries (weather, nearby, events, food) need it.
   */
  needsLocation(message: string): boolean {
    const m = message.toLowerCase();
    const localIndicators = [
      'weather',
      'forecast',
      'temperature',
      'near me',
      'nearby',
      'local',
      'restaurant',
      'food',
      'store',
      'shop',
      'event',
      'concert',
      'traffic',
      'commute',
      'directions',
      'open now',
      'closest',
    ];
    return localIndicators.some((i) => m.includes(i));
  }

  /** Callback type for reporting progress during sendMessage. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async sendMessage(
    message: string,
    provider?: string,
    model?: string,
    history?: ChatMessage[],
    onProgress?: (
      phase:
        | 'location'
        | 'location-done'
        | 'searching'
        | 'search-done'
        | 'generating',
      detail?: string
    ) => void
  ): Promise<ChatResponse> {
    try {
      // Phase 1: Location — only fetch if the query is location-relevant
      let location = null;
      if (this.needsLocation(message)) {
        onProgress?.('location');
        location = await getUserLocation();
        onProgress?.('location-done');
      }

      // Build request body
      const body: Record<string, unknown> = {
        message,
        provider,
        model,
        enableWebSearch: aiConfig.webSearch,
        contentStyle: aiConfig.contentStyle,
        performanceMode: aiConfig.performanceMode,
        ...(location && { userLocation: location }),
      };

      // Add conversation history if enabled
      if (aiConfig.conversationHistory && history && history.length > 0) {
        const historyMessages: HistoryMessage[] = history
          .slice(-aiConfig.maxHistoryMessages)
          .map((msg) => ({
            role: msg.role,
            content: msg.content,
          }));
        body.history = historyMessages;
      }

      // Phase 2: Searching (predicted; actual search happens server-side)
      if (this.willSearch(message)) {
        onProgress?.('searching');
      }

      // Phase 3: API call (search + LLM generation happen here)
      const response = await fetch(`${this.baseUrl}/chat`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify(body),
      });

      // A2UI API response data
      const data = await response.json();
      if (!response.ok) {
        // Surface the backend's actual error message
        const errMsg =
          data?.text || data?.error || `Server error (${response.status})`;
        toast.error(errMsg);
        return {
          text: errMsg,
          a2ui: {
            version: '1.0',
            components: [
              {
                id: 'err',
                type: 'alert',
                props: {
                  variant: 'error',
                  title: 'Error',
                  description: errMsg,
                },
              },
            ],
          },
        };
      }

      // Safety net: if the backend returned the raw LLM JSON in the `text`
      // field (e.g. parse_llm_json fell through), try to recover the
      // structured response so the UI renders rich components.
      const result = ChatService.recoverA2UIResponse(data);

      // Pass the rewritten search query back so the thinking indicator can display it
      const rewrittenQuery = result._search?.query;
      onProgress?.('search-done', rewrittenQuery);
      onProgress?.('generating');

      if (result.a2ui) {
        console.log(
          '[A2UI] API response a2ui:',
          JSON.stringify(result.a2ui, null, 2)
        );
      }
      return result;
    } catch (error) {
      console.error('Chat API error:', error);
      toast.error(
        'Unable to reach the AI service. Check that the backend is running.'
      );
      return {
        text: 'Unable to reach the AI service. Please check that the backend is running.',
        a2ui: {
          version: '1.0',
          components: [
            {
              id: 'err',
              type: 'alert',
              props: {
                variant: 'error',
                title: 'Connection Error',
                description:
                  'The backend at ' +
                  this.baseUrl +
                  ' is not responding. Start it with: cd backend && python3 app.py',
              },
            },
          ],
        },
      };
    }
  }
}
