import type { A2UIResponse } from '@a2ui/core';
import { aiConfig } from '../config/ui-config';
import { getUserLocation } from './geolocation-service';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  a2ui?: A2UIResponse;
  timestamp: number;
  model?: string;
  /** Auth0 user avatar URL (user messages only) */
  avatarUrl?: string;
  /** Initials fallback when no avatar image (user messages only) */
  avatarInitials?: string;
  /** Follow-up suggestions shown below assistant responses */
  suggestions?: string[];
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
  _search?: { searched: boolean; success?: boolean; results_count?: number; images_count?: number; error?: string };
  _location?: boolean;
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

  async sendMessage(
    message: string,
    provider?: string,
    model?: string,
    history?: ChatMessage[]
  ): Promise<ChatResponse> {
    try {
      // Attempt to get user location (non-blocking, cached after first grant)
      const location = await getUserLocation();

      // Build request body
      const body: Record<string, unknown> = { 
        message, 
        provider, 
        model,
        enableWebSearch: aiConfig.webSearch,
        ...(location && { userLocation: location }),
      };

      // Add conversation history if enabled
      if (aiConfig.conversationHistory && history && history.length > 0) {
        const historyMessages: HistoryMessage[] = history
          .slice(-aiConfig.maxHistoryMessages)
          .map(msg => ({
            role: msg.role,
            content: msg.content,
          }));
        body.history = historyMessages;
      }

      const response = await fetch(`${this.baseUrl}/chat`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      // A2UI API response data
      const data = await response.json();
      if (data.a2ui) {
        console.log('[A2UI] API response a2ui:', JSON.stringify(data.a2ui, null, 2));
      }
      return data;
    } catch (error) {
      console.error('Chat API error:', error);
      // Return mock data for demo when backend is unavailable
      return this.getMockResponse(message);
    }
  }

  private getMockResponse(message: string): ChatResponse {
    const lowerMessage = message.toLowerCase();

    // Stock-related queries
    if (lowerMessage.includes('stock') || lowerMessage.includes('trending')) {
      return {
        text: "Here are the top 5 trending stocks right now:",
        a2ui: {
          version: "1.0",
          components: [
            {
              id: "stocks-container",
              type: "container",
              props: { layout: "vertical", gap: "md" },
              children: [
                {
                  id: "stocks-table",
                  type: "data-table",
                  props: {
                    columns: [
                      { key: "symbol", label: "Symbol", width: "80px" },
                      { key: "name", label: "Company", width: "auto" },
                      { key: "price", label: "Price", width: "100px", align: "right" },
                      { key: "change", label: "Change", width: "100px", align: "right" },
                    ],
                    data: [
                      { symbol: "NVDA", name: "NVIDIA Corporation", price: "$892.45", change: "+5.2%" },
                      { symbol: "AAPL", name: "Apple Inc.", price: "$182.63", change: "+1.8%" },
                      { symbol: "MSFT", name: "Microsoft Corporation", price: "$415.28", change: "+2.1%" },
                      { symbol: "GOOGL", name: "Alphabet Inc.", price: "$141.80", change: "+1.5%" },
                      { symbol: "META", name: "Meta Platforms Inc.", price: "$485.92", change: "+3.4%" },
                    ],
                  },
                },
                {
                  id: "chart-prompt",
                  type: "text",
                  props: {
                    content: "💡 Ask me to show a chart of any of these stocks!",
                    variant: "caption",
                  },
                },
              ],
            },
          ],
        },
        suggestions: ['Show NVDA stock chart', 'Compare tech stocks performance'],
      };
    }

    // Chart-related queries
    if (lowerMessage.includes('chart') || lowerMessage.includes('graph') || lowerMessage.includes('visual')) {
      return {
        text: "Here's the performance overview for trending stocks:",
        a2ui: {
          version: "1.0",
          components: [
            {
              id: "chart-container",
              type: "container",
              props: { layout: "vertical", gap: "md" },
              children: [
                {
                  id: "stock-chart",
                  type: "chart",
                  props: {
                    chartType: "line",
                    title: "NVDA — 30 Day Price",
                    data: {
                      labels: [
                        "Jan 6", "Jan 8", "Jan 10", "Jan 13", "Jan 15",
                        "Jan 17", "Jan 21", "Jan 23", "Jan 27", "Jan 29",
                        "Jan 31", "Feb 3",
                      ],
                      datasets: [
                        {
                          label: "NVDA",
                          data: [849, 862, 871, 858, 876, 891, 885, 903, 910, 895, 918, 892],
                          borderColor: "#81c995",
                        },
                      ],
                    },
                    options: {
                      height: 280,
                      fillArea: true,
                      currency: "USD",
                      referenceLine: 849,
                      referenceLabel: "Previous close",
                    },
                  },
                },
                {
                  id: "bar-chart",
                  type: "chart",
                  props: {
                    chartType: "bar",
                    title: "YTD Performance (%)",
                    data: {
                      labels: ["NVDA", "META", "MSFT", "AAPL", "GOOGL"],
                      datasets: [
                        {
                          label: "YTD Change %",
                          data: [85.2, 42.5, 35.8, 22.1, 18.5],
                        },
                      ],
                    },
                    options: {
                      height: 220,
                    },
                  },
                },
                {
                  id: "multi-line",
                  type: "chart",
                  props: {
                    chartType: "line",
                    title: "Price Comparison — 30 Days",
                    data: {
                      labels: ["Week 1", "Week 2", "Week 3", "Week 4"],
                      datasets: [
                        {
                          label: "NVDA",
                          data: [750, 810, 855, 892],
                          borderColor: "#76b900",
                        },
                        {
                          label: "MSFT",
                          data: [390, 400, 408, 415],
                          borderColor: "#8ab4f8",
                        },
                        {
                          label: "META",
                          data: [440, 455, 470, 486],
                          borderColor: "#c58af9",
                        },
                      ],
                    },
                    options: {
                      height: 260,
                      currency: "USD",
                    },
                  },
                },
              ],
            },
          ],
        },
      };
    }

    // Weather queries
    if (lowerMessage.includes('weather')) {
      return {
        text: "Here's the weather forecast:",
        a2ui: {
          version: "1.0",
          components: [
            {
              id: "weather-container",
              type: "container",
              props: { layout: "horizontal", gap: "md", wrap: true },
              children: [
                {
                  id: "today",
                  type: "card",
                  props: {
                    title: "Today",
                    subtitle: "San Francisco",
                  },
                  children: [
                    {
                      id: "today-temp",
                      type: "text",
                      props: { content: "72°F", variant: "h1" },
                    },
                    {
                      id: "today-desc",
                      type: "text",
                      props: { content: "☀️ Sunny", variant: "body" },
                    },
                  ],
                },
                {
                  id: "tomorrow",
                  type: "card",
                  props: { title: "Tomorrow" },
                  children: [
                    {
                      id: "tomorrow-temp",
                      type: "text",
                      props: { content: "68°F", variant: "h2" },
                    },
                    {
                      id: "tomorrow-desc",
                      type: "text",
                      props: { content: "⛅ Partly Cloudy", variant: "body" },
                    },
                  ],
                },
                {
                  id: "day3",
                  type: "card",
                  props: { title: "Wednesday" },
                  children: [
                    {
                      id: "day3-temp",
                      type: "text",
                      props: { content: "65°F", variant: "h2" },
                    },
                    {
                      id: "day3-desc",
                      type: "text",
                      props: { content: "🌧️ Rain", variant: "body" },
                    },
                  ],
                },
              ],
            },
          ],
        },
      };
    }

    // Task list
    if (lowerMessage.includes('task') || lowerMessage.includes('list') || lowerMessage.includes('todo')) {
      return {
        text: "I've created a task list for you:",
        a2ui: {
          version: "1.0",
          components: [
            {
              id: "tasks-card",
              type: "card",
              props: { title: "My Tasks" },
              children: [
                {
                  id: "task-list",
                  type: "list",
                  props: {
                    items: [
                      { id: "1", text: "Review Q4 financial reports", status: "completed" },
                      { id: "2", text: "Prepare presentation slides", status: "in-progress" },
                      { id: "3", text: "Schedule team sync meeting", status: "pending" },
                      { id: "4", text: "Update project documentation", status: "pending" },
                      { id: "5", text: "Send weekly status update", status: "pending" },
                    ],
                    variant: "checklist",
                  },
                },
              ],
            },
          ],
        },
      };
    }

    // Default response
    return {
      text: `I understand you're asking about "${message}". I can help you with:\n\n• Stock market data and charts\n• Weather forecasts\n• Task management\n• Data analysis and visualization\n\nTry asking about "trending stocks" or "show me a chart"!`,
      suggestions: ['Top 5 trending stocks', 'Show weather forecast'],
    };
  }
}
