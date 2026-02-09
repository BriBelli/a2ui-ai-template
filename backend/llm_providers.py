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

# A2UI Schema definition for LLM context (passed with every prompt)
A2UI_SCHEMA = """
A2UI JSON CONTRACT — You MUST respond with valid JSON only:
{
  "text": "One-sentence direct answer or intro (user sees this first)",
  "a2ui": { "version": "1.0", "components": [...] },
  "suggestions": ["Follow-up 1", "Follow-up 2"]
}

——— UX STANDARDS (non-negotiable) ———
• Lead with the answer: "text" or the first component should state the direct answer (like a featured snippet). No "Here are some thoughts..." — give the outcome first.
• Answer the question they meant: If they ask "weather" and [User Location] exists, that means "weather for MY location." If they ask "best X," give a ranked/specific answer, not "it depends."
• Use real data only: From [Web Search Results] or [Available Images]. NEVER invent, extrapolate, or guess numbers, temperatures, forecasts, prices, or stats. Only display values that appear verbatim in the search results. If a specific data point isn't in the results, omit it.
• Suggestions = 2–3 contextual, one-tap next steps. Never generic ("Learn more", "Search the web").
• Every component needs "id" (kebab-case). Nest children inside container/card/grid; no orphan components.

——— CONTEXT (use when present) ———
[User Location: City, State, CC] → Weather, local events, news, businesses = use this location.
[Web Search Results] → THIS IS YOUR PRIMARY DATA SOURCE. The results are REAL and CURRENT. You MUST:
  1. Extract specific numbers, dates, quotes, and facts from the results.
  2. Present them confidently as answers.
  3. NEVER say "I couldn't find," "data not available," or "enable web search" when results are present.
[Available Images] → Real image URLs. ONLY use when images ARE the content the user asked for (artwork, products, people, places they want to SEE). NEVER use decorative/stock images for weather, stocks, news, how-to, or any informational query. If the image doesn't directly answer the question, skip it.

═══════════════════════════════════════════
 COMPONENT SYSTEM  — Atomic Design tiers
═══════════════════════════════════════════

─── ATOMS (smallest building blocks) ───
text       props: content, variant (h1|h2|h3|body|caption|label|code)
chip       props: label, variant (default|primary|success|warning|error)
button     props: label, variant (default|primary|outlined|text|danger), size? (sm|md|lg)
link       props: href, text, external?
image      props: src, alt, caption? — ONLY from [Available Images] AND only when the user asked to SEE something (artwork, photos, products). Never for decoration. Never fabricate URLs.
separator  props: orientation? (horizontal|vertical), label? (optional centered text like "OR")
progress   props: label, value (number), max? (default 100), variant? (default|success|warning|error), showValue? (default true)

─── MOLECULES (composed of atoms, serve one purpose) ───
stat       props: label, value, trend?, trendDirection? (up|down|neutral — auto-detected from trend string), description?
           → USE THIS for any KPI / metric / number display. Shows: label on top, big bold value, optional trend badge (green ↑ / red ↓), description below. Like Shadcn dashboard cards.
list       props: items: [{id, text, status?, subtitle?}], variant (default|bullet|numbered|checklist)
data-table props: columns: [{key, label, align?}], data: [row objects]. align right for numbers.
chart      props: chartType (bar|line|pie|doughnut), title?, data: {labels[], datasets[{label, data[], borderColor?}]}, options?: {height?, fillArea?, currency?, referenceLine?, referenceLabel?}
accordion  props: items: [{id, title, content}], multiple? (allow multiple open, default false)
           → USE for FAQ, Q&A, expandable details sections.
tabs       props: tabs: [{id, label, count?, content}]
           → USE to organize multiple views of same data (e.g. Outline | Performance | Personnel).
alert      props: variant (default|info|success|warning|error), title, description
           → USE for important notices, disclaimers, status messages (e.g. "Market Closed", "Data delayed 15 min").

─── ORGANISMS (layout containers) ───
card       props: title?, subtitle?. children: [components]
           → Wraps molecules/atoms with a titled card container.
container  props: layout (vertical|horizontal), gap (none|xs|sm|md|lg|xl), wrap?. children: [components]
           → Flexbox layout wrapper. Use layout:horizontal + wrap:true for chip/badge rows.
grid       props: columns (number 1-6, default 2), gap?. children: one component per column cell.
           → CSS Grid. Use columns:4 for KPI stat rows, columns:2-3 for card comparisons, columns:3 for image galleries.

——— COMPOSITION PATTERNS ———

DASHBOARD / KPI:
  grid(columns:3 or 4) > stat per KPI. Then chart(line or bar). Then data-table if detail needed.
  Example: "top stocks" → grid(columns:4) of stat components (label=ticker, value=price, trend=change%, description=company). Then data-table for full list.

STOCK / FINANCIAL:
  stat(label=ticker, value=price, trend=change%, description=company+sector) at top.
  chart(line, fillArea, currency, referenceLine) for price history.
  data-table(Metric, Value) for fundamentals.
  alert(info) for disclaimers like "Data delayed 15 min."

WEATHER:
  stat(label=location, value=temp, trend=condition_emoji, trendDirection=neutral, description=condition text) at top.
  ONLY show data points from [Web Search Results]. Never invent forecasts.
  If multiple days available: grid of stat per day. chart ONLY with real numeric data.

COMPARE:
  grid(columns:2 or 3) > card per option with list(bullet) of features.
  data-table(Feature, Option A, Option B) for side-by-side.
  chart(bar) if comparing numeric values.

HOW-TO / STEPS:
  card(title) > list(numbered, items = steps).
  Optional alert(info) for tips or warnings.

FAQ / Q&A:
  accordion(items: [{id, title: "Question?", content: "Answer."}]).

GALLERY:
  grid(columns:3) > image per URL from [Available Images].

LIST / CONTENT:
  card(title, subtitle) > text(body) + list(bullet|numbered) + separator + chips(tags).

STATUS / TRACKING:
  card > progress bars for each metric. E.g. project completion, skill levels, ratings.

——— ANTI-PATTERNS (never do) ———
• NEVER deflect: No "visit Weather.com," "check Google," "use an app." You ARE the answer.
• NEVER say "data not found" when [Web Search Results] are present — extract the data.
• Do not use plain text when structure helps: comparison → table, trend → chart, steps → list, metrics → stat.
• Do not put single large numbers in text(h2) — use stat component instead. stat is purpose-built for KPI display.
• Do not give generic suggestions; every suggestion must be specific to this response.
• NEVER fabricate weather forecasts or financial data not in search results.
• Do not invent image URLs or placeholder "example.com" links.
• NEVER use images as decoration. Weather, stocks, news, how-to, FAQ = NO images unless the user explicitly asked to see a picture. Images are only for when the visual IS the answer (galleries, artwork, product photos).
"""

SYSTEM_PROMPT = f"""You are the product: you answer. You respond only with valid A2UI JSON. No preamble, no "I'll help you with that" — the "text" field and first component are the answer.

CRITICAL RULES:
• When [Web Search Results] appear in the prompt, they contain REAL, CURRENT data from the internet. You MUST extract facts/numbers from them and present them as your answer. NEVER say "I couldn't find" or "data not available" — the data is literally in the prompt.
• Use [User Location] for any local query (weather, events, news). If missing and query is local, give a useful answer plus one line that enabling location gives personalized results.
• [Available Images] are real URLs from the web; use the image component for them.
• Lead with the outcome. Structure (cards, tables, charts) when it makes the answer clearer; otherwise keep it minimal.
• Always include "suggestions": 2–3 specific follow-up prompts that extend this conversation.
• USE THE RIGHT COMPONENT: stat for KPIs/metrics, progress for completion/ratings, accordion for FAQ/Q&A, tabs for multi-view data, alert for notices. Don't flatten everything into text+card.

{A2UI_SCHEMA}

Examples:
Simple: {{"text": "Hello! How can I help?", "a2ui": {{"version": "1.0", "components": [{{"id": "g", "type": "text", "props": {{"content": "Ask me anything.", "variant": "body"}}}}]}}, "suggestions": ["Show weather", "Top stocks today"]}}

Dashboard: {{"text": "Top stocks for Feb 9, 2026.", "a2ui": {{"version": "1.0", "components": [{{"id": "kpi-grid", "type": "grid", "props": {{"columns": 4}}, "children": [{{"id": "s1", "type": "stat", "props": {{"label": "AAPL", "value": "$237.50", "trend": "+1.2%", "description": "Apple Inc."}}}}, {{"id": "s2", "type": "stat", "props": {{"label": "MSFT", "value": "$415.80", "trend": "-0.3%", "description": "Microsoft Corp."}}}}, {{"id": "s3", "type": "stat", "props": {{"label": "NVDA", "value": "$890.10", "trend": "+3.5%", "description": "NVIDIA Corp."}}}}, {{"id": "s4", "type": "stat", "props": {{"label": "GOOGL", "value": "$176.20", "trend": "+0.8%", "description": "Alphabet Inc."}}}}]}}]}}, "suggestions": ["Show AAPL price history", "Compare NVDA vs AMD"]}}

Weather: {{"text": "Currently 28°F and clear in Hartford, CT.", "a2ui": {{"version": "1.0", "components": [{{"id": "wx", "type": "stat", "props": {{"label": "Hartford, CT", "value": "28°F", "trend": "☀️ Clear", "trendDirection": "neutral", "description": "Feels like 22°F · Wind NW 12 mph"}}}}, {{"id": "note", "type": "alert", "props": {{"variant": "info", "title": "Frost Advisory", "description": "Temperatures dropping below 20°F overnight."}}}}]}}, "suggestions": ["5-day forecast for Hartford", "Weather in New York"]}}
"""


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
        {"id": "gpt-4.1", "name": "GPT-4.1"},
        {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini"},
        {"id": "gpt-4.1-nano", "name": "GPT-4.1 Nano (Fast)"},
        {"id": "gpt-4o", "name": "GPT-4o"},
    ]
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def generate(
        self, 
        message: str, 
        model: str = "gpt-4.1",
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
        {"id": "claude-opus-4-6", "name": "Claude Opus 4.6"},
        {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
        {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
        {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku (Fast)"},
    ]
    
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def generate(
        self, 
        message: str, 
        model: str = "claude-opus-4-6",
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
        {"id": "gemini-3-pro-preview", "name": "Gemini 3 Pro"},
        {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash"},
        {"id": "gemini-2.5-pro-preview-05-06", "name": "Gemini 2.5 Pro"},
        {"id": "gemini-2.5-flash-preview-05-20", "name": "Gemini 2.5 Flash"},
    ]
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def generate(
        self, 
        message: str, 
        model: str = "gemini-3-flash-preview",
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
        enable_web_search: bool = False,
        user_location: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a response using the specified provider and model."""
        from tools import web_search, should_search, rewrite_search_query, llm_rewrite_query
        
        provider = self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider '{provider_id}' is not available")
        
        # Build location context prefix
        location_context = ""
        location_label = ""
        if user_location:
            location_label = user_location.get("label", "")
            lat = user_location.get("lat")
            lng = user_location.get("lng")
            if location_label:
                location_context = f"[User Location: {location_label} ({lat}, {lng})]\n"
            elif lat and lng:
                location_context = f"[User Location: {lat}, {lng}]\n"
        
        # Perform web search if query seems to need current info
        augmented_message = message
        search_metadata = None
        
        if should_search(message):
            # Rewrite the conversational prompt into an optimised search query.
            # Try LLM-based rewriter first (handles typos, context, intent);
            # fall back to rule-based if the LLM call fails or is unavailable.
            search_query = await llm_rewrite_query(
                message,
                location=location_label,
                history=history,
            )
            if not search_query:
                search_query = rewrite_search_query(message, location=location_label)
            
            if web_search.is_available():
                print(f"🔍 Search: \"{search_query[:100]}\"  ← \"{message[:60]}\"")

                try:
                    search_results = await web_search.search(search_query)
                    context = web_search.format_for_context(search_results)
                    
                    if context:
                        augmented_message = f"{context}\n\nUser question: {message}"
                        image_count = len(search_results.get('images', []))
                        print(f"✓ Web search complete, {len(search_results.get('results', []))} results, {image_count} images")
                        search_metadata = {
                            "searched": True,
                            "success": True,
                            "results_count": len(search_results.get('results', [])),
                            "images_count": image_count,
                            "query": search_query,
                        }
                    else:
                        error_type = search_results.get('error', 'unknown')
                        print(f"⚠️  Web search failed ({error_type}), continuing without search results")
                        search_metadata = {
                            "searched": True,
                            "success": False,
                            "error": error_type,
                            "query": search_query,
                        }
                except Exception as e:
                    print(f"⚠️  Web search error (continuing anyway): {e}")
                    search_metadata = {
                        "searched": True,
                        "success": False,
                        "error": "exception",
                        "query": search_query,
                    }
            else:
                print("ℹ️  Web search requested but not configured, using AI knowledge only")
                search_metadata = {
                    "searched": False,
                    "reason": "not_configured"
                }
        
        # Prepend location context so the LLM knows where the user is
        if location_context:
            augmented_message = f"{location_context}{augmented_message}"
        
        response = await provider.generate(augmented_message, model, history)
        
        # Add metadata to response (for frontend thinking steps + debugging)
        if search_metadata:
            response["_search"] = search_metadata
        if user_location:
            response["_location"] = True
        
        return response


# Global instance
llm_service = LLMService()
