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
from typing import Any, Dict, List, Optional

import httpx
import openai
import anthropic

from content_styles import (
    DEFAULT_STYLE,
    STYLE_DESCRIPTIONS,
    VALID_STYLE_IDS,
    get_component_priority,
    get_system_prompt,
)

logger = logging.getLogger(__name__)


# ── Utilities ──────────────────────────────────────────────────


def _build_messages(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    max_body_bytes: Optional[int] = None,
    system_prompt: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Build an OpenAI-style messages array with optional history truncation.

    When ``max_body_bytes`` is set, history is trimmed oldest-first to
    keep total content under that byte budget.  This is useful behind
    enterprise WAFs that reject large request bodies.

    ``None`` (default) = unlimited, no trimming.

    ``system_prompt`` should be the fully-composed prompt (with date)
    from :func:`content_styles.get_system_prompt`.
    """
    if system_prompt is None:
        system_prompt = get_system_prompt("content")

    prompt_bytes = len(system_prompt.encode("utf-8"))
    msg_bytes = len(message.encode("utf-8"))
    trimmed = _trim_history(history, prompt_bytes, msg_bytes, max_body_bytes)

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(trimmed)
    messages.append({"role": "user", "content": message})
    return messages


def _trim_history(
    history: Optional[List[Dict[str, str]]],
    system_prompt_bytes: int = 0,
    message_bytes: int = 0,
    max_body_bytes: Optional[int] = None,
) -> List[Dict[str, str]]:
    """Trim history oldest-first to stay within a byte budget.

    ``None`` (default) = unlimited, all history returned as-is.
    Set a positive value to enable WAF-aware truncation
    (e.g. ``7200`` for an 8 KB WAF with ~800 B envelope).
    """
    if not history:
        return []

    if max_body_bytes is None:
        return [{"role": m["role"], "content": m["content"]} for m in history]

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
            "History trimmed: %d→%d turns (WAF limit %d B)",
            len(history),
            len(trimmed),
            max_body_bytes,
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


def _enforce_visual_hierarchy(
    result: Dict[str, Any],
    priority: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Reorder A2UI components according to a style's component priority.

    ``priority`` is an ordered list of component type names (position = rank).
    Types not in the list are placed at the end.
    """
    if priority is None:
        return result

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

    def _rank(component: Dict[str, Any]) -> int:
        ctype = component.get("type", "")
        try:
            return priority.index(ctype)
        except ValueError:
            return len(priority)

    # Stable sort by priority — preserves relative order within same type
    original_order = [c.get("type") for c in dict_components]
    dict_components.sort(key=_rank)
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

    # Strip markdown code fences (handle various fence styles)
    if content.startswith("```"):
        content = re.sub(r"^```\w*\s*", "", content)
        content = re.sub(r"\s*```\s*$", "", content)
        content = content.strip()

    # Strip BOM and zero-width characters that LLMs occasionally inject
    content = content.lstrip("\ufeff\u200b\u200c\u200d\u2060")

    # Try direct parse first (fastest path for clean JSON)
    try:
        result = json.loads(content)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Extract the outermost JSON object via brace matching (more robust
    # than the greedy regex for content with trailing prose).
    json_str = _extract_json_object(content)
    if json_str:
        try:
            result = json.loads(json_str)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse error after extraction: %s — preview: %.200s", exc, json_str[:200])

    # Fallback: regex extraction (catches nested-but-valid JSON)
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    logger.warning("Could not parse LLM JSON — preview: %.300s", content[:300])
    return {"text": content}


def _extract_json_object(text: str) -> Optional[str]:
    """Extract the outermost JSON object by counting braces.

    More reliable than a greedy regex when the LLM appends prose after
    the closing brace.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return None


# ── Content Styles ─────────────────────────────────────────────
# System prompts are now modular — see backend/content_styles/.
# The service layer classifies intent and selects the right style.


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
        system_prompt: Optional[str] = None,
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
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make a single OpenAI call and return parsed JSON or error dict."""
        messages = _build_messages(message, history, system_prompt=system_prompt)

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
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = await self._call_llm(message, model, history, system_prompt)

        # Refusal guard — retry with stronger nudge
        return await _retry_on_refusal(
            result, message,
            lambda msg, hist: self._call_llm(msg, model, hist, system_prompt),
        )


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    name = "Anthropic"
    models = [
        {"id": "claude-opus-4-6", "name": "Claude Opus 4.6"},
        {"id": "claude-sonnet-4-5-20250929", "name": "Claude Sonnet 4.5"},
        {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
        {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5 (Fast)"},
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
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make a single Anthropic call and return parsed JSON or error dict."""
        if system_prompt is None:
            system_prompt = get_system_prompt("content")

        # Anthropic uses a separate system param — trim history independently
        prompt_bytes = len(system_prompt.encode("utf-8"))
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
                system=system_prompt,
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
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = await self._call_llm(message, model, history, system_prompt)

        # Refusal guard — retry with stronger nudge
        return await _retry_on_refusal(
            result, message,
            lambda msg, hist: self._call_llm(msg, model, hist, system_prompt),
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
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        messages = _build_messages(message, history, system_prompt=system_prompt)
        result = await self._call_llm(messages, model)

        # Refusal guard — retry with stronger nudge (no history to save space)
        return await _retry_on_refusal(
            result, message,
            lambda msg, hist: self._call_llm(
                _build_messages(msg, hist, system_prompt=system_prompt), model,
            ),
        )


class GeminiProvider(LLMProvider):
    """Google Gemini provider."""

    name = "Google"
    models = [
        {"id": "gemini-3-pro-preview", "name": "Gemini 3 Pro"},
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
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make a single Gemini call and return parsed JSON or error dict."""
        import google.generativeai as genai  # optional dep — lazy import

        if system_prompt is None:
            system_prompt = get_system_prompt("content")

        genai.configure(api_key=self._api_key)

        gen_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
        )

        # Trim history to stay within WAF budget, then convert to Gemini format
        prompt_bytes = len(system_prompt.encode("utf-8"))
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
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = await self._call_llm(message, model, history, system_prompt)

        # Refusal guard — retry with stronger nudge
        return await _retry_on_refusal(
            result, message,
            lambda msg, hist: self._call_llm(msg, model, hist, system_prompt),
        )


# ── Visual Query Detection ─────────────────────────────────────

_VISUAL_QUERY_RE = re.compile(
    r"\b(?:look\s*like|looks?\s*like|appearance|what\s+does?\s+.{1,40}\s+look"
    r"|show\s+me|pictures?\s+of|photos?\s+of|images?\s+of"
    r"|what\s+(?:is|are|do|does)\s)"
    , re.IGNORECASE,
)

_NO_IMAGES_RE = re.compile(
    r"\b(?:stocks?|prices?|markets?|trading|portfolio|GDP|inflation|interest\s*rate"
    r"|weather|forecast|temperature|code|program\w*|functions?|errors?|bugs?|debug"
    r"|how\s+to|step.?by.?step|configure|install|recipe|tutorial|dashboard"
    r"|KPI|metrics?|analy)"
    , re.IGNORECASE,
)


def _wants_images(message: str) -> bool:
    """Decide whether search images add value for this query.

    Images are shown for visual/knowledge queries (what does X look like,
    tell me about Y) but suppressed for financial, weather, coding, and
    how-to queries where they add noise.
    """
    if _NO_IMAGES_RE.search(message):
        return False
    return bool(_VISUAL_QUERY_RE.search(message))


# ── LLM Classifier ─────────────────────────────────────────────

_CLASSIFIER_SYSTEM = (
    "You are a content-style classifier for a UI system. "
    "You analyze the user's intent, conversation context, and available data "
    "to decide the best presentation style. Reply with exactly one word."
)

_CLASSIFIER_PROMPT_TEMPLATE = (
    "Based on the user's intent and the data context, classify into ONE style.\n\n"
    "Available styles:\n{descriptions}\n\n"
    "{context_section}"
    "User query: {query}\n\n"
    "Reply with ONLY the style ID, nothing else."
)

_CLASSIFIER_MODELS: List[tuple] = [
    ("openai", "gpt-4.1-mini"),
    ("litellm", "gpt-4o-mini"),
    ("anthropic", "claude-haiku-4-5-20251001"),
    ("gemini", "gemini-2.5-flash-preview-05-20"),
]

# ── Performance Mode Constants ─────────────────────────────────

# Optional WAF byte limit — set A2UI_MAX_BODY_BYTES to enable.
# None = unlimited (default). Example: 7200 for an 8 KB WAF.
_raw_waf = os.getenv("A2UI_MAX_BODY_BYTES")
WAF_MAX_BODY_BYTES: Optional[int] = int(_raw_waf) if _raw_waf else None

PERFORMANCE_MODES = {
    "comprehensive": {"use_llm_classifier": True},
    "optimized": {"use_llm_classifier": False},
    "auto": {"use_llm_classifier": True},
}

_AUTO_DEGRADE_THRESHOLD = 0.75


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

    async def _classify_intent(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        search_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Classify user intent using a lightweight LLM call with full context.

        The classifier sees:
        - The user's current query
        - Recent conversation history (summarised)
        - A summary of the search response data shape (field types,
          result count, whether images/numbers/tables are present)

        Returns a valid style ID or ``None`` on failure.
        """
        # Build context section from history + search data
        context_parts: List[str] = []

        if history:
            recent = history[-4:]  # last 2 exchanges max
            history_summary = " | ".join(
                f"{m['role']}: {m['content'][:80]}" for m in recent
            )
            context_parts.append(f"Conversation history: {history_summary}")

        if search_data and search_data.get("success"):
            results = search_data.get("results", [])
            result_count = len(results)
            has_answer = bool(search_data.get("answer"))
            image_count = len(search_data.get("images", []))

            data_summary = (
                f"Search returned {result_count} results"
                f"{', with a direct answer' if has_answer else ''}"
                f"{f', {image_count} images' if image_count else ''}"
            )

            # Summarise the data shape — types of content in the results
            if results:
                snippets = [r.get("content", "")[:100] for r in results[:3]]
                data_summary += f". Sample snippets: {' // '.join(snippets)}"

            context_parts.append(f"Data context: {data_summary}")

        context_section = ""
        if context_parts:
            context_section = "\n".join(context_parts) + "\n\n"

        prompt = _CLASSIFIER_PROMPT_TEMPLATE.format(
            descriptions=STYLE_DESCRIPTIONS,
            context_section=context_section,
            query=message[:500],
        )

        logger.info("── Classifier prompt ──\n%s", prompt)

        for provider_id, model_id in _CLASSIFIER_MODELS:
            provider = self.providers.get(provider_id)
            if not provider or not provider.is_available():
                continue

            try:
                if provider_id in ("openai", "litellm"):
                    resp = await provider.client.chat.completions.create(
                        model=model_id,
                        messages=[
                            {"role": "system", "content": _CLASSIFIER_SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=10,
                        temperature=0,
                    )
                    text = (resp.choices[0].message.content or "").strip().lower()

                elif provider_id == "anthropic":
                    resp = await provider.client.messages.create(
                        model=model_id,
                        max_tokens=10,
                        system=_CLASSIFIER_SYSTEM,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    text = resp.content[0].text.strip().lower()

                elif provider_id == "gemini":
                    import google.generativeai as genai
                    genai.configure(api_key=provider._api_key)
                    gen_model = genai.GenerativeModel(
                        model_name=model_id,
                        system_instruction=_CLASSIFIER_SYSTEM,
                    )
                    resp = gen_model.generate_content(prompt)
                    text = resp.text.strip().lower()
                else:
                    continue

                # Strip surrounding quotes or punctuation the LLM may add
                text = text.strip('"\'.,!; ')

                if text in VALID_STYLE_IDS:
                    logger.info(
                        "LLM classified → '%s' via %s/%s for: %.50s",
                        text, provider_id, model_id, message,
                    )
                    return text

                logger.debug(
                    "LLM classifier returned unexpected '%s' via %s/%s",
                    text, provider_id, model_id,
                )

            except Exception as exc:
                logger.warning(
                    "LLM classifier failed (%s/%s): %s",
                    provider_id, model_id, exc,
                )
                continue

        return None

    async def generate(
        self,
        message: str,
        provider_id: str,
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
        enable_web_search: bool = False,
        user_location: Optional[Dict[str, Any]] = None,
        content_style: str = "auto",
        performance_mode: str = "auto",
    ) -> Dict[str, Any]:
        """Generate a response using the specified provider and model.

        Pipeline order:
        1. Web search (get real data first)
        2. AI classification (uses query + history + search data shape)
        3. LLM generation (with style-specific system prompt)
        4. Post-processing (hierarchy, metadata, images)
        """
        from tools import web_search, should_search, rewrite_search_query, llm_rewrite_query

        provider = self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider '{provider_id}' is not available")

        logger.info(
            "══ GENERATE START ══  provider=%s  model=%s  style=%s  perf=%s",
            provider_id, model, content_style, performance_mode,
        )
        logger.info("User message: %s", message[:200])
        if history:
            logger.info("History: %d messages", len(history))

        perf = PERFORMANCE_MODES.get(performance_mode, PERFORMANCE_MODES["auto"])
        max_body_bytes: Optional[int] = WAF_MAX_BODY_BYTES

        # ── Step 1: Location context ─────────────────────────
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
            logger.info("Location: %s", location_label or f"{lat},{lng}")

        # ── Step 2: Web search (data first) ───────────────────
        augmented_message = message
        search_metadata: Optional[Dict[str, Any]] = None
        search_results_raw: Optional[Dict[str, Any]] = None
        search_images: List[str] = []

        if should_search(message):
            search_query = await llm_rewrite_query(
                message, location=location_label, history=history,
            )
            if not search_query:
                search_query = rewrite_search_query(message, location=location_label)

            if web_search.is_available():
                logger.info("── SEARCH ──  query: \"%s\"  (original: \"%s\")", search_query[:100], message[:60])

                try:
                    search_results_raw = await web_search.search(search_query)
                    context = web_search.format_for_context(search_results_raw)

                    if context:
                        augmented_message = f"{context}\n\nUser question: {message}"
                        search_images = search_results_raw.get("images", [])[:6]
                        logger.info(
                            "── SEARCH RESULTS ──  %d results, %d images, answer=%s",
                            len(search_results_raw.get("results", [])),
                            len(search_images),
                            bool(search_results_raw.get("answer")),
                        )
                        for i, r in enumerate(search_results_raw.get("results", [])[:3]):
                            logger.info(
                                "  result[%d]: %s — %.100s",
                                i, r.get("title", "")[:50], r.get("content", "")[:100],
                            )
                        search_metadata = {
                            "searched": True,
                            "success": True,
                            "results_count": len(search_results_raw.get("results", [])),
                            "images_count": len(search_images),
                            "query": search_query,
                        }
                    else:
                        error_type = search_results_raw.get("error", "unknown")
                        logger.warning("── SEARCH FAILED ── (%s)", error_type)
                        search_metadata = {
                            "searched": True,
                            "success": False,
                            "error": error_type,
                            "query": search_query,
                        }
                except Exception as exc:
                    logger.warning("── SEARCH ERROR ── %s", exc)
                    search_metadata = {
                        "searched": True,
                        "success": False,
                        "error": "exception",
                        "query": search_query,
                    }
            else:
                logger.info("── SEARCH ──  not configured, using AI knowledge only")
                search_metadata = {"searched": False, "reason": "not_configured"}
        else:
            logger.info("── SEARCH ──  skipped (no search triggers in message)")

        # ── Step 3: AI content style classification ───────────
        #
        # The AI classifier receives the full context: user query,
        # conversation history, and the search data shape/content.
        # This lets it reason about WHAT the data looks like, not
        # just keyword-match the query.
        #
        # Regex classification is DISABLED — kept as dead code for
        # future fallback scenarios (PII/PHI, LLM unavailable, etc.)

        if content_style == "auto":
            style_id = await self._classify_intent(
                message,
                history=history,
                search_data=search_results_raw,
            )
            if style_id:
                logger.info("── CLASSIFY ──  AI chose style: '%s'", style_id)
            else:
                style_id = DEFAULT_STYLE
                logger.warning(
                    "── CLASSIFY ──  AI classification failed, using default: '%s'",
                    style_id,
                )
        else:
            style_id = content_style
            logger.info("── CLASSIFY ──  explicit style from user: '%s'", style_id)

        system_prompt = get_system_prompt(style_id)
        component_priority = get_component_priority(style_id)
        logger.info(
            "── STYLE ──  %s  |  prompt=%dB  |  priority=%s",
            style_id,
            len(system_prompt.encode("utf-8")),
            [p for p in component_priority][:5],
        )

        # ── Auto-degrade: expand WAF budget if prompt is tight ─
        if max_body_bytes is not None and performance_mode == "auto":
            prompt_bytes = len(system_prompt.encode("utf-8"))
            if prompt_bytes > max_body_bytes * _AUTO_DEGRADE_THRESHOLD:
                max_body_bytes = max(max_body_bytes, prompt_bytes + 1500)
                logger.info(
                    "Auto-degraded: prompt %dB exceeds %d%% of WAF budget → %d",
                    prompt_bytes, int(_AUTO_DEGRADE_THRESHOLD * 100), max_body_bytes,
                )

        # Prepend location context
        if location_context:
            augmented_message = f"{location_context}{augmented_message}"

        # ── Step 4: LLM generation ────────────────────────────
        logger.info("── GENERATE ──  sending to %s/%s  (%d chars)", provider_id, model, len(augmented_message))
        response = await provider.generate(
            augmented_message, model, history, system_prompt=system_prompt,
        )
        logger.info(
            "── RESPONSE ──  text=%d chars  a2ui=%s  components=%d",
            len(response.get("text", "")),
            bool(response.get("a2ui")),
            len(response.get("a2ui", {}).get("components", [])) if response.get("a2ui") else 0,
        )

        # ── Step 5: Post-processing ──────────────────────────
        response = _enforce_visual_hierarchy(response, component_priority)

        if search_metadata:
            response["_search"] = search_metadata
        if user_location:
            response["_location"] = True

        # Images: AI-driven visual relevance check
        if search_images and _wants_images(message):
            response["_images"] = search_images
            logger.info("── IMAGES ──  attached %d images (query is visual)", len(search_images))
        elif search_images:
            logger.info("── IMAGES ──  suppressed %d images (query not visual)", len(search_images))

        response["_style"] = style_id
        response["_performance"] = performance_mode

        logger.info(
            "══ GENERATE DONE ══  style=%s  keys=%s",
            style_id, list(response.keys()),
        )
        return response


# ── Module-level singleton ─────────────────────────────────────

llm_service = LLMService()
