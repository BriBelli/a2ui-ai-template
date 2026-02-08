"""
LLM Providers for A2UI

Supports multiple AI providers:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude 3.5, Claude 3)
- Google (Gemini Pro, Gemini Flash)

Each provider can generate A2UI JSON responses.
"""

import os
import json
import re
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod


def parse_llm_json(content: str) -> Dict[str, Any]:
    """
    Parse JSON from an LLM response string.
    
    Strips markdown fences, extracts JSON, and returns a dict.
    Providers should use JSON mode when available so this is just a safety net.
    """
    content = content.strip()
    
    # Strip markdown code fences
    if content.startswith("```"):
        content = re.sub(r'^```\w*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
        content = content.strip()
    
    # Extract the outermost JSON object
    match = re.search(r'\{[\s\S]*\}', content)
    if match:
        content = match.group()
    
    try:
        result = json.loads(content)
        if isinstance(result, dict):
            return result
        return {"text": content}
    except json.JSONDecodeError as e:
        print(f"[parse] JSON error: {e} — preview: {content[:200]}")
        return {"text": content}

# A2UI Schema definition for LLM context
A2UI_SCHEMA = """
A2UI is a declarative JSON protocol for UI. You MUST respond with valid JSON containing:

{
  "text": "Optional plain text explanation",
  "a2ui": {
    "version": "1.0",
    "components": [...]
  }
}

Available component types:

1. text - Display text
   props: { content: string, variant: "h1"|"h2"|"h3"|"body"|"caption"|"label"|"code" }

2. container - Layout container
   props: { layout: "vertical"|"horizontal", gap: "none"|"xs"|"sm"|"md"|"lg"|"xl", wrap: boolean }
   children: [components...]

3. card - Card with optional title
   props: { title?: string, subtitle?: string }
   children: [components...]

4. list - List of items
   props: { 
     items: [{ id: string, text: string, status?: "pending"|"in-progress"|"completed", subtitle?: string }],
     variant: "default"|"bullet"|"numbered"|"checklist"
   }

5. data-table - Data table
   props: {
     columns: [{ key: string, label: string, width?: string, align?: "left"|"center"|"right" }],
     data: [{ [key]: value }...]
   }
   Required: columns[].key, columns[].label, data. Optional: width, align.
   When using align: "left" for text (default), "right" for numbers, "center" only for short labels.

6. chart - Chart visualization (bar, line, pie, doughnut)
   props: {
     chartType: "bar"|"line"|"pie"|"doughnut",
     title?: string,
     data: {
       labels: string[],
       datasets: [{ label: string, data: number[], backgroundColor?: string|string[], borderColor?: string }]
     },
     options?: {
       height?: number,           // Chart height in px (default 240)
       fillArea?: boolean,        // Gradient fill under line charts (auto for single dataset)
       showGrid?: boolean,        // Show grid lines (default: off for line, on for bar)
       showLegend?: boolean,      // Show legend (auto: hidden for single dataset)
       currency?: string,         // Format values as currency, e.g. "USD"
       referenceLine?: number,    // Horizontal dotted reference line at this value
       referenceLabel?: string    // Label for the reference line, e.g. "Previous close"
     }
   }
   CHART TIPS:
   - For stock/price data: use line chart with fillArea:true, currency:"USD", and a referenceLine at the opening/previous value
   - For single stock trends: use green borderColor "#81c995" for positive, red "#f28b82" for negative
   - For comparisons: use different borderColor per dataset, no fillArea
   - For rankings/categories: use bar chart
   - Always provide at least 6-12 data points for smooth line charts

7. button - Clickable button
   props: { label: string, variant?: "default"|"primary"|"outlined"|"text"|"danger" }

8. chip - Tag/chip
   props: { label: string, variant?: "default"|"primary"|"success"|"warning"|"error" }

9. link - Hyperlink
   props: { href: string, text: string, external?: boolean }

10. image - Image display
    props: { src: string, alt: string, caption?: string }
    Note: For placeholder images, use URLs like "https://picsum.photos/200" or leave src empty for a placeholder icon

11. grid - Multi-column layout (for dashboards, side-by-side cards)
    props: { columns?: number (default 2), gap?: "none"|"xs"|"sm"|"md"|"lg"|"xl" }
    columns = actual number of columns you want. Children fill one column each.
    Example: grid(columns:3) > card + card + card = 3 equal columns
    Example: grid(columns:2) > card + card = 2 equal columns
    Example: grid(columns:4) > card + card + card + card = 4 equal columns

RULES:
- Always include an "id" field for each component (use descriptive kebab-case)
- Use appropriate component types for the data being displayed
- For tabular data, use data-table
- For comparisons or trends, use chart
- For lists of items, use list with appropriate variant
- Wrap related components in a container or grid
- Keep responses concise but informative
- Use grid for multi-column layouts (dashboards, side-by-side cards, metric rows)
- Use container for simple stacking (vertical or horizontal flow)

COMPOSITION PATTERNS (use these as recipes for common queries):

STOCK / FINANCIAL:
  container(vertical) >
    card(title: company name, subtitle: exchange + ticker) >
      container(horizontal, wrap) > chip(sector) + chip(market cap) + chip(change %)
    chart(line, fillArea, currency:"USD", referenceLine at previous close)
    data-table(columns: Metric, Value — rows: P/E, EPS, Market Cap, Dividend Yield, Revenue)

COMPARISON (X vs Y):
  container(vertical) >
    grid(columns:2) >
      card(title: "Option A") > list(bullet, key features)
      card(title: "Option B") > list(bullet, key features)
    data-table(columns: Feature, Option A, Option B — side-by-side comparison)
    chart(bar — numerical comparisons)

DASHBOARD / METRICS:
  container(vertical) >
    grid(columns:4) >
      card > text(h2, metric value) + text(caption, label)  [repeat for 4 KPIs]
    chart(main visualization)
    data-table(detailed data)

WEATHER / FORECAST:
  container(vertical) >
    card(title: city) > container(horizontal) > chip(condition) + text(temperature)
    grid(columns:3) >
      card(title: "Today") > text + chip
      card(title: "Tomorrow") > text + chip
      card(title: day name) > text + chip
    chart(line — temperature trend)

LIST / CONTENT:
  container(vertical) >
    card(title, subtitle) >
      text(body, main content)
      list(bullet or numbered — key points)
    container(horizontal, wrap) > chip(tag) + chip(tag)

HOW-TO / STEPS:
  container(vertical) >
    card(title: "How to...") >
      list(numbered — step by step instructions)
    text(caption — tip or note)

FOLLOW-UP SUGGESTIONS:
- Include a "suggestions" field in your JSON response: an array of 2-3 short follow-up prompts
- These appear as clickable buttons below your response so the user can explore related topics
- Make them specific and contextual to your response (not generic)
- Example: {"text": "...", "suggestions": ["Show NVDA stock chart", "Compare tech vs energy stocks"]}
"""

SYSTEM_PROMPT = f"""You respond using A2UI JSON protocol. Be concise but helpful.

IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning. Provide helpful, substantive responses even when you cannot access real-time data. Instead of refusing, provide:
- Most recent known data with context
- Historical context and typical ranges
- Useful related information
- Links or guidance to find current data

Never say "I can't provide real-time data" and stop there. Always be maximally helpful.

NOTE: You may receive web search results prefixed with [Web Search Results]. If present, prioritize that information. If NOT present but the query needs current data, acknowledge your knowledge cutoff and provide the best available information from your training.

{A2UI_SCHEMA}

RESPONSE RULES:
1. Simple questions (greetings, short facts) → use just "text" field, maybe one text component
2. Complex topics → use cards with lists for organization
3. Comparisons → use data-table
4. Data/stats → use chart with actual values
5. ALWAYS include "id" on every component
6. For real-time queries (stocks, weather, sports): USE the web search results provided to give accurate current data
7. For stock/market data: ALWAYS use a line chart with fillArea, currency, and referenceLine for price trends. Use actual values from search results.
8. When web search results are present, extract specific numbers and use them in charts and tables — do NOT say "I can't provide real-time data"

Example simple response:
{{"text": "Hello! How can I help?", "a2ui": {{"version": "1.0", "components": [{{"id": "greeting", "type": "text", "props": {{"content": "I'm ready to assist you.", "variant": "body"}}}}]}}}}

Example complex response:
{{"text": "Brief intro", "a2ui": {{"version": "1.0", "components": [{{"id": "main-card", "type": "card", "props": {{"title": "Topic"}}, "children": [{{"id": "info", "type": "text", "props": {{"content": "Details...", "variant": "body"}}}}, {{"id": "points", "type": "list", "props": {{"variant": "bullet", "items": [{{"id": "p1", "text": "Point 1"}}, {{"id": "p2", "text": "Point 2"}}]}}}}]}}]}}}}

Match response complexity to question complexity. Use real data, not placeholders."""


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    name: str
    models: List[Dict[str, str]]
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and available."""
        pass
    
    @abstractmethod
    async def generate(
        self, 
        message: str, 
        model: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Generate a response for the given message with optional history."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""
    
    name = "OpenAI"
    models = [
        {"id": "gpt-4o", "name": "GPT-4o"},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo"},
        {"id": "gpt-4", "name": "GPT-4"},
        {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo"},
    ]
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def generate(
        self, 
        message: str, 
        model: str = "gpt-4o",
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        import openai
        
        client = openai.OpenAI(api_key=self.api_key)
        
        # Build messages with history
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        if history:
            for msg in history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        messages.append({"role": "user", "content": message})
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2000,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        
        content = response.choices[0].message.content.strip()
        return parse_llm_json(content)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""
    
    name = "Anthropic"
    models = [
        {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
        {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
        {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku (Fast)"},
        {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
    ]
    
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def generate(
        self, 
        message: str, 
        model: str = "claude-sonnet-4-20250514",
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        import anthropic
        
        client = anthropic.Anthropic(api_key=self.api_key)
        
        # Build messages with history
        messages = []
        
        if history:
            for msg in history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        messages.append({"role": "user", "content": message})
        
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=messages
        )
        
        content = response.content[0].text.strip()
        return parse_llm_json(content)


class GeminiProvider(LLMProvider):
    """Google Gemini provider."""
    
    name = "Google"
    models = [
        {"id": "gemini-2.5-pro-preview-05-06", "name": "Gemini 2.5 Pro"},
        {"id": "gemini-2.5-flash-preview-05-20", "name": "Gemini 2.5 Flash"},
        {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash"},
        {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
    ]
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def generate(
        self, 
        message: str, 
        model: str = "gemini-2.5-flash-preview-05-20",
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        import google.generativeai as genai
        
        genai.configure(api_key=self.api_key)
        
        gen_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=SYSTEM_PROMPT
        )
        
        # Build chat history for Gemini
        chat_history = []
        if history:
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                chat_history.append({
                    "role": role,
                    "parts": [msg["content"]]
                })
        
        generation_config = {"response_mime_type": "application/json"}
        
        if chat_history:
            chat = gen_model.start_chat(history=chat_history)
            response = chat.send_message(message, generation_config=generation_config)
        else:
            response = gen_model.generate_content(message, generation_config=generation_config)
        
        content = response.text.strip()
        return parse_llm_json(content)


class LLMService:
    """Service for managing LLM providers."""
    
    def __init__(self):
        self.providers = {
            "openai": OpenAIProvider(),
            "anthropic": AnthropicProvider(),
            "gemini": GeminiProvider(),
        }
    
    def get_available_providers(self) -> List[Dict[str, Any]]:
        """Get list of available providers and their models."""
        available = []
        for key, provider in self.providers.items():
            if provider.is_available():
                available.append({
                    "id": key,
                    "name": provider.name,
                    "models": provider.models,
                })
        return available
    
    def get_provider(self, provider_id: str) -> Optional[LLMProvider]:
        """Get a specific provider by ID."""
        provider = self.providers.get(provider_id)
        if provider and provider.is_available():
            return provider
        return None
    
    async def generate(
        self, 
        message: str, 
        provider_id: str, 
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
        enable_web_search: bool = False
    ) -> Dict[str, Any]:
        """Generate a response using the specified provider and model."""
        from tools import web_search, should_search
        
        provider = self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider '{provider_id}' is not available")
        
        # Perform web search if enabled and query seems to need current info
        augmented_message = message
        search_metadata = None
        
        if enable_web_search and should_search(message):
            if web_search.is_available():
                print(f"🔍 Performing web search for: {message[:50]}...")
                try:
                    search_results = await web_search.search(message)
                    context = web_search.format_for_context(search_results)
                    
                    if context:
                        # Search succeeded - add context
                        augmented_message = f"{context}\n\nUser question: {message}"
                        print(f"✓ Web search complete, {len(search_results.get('results', []))} results")
                        search_metadata = {
                            "searched": True,
                            "success": True,
                            "results_count": len(search_results.get('results', []))
                        }
                    else:
                        # Search failed - continue without context
                        error_type = search_results.get('error', 'unknown')
                        print(f"⚠️  Web search failed ({error_type}), continuing without search results")
                        search_metadata = {
                            "searched": True,
                            "success": False,
                            "error": error_type
                        }
                except Exception as e:
                    # Catch any unexpected errors and continue gracefully
                    print(f"⚠️  Web search error (continuing anyway): {e}")
                    search_metadata = {
                        "searched": True,
                        "success": False,
                        "error": "exception"
                    }
            else:
                print("ℹ️  Web search requested but not configured, using AI knowledge only")
                search_metadata = {
                    "searched": False,
                    "reason": "not_configured"
                }
        
        response = await provider.generate(augmented_message, model, history)
        
        # Add search metadata to response (optional, for debugging)
        if search_metadata:
            response["_search"] = search_metadata
        
        return response


# Global instance
llm_service = LLMService()
