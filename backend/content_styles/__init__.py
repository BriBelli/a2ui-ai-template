"""
A2UI Content Styles — modular prompt orchestration.

Instead of one monolithic system prompt, content styles let the system
pick the right prompt definition based on the user's intent.

Public API
----------
- ``classify_style(message)``      → style ID ("analytical", "content", …)
- ``get_system_prompt(style_id)``  → composed prompt (base + style-specific)
- ``get_component_priority(style_id)`` → ordered list of component types
- ``get_available_styles()``       → list of style metadata dicts
- ``CONTENT_STYLES``               → full registry dict

Size constraints
----------------
Each composed prompt (base + style) is validated at import time.
``DEFAULT_MAX_PROMPT_BYTES`` is the soft limit; ``ABSOLUTE_MAX_PROMPT_BYTES``
is the hard ceiling.  Both can be overridden by the caller.
"""

import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional

from ._base import BASE_RULES
from .analytical import STYLE as _analytical
from .comparison import STYLE as _comparison
from .content import STYLE as _content
from .howto import STYLE as _howto
from .quick import STYLE as _quick

logger = logging.getLogger(__name__)

# ── Registry ──────────────────────────────────────────────────

CONTENT_STYLES: Dict[str, Dict[str, Any]] = {
    s["id"]: s for s in [_analytical, _content, _comparison, _howto, _quick]
}

DEFAULT_STYLE = "content"

# ── Size constraints ──────────────────────────────────────────

DEFAULT_MAX_PROMPT_BYTES = 5000
"""Soft limit per composed prompt (base + style).  Logged as warning."""

ABSOLUTE_MAX_PROMPT_BYTES = 7200
"""Hard ceiling matching the enterprise WAF body budget."""


def _compose_prompt(style_id: str) -> str:
    """Combine base rules with a style-specific prompt."""
    style = CONTENT_STYLES[style_id]
    return BASE_RULES + "\n\n" + style["prompt"]


# Pre-compose and validate all styles at import time
_COMPOSED_PROMPTS: Dict[str, str] = {}
for _sid in CONTENT_STYLES:
    _prompt = _compose_prompt(_sid)
    _size = len(_prompt.encode("utf-8"))
    if _size > ABSOLUTE_MAX_PROMPT_BYTES:
        logger.warning(
            "Style '%s' composed prompt is %d bytes — exceeds hard limit %d",
            _sid, _size, ABSOLUTE_MAX_PROMPT_BYTES,
        )
    elif _size > DEFAULT_MAX_PROMPT_BYTES:
        logger.info(
            "Style '%s' composed prompt is %d bytes (soft limit: %d)",
            _sid, _size, DEFAULT_MAX_PROMPT_BYTES,
        )
    _COMPOSED_PROMPTS[_sid] = _prompt


# ── Public API ────────────────────────────────────────────────


def get_system_prompt(style_id: str, max_bytes: Optional[int] = None) -> str:
    """Return the full system prompt for a content style.

    Prepends today's date (matches original behavior).
    If *max_bytes* is given, the raw prompt (without date) is checked
    against that limit and a warning is logged if exceeded.
    """
    prompt = _COMPOSED_PROMPTS.get(style_id)
    if prompt is None:
        logger.warning("Unknown style '%s' — falling back to '%s'", style_id, DEFAULT_STYLE)
        prompt = _COMPOSED_PROMPTS[DEFAULT_STYLE]

    if max_bytes:
        size = len(prompt.encode("utf-8"))
        if size > max_bytes:
            logger.warning(
                "Style '%s' prompt (%d B) exceeds requested limit (%d B)",
                style_id, size, max_bytes,
            )

    today = date.today().strftime("%B %d, %Y")
    return f"Current date: {today}. All responses must be relevant to this date unless the user specifies otherwise.\n\n{prompt}"


def get_component_priority(style_id: str) -> List[str]:
    """Return the component priority array for a content style."""
    style = CONTENT_STYLES.get(style_id)
    if style is None:
        logger.warning("Unknown style '%s' — falling back to '%s'", style_id, DEFAULT_STYLE)
        style = CONTENT_STYLES[DEFAULT_STYLE]
    return style["component_priority"]


def get_available_styles() -> List[Dict[str, str]]:
    """Return metadata for all registered styles (for API / frontend)."""
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "description": s["description"],
        }
        for s in CONTENT_STYLES.values()
    ]


# ── Classifier ────────────────────────────────────────────────

# Ordered list of (compiled_regex, style_id).  First match wins,
# so more specific patterns come before broader ones.
_CLASSIFICATION_RULES = [
    # ── Financial / analytical signals (strongest) ──
    (re.compile(
        r"\b(?:stocks?|ticker|share\s*price|market\s*cap|P/?E\s*ratio|earnings|"
        r"revenue|dividends?|EPS|52.?w(?:ee)?k|nasdaq|dow\s*jones|s&p\s*500|"
        r"bull(?:ish)?|bear(?:ish)?|portfolio|IPO|ETFs?|mutual\s*funds?|bond\s*yields?"
        r")\b", re.IGNORECASE,
    ), "analytical"),
    # Well-known tickers
    (re.compile(
        r"\b(?:NVDA|AAPL|GOOGL?|MSFT|AMZN|TSLA|META|AMD|INTC|QCOM|"
        r"NFLX|BA|JPM|WMT|DIS|V|MA|UNH|JNJ|PG|HD|COST|CRM|AVGO|MU)\b",
    ), "analytical"),
    # Dollar amounts or percentage patterns
    (re.compile(r"\$[\d,.]+[BMTKbmtk]?"), "analytical"),
    # Economic / macro terms
    (re.compile(
        r"\b(?:forecast|GDP|inflation|interest\s*rate|unemployment|economic"
        r"|recession|deficit|trade\s*balance)\b", re.IGNORECASE,
    ), "analytical"),
    (re.compile(r"\b(?:KPI|dashboard|metric|analytics)\b", re.IGNORECASE), "analytical"),

    # ── Rankings with financial context → analytical ──
    (re.compile(
        r"\b(?:top\s+\d+|best\s+\d+|largest|biggest|highest|ranking)\b"
        r".*\b(?:stocks?|compan|funds?|ETFs?|banks?|tech|startups?|crypt)"
        , re.IGNORECASE,
    ), "analytical"),

    # ── Comparison signals ──
    (re.compile(r"\b(?:vs\.?|versus)\b", re.IGNORECASE), "comparison"),
    (re.compile(
        r"\b(?:compare|comparison|which\s+is\s+better|pros?\s+(?:and|&)\s+cons?"
        r"|differences?\s+between|head\s*to\s*head)\b", re.IGNORECASE,
    ), "comparison"),

    # ── How-to signals ──
    (re.compile(
        r"\b(?:how\s+(?:to|do\s+I|can\s+I)|step.?by.?step|guide\s+to|tutorial"
        r"|recipe|instructions?\s+(?:for|to)|set\s*up|install|configure|"
        r"troubleshoot)\b", re.IGNORECASE,
    ), "howto"),

    # ── Content / knowledge signals ──
    (re.compile(
        r"\b(?:what\s+(?:is|are|was|were|does?|do)|who\s+(?:is|are|was|were)"
        r"|explain|history\s+of|define|meaning\s+of|overview\s+of"
        r"|tell\s+me\s+about|describe|look\s+like|looks?\s+like"
        r"|why\s+(?:is|are|do|does|did))\b", re.IGNORECASE,
    ), "content"),

    # ── Generic rankings (non-financial) → content ──
    (re.compile(r"\b(?:top\s+\d+|best\s+\d+)\b", re.IGNORECASE), "content"),
]


def classify_style(message: str) -> str:
    """Classify a user message into a content style via regex.

    Uses rule-based pattern matching (instant, zero-cost).
    Returns a style ID from ``CONTENT_STYLES``.
    """
    msg = message.strip()

    for pattern, style_id in _CLASSIFICATION_RULES:
        if pattern.search(msg):
            return style_id

    # Fallback: short queries get "quick", longer ones get "content"
    word_count = len(msg.split())
    if word_count <= 4:
        return "quick"

    return DEFAULT_STYLE


# ── Style descriptions for LLM classifier ─────────────────────

STYLE_DESCRIPTIONS: str = "\n".join(
    f"- {s['id']}: {s['description']}"
    for s in CONTENT_STYLES.values()
)
"""One-line descriptions of every style, formatted for an LLM classification prompt."""

VALID_STYLE_IDS: frozenset = frozenset(CONTENT_STYLES.keys())
