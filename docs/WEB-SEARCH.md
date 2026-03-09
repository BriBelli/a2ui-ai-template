# Web Search Integration

## Overview

A2UI Chat includes optional web search integration using Tavily API for real-time information retrieval. The system is designed with **graceful fallback** - if search fails or isn't configured, the chat continues working normally using the AI's training data.

## Configuration

### Enable/Disable

Web search is **enabled by default** and can be configured in `apps/a2ui-chat/src/config/ui-config.ts`:

```typescript
export const aiConfig: AIConfig = {
  webSearch: true,  // Set to false to disable
  // ...
};
```

### Setup Tavily API

1. Get a free API key at https://tavily.com (1000 searches/month free)
2. Set environment variable:
   ```bash
   export TAVILY_API_KEY="tvly-xxxxx"
   ```
3. Install the package:
   ```bash
   cd a2ui-agent && pip install tavily-python
   ```

## Graceful Fallback System

### When Search is Triggered

Search automatically triggers for queries with these indicators:
- Time-sensitive: "current", "latest", "today", "now", "recent"
- Real-time data: "price", "stock", "weather", "news"
- Questions: "what is the", "how much", "who won"
- Current years: "2024", "2025", "2026"

### Error Handling Hierarchy

1. **No API Key** → AI uses training data only
   - Status: `not_configured`
   - User sees: Normal AI response with knowledge cutoff acknowledgment

2. **Package Not Installed** → AI uses training data only
   - Status: `package_missing`
   - Terminal: `⚠️ Web search: Tavily package not installed`

3. **Rate Limit Exceeded** → AI uses training data only
   - Status: `rate_limit`
   - Terminal: `⚠️ Web search: Rate limit exceeded`
   - User sees: Response based on AI's knowledge

4. **Invalid API Key** → AI uses training data only
   - Status: `invalid_key`
   - Terminal: `⚠️ Web search: Invalid API key`

5. **Timeout** → AI uses training data only
   - Status: `timeout`
   - Terminal: `⚠️ Web search: Timeout`

6. **Other Errors** → AI uses training data only
   - Status: `unknown`
   - Terminal: `⚠️ Web search failed: {error}`

### What Users See

**With successful search:**
```
AI: According to recent reports, NVIDIA stock is trading at $892.45 
    (up 5.2% today). [Shows data with sources]
```

**With failed search:**
```
AI: Based on my last update in October 2023, NVIDIA has historically 
    been a strong performer in the semiconductor sector. For current 
    prices, I recommend checking [provides link to live data].
```

**No errors shown to users** - the experience degrades gracefully.

## Monitoring

Search attempts are logged to terminal:
- `🔍 Performing web search for: {query}...`
- `✓ Web search complete, {n} results` (success)
- `⚠️ Web search failed ({reason}), continuing...` (failure)
- `ℹ️ Web search requested but not configured` (no API key)

## Response Metadata

Each response includes optional `_search` metadata (for debugging):

```json
{
  "text": "...",
  "a2ui": {...},
  "_search": {
    "searched": true,
    "success": true,
    "results_count": 5
  }
}
```

Or on failure:
```json
{
  "_search": {
    "searched": true,
    "success": false,
    "error": "rate_limit"
  }
}
```

## Testing Fallback

1. **Without API key:**
   ```bash
   unset TAVILY_API_KEY
   # Ask: "What's the current NVIDIA stock price?"
   # Should work, using AI knowledge
   ```

2. **Invalid key:**
   ```bash
   export TAVILY_API_KEY="invalid-key"
   # Should fail gracefully and continue
   ```

3. **Rate limited:**
   - Exceed 1000 queries/month
   - Should gracefully fall back to AI knowledge

## Alternative Search Providers

The `a2ui-agent/tools.py` module can be swapped for:
- **Brave Search** (2000 free/month)
- **DuckDuckGo** (unlimited, free)
- **SerpAPI** (100 free/month)
- **Bing Search API**

See `WebSearchTool` class to implement alternate providers.
