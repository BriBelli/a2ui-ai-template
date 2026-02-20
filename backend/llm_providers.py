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
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

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
            self._client = openai.AsyncOpenAI(
                api_key=self._api_key, timeout=60.0, max_retries=0,
            )
        return self._client

    async def _call_llm(
        self,
        message: str,
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make a single OpenAI call and return parsed JSON or error dict."""
        import time as _time

        messages = _build_messages(message, history, system_prompt=system_prompt)

        total_chars = sum(len(m.get("content", "")) for m in messages)
        logger.info(
            "  [OpenAI] %s  |  %d messages  |  %d chars (~%d tokens)  |  timeout=60s",
            model, len(messages), total_chars, total_chars // 4,
        )

        # GPT-5+ uses max_completion_tokens and only supports temperature=1
        is_gpt5 = model.startswith("gpt-5")
        extra: Dict[str, Any] = (
            {"max_completion_tokens": 4000}
            if is_gpt5
            else {"max_tokens": 4000, "temperature": 0.7}
        )

        t0 = _time.monotonic()
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                **extra,
            )
        except openai.APITimeoutError:
            elapsed = _time.monotonic() - t0
            logger.error(
                "  [OpenAI] TIMEOUT after %.1fs  |  %s  |  %d chars input",
                elapsed, model, total_chars,
            )
            return _error_response(
                "Request Timeout",
                "The model took too long to respond. Try again or switch to a faster model.",
                variant="warning",
            )
        except openai.APIError as exc:
            elapsed = _time.monotonic() - t0
            logger.error(
                "  [OpenAI] ERROR after %.1fs  |  %s  |  %s",
                elapsed, model, exc,
            )
            return _error_response(
                "Something Went Wrong",
                "The AI service returned an error. Please try again in a moment.",
            )

        elapsed = _time.monotonic() - t0
        usage = response.usage
        logger.info(
            "  [OpenAI] OK %.1fs  |  %s  |  in=%s  out=%s  total=%s tokens",
            elapsed, model,
            usage.prompt_tokens if usage else "?",
            usage.completion_tokens if usage else "?",
            usage.total_tokens if usage else "?",
        )

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
                max_retries=0,
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
        except anthropic.APITimeoutError:
            logger.error("Anthropic timeout (%s)", model)
            return _error_response(
                "Request Timeout",
                "The model took too long to respond. Try again or switch to a faster model.",
                variant="warning",
            )
        except anthropic.APIError as exc:
            logger.error("Anthropic API error (%s): %s", model, exc)
            return _error_response(
                "Something Went Wrong",
                "The AI service returned an error. Please try again in a moment.",
            )

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
                max_retries=0,
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
        except openai.APITimeoutError:
            logger.error("Exploration Lab timeout (%s)", model)
            return _error_response(
                "Request Timeout",
                "The model took too long to respond. Try again or switch to a faster model.",
                variant="warning",
            )
        except openai.APIError as exc:
            logger.error("Exploration Lab API error (%s): %s", model, exc)
            return _error_response(
                "Something Went Wrong",
                "The AI service returned an error. Please try again in a moment.",
            )

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

_ANALYZER_SYSTEM = (
    "You are an intent analyzer for an AI UI system. "
    "Given a user query, decide:\n"
    "1. The best content presentation style\n"
    "2. Whether real-time web search is needed (current events, prices, weather, live data)\n"
    "3. Whether the user's geographic location is relevant\n"
    "4. If search is needed, an optimized search query\n"
    "5. Whether any available data sources should be queried, and if so which endpoints/questions to use\n"
    "Respond with ONLY a valid JSON object. No markdown, no explanation."
)

_ANALYZER_PROMPT_TEMPLATE = (
    "Content styles:\n{descriptions}\n\n"
    "{data_sources_section}"
    "{context_section}"
    "User query: {query}\n\n"
    'Reply with JSON: {{"style":"<style_id>","search":<true|false>,"location":<true|false>,'
    '"search_query":"<optimized query or empty>",'
    '"data_sources":[{{"source":"<source_id>","endpoint":"<path or question>","params":{{}}}}]}}\n'
    "If no data sources are relevant, return an empty array for data_sources."
)

_ANALYZER_MODELS: List[tuple] = [
    ("openai", "gpt-4.1-mini"),
    ("litellm", "gpt-4o-mini"),
    ("anthropic", "claude-haiku-4-5-20251001"),
    ("gemini", "gemini-2.5-flash-preview-05-20"),
]

# ── Tool Configuration (env-level overrides) ──────────────────
#
# Each tool can be globally locked via an environment variable.
# True  = enabled (default for most tools)
# False = globally disabled — user settings are ignored
#
# Resolution order: Env (locked) > User setting > Default

def _env_bool(key: str, default: bool = True) -> Optional[bool]:
    """Read an env var as a tri-state: True, False, or None (unset)."""
    val = os.getenv(key)
    if val is None:
        return None
    return val.lower() in ("1", "true", "yes", "on")

TOOL_WEB_SEARCH_ENV: Optional[bool] = _env_bool("A2UI_TOOL_WEB_SEARCH")
TOOL_GEOLOCATION_ENV: Optional[bool] = _env_bool("A2UI_TOOL_GEOLOCATION")
TOOL_HISTORY_ENV: Optional[bool] = _env_bool("A2UI_TOOL_HISTORY")
TOOL_AI_CLASSIFIER_ENV: Optional[bool] = _env_bool("A2UI_TOOL_AI_CLASSIFIER")
TOOL_DATA_SOURCES_ENV: Optional[bool] = _env_bool("A2UI_TOOL_DATA_SOURCES")


def resolve_tool(env_override: Optional[bool], user_setting: bool, default: bool = True) -> bool:
    """Resolve a tool's effective state: env override > user setting > default."""
    if env_override is not None:
        return env_override
    return user_setting


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

    @staticmethod
    def get_tool_states() -> List[Dict[str, Any]]:
        """Return the current state of all configurable tools.

        Each tool reports:
        - id: machine identifier
        - name: human-readable label
        - description: what the tool does
        - default: default enabled state
        - env_override: value from environment (None if unset)
        - locked: True if the env variable forces a specific state
        """
        from tools import web_search as _ws
        from data_sources import get_all_sources as _get_ds

        ds_available = any(s.is_available() for s in _get_ds())
        tools = [
            {
                "id": "web_search",
                "name": "Web Search",
                "description": "Search the web for current information",
                "default": True,
                "env_override": TOOL_WEB_SEARCH_ENV,
                "locked": TOOL_WEB_SEARCH_ENV is not None,
                "available": _ws.is_available(),
            },
            {
                "id": "geolocation",
                "name": "Geolocation",
                "description": "Use device location for local context",
                "default": True,
                "env_override": TOOL_GEOLOCATION_ENV,
                "locked": TOOL_GEOLOCATION_ENV is not None,
            },
            {
                "id": "history",
                "name": "Conversation History",
                "description": "Include previous messages for context",
                "default": True,
                "env_override": TOOL_HISTORY_ENV,
                "locked": TOOL_HISTORY_ENV is not None,
            },
            {
                "id": "ai_classifier",
                "name": "AI Style Classifier",
                "description": "Use AI to auto-detect the best content style",
                "default": True,
                "env_override": TOOL_AI_CLASSIFIER_ENV,
                "locked": TOOL_AI_CLASSIFIER_ENV is not None,
            },
            {
                "id": "data_sources",
                "name": "Data Sources",
                "description": "Query configured external APIs and databases",
                "default": True,
                "env_override": TOOL_DATA_SOURCES_ENV,
                "locked": TOOL_DATA_SOURCES_ENV is not None,
                "available": ds_available,
            },
        ]
        return tools

    async def _analyze_intent(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze user intent with a fast LLM to decide tools and style.

        This is the FIRST step in the pipeline — it decides everything:
        - Content style
        - Whether web search is needed
        - Whether geolocation is relevant
        - Optimized search query (if search needed)

        Returns a dict like:
            {"style": "content", "search": True, "location": False, "search_query": "..."}
        or ``None`` on failure (caller falls back to regex).
        """
        from data_sources import get_analyzer_context

        context_parts: List[str] = []

        if history:
            recent = history[-4:]
            history_summary = " | ".join(
                f"{m['role']}: {m['content'][:80]}" for m in recent
            )
            context_parts.append(f"Conversation context: {history_summary}")

        context_section = ""
        if context_parts:
            context_section = "\n".join(context_parts) + "\n\n"

        ds_context = get_analyzer_context()
        data_sources_section = f"{ds_context}\n\n" if ds_context else ""

        prompt = _ANALYZER_PROMPT_TEMPLATE.format(
            descriptions=STYLE_DESCRIPTIONS,
            data_sources_section=data_sources_section,
            context_section=context_section,
            query=message[:500],
        )

        logger.info("── ANALYZE ──  prompt:\n%s", prompt)

        for provider_id, model_id in _ANALYZER_MODELS:
            provider = self.providers.get(provider_id)
            if not provider or not provider.is_available():
                continue

            try:
                if provider_id in ("openai", "litellm"):
                    resp = await provider.client.chat.completions.create(
                        model=model_id,
                        messages=[
                            {"role": "system", "content": _ANALYZER_SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=300,
                        temperature=0,
                    )
                    text = (resp.choices[0].message.content or "").strip()

                elif provider_id == "anthropic":
                    resp = await provider.client.messages.create(
                        model=model_id,
                        max_tokens=300,
                        system=_ANALYZER_SYSTEM,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    text = resp.content[0].text.strip()

                elif provider_id == "gemini":
                    import google.generativeai as genai
                    genai.configure(api_key=provider._api_key)
                    gen_model = genai.GenerativeModel(
                        model_name=model_id,
                        system_instruction=_ANALYZER_SYSTEM,
                    )
                    resp = gen_model.generate_content(prompt)
                    text = resp.text.strip()
                else:
                    continue

                # Strip markdown fences if the LLM wraps JSON in ```
                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\s*", "", text)
                    text = re.sub(r"\s*```$", "", text)

                result = json.loads(text)

                style = result.get("style", "").lower().strip()
                if style not in VALID_STYLE_IDS:
                    logger.warning(
                        "Analyzer returned invalid style '%s' via %s/%s",
                        style, provider_id, model_id,
                    )
                    continue

                ds_queries = result.get("data_sources") or []
                if not isinstance(ds_queries, list):
                    ds_queries = []

                analysis = {
                    "style": style,
                    "search": bool(result.get("search", False)),
                    "location": bool(result.get("location", False)),
                    "search_query": str(result.get("search_query", "")),
                    "data_sources": ds_queries,
                }

                logger.info(
                    "── ANALYZE OK ──  %s via %s/%s  |  style=%s  search=%s  location=%s  query='%s'  data_sources=%d",
                    message[:50], provider_id, model_id,
                    analysis["style"], analysis["search"],
                    analysis["location"], analysis["search_query"][:60],
                    len(ds_queries),
                )
                return analysis

            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning(
                    "Analyzer JSON parse failed (%s/%s): %s — raw: %.100s",
                    provider_id, model_id, exc, locals().get("text", "?"),
                )
                continue
            except Exception as exc:
                logger.warning(
                    "Analyzer failed (%s/%s): %s",
                    provider_id, model_id, exc,
                )
                continue

        return None

    async def generate_stream(
        self,
        message: str,
        provider_id: str,
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
        user_location: Optional[Dict[str, Any]] = None,
        content_style: str = "auto",
        performance_mode: str = "auto",
        enable_web_search: bool = True,
        enable_geolocation: bool = True,
        enable_data_sources: bool = True,
        data_context: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Async generator that yields SSE events during response generation.

        Events emitted:
        - step  (id, status:start|done, label, detail?)  — pipeline progress
        - complete  (full response dict)                  — final result
        - error  (message)                                — failure

        Pipeline order (AI-first):
        0. Resolve tool states (env override > user setting)
        1. AI intent analysis (decides style + which tools to activate)
        2. Location context (only if AI said yes AND tool enabled)
        3. Web search (only if AI said yes AND tool enabled)
        4. LLM generation (with style-specific system prompt)
        5. Post-processing (hierarchy, metadata, images)

        When AI analyzer is unavailable, regex fallbacks decide tools.
        """
        from tools import web_search, should_search, rewrite_search_query

        provider = self.get_provider(provider_id)
        if not provider:
            yield {"event": "error", "data": {"message": f"Provider '{provider_id}' is not available"}}
            return

        # ── Step 0: Resolve tool states (env > user) ──────────
        web_search_allowed = resolve_tool(TOOL_WEB_SEARCH_ENV, enable_web_search)
        geolocation_allowed = resolve_tool(TOOL_GEOLOCATION_ENV, enable_geolocation)
        history_active = resolve_tool(TOOL_HISTORY_ENV, history is not None and len(history) > 0)
        classifier_active = resolve_tool(TOOL_AI_CLASSIFIER_ENV, True)
        data_sources_allowed = resolve_tool(TOOL_DATA_SOURCES_ENV, enable_data_sources)

        effective_history = history if history_active else None

        logger.info(
            "══ GENERATE START ══  provider=%s  model=%s  style=%s  perf=%s",
            provider_id, model, content_style, performance_mode,
        )
        logger.info("User message: %s", message[:200])
        logger.info(
            "Tool gates: web_search=%s  geolocation=%s  history=%s  ai_analyzer=%s  data_sources=%s",
            web_search_allowed, geolocation_allowed, history_active, classifier_active, data_sources_allowed,
        )
        if effective_history:
            logger.info("History: %d messages", len(effective_history))

        perf = PERFORMANCE_MODES.get(performance_mode, PERFORMANCE_MODES["auto"])
        max_body_bytes: Optional[int] = WAF_MAX_BODY_BYTES

        yield {"event": "step", "data": {
            "id": "tools", "status": "done",
            "label": "Tools configured",
            "detail": f"search={web_search_allowed} geo={geolocation_allowed} history={history_active} ai={classifier_active} data={data_sources_allowed}",
        }}

        # ── Step 1: AI Intent Analysis (FIRST) ────────────────
        #
        # The AI analyzer decides EVERYTHING in one fast call:
        #   - Content style
        #   - Whether web search is needed
        #   - Whether geolocation is relevant
        #   - Optimized search query
        #
        # Tool gates (env/user) are applied AFTER AI decides.
        # If user disabled search, AI's "search=true" is overridden.
        #
        # Regex fallback only fires if AI is unavailable or fails.

        ai_wants_search = False
        ai_wants_location = False
        ai_search_query = ""
        ai_data_queries: List[Dict[str, Any]] = []
        style_id = DEFAULT_STYLE

        yield {"event": "step", "data": {"id": "analyzer", "status": "start", "label": "Analyzing intent"}}

        if content_style != "auto":
            # User explicitly chose a style — skip AI for style
            style_id = content_style
            logger.info("── ANALYZE ──  explicit style from user: '%s'", style_id)
            # Still run AI to decide tools (search/location)
            if classifier_active:
                analysis = await self._analyze_intent(message, history=effective_history)
                if analysis:
                    ai_wants_search = analysis["search"]
                    ai_wants_location = analysis["location"]
                    ai_search_query = analysis["search_query"]
                    ai_data_queries = analysis.get("data_sources") or []
                    logger.info(
                        "── ANALYZE ──  tools: search=%s  location=%s  query='%s'  data_sources=%d",
                        ai_wants_search, ai_wants_location, ai_search_query[:60], len(ai_data_queries),
                    )
                else:
                    logger.warning("── ANALYZE ──  AI failed, falling back to regex for tool decisions")
                    ai_wants_search = should_search(message)
                    ai_wants_location = self._regex_needs_location(message)
            else:
                logger.info("── ANALYZE ──  AI disabled, using regex fallback for tools")
                ai_wants_search = should_search(message)
                ai_wants_location = self._regex_needs_location(message)

        elif classifier_active:
            # Auto mode — AI decides everything
            analysis = await self._analyze_intent(message, history=effective_history)
            if analysis:
                style_id = analysis["style"]
                ai_wants_search = analysis["search"]
                ai_wants_location = analysis["location"]
                ai_search_query = analysis["search_query"]
                ai_data_queries = analysis.get("data_sources") or []
                logger.info(
                    "── ANALYZE OK ──  style=%s  search=%s  location=%s  query='%s'  data_sources=%d",
                    style_id, ai_wants_search, ai_wants_location, ai_search_query[:60], len(ai_data_queries),
                )
            else:
                style_id = DEFAULT_STYLE
                ai_wants_search = should_search(message)
                ai_wants_location = self._regex_needs_location(message)
                logger.warning(
                    "── ANALYZE ──  AI failed → regex fallback: style=%s  search=%s  location=%s",
                    style_id, ai_wants_search, ai_wants_location,
                )
        else:
            # AI disabled entirely — full regex fallback
            from content_styles import classify_style
            style_id = classify_style(message)
            ai_wants_search = should_search(message)
            ai_wants_location = self._regex_needs_location(message)
            logger.info(
                "── ANALYZE ──  AI disabled → regex: style=%s  search=%s  location=%s",
                style_id, ai_wants_search, ai_wants_location,
            )

        # Apply tool gates: AI decision AND user/env permission
        do_search = ai_wants_search and web_search_allowed
        do_location = ai_wants_location and geolocation_allowed

        logger.info(
            "── TOOLS ──  search: ai=%s gate=%s → %s  |  location: ai=%s gate=%s → %s",
            ai_wants_search, web_search_allowed, do_search,
            ai_wants_location, geolocation_allowed, do_location,
        )

        # ── Budget / performance style overrides ───────────────
        # Only touch style when the user left it on "auto".
        # Explicit user-chosen styles are NEVER overridden.
        if content_style == "auto" and style_id != "quick":
            if performance_mode == "optimized":
                # Optimized → always quick for minimal tokens/cost
                logger.info("Optimized mode → downgrading %s → quick", style_id)
                style_id = "quick"

            elif performance_mode == "auto" and max_body_bytes is not None:
                # Auto + WAF budget → downgrade at 75% threshold
                style_bytes = len(get_system_prompt(style_id).encode("utf-8"))
                if style_bytes > max_body_bytes * 0.75:
                    for fallback in ("content", "quick"):
                        fb_bytes = len(get_system_prompt(fallback).encode("utf-8"))
                        if fb_bytes <= max_body_bytes * 0.75:
                            logger.info(
                                "Budget-aware downgrade: %s(%dB) → %s(%dB), budget=%d @75%%",
                                style_id, style_bytes, fallback, fb_bytes, max_body_bytes,
                            )
                            style_id = fallback
                            break

        yield {"event": "step", "data": {
            "id": "analyzer", "status": "done",
            "label": "Intent analyzed",
            "detail": f"style={style_id} search={do_search} location={do_location}",
            "result": {
                "style": style_id,
                "search": do_search,
                "location": do_location,
                "query": ai_search_query,
            },
        }}

        # ── Step 2: Location context ──────────────────────────
        location_context = ""
        location_label = ""
        if do_location and user_location:
            location_label = user_location.get("label", "")
            lat = user_location.get("lat")
            lng = user_location.get("lng")
            if location_label:
                location_context = f"[User Location: {location_label} ({lat}, {lng})]\n"
            elif lat and lng:
                location_context = f"[User Location: {lat}, {lng}]\n"
            logger.info("── LOCATION ──  %s", location_label or f"{lat},{lng}")
        elif ai_wants_location and not geolocation_allowed:
            logger.info("── LOCATION ──  AI requested but tool disabled")
        elif ai_wants_location and not user_location:
            logger.info("── LOCATION ──  AI requested but no location data provided")

        # ── Step 3: Web search ────────────────────────────────
        augmented_message = message
        search_metadata: Optional[Dict[str, Any]] = None
        search_results_raw: Optional[Dict[str, Any]] = None
        search_images: List[str] = []

        if do_search:
            search_query = ai_search_query or rewrite_search_query(
                message, location=location_label,
            )
            yield {"event": "step", "data": {
                "id": "search", "status": "start",
                "label": "Searching the web",
                "detail": search_query[:80],
            }}

            if web_search.is_available():
                logger.info(
                    "── SEARCH ──  query: \"%s\"  (original: \"%s\")",
                    search_query[:100], message[:60],
                )
                try:
                    search_results_raw = await web_search.search(search_query)
                    context = web_search.format_for_context(search_results_raw)

                    if context:
                        augmented_message = f"{context}\n\nUser question: {message}"
                        search_images = search_results_raw.get("images", [])[:6]
                        logger.info(
                            "── SEARCH OK ──  %d results, %d images, answer=%s",
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
                        yield {"event": "step", "data": {
                            "id": "search", "status": "done",
                            "label": "Search complete",
                            "detail": f"{search_metadata['results_count']} results",
                        }}
                    else:
                        error_type = search_results_raw.get("error", "unknown")
                        logger.warning("── SEARCH FAILED ── (%s)", error_type)
                        search_metadata = {
                            "searched": True,
                            "success": False,
                            "error": error_type,
                            "query": search_query,
                        }
                        yield {"event": "step", "data": {"id": "search", "status": "done", "label": "Search returned no results"}}
                except Exception as exc:
                    logger.warning("── SEARCH ERROR ── %s", exc)
                    search_metadata = {
                        "searched": True,
                        "success": False,
                        "error": "exception",
                        "query": search_query,
                    }
                    yield {"event": "step", "data": {"id": "search", "status": "done", "label": "Search failed"}}
            else:
                logger.info("── SEARCH ──  not configured (no API key)")
                search_metadata = {"searched": False, "reason": "not_configured"}
                yield {"event": "step", "data": {"id": "search", "status": "done", "label": "Search unavailable"}}
        elif ai_wants_search and not web_search_allowed:
            logger.info("── SEARCH ──  AI requested but tool disabled by user/env")
        else:
            logger.info("── SEARCH ──  not needed (AI decided)")

        # ── Step 3.5: Data source queries ─────────────────────
        from data_sources import (
            query_sources,
            format_results_for_context,
            get_rules_context,
        )

        ds_context = ""
        ds_metadata: Optional[Dict[str, Any]] = None

        # Passive injection: data_context provided in request body
        if data_context:
            passive_blocks: List[str] = []
            for dc in data_context:
                label = dc.get("label") or dc.get("source") or "External Data"
                import json as _json
                serialized = _json.dumps(dc.get("data", {}), default=str, ensure_ascii=False)
                if len(serialized) > 12_000:
                    serialized = serialized[:12_000] + "\n... (truncated)"
                passive_blocks.append(f"[Data Source: {label}]\n{serialized}")
            ds_context = "\n".join(passive_blocks)
            ds_metadata = {"passive": True, "sources": len(data_context)}
            logger.info(
                "── DATA SOURCES ──  passive injection: %d sources, %d chars",
                len(data_context), len(ds_context),
            )

        # Active queries: AI-decided data source queries
        elif ai_data_queries and data_sources_allowed:
            yield {"event": "step", "data": {
                "id": "data_sources", "status": "start",
                "label": "Querying data sources",
                "detail": f"{len(ai_data_queries)} queries",
            }}

            results = await query_sources(ai_data_queries)
            ds_context = format_results_for_context(results)
            successful = [r for r in results if r.get("success")]
            failed = [r for r in results if not r.get("success")]

            ds_metadata = {
                "active": True,
                "queries": len(ai_data_queries),
                "successful": len(successful),
                "failed": len(failed),
            }

            logger.info(
                "── DATA SOURCES OK ──  %d/%d queries succeeded, context=%d chars",
                len(successful), len(ai_data_queries), len(ds_context),
            )
            for r in successful:
                logger.info(
                    "  source[%s]: %d records",
                    r.get("_source_id", "?"), r.get("record_count", 0),
                )

            yield {"event": "step", "data": {
                "id": "data_sources", "status": "done",
                "label": f"Data received ({len(successful)} sources)",
                "detail": f"{sum(r.get('record_count', 0) for r in successful)} records",
            }}

        elif ai_data_queries and not data_sources_allowed:
            logger.info("── DATA SOURCES ──  AI requested but tool disabled by user/env")
        else:
            logger.info("── DATA SOURCES ──  not needed")

        if ds_context:
            augmented_message = f"{ds_context}\n\n{augmented_message}"

        # Data source rules (injected into system prompt context)
        ds_rules = get_rules_context()

        # ── Step 3b: Style prompt setup ───────────────────────
        system_prompt = get_system_prompt(style_id)
        component_priority = get_component_priority(style_id)
        logger.info(
            "── STYLE ──  %s  |  prompt=%dB  |  priority=%s",
            style_id,
            len(system_prompt.encode("utf-8")),
            list(component_priority)[:5],
        )

        if max_body_bytes is not None and performance_mode == "auto":
            prompt_bytes = len(system_prompt.encode("utf-8"))
            if prompt_bytes > max_body_bytes * _AUTO_DEGRADE_THRESHOLD:
                max_body_bytes = max(max_body_bytes, prompt_bytes + 1500)
                logger.info(
                    "Auto-degraded: prompt %dB exceeds %d%% of WAF budget → %d",
                    prompt_bytes, int(_AUTO_DEGRADE_THRESHOLD * 100), max_body_bytes,
                )

        if ds_rules:
            system_prompt = f"{system_prompt}\n\n{ds_rules}"

        if location_context:
            augmented_message = f"{location_context}{augmented_message}"

        # ── Step 4: LLM generation ────────────────────────────
        yield {"event": "step", "data": {
            "id": "llm", "status": "start",
            "label": "Generating response",
            "detail": f"{provider_id}/{model}",
        }}
        logger.info(
            "── GENERATE ──  sending to %s/%s  (%d chars)",
            provider_id, model, len(augmented_message),
        )
        llm_t0 = time.time()
        response = await provider.generate(
            augmented_message, model, effective_history, system_prompt=system_prompt,
        )
        llm_elapsed = time.time() - llm_t0
        logger.info(
            "── RESPONSE ──  text=%d chars  a2ui=%s  components=%d  elapsed=%.1fs",
            len(response.get("text", "")),
            bool(response.get("a2ui")),
            len(response.get("a2ui", {}).get("components", [])) if response.get("a2ui") else 0,
            llm_elapsed,
        )
        yield {"event": "step", "data": {
            "id": "llm", "status": "done",
            "label": "Response generated",
            "detail": f"{llm_elapsed:.1f}s",
        }}

        # ── Step 5: Post-processing ──────────────────────────
        response = _enforce_visual_hierarchy(response, component_priority)

        if search_metadata:
            response["_search"] = search_metadata
        if user_location and do_location:
            response["_location"] = True

        if search_images and _wants_images(message):
            response["_images"] = search_images
            logger.info("── IMAGES ──  attached %d images (query is visual)", len(search_images))
        elif search_images:
            logger.info("── IMAGES ──  suppressed %d images (query not visual)", len(search_images))

        if ds_metadata:
            response["_data_sources"] = ds_metadata

        response["_style"] = style_id
        response["_performance"] = performance_mode

        logger.info(
            "══ GENERATE DONE ══  style=%s  keys=%s",
            style_id, list(response.keys()),
        )
        yield {"event": "complete", "data": response}

    async def generate(
        self,
        message: str,
        provider_id: str,
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
        user_location: Optional[Dict[str, Any]] = None,
        content_style: str = "auto",
        performance_mode: str = "auto",
        enable_web_search: bool = True,
        enable_geolocation: bool = True,
        enable_data_sources: bool = True,
        data_context: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Non-streaming wrapper — collects the final result from generate_stream."""
        result: Dict[str, Any] = {}
        async for event in self.generate_stream(
            message, provider_id, model,
            history=history,
            user_location=user_location,
            content_style=content_style,
            performance_mode=performance_mode,
            enable_web_search=enable_web_search,
            enable_geolocation=enable_geolocation,
            enable_data_sources=enable_data_sources,
            data_context=data_context,
        ):
            if event["event"] == "complete":
                result = event["data"]
            elif event["event"] == "error":
                raise ValueError(event["data"].get("message", "Unknown error"))
        return result or {"text": "No response generated"}

    @staticmethod
    def _regex_needs_location(message: str) -> bool:
        """Regex fallback for location relevance (used when AI is unavailable)."""
        m = message.lower()
        indicators = [
            "weather", "forecast", "temperature", "near me", "nearby",
            "local", "restaurant", "food", "store", "shop", "event",
            "concert", "traffic", "commute", "directions", "open now",
            "closest",
        ]
        return any(i in m for i in indicators)


# ── Module-level singleton ─────────────────────────────────────

llm_service = LLMService()
