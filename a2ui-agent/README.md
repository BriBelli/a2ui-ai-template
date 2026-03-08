# A2UI Agent

Python FastAPI agent powering the A2UI chat interface with multi-provider LLM support, AI-driven tool orchestration, and modular content styles.

## Setup

```bash
cd a2ui-agent
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
pip3 install -r requirements.txt
cp .env.example .env       # then fill in your API keys
```

## Running

```bash
python3 app.py
```

Agent runs on `http://localhost:8000`. Enable debug mode (docs + hot-reload) with `A2UI_DEBUG=true`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api` | Health check |
| `GET` | `/api/providers` | Available LLM providers and models |
| `GET` | `/api/styles` | Available content styles |
| `GET` | `/api/tools` | Configurable tools and their lock state |
| `POST` | `/api/chat` | Chat completion with A2UI response |

### POST /api/chat

```json
{
  "message": "Top 5 trending stocks",
  "provider": "openai",
  "model": "gpt-4.1",
  "history": [{"role": "user", "content": "..."}],
  "enableWebSearch": true,
  "enableGeolocation": true,
  "contentStyle": "auto",
  "performanceMode": "auto"
}
```

## Architecture

### AI-First Pipeline

Every request follows a phased pipeline — AI decides tool activation, not regex:

```
Phase 1:  Parallel Analysis (asyncio.gather)
          ├── Intent Classifier  → style, search, location, search_query
          └── Data Source Router → [{source, endpoint, params}]
Phase 1+: Skip check (_can_skip_explorers)
Phase 2:  Location pre-step (may pause for browser)
          Parallel Explorers (asyncio.gather)
          ├── Web Search (if AI decided + tool gate allows)
          └── Data Sources (if AI decided + tool gate allows)
Phase 2.5: Data-Driven Hints (_derive_hints_from_data)
           Style Refinement (_refine_style_from_data)
Step 3:   Style prompt + micro-context injection + adaptive model routing
Step 4:   LLM generation (with token streaming + model fallback)
Step 5:   Post-processing (normalize, chart hints, hierarchy, metadata)
```

Key improvements over the previous single-analyzer design:
- **Split analyzer** — classifier and router run in parallel with independent fallbacks
- **Phase 2 skip** — trivial queries (greetings, general knowledge) skip all explorers
- **Data-driven hints** — component hints and complexity derived from actual data, not blind guessing
- **Style refinement** — content style upgraded based on real data characteristics
- **Parallel explorers** — web search and data sources run concurrently
- **Component normalization** — fixes LLM output quirks (type aliases, missing props, chart data format)
- **Token streaming** — progressive text rendering via SSE `token` events
- **Model fallback** — if primary model fails, tries an alternate model automatically

When AI is unavailable (disabled, failed), regex-based fallbacks handle tool decisions.

### Content Styles

Modular prompt system — each style has its own system prompt and component priority:

| Style | Description |
|-------|-------------|
| `analytical` | Data dashboards with KPIs, charts, tables |
| `content` | Editorial narrative with sections, lists, accordions |
| `comparison` | Side-by-side analysis with charts and feature tables |
| `howto` | Step-by-step instructions and procedural guides |
| `quick` | Concise direct answers with minimal components |

Style is auto-detected by the AI analyzer or explicitly set by the user.

### Configurable Tools

Tools are features that can be controlled at three layers:

```
Environment (admin locks)  >  User setting (UI toggle)  >  Default
```

| Tool | Env Variable | Default |
|------|-------------|---------|
| Web Search | `A2UI_TOOL_WEB_SEARCH` | `true` |
| Geolocation | `A2UI_TOOL_GEOLOCATION` | `true` |
| Conversation History | `A2UI_TOOL_HISTORY` | `true` |
| AI Style Classifier | `A2UI_TOOL_AI_CLASSIFIER` | `true` |
| Data Sources | `A2UI_TOOL_DATA_SOURCES` | `true` |

Set an env variable to globally lock a tool on or off. When locked, the user's UI toggle is disabled.

### LLM Providers

| Provider | Models | Env Variable |
|----------|--------|-------------|
| OpenAI | GPT-5.1, GPT-5, GPT-4.1, GPT-4.1 Mini | `OPENAI_API_KEY` |
| Anthropic | Claude Opus 4.6, Sonnet 4.6, Sonnet 4.5, Haiku 4.5 | `ANTHROPIC_API_KEY` |
| Google Gemini | Gemini 3 Pro, Gemini 2.5 Flash | `GEMINI_API_KEY` |

## Environment Variables

```bash
# LLM Providers (at least one required)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Web Search
TAVILY_API_KEY=

# App Settings
A2UI_API_KEY=              # Set to require X-API-Key header; unset = open
A2UI_CORS_ORIGINS=         # Comma-separated origins (defaults provided)
A2UI_DEBUG=false           # true enables /api/docs and hot-reload
A2UI_MAX_BODY_BYTES=       # WAF body byte limit (unset = unlimited)

# Tool Overrides (unset = user-controlled)
A2UI_TOOL_WEB_SEARCH=      # true/false — lock web search on/off
A2UI_TOOL_GEOLOCATION=     # true/false — lock geolocation on/off
A2UI_TOOL_HISTORY=         # true/false — lock conversation history on/off
A2UI_TOOL_AI_CLASSIFIER=   # true/false — lock AI classifier on/off
```

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | FastAPI routes, middleware, request models |
| `llm_providers.py` | LLM providers, split classifier/router, phased pipeline, component normalization, token streaming |
| `tools.py` | Web search (Tavily), query rewriting, search utilities |
| `content_styles/` | Modular prompt definitions per content style |
| `content_styles/_base.py` | Shared base rules prepended to all styles |
| `data_sources/` | External API connectors (REST, Databricks Genie) |
| `micro_contexts.py` | Chart/component micro-context fragments for system prompt injection |
