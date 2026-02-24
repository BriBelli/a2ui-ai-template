# A2UI - Agent-to-User Interface

An Nx monorepo implementing [Google's A2UI specification](https://github.com/google/A2UI) - an open standard that allows AI agents to generate rich, interactive user interfaces.

## Overview

A2UI enables agents to "speak UI" by sending declarative JSON describing the intent of the UI. The client application renders this using native component libraries, ensuring that agent-generated UIs are **safe like data, but expressive like code**.

## Project Structure

```
a2ui/
├── apps/
│   ├── frontend/          # Original React app (OpenAI integration)
│   ├── a2ui-demo/         # A2UI component demo application (React)
│   └── a2ui-chat/         # A2UI chat interface (Lit/Web Components)
├── libs/
│   ├── a2ui-core/         # Core types, validation, and utilities
│   ├── a2ui-react/        # React renderer implementation
│   └── a2ui-lit/          # Lit/Web Components renderer implementation
├── backend/               # Python FastAPI backend with LLM providers
├── docs/                  # Additional documentation and guides
└── nx.json               # Nx workspace configuration
```

## A2UI Libraries

### @a2ui/core

Core library containing:
- **Types**: A2UIResponse, A2UIComponent, actions, events
- **Schema validation**: Validate A2UI responses
- **Registry**: Framework-agnostic component registry
- **Utilities**: Tree building, data binding, conditional evaluation

### @a2ui/react

React implementation featuring:
- **A2UIRenderer**: Main component for rendering A2UI responses
- **Built-in components**: Card, Button, TextField, Select, Checkbox, etc.
- **Hooks**: useA2UI, useA2UIFetch for state management
- **Context**: Shared state across component tree

### @a2ui/lit

Lit/Web Components implementation featuring:
- **Native web components**: Framework-agnostic components
- **Built-in components**: Card, Button, Text, Container, Chart, DataTable, List, etc.
- **Chat interface**: Pre-built chat components for conversational UIs
- **Lightweight**: No framework dependencies, runs anywhere

## Getting Started

### Installation

```bash
npm install
```

### Quick Start (Recommended)

```bash
# Run backend + chat interface together
npm run dev
```

This starts both the Python backend and the a2ui-chat interface for a full development experience.

### Running Applications Individually

#### A2UI Chat Interface (Lit/Web Components)

```bash
npm run a2ui:chat
# or
nx dev a2ui-chat
```

Interactive chat interface with A2UI component rendering. Best for testing conversational AI integrations.

#### A2UI Demo (React)

```bash
npm run a2ui:demo
# or
nx dev a2ui-demo
```

Static demo showcasing:
- Restaurant finder UI
- Flight booking form
- Settings panel
- Loading states

#### Original Frontend (React)

```bash
npm run frontend:start
```

#### Backend

```bash
npm run backend:start
# or
cd backend && python3 app.py
```

## Building

```bash
# Build all projects
npm run build:all

# Build specific libraries
npm run a2ui:core:build
npm run a2ui:react:build

# Build applications
npm run a2ui:demo:build
npm run a2ui:chat:build
npm run frontend:build
```

## A2UI Response Format

```json
{
  "version": "0.8",
  "root": "root-id",
  "components": [
    {
      "id": "root-id",
      "type": "container",
      "props": { "direction": "column" },
      "children": ["child-1", "child-2"]
    },
    {
      "id": "child-1",
      "type": "text",
      "props": { "content": "Hello A2UI!", "variant": "heading" }
    },
    {
      "id": "child-2",
      "type": "button",
      "props": { "label": "Click Me", "variant": "filled" }
    }
  ],
  "data": {}
}
```

## Built-in Component Types

| Type | Description |
|------|-------------|
| `card` | Container with title, subtitle, elevation |
| `button` | Interactive button with variants |
| `text-field` | Text input with validation |
| `text` | Typography component |
| `container` | Flex layout container |
| `image` | Image display |
| `select` | Dropdown selection |
| `checkbox` | Boolean toggle |
| `chip` | Tag/chip component |
| `progress` | Linear/circular progress |
| `divider` | Visual separator |

## Creating Custom Components

Register custom components with the renderer:

```tsx
import { createReactRegistry, A2UIRenderer } from '@a2ui/react';

const customRegistry = createReactRegistry();

customRegistry.register({
  type: 'my-custom-component',
  render: (component, context) => (
    <div>Custom: {component.props?.label}</div>
  ),
});

<A2UIRenderer 
  response={response}
  registry={customRegistry}
/>
```

## Roadmap to Nx Plugin

This project is structured to eventually become an Nx plugin:

1. **Generator**: Create new A2UI renderers (React, Vue, Angular)
2. **Executor**: Build and validate A2UI libraries
3. **Schematic**: Add A2UI support to existing projects

## Backend (Python FastAPI)

AI-first backend with multi-provider LLM support and tool orchestration. See [`backend/README.md`](backend/README.md) for full documentation.

```bash
cd backend
pip3 install -r requirements.txt
cp .env.example .env   # add your API keys
python3 app.py
```

Backend runs on `http://localhost:8000`

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/providers` | Available LLM providers and models |
| `GET` | `/api/styles` | Available content styles |
| `GET` | `/api/tools` | Configurable tools and lock state |
| `POST` | `/api/chat` | Chat completion with A2UI response |

### AI-First Pipeline

Every request follows: **AI Intent Analysis** (decides style + tools) → **Execute tools** (search, location) → **LLM Generation** → **Post-processing**. Regex fallbacks only when AI is unavailable.

### Configurable Tools

Tools (web search, geolocation, history, AI classifier) can be controlled at three layers: **Environment** (admin lock) > **User setting** (UI toggle) > **Default**. Set `A2UI_TOOL_WEB_SEARCH=false` to globally disable web search regardless of user settings.

### LLM Providers

Configure via environment variables: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `TAVILY_API_KEY` (web search).

## Documentation

Additional documentation is available in the `docs/` folder:

- **[HOW-A2UI-WORKS.md](docs/HOW-A2UI-WORKS.md)** - Deep dive into how A2UI works internally
- **[SCAFFOLDING-AND-PROTOCOL.md](docs/SCAFFOLDING-AND-PROTOCOL.md)** - Protocol specifications and scaffolding
- **[WEB-SEARCH.md](docs/WEB-SEARCH.md)** - Web search integration guide
- **[AGENTS.md](AGENTS.md)** - Instructions for AI agents working with A2UI

## License

Apache-2.0 (following Google's A2UI specification)

## References

- [A2UI Specification](https://github.com/google/A2UI)
- [A2UI Documentation](https://a2ui.org)
- [Nx Documentation](https://nx.dev)
