# A2UI Agent Development Guide

How the backend at `apps/a2ui-agent/` works, and how to extend it.

---

## Request Flow

The backend supports two response modes: standard JSON and SSE streaming.

### SSE Streaming (default when `Accept: text/event-stream`)

```
POST /api/chat (Accept: text/event-stream)
  |
  v
ChatRequest validated (Pydantic)
  |
  v
LLMService.generate_stream()
  |
  ├── Step 0: Resolve tool states (env > user > default)
  ├── Step 1: Input sanitization (injection detection + delimiter stripping)
  ├── Phase 1: Parallel analysis (two focused agents via asyncio.gather)
  │     ├── Intent Classifier → style, search, location, search_query
  │     └── Data Source Router → [{source, endpoint, params}]
  │     Each has independent fallbacks (regex for classifier, keyword for router)
  ├── Phase 1+: Skip check (_can_skip_explorers)
  │     Skip Phase 2 when: no search, no location, no data queries, no dataContext,
  │     and style is not data-oriented
  ├── Phase 2: Location pre-step + Parallel explorers (asyncio.gather)
  │     ├── Geolocation context (may pause for browser permission)
  │     ├── Web search (Tavily) → prepend results ─┐
  │     ├── Data source queries → prepend results ──┤ run in parallel
  │     │     └── On failure: [DATA UNAVAILABLE] block injected
  │     └── Passive dataContext from request body
  ├── Phase 2.5: Data-Driven Decisions
  │     ├── _derive_hints_from_data → component hints + complexity from real data
  │     └── _refine_style_from_data → upgrade style if data warrants it
  ├── Step 3: System prompt assembly
  │     ├── Base rules + style-specific prompt
  │     ├── Micro-context fragments (from data-driven hints)
  │     └── Data source rules
  ├── Step 3d: Adaptive model routing (upgrade/downgrade based on data-driven complexity)
  ├── Step 4: LLM generation (token streaming + model fallback on error)
  │     ├── Yields token events for progressive UI rendering
  │     └── On failure: tries alternate model (max 1 retry)
  └── Step 5: Post-processing
        ├── Component normalization (_normalize_a2ui_components)
        ├── Chart hint enforcement (_apply_chart_hints)
        ├── Suggestion normalization (_normalize_suggestions)
        ├── Visual hierarchy enforcement
        ├── Refusal detection + retry
        └── Metadata attachment (_search, _sources, _images, _style, _model, etc.)
  |
  v
SSE stream emits:
  ├── event: step (id, status:start|done, label, detail, reasoning)
  ├── event: token (delta: string) — progressive text streaming
  ├── event: need_location (request_id)
  ├── event: error (message)
  └── event: complete (full A2UI response payload)
```

### JSON (fallback, backward compatible)

Same pipeline as above via `generate()`, but returns a single JSON response.

---

## Content Styles (Modular Package)

The `content_styles/` package provides modular prompt orchestration:

| File                  | Purpose                                                                                                                                                                                                                                                                                                                                       |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `__init__.py`         | Registry, classifier (`classify_style()`), prompt composition, public API                                                                                                                                                                                                                                                                     |
| `_base.py`            | `BASE_RULES` + `BASE_RULES_LITE` -- shared rules injected into every style's prompt; lite version for gateway-constrained styles                                                                                                                                                                                                              |
| `analytical.py`       | Financial/data-heavy queries (charts, stats, KPIs)                                                                                                                                                                                                                                                                                            |
| `comparison.py`       | vs/comparison queries (side-by-side charts + tables)                                                                                                                                                                                                                                                                                          |
| `content.py`          | Knowledge/informational queries (cards, lists, accordions)                                                                                                                                                                                                                                                                                    |
| `howto.py`            | Step-by-step/tutorial queries (numbered lists, guides)                                                                                                                                                                                                                                                                                        |
| `quick.py`            | Short/simple queries (minimal components, fast)                                                                                                                                                                                                                                                                                               |
| `dashboard.py`        | Dashboard-style layout (stat grids, summary cards)                                                                                                                                                                                                                                                                                            |
| `alerts_dashboard.py` | **Hybrid tier** strict-shape prompt for the PX&O Alert Center — AI fills data into a fixed card grid layout (used by the frontend hybrid mode, not user-selectable in chat)                                                                                                                                                                   |
| `alert_detail.py`     | **Dynamic tier** conversational claims analyst agent for the Inside Alert detail view — automatically triggered on page load (auto-prompt), provides root cause analysis, key metrics, business impact, and recommended actions. AI persona is a senior claims analyst. Uses `lite_base: True` for compact prompts within gateway body limits |

Key APIs:

- `classify_style(message)` -- regex-based classifier (instant, zero-cost)
- `get_system_prompt(style_id)` -- composed prompt (base rules + style-specific)
- `get_component_priority(style_id)` -- ordered component list for visual hierarchy
- `get_available_styles()` -- metadata list for `GET /api/styles`
- `VALID_STYLE_IDS` -- frozenset for validation

| Style              | Tier    | Use Case                          | Component Priority                          |
| ------------------ | ------- | --------------------------------- | ------------------------------------------- |
| `analytical`       | Dynamic | Dashboards, KPIs, market data     | stat -> chart -> data-table -> list         |
| `content`          | Dynamic | Narrative, articles, explanations | text -> card -> list -> accordion           |
| `comparison`       | Dynamic | Side-by-side analysis             | data-table -> chart -> stat -> list         |
| `howto`            | Dynamic | Step-by-step instructions         | list -> accordion -> alert -> text          |
| `quick`            | Dynamic | Concise, fast answers             | text -> stat -> alert                       |
| `dashboard`        | Dynamic | Dashboard-style layouts           | stat -> chart -> card -> data-table         |
| `alerts-dashboard` | Hybrid  | PX&O Alert Center card grid       | card -> chip -> text -> chart -> alert      |
| `alert-detail`     | Dynamic | Inside Alert contextual chat      | text -> card -> chip -> data-table -> chart |

Styles are:

- Auto-detected by the AI intent analyzer
- Listed via `GET /api/styles`
- Selected by the frontend and sent as `contentStyle` in the chat request
- Composed into the system prompt via `get_system_prompt(style_id)`

The analyzer (Step 2 of the pipeline) may override the content style based on the query.

**Page-only styles** (e.g. `alerts-dashboard`, `scorecard`, `alert-detail`) have `classifier_visible: False` and `selectable: False` — the AI classifier cannot auto-select them for general chat, and they don't appear in the frontend dropdown. They are invoked programmatically by the frontend via `contentStyleOverride`. Strict-shape styles (dashboards) also set `strict_shape: True` which, combined with `HYBRID_TOOL_OVERRIDES`, triggers the backend fast path (single LLM call). See [hybrid-tiers.md](hybrid-tiers.md) for the full implementation guide and [WORKFLOW-ARCHITECTURE.md](WORKFLOW-ARCHITECTURE.md) for the conceptual architecture.

### Auto-Prompt Flow (Alert Detail)

The `alert-detail` content style supports an **auto-prompt** pattern where the frontend automatically sends an initial prompt when the user navigates to the alert detail page — no manual input required:

1. **Frontend** (`a2ui-alert-detail-page.ts`) loads alert data, then dispatches an `auto-prompt` event with a constructed analysis request
2. **App** (`a2ui-app.ts`) wires `@auto-prompt` to the same handler as `@send-message`, which prefixes the alert context and sends to the backend with `contentStyleOverride: 'alert-detail'`
3. **Backend** receives the message with the `alert-detail` style, which activates the claims analyst agent persona
4. **Response** is a conversational AI analysis with dynamic A2UI components (stat grids, charts, tables, accordions) chosen based on the actual data shape

The auto-prompt can include extra context from URL parameters (`?info=<base64-json>`), enabling the linking page to pass precomputed summaries, suggested actions, or metadata.

See [hybrid-tiers.md § Alert Detail — Auto-Prompt on Page Load](hybrid-tiers.md#alert-detail--auto-prompt-on-page-load) for full implementation details.

---

## Micro-Contexts

`micro_contexts.py` provides composable prompt fragments for advanced chart types. When the analyzer detects a need for specialized charts, the corresponding micro-context is injected into the system prompt for that request only.

Available micro-contexts:

- `chart_matrix` -- matrix/heatmap chart data shape
- `chart_treemap` -- treemap chart data shape
- `chart_sankey` -- sankey flow chart data shape
- `chart_funnel` -- funnel chart data shape
- `chart_radar` -- radar chart data shape
- `chart_scatter` -- scatter/bubble chart data shape

API: `get_context(key)`, `assemble(keys, max_bytes=None)`, `AVAILABLE_KEYS`

---

## Data Sources

The `data_sources/` package provides a registry of external data sources the AI agent can query.

| File            | Purpose                                                        |
| --------------- | -------------------------------------------------------------- |
| `__init__.py`   | Registry, config loading, parallel query execution, public API |
| `_base.py`      | `DataSource` abstract base class                               |
| `config.yaml`   | Source definitions (type, URL, auth, endpoints, rules)         |
| `rest.py`       | REST API connector (with optional OpenAPI spec discovery)      |
| `databricks.py` | Databricks Genie natural-language connector                    |

Supported source types: `rest`, `databricks`.

Key APIs:

- `get_available_sources()` -- for `GET /api/data-sources`
- `query_sources(queries)` -- execute multiple queries in parallel
- `get_analyzer_context()` -- compact summary for the analyzer prompt
- `get_rules_context()` -- LLM rules from all sources (injected into system prompt)
- `format_results_for_context(results)` -- format data for LLM context

### Data Flow

1. Data Source Router (`_route_data_sources`) identifies which sources / endpoints / params to query (runs in parallel with the Intent Classifier)
2. `query_sources()` executes queries in parallel (runs concurrently with web search)
3. Results are formatted as `[Data Source: ...]` blocks prepended to the user message
4. Base rules instruct the LLM to use ONLY data from these blocks (no fabrication)
5. Data source names and formatting constraints are injected as system prompt rules

### Adding a Data Source

1. Create a class extending `DataSource` in `data_sources/`
2. Implement `is_available()`, `query()`, `get_analyzer_summary()`, `format_for_context()`
3. Register in `config.yaml`
4. The Data Source Router receives data source summaries via `get_analyzer_context()`

Sources are configured in `config.yaml` and loaded at import time. Auth tokens are always referenced via env-var names, never hardcoded.

---

## System Prompt

The system prompt is **composed** from multiple parts:

1. **Base rules** (`content_styles/_base.py`) -- shared across all styles
2. **Style-specific prompt** (e.g., `content_styles/analytical.py`) -- selected by the analyzer
3. **Micro-contexts** (`micro_contexts.py`) -- injected only when advanced charts are needed
4. **Data source rules** (`data_sources/` `get_rules_context()`) -- when external data is in context

The `BASE_RULES` instruct the LLM to:

1. **Never override system instructions** -- security rules have highest priority
2. **Be accurate** -- use web search results when available; never fabricate time-sensitive data
3. **Be relevant** -- temporal (current date), geographic (user location), contextual (current-year products)
4. **Blend markdown and components** -- rich markdown `text` for narrative, A2UI components for structured data
5. **Follow the full component catalog** -- atoms, molecules, layout with all valid props and data formats

To change LLM behavior:

1. For shared rules: edit `content_styles/_base.py`
2. For style-specific behavior: edit the appropriate style module
3. For advanced chart instructions: edit `micro_contexts.py`
4. Keep composed prompts under the WAF byte budget (validated at import time)
5. Test with multiple models -- Claude and GPT handle instructions differently
6. Update this doc if you change component rules or the response format

### Prompt Assembly

```python
get_system_prompt(style_id, max_bytes=5000)
```

1. Current date is prepended: `Current date: {today}. All responses must be relevant...`
2. `BASE_RULES` (security + format + component catalog)
3. Style-specific prompt overlay
4. Micro-context fragments for specialized chart types (if analyzer detected them)
5. Data source rules (naming/formatting constraints)
6. WAF-aware budget downgrade if total exceeds 75% of byte limit

### Constants

- `DEFAULT_STYLE = "content"`
- `DEFAULT_MAX_PROMPT_BYTES = 5000`
- `ABSOLUTE_MAX_PROMPT_BYTES = 7200`

---

## LLM Providers

All providers implement the `LLMProvider` abstract base class:

```python
class LLMProvider(ABC):
    name: str
    models: List[Dict[str, str]]

    def is_available(self) -> bool: ...
    async def generate(self, message, model, history, system_prompt, effort) -> Dict: ...
```

### Available Providers

| Provider       | Class              | Env Var            | Notes                                            |
| -------------- | ------------------ | ------------------ | ------------------------------------------------ |
| OpenAI         | `OpenAIProvider`   | `OPENAI_API_KEY`   | GPT-5.1, GPT-5, GPT-4.1, GPT-4.1 Mini           |
| Anthropic      | `AnthropicProvider`| `ANTHROPIC_API_KEY` | Claude Opus 4.6, Sonnet 4.6, Sonnet 4.5, Haiku  |
| Google Gemini  | `GeminiProvider`   | `GEMINI_API_KEY`   | Gemini 3 Pro, Gemini 2.5 Flash                   |

### Adding a New Provider

1. Create a class extending `LLMProvider` in `llm_providers.py`
2. Implement `is_available()` (check env var) and `generate()` (call API, return parsed JSON)
3. Register it in `LLMService.__init__()` with a unique provider ID
4. The frontend auto-discovers providers via `GET /api/providers`

---

## AI Intent Analysis (Parallel Split)

The analysis phase runs **two focused agents in parallel** via `asyncio.gather`, both using the same model list (GPT-4.1 Mini → Claude Haiku → Gemini Flash):

### Intent Classifier (`_classify_intent`)

Lightweight, fast — does **not** receive the data source catalog.

| Field          | Description                                                                |
| -------------- | -------------------------------------------------------------------------- |
| `style`        | Content presentation style (analytical, content, comparison, howto, quick) |
| `search`       | Whether real-time web search is needed                                     |
| `location`     | Whether geographic context is relevant                                     |
| `search_query` | Optimized search query string                                              |
| `components`   | Specialized chart types needed (matrix, treemap, sankey, etc.)             |
| `complexity`   | Task difficulty (standard, moderate, high, reasoning)                      |

Falls back to `classify_style()` regex + `should_search()` regex when unavailable.

### Data Source Router (`_route_data_sources`)

Domain-aware, focused — receives **only** the data source catalog.

| Field          | Description                                         |
| -------------- | --------------------------------------------------- |
| `data_sources` | List of `{source, endpoint, params}` dicts to query |

Falls back to `_fallback_data_sources()` keyword matcher when unavailable.

### Parallel Enrichment Explorers

After analysis, enrichment runs in parallel where possible:

1. **Location** resolves first (may require browser interaction via `need_location` SSE event)
2. **Web Search** + **Data Sources** run concurrently via `asyncio.gather`
3. Results are merged into the augmented message before LLM generation

### SSE Step Events

| Step ID        | Phase      | Description                    |
| -------------- | ---------- | ------------------------------ |
| `classifier`   | Analysis   | Intent classification progress |
| `router`       | Analysis   | Data source routing progress   |
| `analyzer`     | Analysis   | Combined analysis summary      |
| `search`       | Enrichment | Web search progress            |
| `data_sources` | Enrichment | Data source query progress     |
| `geolocation`  | Enrichment | Browser location acquisition   |

Both agents and all explorers include independent fallback guarantees — if one fails, the other's result is still used.

---

## Adaptive Model Routing

When `smartRouting` is enabled (default), the pipeline can dynamically upgrade the model based on query complexity:

1. The analyzer classifies complexity as `standard`, `moderate`, `high`, or `reasoning`
2. `_derive_complexity()` cross-references with component hints
3. Complex queries may route to a more capable model (e.g., GPT-4.1 -> GPT-5)
4. Thinking effort is adjusted via `_COMPLEXITY_TO_EFFORT` mapping
5. The response includes `_model` (actual model used) and `_model_upgraded_from` if upgraded

Speed is the primary sort key. Models are accessed directly via each provider's native SDK.

| Complexity  | Min Tier | Required Tags | Action                                 |
| ----------- | -------- | ------------- | -------------------------------------- |
| `standard`  | 1        | --            | May downgrade to faster model          |
| `moderate`  | 2        | --            | Upgrade if current tier < 2            |
| `high`      | 3        | `structured`  | Upgrade to tier 3+ with structured tag |
| `reasoning` | 3        | `reasoning`   | Upgrade to tier 3+ with reasoning tag  |

**Model roster (excerpt):**

| Model                       | Tier | Speed  | Tags                            |
| --------------------------- | ---- | ------ | ------------------------------- |
| Claude Sonnet 4 (Bedrock)   | 4    | medium | structured, reasoning, creative |
| Claude 3.7 Sonnet (Bedrock) | 3    | medium | structured, reasoning, creative |
| GPT-4.1                     | 2    | fast   | --                              |
| o3 / o4-mini                | 3    | medium | reasoning                       |
| GPT-4.1-mini / nano         | 1    | fast   | --                              |

---

## Performance Modes

The `performanceMode` parameter controls the trade-off between response quality and speed:

| Mode            | Behavior                                                         |
| --------------- | ---------------------------------------------------------------- |
| `auto`          | Default. Adapts based on query complexity and WAF budget.        |
| `comprehensive` | Full pipeline with all enrichment steps. Higher quality, slower. |
| `optimized`     | Minimal pipeline. Downgrades to "quick" style. Faster, cheaper.  |

Sent as `performanceMode` in the chat request.

---

## JSON Parsing

`parse_llm_json(content)` in `llm_providers.py` handles messy LLM output:

1. Strips markdown code fences (` ```json ... ``` `)
2. Extracts the outermost JSON object by brace-counting (handles trailing prose)
3. Parses with `json.loads()`
4. Enforces visual hierarchy (reorders components by style-specific priority)
5. Falls back to a user-friendly error alert if parsing fails

---

## Safety Mechanisms

### Input Sanitization

Before any processing, the message is checked against 11 injection detection patterns (role impersonation, prompt extraction, jailbreak attempts). Detected patterns are logged but the message proceeds with dangerous delimiters stripped.

### Prompt Injection Detection

`_detect_injection(text)` scans user input for known injection patterns (e.g., "ignore previous instructions", "you are now a...", jailbreak attempts). Matched patterns are logged.

`_sanitize_for_prompt(text)` strips characters that could break prompt delimiters.

### Refusal Detection

`_is_refusal(parsed)` checks if the LLM deflected instead of answering. If detected, `_retry_on_refusal()` retries once with a stronger nudge.

### Model Fallback

The pipeline has fallback logic. If a model returns empty responses after retries, it automatically falls back to a compatible model on the same or a different provider.

### History Trimming

`_trim_history()` trims conversation history oldest-first to stay under the enterprise WAF's body byte limit. The system prompt and current message get priority; history fills the remaining budget. Controlled by `A2UI_MAX_BODY_BYTES` env var.

### Tool Locking

Environment variables can lock tools regardless of user settings:

| Env Var                   | Tool                  |
| ------------------------- | --------------------- |
| `A2UI_TOOL_WEB_SEARCH`    | Web search            |
| `A2UI_TOOL_GEOLOCATION`   | Geolocation           |
| `A2UI_TOOL_HISTORY`       | Conversation history  |
| `A2UI_TOOL_AI_CLASSIFIER` | AI intent analysis    |
| `A2UI_TOOL_DATA_SOURCES`  | External data sources |

Tool states are resolved in priority order: **environment variable** > **user request setting** > **default**.

---

## Web Search Integration

When web search is enabled and the intent analyzer (or `should_search()` regex) determines search is needed:

1. Query is rewritten via LLM (`llm_rewrite_query()` using `gpt-4.1-nano`) or rule-based rewrite
2. Tavily search API is called (via `WebSearchTool` in `tools.py`)
3. Results are formatted and prepended to the user message as `[Web Search Results]` context
4. Images from search results are collected for the response metadata

Requires `TAVILY_API_KEY` environment variable.

---

## Genie Integration

When `askGenie` is true:

1. Backend calls `call_genie()` in `genie_client.py` with the user's question
2. Genie queries Databricks and returns structured data
3. Data is formatted and prepended to the message as context
4. Suggested follow-up questions from Genie are attached to the response

Requires `GENIE_API_URL` environment variable (defaults to `http://localhost:8001`).

---

## API Endpoints

| Method | Path                                 | Rate Limit | Description                                      |
| ------ | ------------------------------------ | ---------- | ------------------------------------------------ |
| `GET`  | `/api`                               | 60/min     | Health / welcome                                 |
| `GET`  | `/api/providers`                     | 60/min     | List available LLM providers and models          |
| `GET`  | `/api/styles`                        | 60/min     | List available content styles                    |
| `GET`  | `/api/tools`                         | 60/min     | List tool states (web search, geolocation, etc.) |
| `GET`  | `/api/data-sources`                  | 60/min     | List available data sources                      |
| `POST` | `/api/provide-location/{request_id}` | 30/min     | Receive geolocation from frontend                |
| `POST` | `/api/chat`                          | 20/min     | Send message, get A2UI response (JSON or SSE)    |

### Chat Request Schema

```json
{
  "message": "string (1-10000 chars)",
  "provider": "string (optional, alphanumeric + hyphens)",
  "model": "string (optional, alphanumeric + dots/hyphens)",
  "history": [{ "role": "user|assistant", "content": "string (max 10000)" }],
  "enableWebSearch": true,
  "enableGeolocation": true,
  "enableDataSources": true,
  "askGenie": false,
  "userLocation": { "lat": 0, "lng": 0, "label": "string" },
  "dataContext": [{ "source": "source-id", "label": "optional", "data": {} }],
  "contentStyle": "auto|analytical|content|comparison|dashboard|howto|quick|alerts-dashboard|alert-detail",
  "performanceMode": "auto|comprehensive|optimized",
  "smartRouting": true
}
```

### SSE Event Types

When the client sends `Accept: text/event-stream`, the response is an SSE stream:

| Event           | Description                                                                             |
| --------------- | --------------------------------------------------------------------------------------- |
| `step`          | Pipeline progress update (analyzing, searching, generating, etc.)                       |
| `need_location` | Backend needs geolocation; frontend should POST to `/api/provide-location/{request_id}` |
| `complete`      | Final A2UI JSON response                                                                |
| `error`         | Pipeline error                                                                          |

### Chat Response Metadata

The response includes optional metadata fields:

| Field                     | Type    | Description                                 |
| ------------------------- | ------- | ------------------------------------------- |
| `_search`                 | object  | Search metadata                             |
| `_sources`                | array   | Source citations                            |
| `_images`                 | array   | Image URLs from search                      |
| `_location`               | boolean | Whether location was used                   |
| `_data_sources`           | object  | Data source metadata                        |
| `_style`                  | string  | Content style used                          |
| `_performance`            | string  | Performance mode used                       |
| `_model`                  | string  | Model used for generation                   |
| `_provider`               | string  | Provider used                               |
| `_model_upgraded_from`    | string  | Original model if smart routing upgraded    |
| `_provider_upgraded_from` | string  | Original provider if smart routing upgraded |

---

## Security

- **CORS**: restricted to configured origins (`A2UI_CORS_ORIGINS`)
- **Rate limiting**: 20 req/min on `/api/chat`, 30 req/min on `/api/provide-location`, 60 req/min on other endpoints
- **API key auth**: optional, via `A2UI_API_KEY` and `X-API-Key` header
- **Body size limit**: 1 MB (`MAX_BODY_BYTES`)
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`
- **Input validation**: Pydantic models with field-level constraints and pattern matching
- **Injection detection**: 11 regex patterns for prompt injection, role impersonation, jailbreak attempts
- **Input sanitization**: Dangerous delimiters stripped after detection
- **Data source path traversal**: Endpoint whitelist and path validation for REST sources

---

## Environment Variables

| Variable                  | Purpose                                                             |
| ------------------------- | ------------------------------------------------------------------- |
| `A2UI_CORS_ORIGINS`       | CORS allowed origins                                                |
| `A2UI_API_KEY`            | Optional API key auth                                               |
| `A2UI_DEBUG`              | Enable debug mode (shows API docs)                                  |
| `A2UI_MAX_BODY_BYTES`     | WAF body size limit                                                 |
| `GENIE_API_URL`           | Databricks Genie API URL                                            |
| `OPENAI_API_KEY`          | OpenAI provider (at least one LLM key required)                    |
| `ANTHROPIC_API_KEY`       | Anthropic provider                                                  |
| `GEMINI_API_KEY`          | Google Gemini provider                                              |
| `TAVILY_API_KEY`          | Web search                                                          |
| `A2UI_TOOL_WEB_SEARCH`    | Lock web search tool                                                |
| `A2UI_TOOL_GEOLOCATION`   | Lock geolocation tool                                               |
| `A2UI_TOOL_HISTORY`       | Lock history tool                                                   |
| `A2UI_TOOL_AI_CLASSIFIER` | Lock AI classifier tool                                             |
| `A2UI_TOOL_DATA_SOURCES`  | Lock data sources tool                                              |
