"""
LLM Providers for A2UI

Multi-provider AI service with a unified interface:
- OpenAI  (GPT-4.1, GPT-5)
- Anthropic  (Claude Opus 4.6, Claude Sonnet 4, Claude 3.5)
- Google Gemini  (Gemini 3 Pro, Gemini 2.5)
- Exploration Lab  (LiteLLM gateway — OpenAI-compatible)

Each provider implements the same abstract interface and returns
parsed A2UI JSON responses ready for the frontend.
"""

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List, Optional

import httpx
import openai
import anthropic

logger = logging.getLogger(__name__)


# ── Utilities ──────────────────────────────────────────────────


def _build_messages(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    max_body_bytes: int = 7200,
) -> List[Dict[str, str]]:
    """Build an OpenAI-style messages array with smart history truncation.

    The enterprise WAF rejects request bodies > 8 KB.  We budget
    ``max_body_bytes`` for total message *content* (system + history +
    user) leaving ~800 bytes for the JSON envelope / model params.

    History is trimmed **oldest-first** so the most recent turns are
    always preserved.
    """
    today = date.today().strftime("%B %d, %Y")  # e.g. "February 11, 2026"
    prompt = f"Today is {today}.\n\n{SYSTEM_PROMPT}"

    prompt_bytes = len(prompt.encode("utf-8"))
    msg_bytes = len(message.encode("utf-8"))
    trimmed = _trim_history(history, prompt_bytes, msg_bytes, max_body_bytes)

    messages: List[Dict[str, str]] = [{"role": "system", "content": prompt}]
    messages.extend(trimmed)
    messages.append({"role": "user", "content": message})
    return messages


def _trim_history(
    history: Optional[List[Dict[str, str]]],
    system_prompt_bytes: int = 0,
    message_bytes: int = 0,
    max_body_bytes: int = 7200,
) -> List[Dict[str, str]]:
    """Trim history oldest-first to stay within the WAF byte budget.

    This is a provider-agnostic helper.  ``_build_messages`` (OpenAI format)
    uses it internally; Anthropic and Gemini call it directly because they
    send the system prompt separately.
    """
    if not history:
        return []

    budget = max(0, max_body_bytes - system_prompt_bytes - message_bytes)
    trimmed: List[Dict[str, str]] = []

    for msg in reversed(history):
        msg_bytes = len(msg["content"].encode("utf-8"))
        if msg_bytes > budget:
            break
        trimmed.insert(0, {"role": msg["role"], "content": msg["content"]})
        budget -= msg_bytes

    if len(trimmed) < len(history):
        logger.info(
            "History trimmed: %d→%d turns to stay under WAF limit",
            len(history),
            len(trimmed),
        )
    return trimmed


# Phrases that indicate the LLM refused instead of answering
_REFUSAL_PHRASES = [
    "not available",
    "not yet available",
    "cannot provide",
    "don't have access",
    "no data available",
    "data is unavailable",
    "please refer to",
    "please consult",
    "consult financial",
    "check a financial",
    "unable to provide",
    "i can't provide",
    "i cannot access",
]


def _is_refusal(parsed: Dict[str, Any]) -> bool:
    """Detect if the LLM response is a refusal/deflection instead of real data."""
    text = (parsed.get("text") or "").lower()
    components = (parsed.get("a2ui") or {}).get("components") or []

    # Check the "text" field
    if any(phrase in text for phrase in _REFUSAL_PHRASES):
        return True

    # Check if the only component is a single alert about availability
    if len(components) == 1 and components[0].get("type") == "alert":
        desc = (components[0].get("props") or {}).get("description", "").lower()
        if any(phrase in desc for phrase in _REFUSAL_PHRASES):
            return True

    return False


async def _retry_on_refusal(
    result: Dict[str, Any],
    message: str,
    generate_fn,
) -> Dict[str, Any]:
    """If the LLM refused, retry once with a stronger nudge.

    ``generate_fn`` must be an async callable with signature
    ``(message: str, history=None) -> Dict[str, Any]``.
    """
    if not _is_refusal(result):
        return result

    logger.info("Refusal detected — retrying with override nudge")
    nudge = (
        "IMPORTANT: Do NOT say data is unavailable. You MUST provide "
        "approximate values from your training knowledge. Use a data-table "
        "and chart with your best estimates, and add an info alert noting "
        "the data is approximate. Original question: " + message
    )
    return await generate_fn(nudge, None)


def _clean_error_message(raw: str) -> str:
    """Strip HTML tags and clean up error messages for user display."""
    if "<html" in raw.lower() or "<body" in raw.lower():
        # Extract meaningful text from HTML error pages
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
        return text if text else "Unknown error"
    return raw


def _error_response(title: str, description: str, variant: str = "error") -> Dict[str, Any]:
    """Return a standardized A2UI error payload."""
    description = _clean_error_message(description)
    return {
        "text": f"{title}: {description}",
        "a2ui": {
            "version": "1.0",
            "components": [
                {
                    "id": "error",
                    "type": "alert",
                    "props": {
                        "variant": variant,
                        "title": title,
                        "description": description,
                    },
                }
            ],
        },
    }


# Component type → visual hierarchy priority (lower = appears first)
# Matches CRITICAL RULE #2: alert → stat grid → chart → data-table
_COMPONENT_PRIORITY = {
    "alert": 0,
    "grid": 1,
    "stat": 2,
    "chart": 3,
    "data-table": 4,
    "list": 5,
    "accordion": 6,
    "tabs": 7,
    "card": 8,
}


def _enforce_visual_hierarchy(result: Dict[str, Any]) -> Dict[str, Any]:
    """Reorder A2UI components to enforce chart-before-table visual hierarchy."""
    a2ui = result.get("a2ui")
    if not a2ui or not isinstance(a2ui, dict):
        return result

    components = a2ui.get("components")
    if not components or not isinstance(components, list) or len(components) < 2:
        return result

    # Filter to only dicts — sometimes the LLM slips in strings
    dict_components = [c for c in components if isinstance(c, dict)]
    if len(dict_components) < 2:
        return result

    # Stable sort by priority — preserves relative order within same type
    original_order = [c.get("type") for c in dict_components]
    dict_components.sort(key=lambda c: _COMPONENT_PRIORITY.get(c.get("type", ""), 99))
    new_order = [c.get("type") for c in dict_components]

    if original_order != new_order:
        logger.info("Visual hierarchy enforced: %s → %s", original_order, new_order)

    a2ui["components"] = dict_components
    return result


def parse_llm_json(content: str) -> Dict[str, Any]:
    """
    Parse JSON from an LLM response string.

    Strips markdown fences, extracts the outermost JSON object, and
    returns a dict.  Providers should use JSON mode when available so
    this is just a safety net.
    """
    content = content.strip()

    # Strip markdown code fences
    if content.startswith("```"):
        content = re.sub(r"^```\w*\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
        content = content.strip()

    # Extract the outermost JSON object
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        content = match.group()

    try:
        result = json.loads(content)
        if isinstance(result, dict):
            return _enforce_visual_hierarchy(result)
        return {"text": content}
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse error: %s — preview: %.200s", exc, content)
        return {"text": content}


# ── Prompts ────────────────────────────────────────────────────

SYSTEM_PROMPT = """CRITICAL RULES (non-negotiable):
1. NEVER refuse or say "not available". Always provide data from training knowledge. If approximate, add an info alert.
2. COMPONENT ORDER: alert → stat grid → chart → data-table. Charts ALWAYS come BEFORE tables. Visual insight first, dense data last. This order is mandatory.

Respond ONLY with valid A2UI JSON. No prose outside JSON.
{"text":"Direct answer","a2ui":{"version":"1.0","components":[...]},"suggestions":["Follow-up 1","Follow-up 2"]}

RULES:
• "text" = direct answer. No "Here are some thoughts…"
• Every component: {"id":"kebab-case","type","props"}
• Use [Web Search Results] when present. Otherwise use training knowledge.
• NEVER deflect to websites. You ARE the answer.
• [User Location] → weather/local. [Available Images] → only when user wants to SEE something.
• "suggestions" = 2–3 specific actions that trigger rich dashboard views. Examples: "NVDA 6-month price history", "Compare NVDA vs AMD performance", "Top tech ETFs by return". NEVER generic like "Learn more" or "View details".

COMPONENTS:
Atoms: text(content,variant:h1|h2|h3|body|caption|code) · chip(label,variant) · link(href,text) · image(src,alt—only [Available Images]) · progress(label,value,max?,variant?)
Molecules:
  stat — label, value(MUST be number/price), trend?, trendDirection?(up|down|neutral), description?
  list — items[{id,text,subtitle?}], variant(bullet|numbered|checklist)
  data-table — columns[{key,label,align?}], data[rows]. align:"right" for numbers.
  chart — chartType(bar|line|pie|doughnut), title?, data{labels[],datasets[{label,data[]}]}, options?{fillArea?,currency?,height?,xAxisLabel?,yAxisLabel?}. ALWAYS include xAxisLabel and yAxisLabel so axes are meaningful.
  accordion — items[{id,title,content}]
  tabs — tabs[{id,label,content}]
  alert — variant(info|success|warning|error), title, description
Layout:
  card — title?, subtitle?, children[]
  container — layout(vertical|horizontal), gap(xs|sm|md|lg|xl), wrap?, children[]
  grid — columns(1–6 or "auto"), children[]. columns=item count when ≤6; "auto" for 7+.

COMPONENT SELECTION (follow strictly):
• ANY numeric/financial data → MUST include chart. No exceptions.
  - Trends over time → line(fillArea:true). Compare → bar. Proportions → pie/doughnut.
• "Top N stocks/companies" rankings (largest, biggest, highest market cap, best performing) → chart(bar, market cap or metric in trillions) + data-table(7+ companies with name, mkt cap, sector). If [Web Search Results] include web snippets at top. Chart FIRST, table second.
• STOCK/TICKER (any price, ticker, stock history, financial query) → ALWAYS full dashboard: grid(4)>stat(price,change%,vol,mktCap) + chart(line,fillArea,currency:USD) + alert(info, if [Web Search Results] present: "Live market data. Prices may be slightly delayed." else: "Based on training data. Prices may differ from real-time.") + data-table(P/E,EPS,52wk,dividend,beta). NEVER just chart+date-table.
• Multiple stocks comparison → chart(bar,compare all on one axis) + data-table(detail per stock).
• Compare N items → chart(bar,1-10 ratings/feature) + data-table(8+ rows). No mixed units on axis.
• Monthly/yearly (non-stock) → chart + data-table(rows per period). Never separate cards.
• KPIs (≤6) → grid(columns:N) > stat. Pair with chart for financial data.
• How-to → list(numbered). FAQ → accordion.
• 7+ items → data-table or list. Never 7+ separate cards.
• No real numbers → data-table or list, NOT stat.

CHART GUIDE (ALWAYS include xAxisLabel and yAxisLabel):
Line: {"chartType":"line","data":{"labels":["Jan","Feb","Mar","Apr","May","Jun"],"datasets":[{"label":"Price","data":[800,820,850,830,870,890]}]},"options":{"fillArea":true,"currency":"USD","xAxisLabel":"Month","yAxisLabel":"Price (USD)"}}
Bar: {"chartType":"bar","data":{"labels":["Q1","Q2","Q3","Q4"],"datasets":[{"label":"Revenue","data":[100,115,130,150]}]},"options":{"currency":"USD","xAxisLabel":"Quarter","yAxisLabel":"Revenue (B USD)"}}

EXAMPLE — Stock Dashboard (stat grid + chart + alert + table):
{"text":"NVDA at $890, up 3.5%.","a2ui":{"version":"1.0","components":[{"id":"kpi","type":"grid","props":{"columns":4},"children":[{"id":"p","type":"stat","props":{"label":"Price","value":"$890","trend":"+3.5%"}},{"id":"v","type":"stat","props":{"label":"Volume","value":"45.2M"}},{"id":"m","type":"stat","props":{"label":"Mkt Cap","value":"$2.19T"}},{"id":"pe","type":"stat","props":{"label":"P/E","value":"65.4"}}]},{"id":"ch","type":"chart","props":{"chartType":"line","title":"6-Month Price","data":{"labels":["Sep","Oct","Nov","Dec","Jan","Feb"],"datasets":[{"label":"NVDA","data":[780,810,850,870,880,890]}]},"options":{"fillArea":true,"currency":"USD","xAxisLabel":"Month","yAxisLabel":"Price (USD)"}}},{"id":"n","type":"alert","props":{"variant":"info","title":"Note","description":"Based on training data. Prices may differ from real-time."}},{"id":"t","type":"data-table","props":{"columns":[{"key":"m","label":"Metric"},{"key":"v","label":"Value","align":"right"}],"data":[{"m":"52wk Range","v":"$560–$950"},{"m":"EPS","v":"$13.59"},{"m":"Dividend","v":"0.02%"},{"m":"Beta","v":"1.68"}]}}]},"suggestions":["Compare NVDA vs AMD","NVDA revenue trend","Top AI stocks"]}

EXAMPLE — Comparison (bar chart with 1-10 ratings + data-table with 8+ filled rows, NEVER empty cards):
{"text":"iPhone vs Android compared.","a2ui":{"version":"1.0","components":[{"id":"ch","type":"chart","props":{"chartType":"bar","title":"Feature Ratings (1-10)","data":{"labels":["Camera","Battery","Display","Performance","AI Features","Value"],"datasets":[{"label":"iPhone 16 Pro","data":[9,8,9,9,8,7]},{"label":"Galaxy S25 Ultra","data":[10,8,9,9,9,7]}]},"options":{"xAxisLabel":"Feature","yAxisLabel":"Rating (1-10)"}}},{"id":"t","type":"data-table","props":{"columns":[{"key":"f","label":"Feature"},{"key":"a","label":"iPhone"},{"key":"b","label":"Android"}],"data":[{"f":"OS","a":"iOS 18","b":"Android 15"},{"f":"Ecosystem","a":"Apple integrated","b":"Open, customizable"},{"f":"AI","a":"Apple Intelligence","b":"Google Gemini"},{"f":"Camera","a":"48MP ProRes","b":"200MP expert RAW"},{"f":"Price","a":"$799–$1599","b":"$199–$1799"},{"f":"Updates","a":"6+ years","b":"7 years (Samsung)"},{"f":"Security","a":"Face ID, Enclave","b":"Fingerprint, Knox"},{"f":"Charging","a":"MagSafe USB-C","b":"USB-C fast charge"}]}}]},"suggestions":["iPhone 16 Pro vs S25 Ultra specs","Best budget Androids 2025","iOS vs Android market share"]}

EXAMPLE — Top N Rankings (bar chart + table, NO stat cards):
{"text":"Top tech stocks.","a2ui":{"version":"1.0","components":[{"id":"ch","type":"chart","props":{"chartType":"bar","title":"Market Cap (Trillions)","data":{"labels":["NVDA","AAPL","GOOGL","MSFT","AMZN","TSMC","META"],"datasets":[{"label":"Market Cap","data":[4.6,4.0,3.8,3.0,2.2,1.6,1.7]}]},"options":{"xAxisLabel":"Ticker","yAxisLabel":"Market Cap (Trillions USD)"}}},{"id":"t","type":"data-table","props":{"columns":[{"key":"c","label":"Company"},{"key":"m","label":"Mkt Cap","align":"right"}],"data":[{"c":"Nvidia","m":"$4.6T"},{"c":"Apple","m":"$4.0T"},{"c":"Alphabet","m":"$3.8T"},{"c":"Microsoft","m":"$3.0T"},{"c":"Amazon","m":"$2.2T"},{"c":"TSMC","m":"$1.6T"},{"c":"Meta","m":"$1.7T"}]}}]},"suggestions":["Compare NVDA vs AAPL","Top AI stocks"]}"""


# ── Abstract Base ──────────────────────────────────────────────


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    name: str
    models: List[Dict[str, str]]

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and available."""

    @abstractmethod
    async def generate(
        self,
        message: str,
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Generate a response for the given message with optional history."""


# ── Provider Implementations ──────────────────────────────────


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""

    name = "OpenAI"
    models = [
        {"id": "gpt-4.1", "name": "GPT-4.1"},
        {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini (Fast)"},
        {"id": "gpt-5", "name": "GPT-5"},
        {"id": "gpt-5-mini", "name": "GPT-5 Mini"},
    ]

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY")
        self._client: Optional[openai.AsyncOpenAI] = None

    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def client(self) -> openai.AsyncOpenAI:
        """Lazily create and reuse a single async client."""
        if self._client is None:
            self._client = openai.AsyncOpenAI(api_key=self._api_key, timeout=60.0)
        return self._client

    async def _call_llm(
        self,
        message: str,
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Make a single OpenAI call and return parsed JSON or error dict."""
        messages = _build_messages(message, history)

        # GPT-5+ uses max_completion_tokens and only supports temperature=1
        is_gpt5 = model.startswith("gpt-5")
        extra: Dict[str, Any] = (
            {"max_completion_tokens": 4000}
            if is_gpt5
            else {"max_tokens": 4000, "temperature": 0.7}
        )

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                **extra,
            )
        except openai.APIError as exc:
            logger.error("OpenAI API error (%s): %s", model, exc)
            return _error_response("OpenAI Error", str(exc))

        content = (response.choices[0].message.content or "").strip()
        if not content:
            logger.warning(
                "%s returned empty content (finish_reason: %s)",
                model,
                response.choices[0].finish_reason,
            )
            return _error_response(
                "Empty Response",
                "The AI returned an empty response. Please try again or switch models.",
                variant="warning",
            )
        return parse_llm_json(content)

    async def generate(
        self,
        message: str,
        model: str = "gpt-4.1",
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        result = await self._call_llm(message, model, history)

        # Refusal guard — retry with stronger nudge
        return await _retry_on_refusal(
            result, message,
            lambda msg, hist: self._call_llm(msg, model, hist),
        )


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    name = "Anthropic"
    models = [
        {"id": "claude-opus-4-6", "name": "Claude Opus 4.6"},
        {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
        {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
        {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku (Fast)"},
    ]

    def __init__(self) -> None:
        self._api_key = os.getenv("ANTHROPIC_API_KEY")
        self._client: Optional[anthropic.AsyncAnthropic] = None

    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        """Lazily create and reuse a single async client."""
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=self._api_key,
                timeout=60.0,
            )
        return self._client

    async def _call_llm(
        self,
        message: str,
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Make a single Anthropic call and return parsed JSON or error dict."""
        # Anthropic uses a separate system param — trim history independently
        prompt_bytes = len(SYSTEM_PROMPT.encode("utf-8"))
        msg_bytes = len(message.encode("utf-8"))
        trimmed = _trim_history(history, prompt_bytes, msg_bytes)

        messages: List[Dict[str, str]] = []
        for msg in trimmed:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": message})

        try:
            response = await self.client.messages.create(
                model=model,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
        except anthropic.APIError as exc:
            logger.error("Anthropic API error (%s): %s", model, exc)
            return _error_response("Anthropic Error", str(exc))

        content = response.content[0].text.strip()
        if not content:
            logger.warning("%s returned empty content", model)
            return _error_response(
                "Empty Response",
                "The AI returned an empty response. Please try again or switch models.",
                variant="warning",
            )
        return parse_llm_json(content)

    async def generate(
        self,
        message: str,
        model: str = "claude-opus-4-6",
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        result = await self._call_llm(message, model, history)

        # Refusal guard — retry with stronger nudge
        return await _retry_on_refusal(
            result, message,
            lambda msg, hist: self._call_llm(msg, model, hist),
        )


class LiteLLMProvider(LLMProvider):
    """Exploration Lab provider — OpenAI SDK pointed at the LiteLLM gateway."""

    name = "Exploration Lab"
    models = [
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini (Fast)"},
        {"id": "gpt-4.1", "name": "GPT-4.1"},
        {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini"},
        {"id": "gpt-5", "name": "GPT-5"},
        {"id": "gpt-5-nano", "name": "GPT-5 Nano (Fast)"},
        {"id": "o4-mini", "name": "o4 Mini (Reasoning)"},
        {"id": "claude-sonnet-4-5-20250929", "name": "Claude Sonnet 4.5"},
        {"id": "gpt-4o", "name": "GPT-4o"},
    ]

    BASE_URL = "https://litellm.ai-coe-test.aws.evernorthcloud.com/v1"

    def __init__(self) -> None:
        self._api_key = os.getenv("LITELLM_API_KEY")
        self._client: Optional[openai.AsyncOpenAI] = None

    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def client(self) -> openai.AsyncOpenAI:
        """Lazily create and reuse a single async client.

        Uses a custom httpx client with SSL verification disabled to
        work behind corporate proxies that inject custom CA certificates.
        """
        if self._client is None:
            self._client = openai.AsyncOpenAI(
                api_key=self._api_key,
                base_url=self.BASE_URL,
                timeout=60.0,
                http_client=httpx.AsyncClient(verify=False, timeout=60.0),
            )
        return self._client

    async def _call_llm(
        self,
        messages: List[Dict[str, str]],
        model: str,
    ) -> Dict[str, Any]:
        """Make a single LLM call and return parsed JSON or error dict."""
        # Claude models don't support response_format parameter
        is_claude = model.startswith("claude-")
        # o-series reasoning models don't support temperature and use max_completion_tokens
        is_reasoning = model.startswith("o1") or model.startswith("o3") or model.startswith("o4")

        try:
            call_params: Dict[str, Any] = {
                "model": model,
                "messages": messages,
            }

            # Reasoning models: no temperature, use max_completion_tokens
            if is_reasoning:
                call_params["max_completion_tokens"] = 4000
            else:
                call_params["temperature"] = 0.7
                call_params["max_tokens"] = 4000

            # Only add response_format for non-Claude, non-reasoning models
            if not is_claude and not is_reasoning:
                call_params["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**call_params)
        except openai.AuthenticationError as exc:
            logger.error("Exploration Lab auth error (%s): %s", model, exc)
            return _error_response(
                "Authentication Error",
                "Your Exploration Lab API key is invalid or expired. Please check LITELLM_API_KEY.",
            )
        except openai.PermissionDeniedError as exc:
            logger.error("Exploration Lab 403 (%s): %s", model, exc)
            return _error_response(
                "Access Denied",
                f"The model '{model}' is not available on the Exploration Lab gateway. "
                "Try a different model, or check that you're on the corporate network/VPN.",
            )
        except openai.NotFoundError as exc:
            logger.error("Exploration Lab 404 (%s): %s", model, exc)
            return _error_response(
                "Model Not Found",
                f"The model '{model}' was not found on the Exploration Lab gateway. "
                "Try a different model.",
            )
        except openai.RateLimitError as exc:
            logger.warning("Exploration Lab rate limit (%s): %s", model, exc)
            return _error_response(
                "Rate Limited",
                "Too many requests. Please wait a moment and try again.",
                variant="warning",
            )
        except openai.APIError as exc:
            logger.error("Exploration Lab API error (%s): %s", model, exc)
            return _error_response("Exploration Lab Error", str(exc))

        # Guard against gateway returning empty/null choices
        if not response.choices:
            logger.warning("Exploration Lab %s returned no choices", model)
            return _error_response(
                "Empty Response",
                "The gateway returned no choices. Please try again or switch models.",
                variant="warning",
            )

        content = (response.choices[0].message.content or "").strip()
        finish_reason = response.choices[0].finish_reason

        if not content:
            logger.warning(
                "Exploration Lab %s returned empty content (finish_reason: %s)",
                model,
                finish_reason,
            )
            return _error_response(
                "Empty Response",
                "The AI returned an empty response. Please try again or switch models.",
                variant="warning",
            )

        logger.debug("Exploration Lab %s raw (first 500 chars): %.500s", model, content)
        parsed = parse_llm_json(content)

        # Safety net: if parsed result has no text AND no a2ui components,
        # return the raw content as text so the user sees something
        has_text = bool(parsed.get("text"))
        has_components = bool((parsed.get("a2ui") or {}).get("components"))
        if not has_text and not has_components:
            logger.warning(
                "Exploration Lab %s: parsed JSON has no text/components. Raw: %.300s",
                model, content,
            )
            return {
                "text": content[:1000] if len(content) > 20 else "The AI response could not be parsed. Please try again.",
                "a2ui": {
                    "version": "1.0",
                    "components": [
                        {
                            "id": "parse-warn",
                            "type": "alert",
                            "props": {
                                "variant": "warning",
                                "title": "Response Format Issue",
                                "description": "The AI response didn't match the expected format. Showing raw output.",
                            },
                        }
                    ],
                },
            }

        return parsed

    async def generate(
        self,
        message: str,
        model: str = "gpt-4o-mini",
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        messages = _build_messages(message, history)
        result = await self._call_llm(messages, model)

        # Refusal guard — retry with stronger nudge (no history to save space)
        return await _retry_on_refusal(
            result, message,
            lambda msg, hist: self._call_llm(_build_messages(msg, hist), model),
        )


class GeminiProvider(LLMProvider):
    """Google Gemini provider."""

    name = "Google"
    models = [
        {"id": "gemini-3-pro-preview", "name": "Gemini 3 Pro"},
        {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash"},
        {"id": "gemini-2.5-pro-preview-05-06", "name": "Gemini 2.5 Pro"},
        {"id": "gemini-2.5-flash-preview-05-20", "name": "Gemini 2.5 Flash"},
    ]

    def __init__(self) -> None:
        self._api_key = os.getenv("GEMINI_API_KEY")

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def _call_llm(
        self,
        message: str,
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Make a single Gemini call and return parsed JSON or error dict."""
        import google.generativeai as genai  # optional dep — lazy import

        genai.configure(api_key=self._api_key)

        gen_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=SYSTEM_PROMPT,
        )

        # Trim history to stay within WAF budget, then convert to Gemini format
        prompt_bytes = len(SYSTEM_PROMPT.encode("utf-8"))
        msg_bytes = len(message.encode("utf-8"))
        trimmed = _trim_history(history, prompt_bytes, msg_bytes)

        chat_history = []
        for msg in trimmed:
            role = "user" if msg["role"] == "user" else "model"
            chat_history.append({"role": role, "parts": [msg["content"]]})

        generation_config = {"response_mime_type": "application/json"}

        try:
            if chat_history:
                chat = gen_model.start_chat(history=chat_history)
                response = chat.send_message(message, generation_config=generation_config)
            else:
                response = gen_model.generate_content(message, generation_config=generation_config)
        except Exception as exc:
            logger.error("Gemini API error (%s): %s", model, exc)
            return _error_response("Gemini Error", str(exc))

        content = response.text.strip()
        if not content:
            logger.warning("%s returned empty content", model)
            return _error_response(
                "Empty Response",
                "The AI returned an empty response. Please try again or switch models.",
                variant="warning",
            )
        return parse_llm_json(content)

    async def generate(
        self,
        message: str,
        model: str = "gemini-3-flash-preview",
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        result = await self._call_llm(message, model, history)

        # Refusal guard — retry with stronger nudge
        return await _retry_on_refusal(
            result, message,
            lambda msg, hist: self._call_llm(msg, model, hist),
        )


# ── Service Layer ──────────────────────────────────────────────


class LLMService:
    """Orchestrates provider selection, web search, and response generation."""

    def __init__(self) -> None:
        self.providers: Dict[str, LLMProvider] = {
            "litellm": LiteLLMProvider(),
            "openai": OpenAIProvider(),
            "anthropic": AnthropicProvider(),
            "gemini": GeminiProvider(),
        }

    def get_available_providers(self) -> List[Dict[str, Any]]:
        """Return providers that have valid API keys configured."""
        return [
            {"id": key, "name": provider.name, "models": provider.models}
            for key, provider in self.providers.items()
            if provider.is_available()
        ]

    def get_provider(self, provider_id: str) -> Optional[LLMProvider]:
        """Get a specific provider by ID (only if available)."""
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

        # ── Web search augmentation ──────────────────────────
        augmented_message = message
        search_metadata = None

        if should_search(message):
            # Rewrite conversational prompt → optimised search query.
            # LLM-based first; fall back to rule-based.
            search_query = await llm_rewrite_query(
                message,
                location=location_label,
                history=history,
            )
            if not search_query:
                search_query = rewrite_search_query(message, location=location_label)

            if web_search.is_available():
                logger.info('Search: "%s"  ← "%s"', search_query[:100], message[:60])

                try:
                    search_results = await web_search.search(search_query)
                    context = web_search.format_for_context(search_results)

                    if context:
                        augmented_message = f"{context}\n\nUser question: {message}"
                        image_count = len(search_results.get("images", []))
                        logger.info(
                            "Web search complete — %d results, %d images",
                            len(search_results.get("results", [])),
                            image_count,
                        )
                        search_metadata = {
                            "searched": True,
                            "success": True,
                            "results_count": len(search_results.get("results", [])),
                            "images_count": image_count,
                            "query": search_query,
                        }
                    else:
                        error_type = search_results.get("error", "unknown")
                        logger.warning("Web search failed (%s), continuing without results", error_type)
                        search_metadata = {
                            "searched": True,
                            "success": False,
                            "error": error_type,
                            "query": search_query,
                        }
                except Exception as exc:
                    logger.warning("Web search error (continuing): %s", exc)
                    search_metadata = {
                        "searched": True,
                        "success": False,
                        "error": "exception",
                        "query": search_query,
                    }
            else:
                logger.info("Web search not configured — using AI knowledge only")
                search_metadata = {"searched": False, "reason": "not_configured"}

        # Prepend location context
        if location_context:
            augmented_message = f"{location_context}{augmented_message}"

        # ── LLM generation ───────────────────────────────────
        response = await provider.generate(augmented_message, model, history)

        # Attach metadata for frontend thinking steps / debugging
        if search_metadata:
            response["_search"] = search_metadata
        if user_location:
            response["_location"] = True

        return response


# ── Module-level singleton ─────────────────────────────────────

llm_service = LLMService()
