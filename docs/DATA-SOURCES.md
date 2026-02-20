# Data Sources

Connect the A2UI agent to external data — REST APIs, databases, data warehouses — so it can query, analyze, and render live data as rich A2UI components.

## Overview

Data Sources is a configurable tool that gives the AI agent access to external data. It operates in two modes:

| Mode | Who fetches the data | When to use |
|------|---------------------|-------------|
| **Passive** | Your app fetches data, sends it in the request | You already have data from another service, database, or connector |
| **Active** | The AI agent autonomously decides what to fetch | You configure API endpoints and let the agent discover what's relevant |

Both modes feed data into the full AI pipeline — the AI analyzer classifies the content style, and the LLM builds A2UI components (charts, tables, stats, etc.) from the real data.

---

## Quick Start

### 1. Passive Mode (Bring Your Own Data)

Send pre-fetched data in the `dataContext` field of your `/api/chat` request. No backend configuration needed.

```json
POST /api/chat
{
  "message": "Summarize Q1 sales performance",
  "provider": "openai",
  "model": "gpt-4.1-mini",
  "dataContext": [
    {
      "source": "sales-api",
      "label": "Q1 Sales Report",
      "data": {
        "revenue": 2450000,
        "deals_closed": 47,
        "top_rep": "Sarah Chen",
        "monthly": [
          { "month": "Jan", "revenue": 720000 },
          { "month": "Feb", "revenue": 830000 },
          { "month": "Mar", "revenue": 900000 }
        ]
      }
    }
  ]
}
```

The `dataContext` array accepts **1 to N sources** in a single request:

```json
"dataContext": [
  { "source": "sales-api",  "label": "Revenue",     "data": { ... } },
  { "source": "crm-api",    "label": "Satisfaction", "data": [ ... ] },
  { "source": "hr-api",     "label": "Headcount",   "data": { ... } }
]
```

Each item has three fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | Yes | Identifier for the data origin |
| `label` | string | No | Human-readable name (shown in AI context) |
| `data` | any | Yes | The actual data — object, array, nested, whatever the upstream returns |

### 2. Active Mode (AI-Driven Discovery)

Configure API endpoints in `backend/data_sources/config.yaml`. The AI analyzer sees the available sources and autonomously decides which to query based on the user's prompt.

```yaml
# backend/data_sources/config.yaml
sources:
  - id: sales-api
    type: rest
    name: Sales Dashboard
    base_url: https://internal-api.company.com/v1
    auth:
      type: bearer
      token_env: SALES_API_TOKEN
    endpoints:
      - path: /revenue
        method: GET
        description: Revenue by quarter
        params: [period, year]
      - path: /pipeline
        method: GET
        description: Deal pipeline with stages
        params: [stage, rep_id]
    description: Sales data including revenue, pipeline, and rep performance.
    rules: Always include date ranges when querying /revenue.
```

After adding a source, restart the backend. The AI will see it and query it when relevant.

---

## Configuration Reference

### Source Types

#### `rest` — Generic REST API

Connects to any REST API. Supports manual endpoint definitions and/or auto-discovery from OpenAPI specs.

```yaml
- id: my-api                          # Unique identifier
  type: rest
  name: My API                        # Display name
  base_url: https://api.example.com   # Base URL for all endpoints
  auth:
    type: bearer                      # bearer | api_key | none
    token_env: MY_API_TOKEN           # Env var holding the secret
  endpoints:                          # Manual endpoint list
    - path: /data
      method: GET
      description: Returns all records
      params: [limit, offset, filter]
  openapi_spec: ./specs/my-api.yaml   # Optional: auto-discover from OpenAPI
  description: What this data source contains
  rules: Instructions for the AI on how to use this source
  enabled: true                       # Default: true
```

**Auth options:**

| Type | Fields | Header sent |
|------|--------|-------------|
| `bearer` | `token_env` | `Authorization: Bearer <token>` |
| `api_key` | `token_env`, `header` (optional, default `Authorization`) | `<header>: <token>` |
| `none` | — | No auth header |

Auth tokens are **always** referenced via environment variable names — never paste secrets into config.yaml.

#### `databricks` — Databricks Genie

Connects to a Databricks Genie space for natural-language data queries against enterprise warehouses.

```yaml
- id: enterprise-data
  type: databricks
  name: Enterprise Analytics
  config:
    workspace_url_env: DATABRICKS_WORKSPACE_URL
    token_env: DATABRICKS_TOKEN
    space_id: "your-genie-space-id"
  description: Customer analytics, product metrics, operational KPIs
  rules: Use for deep analytical questions about internal company data
```

### The `rules` Field

The `rules` string is injected into the LLM's system prompt as `[Data Source Rules]`. Use it to teach the AI **how** and **when** to use specific sources or endpoints:

```yaml
rules: >
  Always include date ranges when querying /revenue.
  Use /pipeline for forecasting questions.
  Prefer /revenue?period=summary for quick overviews.
  Never query /admin endpoints — they require elevated permissions.
```

### The `description` Field

The `description` is shown to the AI analyzer when it decides whether to query a source. Write it like you're explaining to a colleague what data lives here:

```yaml
description: >
  Sales data warehouse with quarterly revenue, deal pipeline
  by stage, customer segments, and rep performance metrics.
```

---

## How It Works

### Pipeline Flow

```
User prompt
    │
    ▼
┌─────────────────────────────┐
│ Step 1: AI Analyzer         │ ← Sees data source descriptions + endpoints
│ Decides: content style,     │   Decides: which sources to query (active)
│ web search, data sources    │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Step 2: Location context    │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Step 3: Web search          │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Step 3.5: Data Sources      │ ← Passive: inject dataContext
│                             │   Active: execute AI-decided queries
│                             │   Results become [Data Source: ...] blocks
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Step 4: LLM Generation      │ ← Sees all data in context
│ Builds A2UI components      │   Charts, tables, stats from real data
└─────────────┬───────────────┘
              │
              ▼
        A2UI Response
```

### What the LLM Sees

Data sources are injected as tagged context blocks, identical to web search results:

```
[Data Source: Q1 Sales Report]
{"revenue": 2450000, "deals_closed": 47, "monthly": [...]}

[Data Source: Customer Satisfaction]
[{"quarter": "Q1", "nps": 72}, {"quarter": "Q2", "nps": 75}, ...]

User question: Compare our sales and customer satisfaction trends
```

The LLM then builds A2UI components directly from this data — bar charts from revenue arrays, line charts from trend data, stat grids from KPIs.

---

## Tool Gating (3-Layer Control)

Data Sources follows the same 3-layer control as all A2UI tools:

| Layer | Mechanism | Effect |
|-------|-----------|--------|
| **1. Environment** | `A2UI_TOOL_DATA_SOURCES=false` | Globally disables — overrides everything, UI toggle is locked |
| **2. User Setting** | Settings panel toggle | User enables/disables per session |
| **3. AI Decision** | Analyzer decides per query | AI skips sources when not relevant |

Layer 1 beats Layer 2 beats Layer 3. If the env var is set to `false`, data sources are off regardless of user settings or AI decisions.

---

## API Endpoints

### `GET /api/data-sources`

Returns configured sources and their availability.

```json
{
  "sources": [
    {
      "id": "sales-api",
      "name": "Sales Dashboard",
      "description": "Sales data including revenue and pipeline",
      "enabled": true,
      "available": true,
      "has_rules": true,
      "endpoints": "  GET /revenue — Revenue by quarter\n  GET /pipeline — Deal pipeline"
    }
  ]
}
```

### `POST /api/chat` — dataContext field

Include `dataContext` for passive injection. Include `enableDataSources` to control the tool gate.

```json
{
  "message": "...",
  "enableDataSources": true,
  "dataContext": [
    { "source": "...", "label": "...", "data": { ... } }
  ]
}
```

### Response Metadata

Responses include `_data_sources` metadata:

```json
// Passive mode
"_data_sources": { "passive": true, "sources": 3 }

// Active mode
"_data_sources": { "active": true, "queries": 2, "successful": 2, "failed": 0 }
```

---

## Testing

### Run the Test Suite

```bash
cd backend
python3 data_sources/test_data_sources.py
```

This runs 5 tests:

| Test | Description |
|------|-------------|
| Health Check | Verifies server is running and sources are loaded |
| Passive (single) | Injects sales data, confirms AI builds dashboard |
| Passive (multi) | Injects 3 sources at once, confirms all are used |
| Active | Asks about users — AI queries JSONPlaceholder `/users` |
| Tool Gate | Same query with `enableDataSources=false` — confirms skip |
| Active (todos) | Different endpoint — AI queries `/todos`, builds pie chart |

### Test Active Mode from the Chat UI

With the sample JSONPlaceholder source configured, try these prompts:

- "Show me all users from the sample database"
- "How many todos are completed vs pending?"
- "Show me posts by user 1"

### Test Passive Mode with curl

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Analyze this data",
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "dataContext": [
      {
        "source": "my-app",
        "label": "My Dataset",
        "data": [
          {"name": "Alpha", "value": 100},
          {"name": "Beta", "value": 250},
          {"name": "Gamma", "value": 175}
        ]
      }
    ]
  }'
```

---

## Adding a Custom Connector

To add a new data source type beyond REST and Databricks:

1. Create `backend/data_sources/your_connector.py`
2. Extend the `DataSource` base class
3. Implement `is_available()` and `query()`
4. Register it in `backend/data_sources/__init__.py` (`_create_source` factory)

```python
from ._base import DataSource

class MyConnector(DataSource):
    def __init__(self, cfg):
        super().__init__(
            id=cfg["id"],
            name=cfg.get("name", cfg["id"]),
            description=cfg.get("description", ""),
            rules=cfg.get("rules", ""),
        )
        # Parse your config...

    def is_available(self) -> bool:
        # Return True when properly configured
        return True

    async def query(self, endpoint, params=None, method="GET"):
        # Fetch data and return:
        return {"success": True, "data": {...}, "record_count": N}
        # Or on failure:
        return {"success": False, "error": "reason"}
```

Then add `type: your_type` in config.yaml and register in the factory:

```python
# backend/data_sources/__init__.py
def _create_source(src_type, cfg):
    ...
    elif src_type == "your_type":
        from .your_connector import MyConnector
        return MyConnector(cfg)
```

---

## Architecture Notes

- **Secrets**: Auth tokens are always env-var references, never stored in config
- **Truncation**: Payloads over 12,000 characters are truncated before LLM injection
- **Parallel queries**: Active mode executes multiple source queries concurrently
- **SSE events**: Data source queries emit `data_sources:start` / `data_sources:done` events for real-time loading UX
- **OpenAPI auto-discovery**: REST sources can parse OpenAPI 3.x / Swagger 2.x specs to auto-discover endpoints
- **Graceful skip**: If no sources are configured or available, the tool is silently skipped — zero overhead
