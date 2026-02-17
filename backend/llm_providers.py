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
    classify_style,
    get_component_priority,
    get_system_prompt,
)

logger = logging.getLogger(__name__)


# ── Utilities ──────────────────────────────────────────────────


def _build_messages(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    max_body_bytes: int = 7200,
    system_prompt: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Build an OpenAI-style messages array with smart history truncation.

    The enterprise WAF rejects request bodies > 8 KB.  We budget
    ``max_body_bytes`` for total message *content* (system + history +
    user) leaving ~800 bytes for the JSON envelope / model params.

    History is trimmed **oldest-first** so the most recent turns are
    always preserved.

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
        content_style: str = "auto",
    ) -> Dict[str, Any]:
        """Generate a response using the specified provider and model.

        ``content_style`` controls the system prompt and component
        hierarchy.  Use ``"auto"`` (default) to classify automatically,
        or pass a specific style ID (``"analytical"``, ``"content"``,
        ``"comparison"``, ``"howto"``, ``"quick"``).
        """
        from tools import web_search, should_search, rewrite_search_query, llm_rewrite_query

        provider = self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider '{provider_id}' is not available")

        # ── Content style classification ─────────────────────
        if content_style == "auto":
            style_id = classify_style(message)
            logger.info("Auto-classified content style: '%s' for: %.60s", style_id, message)
        else:
            style_id = content_style

        system_prompt = get_system_prompt(style_id)
        component_priority = get_component_priority(style_id)

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
        response = await provider.generate(
            augmented_message, model, history, system_prompt=system_prompt,
        )

        # Enforce style-specific visual hierarchy
        response = _enforce_visual_hierarchy(response, component_priority)

        # Attach metadata for frontend thinking steps / debugging
        if search_metadata:
            response["_search"] = search_metadata
        if user_location:
            response["_location"] = True
        response["_style"] = style_id

        return response


# ── Module-level singleton ─────────────────────────────────────

llm_service = LLMService()
