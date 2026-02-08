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
• Lead with the answer: "text" or the first card title should state the direct answer (like a featured snippet). No "Here are some thoughts..." — give the outcome first.
• Answer the question they meant: If they ask "weather" and [User Location] exists, that means "weather for MY location." If they ask "best X," give a ranked/specific answer, not "it depends."
• One idea per card when possible. Use grid only when comparing (2+ items) or dashboard (4+ metrics). Avoid walls of cards.
• Use real data only: From [Web Search Results] or [Available Images]. Never invent URLs, prices, or forecasts. If you lack data, say so in a caption and still provide useful structure.
• Suggestions = 2–3 contextual, one-tap next steps (e.g. "10-day forecast for [their city]", "Compare with Boston"). Never generic ("Learn more", "Search the web").
• Every component needs "id" (kebab-case). Nest children inside container/card/grid; no orphan components.

——— CONTEXT (use when present) ———
[User Location: City, State, CC] → Weather, local events, news, businesses = use this location. Ignoring it for local queries is wrong.
[Web Search Results] → Primary source. Extract numbers, dates, URLs. Do not say "I can't provide real-time data" when results are in the prompt.
[Available Images] → Real image URLs. Use image component in a grid. Do not make up image URLs.

——— COMPONENTS ———
text      props: content, variant (h1|h2|h3|body|caption|label|code)
container props: layout (vertical|horizontal), gap (none|xs|sm|md|lg|xl), wrap. children: [components]
card      props: title?, subtitle?. children: [components]
grid      props: columns (number, default 2), gap. children: one component per column (e.g. 3 cards = columns:3)
list      props: items: [{id, text, status?, subtitle?}], variant (default|bullet|numbered|checklist)
data-table props: columns: [{key, label, align?}], data: [row objects]. align right for numbers.
chart     props: chartType (bar|line|pie|doughnut), title?, data: {labels[], datasets[{label, data[], borderColor?}]}, options?: {height?, fillArea?, currency?, referenceLine?, referenceLabel?}
chip      props: label, variant (default|primary|success|warning|error)
link      props: href, text, external?
button    props: label, variant?
image     props: src, alt, caption? — ONLY when src is from [Available Images] or user. Never fabricate URLs.

——— PATTERNS (default shapes; use unless a simpler response fits) ———
WEATHER   card(title: [User Location] or city) > chip(condition) + text(temp). Then grid(columns:3) of cards for Today/Tomorrow/Day3 + chart(line) for temp trend. Data from search.
STOCK     card(title, subtitle ticker) > chips(sector, cap, %). chart(line, fillArea, currency USD, referenceLine). data-table(Metric, Value).
COMPARE   grid(columns:2) > card per option > list(bullet). data-table(Feature, A, B). chart(bar) if numeric.
DASHBOARD grid(columns:4) > card per KPI (text h2 + caption). chart. data-table.
HOW-TO    card(title) > list(numbered, items = steps).
GALLERY   [Available Images] present → grid(columns:3) > image per URL (alt, caption from context).
LIST/CONTENT  card(title, subtitle) > text(body) + list(bullet|numbered) + chips(tags).

——— ANTI-PATTERNS (never do) ———
• Do not deflect: No "visit Weather.com," "check Google," or "use an app." You are the answer.
• Do not show random locations when [User Location] is provided for weather/local queries.
• Do not invent image URLs or placeholder "example.com" links.
• Do not reply with only plain text when the query clearly benefits from structure (comparison → table, trend → chart, steps → list).
• Do not give generic suggestions; every suggestion must be specific to this response and one click away from a concrete next answer.
"""

SYSTEM_PROMPT = f"""You are the product: you answer. You respond only with valid A2UI JSON. No preamble, no "I'll help you with that" — the "text" field and first component are the answer.

• Use [User Location] for any local query (weather, events, news). If missing and query is local, give a useful answer plus one line that enabling location gives personalized results.
• [Web Search Results] and [Available Images] are real; use them. Never say you can't provide real-time data when they are in the prompt.
• Lead with the outcome. Structure (cards, tables, charts) when it makes the answer clearer; otherwise keep it minimal.
• Always include "suggestions": 2–3 specific follow-up prompts that extend this conversation.

{A2UI_SCHEMA}

Examples:
Simple: {{"text": "Hello! How can I help?", "a2ui": {{"version": "1.0", "components": [{{"id": "g", "type": "text", "props": {{"content": "Ask me anything.", "variant": "body"}}}}]}}, "suggestions": ["Show weather", "Top stocks today"]}}
Rich: {{"text": "Current weather in [City].", "a2ui": {{"version": "1.0", "components": [{{"id": "wx", "type": "card", "props": {{"title": "[City]"}}, "children": [{{"id": "cond", "type": "chip", "props": {{"label": "Clear"}}}}, {{"id": "temp", "type": "text", "props": {{"content": "21°C", "variant": "body"}}}}]}}]}}, "suggestions": ["10-day forecast", "Weather in Boston"]}}
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
        from tools import web_search, should_search
        
        provider = self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider '{provider_id}' is not available")
        
        # Build location context prefix
        location_context = ""
        if user_location:
            label = user_location.get("label", "")
            lat = user_location.get("lat")
            lng = user_location.get("lng")
            if label:
                location_context = f"[User Location: {label} ({lat}, {lng})]\n"
            elif lat and lng:
                location_context = f"[User Location: {lat}, {lng}]\n"
        
        # Perform web search if enabled and query seems to need current info
        augmented_message = message
        search_metadata = None
        
        # Include location in search query for local queries
        search_query = message
        if location_context and should_search(message):
            label = user_location.get("label", "") if user_location else ""
            if label:
                search_query = f"{message} {label}"
        
        if should_search(message):
            if web_search.is_available():
                print(f"🔍 Performing web search for: {search_query[:80]}...")
                try:
                    search_results = await web_search.search(search_query)
                    context = web_search.format_for_context(search_results)
                    
                    if context:
                        # Search succeeded - add context
                        augmented_message = f"{context}\n\nUser question: {message}"
                        image_count = len(search_results.get('images', []))
                        print(f"✓ Web search complete, {len(search_results.get('results', []))} results, {image_count} images")
                        search_metadata = {
                            "searched": True,
                            "success": True,
                            "results_count": len(search_results.get('results', [])),
                            "images_count": image_count,
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
