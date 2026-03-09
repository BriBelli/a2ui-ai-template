"""
LLM Providers for A2UI

Multi-provider AI service with a unified interface:
- OpenAI  (GPT-5.1, GPT-5, GPT-4.1)
- Anthropic  (Claude Opus 4.6, Claude Sonnet 4, Claude 3.5)
- Google Gemini  (Gemini 3 Pro, Gemini 2.5)

Each provider implements the same abstract interface and returns
parsed A2UI JSON responses ready for the frontend.
"""

import asyncio
import json
import logging
import os
import re
import uuid
from abc import ABC, abstractmethod
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import openai
import anthropic

from content_styles import (
    CONTENT_STYLES,
    DEFAULT_STYLE,
    STYLE_DESCRIPTIONS,
    VALID_STYLE_IDS,
    get_component_priority,
    get_system_prompt,
)

logger = logging.getLogger(__name__)


# ── Security: Input Sanitization ──────────────────────────────

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|above|prior|system)\s+(instructions?|prompts?|rules?)", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an|my)\s+", re.I),
    re.compile(r"(system|assistant)\s*:\s*", re.I),
    re.compile(r"<<<\s*(SYSTEM|END_SYSTEM|SYSTEM_INSTRUCTIONS|END_SYSTEM_INSTRUCTIONS)\s*>>>", re.I),
    re.compile(r"\[INST\]|\[/INST\]|<\|im_start\|>|<\|im_end\|>", re.I),
    re.compile(r"repeat\s+(the\s+)?(system\s+)?(prompt|instructions?|rules?)\s+(back|above|verbatim|exactly)", re.I),
    re.compile(r"(print|output|show|reveal|display)\s+(your|the|system)\s+(prompt|instructions?|rules?|context)", re.I),
    re.compile(r"act\s+as\s+(if\s+)?(you\s+are|a|an)\s+", re.I),
    re.compile(r"pretend\s+(you\s+are|to\s+be|you're)\s+", re.I),
    re.compile(r"jailbreak|DAN\s+mode|developer\s+mode|do\s+anything\s+now", re.I),
]


def _detect_injection(text: str) -> List[str]:
    """Return list of matched injection pattern names (empty = clean)."""
    hits: List[str] = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern[:60])
    return hits


def _sanitize_for_prompt(text: str) -> str:
    """Strip characters that could break prompt delimiters."""
    text = re.sub(r"<<<\s*\w+\s*>>>", "", text)
    return text


def _sanitize_label(text: Any, max_len: int = 200) -> str:
    """Sanitize a label/tag before embedding in a prompt context block."""
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    text = re.sub(r"<<<\s*\w+\s*>>>", "", text)
    text = re.sub(r"[\n\r\x00]", " ", text)
    return text[:max_len].strip()


def _build_location_context(loc: Dict[str, Any]) -> tuple[str, str]:
    """Extract (label, context_string) from a location dict.

    Returns a (label, context) tuple where context is a ready-to-prepend
    ``[User Location: ...]`` block, or empty strings if no usable data.
    """
    label = _sanitize_label(loc.get("label", ""), max_len=100)
    lat = loc.get("lat")
    lng = loc.get("lng")
    if label:
        return label, f"[User Location: {label} ({lat}, {lng})]\n"
    if lat and lng:
        return "", f"[User Location: {lat}, {lng}]\n"
    return "", ""


# ── Pending-location store ─────────────────────────────────────
# When the analyzer decides location is needed but the frontend hasn't
# provided it, the pipeline emits a ``need_location`` SSE event and pauses
# on an asyncio.Event. The frontend POSTs the location to
# /api/provide-location/{request_id}, which sets the event and stores the
# result here so the pipeline can resume.

_LOCATION_TIMEOUT = 15  # seconds to wait for frontend to provide location


class _PendingLocation:
    """Holds an asyncio.Event + optional location dict for one request."""
    __slots__ = ("event", "location")

    def __init__(self) -> None:
        self.event = asyncio.Event()
        self.location: Optional[Dict[str, Any]] = None


_pending_locations: Dict[str, _PendingLocation] = {}


def provide_location(request_id: str, location: Optional[Dict[str, Any]]) -> bool:
    """Called from the /api/provide-location endpoint to unblock the pipeline."""
    pending = _pending_locations.get(request_id)
    if not pending:
        return False
    pending.location = location
    pending.event.set()
    return True


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
    messages.append({"role": "user", "content": f"<<<USER_MESSAGE>>>\n{message}\n<<<END_USER_MESSAGE>>>"})
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
    if parsed.get("_is_error"):
        return False
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
        "_is_error": True,
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


# ── Type aliases the LLM frequently uses instead of canonical A2UI types ──
_TYPE_ALIASES = {
    "table": "data-table", "datatable": "data-table",
    "stats": "stats", "stat-grid": "stats", "stat_grid": "stats",
    "statgrid": "stats", "stats_grid": "stats", "stats-grid": "stats",
}


def _normalize_a2ui_components(result: Dict[str, Any]) -> Dict[str, Any]:
    """Fix common LLM output quirks in A2UI components in-place.

    Runs after LLM generation, before the response is sent to the client.

    Fixes applied:
    1. Type aliases (table -> data-table)
    2. Missing ``props`` wrapper — lift top-level keys into props
    3. Chart semantic data -> Chart.js {labels, datasets} format
    4. data-table missing ``columns`` -> auto-generate from data keys
    5. Alert ``message`` -> ``description``
    6. ``stats`` type -> individual ``stat`` children in a ``grid``
    """
    a2ui = result.get("a2ui")
    if not a2ui or not isinstance(a2ui, dict):
        return result

    components = a2ui.get("components")
    if not components or not isinstance(components, list):
        return result

    normalized: List[Dict[str, Any]] = []
    for comp in components:
        if not isinstance(comp, dict) or "type" not in comp:
            continue
        fixed = _normalize_single(comp)
        if isinstance(fixed, list):
            normalized.extend(fixed)
        else:
            normalized.append(fixed)

    a2ui["components"] = normalized
    return result


_RESERVED_KEYS = {"id", "type", "props", "children", "events", "bindings", "when", "a11y"}


def _normalize_single(comp: Dict[str, Any]) -> Any:
    """Normalize one component dict. May return a list (stats expansion)."""
    ctype = comp.get("type", "")
    ctype = _TYPE_ALIASES.get(ctype, ctype)
    comp["type"] = ctype

    props = comp.get("props")
    if not props or not isinstance(props, dict):
        props = comp.get("config") or {}
        if not isinstance(props, dict):
            props = {}
        for k, v in list(comp.items()):
            if k not in _RESERVED_KEYS and k != "config":
                props[k] = v
        comp["props"] = props
        comp.pop("config", None)

    if "children" in props and "children" not in comp:
        comp["children"] = props.pop("children")

    if ctype == "chip" and props.get("text") and not props.get("label"):
        props["label"] = props.pop("text")

    if ctype == "alert" and props.get("message") and not props.get("description"):
        props["description"] = props.pop("message")

    if ctype == "data-table":
        headers = props.get("headers")
        rows_raw = props.get("rows")
        if headers and isinstance(headers, list) and rows_raw and isinstance(rows_raw, list):
            if isinstance(rows_raw[0], list):
                keys = [h.lower().replace(" ", "_") for h in headers]
                props["columns"] = [{"key": k, "label": h} for k, h in zip(keys, headers)]
                props["data"] = [{k: v for k, v in zip(keys, row)} for row in rows_raw]
                props.pop("headers", None)
                props.pop("rows", None)

        rows = props.get("data")
        columns = props.get("columns")

        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            data_keys = set(rows[0].keys())

            if not columns:
                props["columns"] = [{"key": k, "label": k} for k in rows[0].keys()]
            elif isinstance(columns, list) and columns:
                col_keys = {(c.get("key") if isinstance(c, dict) else c) for c in columns}
                if not col_keys & data_keys:
                    props["columns"] = [
                        {"key": k, "label": k.replace("_", " ").replace("-", " ").title()}
                        for k in rows[0].keys()
                    ]

    if ctype == "stats":
        items = props.get("stats") or props.get("items") or []
        if isinstance(items, list) and items:
            children = [
                {"id": f"{comp.get('id','s')}-{i}", "type": "stat", "props": {
                    "label": s.get("label") or s.get("title", ""),
                    "value": str(s.get("value", "")),
                    "trend": s.get("trend", ""),
                    "trendDirection": s.get("trendDirection") or s.get("trend", "neutral"),
                    "description": s.get("description", ""),
                }} for i, s in enumerate(items)
            ]
            return {"id": comp.get("id", "stat-grid"), "type": "grid",
                    "props": {"columns": min(len(children), 4)}, "children": children}
        return []

    if ctype == "chart":
        _normalize_chart_data(props)

    children = comp.get("children")
    if children and isinstance(children, list):
        normalized_children: List[Dict[str, Any]] = []
        for child in children:
            if not isinstance(child, dict) or "type" not in child:
                continue
            fixed = _normalize_single(child)
            if isinstance(fixed, list):
                normalized_children.extend(fixed)
            else:
                normalized_children.append(fixed)
        comp["children"] = normalized_children

    return comp


def _normalize_chart_data(props: Dict[str, Any]) -> None:
    """Convert semantic chart rows into Chart.js {labels, datasets} format."""
    raw = props.get("data")
    if not raw:
        return

    if isinstance(raw, dict) and isinstance(raw.get("datasets"), list):
        return

    rows: Optional[List[Dict]] = None
    series: List[Dict] = []
    x_field = ""

    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        rows = raw
        xa = props.get("xAxis") or props.get("x_axis") or {}
        x_field = xa.get("field", "") if isinstance(xa, dict) else ""
        for axis_key in ("yAxisLeft", "y_axis_left", "yAxisRight", "y_axis_right"):
            ax = props.get(axis_key)
            if isinstance(ax, dict) and isinstance(ax.get("series"), list):
                tag = "right" if "right" in axis_key.lower() else "left"
                for s in ax["series"]:
                    series.append({**s, "_ax": tag})
        if not series and isinstance(props.get("series"), list):
            series = props["series"]
    elif isinstance(raw, dict):
        rows = raw.get("data") if isinstance(raw.get("data"), list) else None
        series = raw.get("series", [])
        xa = raw.get("x_axis") or raw.get("xAxis") or {}
        x_field = xa.get("field", "") if isinstance(xa, dict) else ""
        if raw.get("title") and not props.get("title"):
            props["title"] = raw["title"]

    if not rows:
        return

    if not x_field:
        for k, v in rows[0].items():
            if isinstance(v, str):
                x_field = k
                break
    if not x_field:
        return

    if not series:
        series = [{"field": k, "label": k.replace("_", " "), "type": "bar"}
                  for k, v in rows[0].items() if k != x_field and isinstance(v, (int, float))]
    if not series:
        return

    labels = [str(r.get(x_field, "")) for r in rows]
    has_line = any(s.get("type") == "line" or s.get("_ax") == "right" for s in series)

    datasets = []
    for s in series:
        field = s.get("field", "")
        ds: Dict[str, Any] = {"label": s.get("label", field), "data": [r.get(field, 0) for r in rows]}
        if s.get("type") == "line" or s.get("_ax") == "right":
            ds.update(type="line", borderWidth=2, fill=False, tension=0.3)
            if has_line:
                ds["yAxisID"] = "y1"
        elif has_line:
            ds["yAxisID"] = "y"
        datasets.append(ds)

    ct = str(props.get("type", "bar"))
    if "line" in ct and "bar" not in ct:
        props["chartType"] = props.get("chartType", "line")
    else:
        props["chartType"] = props.get("chartType", "bar")

    if has_line:
        opts = props.get("options") or {}
        if not isinstance(opts, dict):
            opts = {}
        opts["scales"] = {
            "y": {"position": "left"},
            "y1": {"position": "right", "grid": {"drawOnChartArea": False}},
        }
        opts["showLegend"] = True
        opts["showGrid"] = True
        props["options"] = opts

    props["data"] = {"labels": labels, "datasets": datasets}

    for k in ("xAxis", "x_axis", "yAxisLeft", "y_axis_left", "yAxisRight", "y_axis_right", "series"):
        props.pop(k, None)


def _apply_chart_hints(
    response: Dict[str, Any],
    ds_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Use ``chart_hint`` from data-source responses to build/fix charts deterministically."""
    if not ds_results:
        return response

    a2ui = response.get("a2ui")
    if not a2ui or not isinstance(a2ui, dict):
        return response
    components = a2ui.get("components", [])

    for r in ds_results:
        if not r.get("success"):
            continue
        payload = r.get("data", {})
        if not isinstance(payload, dict):
            continue

        hint = payload.get("chart_hint")
        if not isinstance(hint, dict):
            continue

        rows = payload.get("data", [])
        if not isinstance(rows, list) or not rows:
            continue

        x_axis = hint.get("x_axis") or {}
        x_field = x_axis.get("field", "")
        x_label = x_axis.get("label", "")
        if not x_field:
            continue

        labels = [str(row.get(x_field, "")) for row in rows]
        datasets: List[Dict[str, Any]] = []

        y_left = hint.get("y_axis_left") or {}
        y_left_label = y_left.get("label", "")
        for bar_spec in (y_left.get("stacked_bars") or y_left.get("bars") or []):
            field = bar_spec.get("field", "")
            lbl = bar_spec.get("label", field.replace("_", " ").title())
            if lbl == "Bar":
                lbl = y_left_label or field.replace("_", " ").title()
            datasets.append({
                "label": lbl,
                "data": [row.get(field, 0) for row in rows],
                "yAxisID": "y",
            })
        if not datasets and y_left.get("field"):
            datasets.append({
                "label": y_left_label or y_left["field"].replace("_", " ").title(),
                "data": [row.get(y_left["field"], 0) for row in rows],
                "yAxisID": "y",
            })

        y_right = hint.get("y_axis_right") or {}
        r_field = y_right.get("field", "")
        if r_field:
            datasets.append({
                "label": y_right.get("series_label") or y_right.get("label") or r_field.replace("_", " ").title(),
                "data": [row.get(r_field, 0) for row in rows],
                "type": "line",
                "yAxisID": "y1",
                "borderWidth": 2,
                "fill": False,
                "tension": 0.3,
            })

        if not datasets:
            continue

        has_line = any(ds.get("type") == "line" for ds in datasets)
        chart_data = {"labels": labels, "datasets": datasets}
        chart_options: Dict[str, Any] = {
            "xAxisLabel": x_label,
            "yAxisLabel": y_left_label,
            "showLegend": True,
            "showGrid": True,
        }
        if has_line:
            chart_options["scales"] = {
                "y": {"position": "left"},
                "y1": {"position": "right", "grid": {"drawOnChartArea": False}},
            }

        title = hint.get("title", "")

        replaced = False
        for comp in components:
            if isinstance(comp, dict) and comp.get("type") == "chart":
                props = comp.get("props") or {}
                comp["props"] = {**props, "data": chart_data, "chartType": "bar", "options": chart_options}
                if title:
                    comp["props"]["title"] = title
                replaced = True
                logger.info("── CHART HINT ──  replaced LLM chart with deterministic bar+line from chart_hint")
                break

        if not replaced:
            components.append({
                "id": "chart-hint-generated",
                "type": "chart",
                "props": {
                    "title": title,
                    "chartType": "bar",
                    "data": chart_data,
                    "options": chart_options,
                },
            })
            logger.info("── CHART HINT ──  appended deterministic bar+line chart from chart_hint")

    return response


def _normalize_suggestions(response: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure ``suggestions`` is always a flat list of strings."""
    raw = response.get("suggestions")
    if not raw or not isinstance(raw, list):
        return response

    normalized: List[str] = []
    for item in raw:
        if isinstance(item, str):
            normalized.append(item.strip())
        elif isinstance(item, dict):
            text = item.get("text") or item.get("label") or item.get("title") or ""
            if isinstance(text, str) and text.strip():
                normalized.append(text.strip())
    response["suggestions"] = normalized
    return response


# ── Data-Aware Hint Derivation ─────────────────────────────────

_CHART_TYPE_TO_HINT: Dict[str, Optional[str]] = {
    "stacked_bar_with_line": None,
    "bar_with_line": None,
    "bar": None,
    "stacked_bar": None,
    "line": None,
    "multi_line": None,
    "donut": None,
    "table": None,
    "horizontal_grouped_bar": None,
    "matrix": "chart_matrix",
    "heatmap": "chart_matrix",
    "treemap": "chart_treemap",
    "sankey": "chart_sankey",
    "funnel": "chart_funnel",
    "radar": "chart_radar",
    "scatter": "chart_scatter",
    "bubble": "chart_scatter",
    "choropleth": "chart_choropleth",
    "geo": "chart_choropleth",
    "geographic": "chart_choropleth",
    "bubblemap": "chart_bubblemap",
    "bubble_map": "chart_bubblemap",
}

_EXOTIC_CHART_PATTERNS: Dict[str, re.Pattern] = {
    "chart_matrix": re.compile(r"\b(?:heatmap|heat\s*map|matrix|correlation\s*matrix)\b", re.IGNORECASE),
    "chart_treemap": re.compile(r"\b(?:treemap|tree\s*map)\b", re.IGNORECASE),
    "chart_sankey": re.compile(r"\b(?:sankey|flow\s*diagram|alluvial)\b", re.IGNORECASE),
    "chart_funnel": re.compile(r"\b(?:funnel|conversion\s*funnel|sales\s*pipeline)\b", re.IGNORECASE),
    "chart_radar": re.compile(r"\b(?:radar|spider\s*chart|star\s*chart)\b", re.IGNORECASE),
    "chart_scatter": re.compile(r"\b(?:scatter|bubble\s*chart|correlation\s*plot)\b", re.IGNORECASE),
    "chart_choropleth": re.compile(r"\b(?:choropleth|geo(?:graphic)?\s*map|country\s*map|state\s*map|world\s*map|us\s*map)\b", re.IGNORECASE),
    "chart_bubblemap": re.compile(r"\b(?:bubble\s*map|geo(?:graphic)?\s*bubble|location\s*map|city\s*map|lat(?:itude)?\s*long(?:itude)?)\b", re.IGNORECASE),
}


def _derive_hints_from_data(
    ds_results: List[Dict[str, Any]],
    query: str,
) -> Tuple[List[str], str]:
    """Derive component hints and complexity from ACTUAL data, not blind guessing.

    Returns ``(component_hints, complexity)``.
    """
    hints: List[str] = []
    has_multi_dataset = False
    has_complex_structure = False

    for r in ds_results:
        if not r.get("success"):
            continue
        payload = r.get("data", {})
        if not isinstance(payload, dict):
            continue

        chart_hint = payload.get("chart_hint", {})
        if not isinstance(chart_hint, dict):
            continue
        chart_type = str(chart_hint.get("chart_type", "")).lower().strip()

        if chart_type in _CHART_TYPE_TO_HINT:
            micro_key = _CHART_TYPE_TO_HINT[chart_type]
            if micro_key and micro_key not in hints:
                hints.append(micro_key)

        y_left = chart_hint.get("y_axis_left") or {}
        stacked = y_left.get("stacked_bars") or []
        if isinstance(stacked, list) and len(stacked) > 2:
            has_multi_dataset = True
        if chart_hint.get("y_axis_right"):
            has_multi_dataset = True

        rows = payload.get("data", [])
        if isinstance(rows, list) and len(rows) > 50:
            has_complex_structure = True

    if not ds_results:
        for key, pattern in _EXOTIC_CHART_PATTERNS.items():
            if pattern.search(query) and key not in hints:
                hints.append(key)

    if hints:
        complexity = "high"
    elif has_complex_structure or has_multi_dataset:
        complexity = "moderate"
    else:
        complexity = "standard"

    return hints, complexity


# ── Phase 2 Skip Logic ────────────────────────────────────────

_DATA_ORIENTED_STYLES = frozenset({
    "analytical", "comparison", "dashboard",
})


def _can_skip_explorers(
    classification: Optional[Dict[str, Any]],
    routing: Optional[List[Dict[str, Any]]],
    content_style: str,
    has_data_context: bool,
) -> bool:
    """Decide whether Phase 2 (explorers) can be skipped.

    Skip conditions (ALL must be true):
    - Classifier says search = False
    - Classifier says location = False
    - Router returned no data source queries
    - No passive dataContext from the frontend
    - Resolved style is not data-oriented
    """
    if not classification:
        return False

    if classification.get("search"):
        return False
    if classification.get("location"):
        return False

    if routing:
        return False

    if has_data_context:
        return False

    style = content_style if content_style != "auto" else classification.get("style", "content")
    if style in _DATA_ORIENTED_STYLES:
        return False

    return True


# ── Post-Data Style Refinement ─────────────────────────────────

def _refine_style_from_data(
    current_style: str,
    ds_results: List[Dict[str, Any]],
    component_hints: List[str],
    style_was_auto: bool,
) -> Tuple[str, Optional[str]]:
    """Refine content style based on actual data source responses.

    Only modifies style when the user left content_style on "auto".
    Returns ``(refined_style, reason)`` — reason is ``None`` if unchanged.
    """
    if not style_was_auto:
        return current_style, None

    if not ds_results:
        return current_style, None

    successful = [r for r in ds_results if r.get("success")]
    if not successful:
        return current_style, None

    if current_style in ("analytical", "dashboard"):
        return current_style, None

    has_chart_hints = False
    total_records = 0
    has_metrics_metadata = False

    for r in successful:
        total_records += r.get("record_count", 0)
        payload = r.get("data", {})
        if isinstance(payload, dict):
            if payload.get("chart_hint"):
                has_chart_hints = True
            if payload.get("metrics_metadata"):
                has_metrics_metadata = True

    if has_chart_hints or has_metrics_metadata:
        return "analytical", f"data has chart_hint/metrics_metadata -> analytical"

    if total_records > 20:
        return "analytical", f"{total_records} records -> analytical"

    if total_records > 0 and current_style == "quick":
        return "content", f"data returned ({total_records} records) -> content"

    return current_style, None


# ── Content Styles ─────────────────────────────────────────────
# System prompts are now modular — see a2ui-agent/content_styles/.
# The service layer classifies intent and selects the right style.


# ── Abstract Base ──────────────────────────────────────────────


class LLMStreamError(Exception):
    """Raised by streaming LLM calls when the provider returns an error.

    Carries the same error-response dict that ``_error_response()`` produces
    so callers can yield it as a normal ``complete`` event.
    """

    def __init__(self, error_response: Dict[str, Any]):
        self.error_response = error_response
        super().__init__(error_response.get("text", "Stream error"))


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
        effort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a response for the given message with optional history.

        Args:
            effort: Thinking effort level for models that support adaptive
                    thinking ("low", "medium", "high", "max"). None = provider default.
        """

    async def generate_stream_tokens(
        self,
        message: str,
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        effort: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Yield token deltas as they arrive from the LLM.

        Default implementation falls back to non-streaming ``generate()`` and
        yields the full text in one chunk.  Subclasses should override this
        with a true streaming implementation.

        Raises ``LLMStreamError`` on provider errors.
        """
        result = await self.generate(
            message, model, history,
            system_prompt=system_prompt, effort=effort,
        )
        if result.get("_is_error"):
            raise LLMStreamError(result)
        yield json.dumps(result)
        return  # noqa: B901 — explicit return in async generator


# ── Provider Implementations ──────────────────────────────────


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""

    name = "OpenAI"
    models = [
        {"id": "gpt-5.1", "name": "GPT-5.1"},
        {"id": "gpt-5", "name": "GPT-5"},
        {"id": "gpt-5-mini", "name": "GPT-5 Mini"},
        {"id": "gpt-4.1", "name": "GPT-4.1"},
        {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini (Fast)"},
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
                api_key=self._api_key, timeout=120.0, max_retries=0,
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
            "  [OpenAI] %s  |  %d messages  |  %d chars (~%d tokens)  |  timeout=120s",
            model, len(messages), total_chars, total_chars // 4,
        )

        # GPT-5+ uses max_completion_tokens and only supports temperature=1.
        # 16384 output tokens needed — GPT-5 is verbose with structured JSON
        # and data-heavy contexts (28K+ chars from data sources) easily exceed 4K.
        is_gpt5 = model.startswith("gpt-5")
        extra: Dict[str, Any] = (
            {"max_completion_tokens": 16384}
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

    async def _call_llm_stream(
        self,
        message: str,
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming variant — yields token deltas. Raises LLMStreamError on failure."""
        messages = _build_messages(message, history, system_prompt=system_prompt)

        is_gpt5 = model.startswith("gpt-5")
        extra: Dict[str, Any] = (
            {"max_completion_tokens": 16384}
            if is_gpt5
            else {"max_tokens": 4000, "temperature": 0.7}
        )

        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                stream=True,
                **extra,
            )
        except openai.APITimeoutError:
            raise LLMStreamError(_error_response(
                "Request Timeout",
                "The model took too long to respond. Try again or switch to a faster model.",
                variant="warning",
            ))
        except openai.APIError as exc:
            raise LLMStreamError(_error_response(
                "Something Went Wrong",
                "The AI service returned an error. Please try again in a moment.",
            ))

        try:
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:
            logger.error("OpenAI stream interrupted (%s): %s", model, exc)
            raise LLMStreamError(_error_response(
                "Stream Interrupted",
                "The response stream was interrupted. Please try again.",
                variant="warning",
            ))

    async def generate(
        self,
        message: str,
        model: str = "gpt-4.1",
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        effort: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = await self._call_llm(message, model, history, system_prompt)

        # Refusal guard — retry with stronger nudge
        return await _retry_on_refusal(
            result, message,
            lambda msg, hist: self._call_llm(msg, model, hist, system_prompt),
        )

    async def generate_stream_tokens(
        self,
        message: str,
        model: str = "gpt-4.1",
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        effort: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Yield raw token deltas from the LLM as they arrive."""
        async for delta in self._call_llm_stream(message, model, history, system_prompt):
            yield delta


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    name = "Anthropic"
    models = [
        {"id": "claude-opus-4-6", "name": "Claude Opus 4.6"},
        {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6"},
        {"id": "claude-sonnet-4-5-20250929", "name": "Claude Sonnet 4.5"},
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
                timeout=120.0,
                max_retries=0,
            )
        return self._client

    # Models that support adaptive thinking (type: "adaptive" + effort)
    _ADAPTIVE_MODELS = frozenset({"claude-opus-4-6", "claude-sonnet-4-6"})
    # Sonnet 4.6 also supports manual extended thinking; adaptive is preferred
    _THINKING_MODELS = _ADAPTIVE_MODELS

    async def _call_llm(
        self,
        message: str,
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        effort: Optional[str] = None,
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

        # Build kwargs — add adaptive thinking for 4.6 models
        kwargs: Dict[str, Any] = dict(
            model=model,
            max_tokens=16000 if model in self._THINKING_MODELS and effort else 4000,
            system=system_prompt,
            messages=messages,
        )

        if model in self._ADAPTIVE_MODELS and effort:
            valid_efforts = ("low", "medium", "high", "max")
            effort_val = effort if effort in valid_efforts else "high"
            # "max" effort only supported on Opus 4.6
            if effort_val == "max" and model != "claude-opus-4-6":
                effort_val = "high"
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["output_config"] = {"effort": effort_val}
            logger.info("  [Anthropic] %s  adaptive thinking  effort=%s", model, effort_val)

        try:
            response = await self.client.messages.create(**kwargs)
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

        # Extract text from response — skip thinking blocks
        text_parts = []
        for block in response.content:
            if hasattr(block, "text") and block.type == "text":
                text_parts.append(block.text)
        content = " ".join(text_parts).strip()

        if not content:
            logger.warning("%s returned empty content", model)
            return _error_response(
                "Empty Response",
                "The AI returned an empty response. Please try again or switch models.",
                variant="warning",
            )
        return parse_llm_json(content)

    async def _call_llm_stream(
        self,
        message: str,
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        effort: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming variant — yields token deltas. Raises LLMStreamError on failure."""
        if system_prompt is None:
            system_prompt = get_system_prompt("content")

        prompt_bytes = len(system_prompt.encode("utf-8"))
        msg_bytes = len(message.encode("utf-8"))
        trimmed = _trim_history(history, prompt_bytes, msg_bytes)

        messages: List[Dict[str, str]] = []
        for msg in trimmed:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": message})

        kwargs: Dict[str, Any] = dict(
            model=model,
            max_tokens=4000,
            system=system_prompt,
            messages=messages,
        )

        try:
            async with self.client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.APITimeoutError:
            raise LLMStreamError(_error_response(
                "Request Timeout",
                "The model took too long to respond. Try again or switch to a faster model.",
                variant="warning",
            ))
        except anthropic.APIError as exc:
            raise LLMStreamError(_error_response(
                "Something Went Wrong",
                "The AI service returned an error. Please try again in a moment.",
            ))
        except Exception as exc:
            logger.error("Anthropic stream interrupted (%s): %s", model, exc)
            raise LLMStreamError(_error_response(
                "Stream Interrupted",
                "The response stream was interrupted. Please try again.",
                variant="warning",
            ))

    async def generate(
        self,
        message: str,
        model: str = "claude-opus-4-6",
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        effort: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = await self._call_llm(message, model, history, system_prompt, effort)

        # Refusal guard — retry with stronger nudge
        return await _retry_on_refusal(
            result, message,
            lambda msg, hist: self._call_llm(msg, model, hist, system_prompt, effort),
        )

    async def generate_stream_tokens(
        self,
        message: str,
        model: str = "claude-opus-4-6",
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        effort: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Yield raw token deltas from the LLM as they arrive."""
        async for delta in self._call_llm_stream(message, model, history, system_prompt, effort):
            yield delta


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
        effort: Optional[str] = None,
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


# ── LLM Classifier & Data Source Router ────────────────────────
#
# The analysis phase runs TWO focused agents in parallel:
#   1. Intent Classifier  — style, search, location, search_query
#   2. Data Source Router  — which data sources / endpoints / params to query
#
# Each has its own system prompt, user prompt template, and max_tokens.
# Both use temperature=0 and select models based on performance_mode:
#   - default/auto/comprehensive: _ANALYZER_MODELS  (Sonnet 4.6)
#   - optimized (speed):          _ANALYZER_MODELS_FAST (Haiku 4.5)


def _make_classifier_system() -> str:
    """System prompt for the Intent Classifier agent.

    Decides style, search, location, and search_query only.
    Component hints and complexity are derived later from actual data
    source responses (see ``_derive_hints_from_data``).
    """
    from datetime import date
    today = date.today().strftime("%B %d, %Y")
    return (
        f"You are an intent classifier for an AI UI system. Today is {today}.\n"
        "Given a user query, decide:\n"
        "1. The best content presentation style\n"
        "2. Whether real-time web search is needed (current events, prices, weather, live data)\n"
        "3. Whether the user's geographic location is relevant\n"
        "4. If search is needed, an optimized search query (MUST include the current year for time-sensitive topics)\n"
        "Respond with ONLY a valid JSON object. No markdown, no explanation."
    )


_CLASSIFIER_PROMPT_TEMPLATE = (
    "Content styles:\n{descriptions}\n\n"
    "{context_section}"
    "User query: {query}\n\n"
    'Reply with JSON: {{"style":"<style_id>","search":<true|false>,"location":<true|false>,'
    '"search_query":"<optimized query or empty>"}}\n'
)


def _make_router_system() -> str:
    """System prompt for the Data Source Router agent."""
    from datetime import date
    today = date.today().strftime("%B %d, %Y")
    return (
        f"You are a data source router for an AI system. Today is {today}.\n"
        "Given a user query and a catalog of available data sources, decide which\n"
        "data sources (if any) should be queried to answer the question.\n"
        "Pick the BEST matching endpoint(s) — do not query endpoints that are not relevant.\n"
        "Fill in sensible default parameters based on the query context.\n"
        "IMPORTANT: If the user explicitly mentions 'Genie' (case-insensitive), always route to the Genie endpoint.\n"
        "Respond with ONLY a valid JSON object. No markdown, no explanation."
    )


_ROUTER_PROMPT_TEMPLATE = (
    "{data_sources_section}"
    "{context_section}"
    "User query: {query}\n\n"
    'Reply with JSON: {{"data_sources":[{{"source":"<source_id>","endpoint":"<path>","params":{{}}}}]}}\n'
    "If no data sources are relevant, return an empty array for data_sources.\n"
    "Only include sources and endpoints from the catalog above.\n"
    "For the Genie endpoint (/api/v1/genie/ask), set params.question to the user's query."
)

_ANALYZER_MODELS: List[tuple] = [
    ("anthropic", "claude-sonnet-4-6"),
]

_ANALYZER_MODELS_FAST: List[tuple] = [
    ("anthropic", "claude-haiku-4-5-20251001"),
]


def _fallback_data_sources(message: str) -> List[Dict[str, Any]]:
    """Keyword-based data source matching — safety net when the AI router fails.

    Scans the registered REST data sources for endpoint descriptions that match
    the user's query keywords.  Returns a list of query dicts in the same format
    the AI router would produce:
        [{"source": "...", "endpoint": "/...", "params": {}}]

    Only the BEST matching endpoint per source is returned (highest keyword
    overlap) to avoid flooding the pipeline with irrelevant queries.

    When the user explicitly mentions "genie" (case-insensitive), the Genie
    endpoint receives a large score boost so it always wins over other matches.
    """
    from data_sources import get_all_sources
    from data_sources.rest import RESTDataSource

    query_lower = message.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    results: List[Dict[str, Any]] = []

    genie_mentioned = "genie" in query_lower

    for source in get_all_sources():
        if not source.is_available() or not isinstance(source, RESTDataSource):
            continue

        best_ep = None
        best_score = 0

        for ep in source._endpoints:
            desc_words = set(re.findall(r'\w+', (ep.description or "").lower()))
            param_words = set(p.lower() for p in (ep.params or []))
            score = len(query_words & (desc_words | param_words))

            if genie_mentioned and "genie" in ep.path.lower():
                score += 100

            if score > best_score:
                best_score = score
                best_ep = ep

        if best_ep and best_score >= 1:
            params: Dict[str, Any] = {}
            if "/genie/ask" in best_ep.path:
                params["question"] = message

            entry: Dict[str, Any] = {
                "source": source.id,
                "endpoint": best_ep.path,
                "params": params,
            }
            if best_ep.method != "GET":
                entry["method"] = best_ep.method

            results.append(entry)
            logger.info(
                "── DATA SOURCE FALLBACK ──  matched %s %s %s  (score=%d%s)",
                best_ep.method, source.id, best_ep.path, best_score,
                " [genie-boost]" if genie_mentioned and best_score >= 100 else "",
            )

    return results

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

# ── Adaptive Model Routing ─────────────────────────────────────
#
# Task-based model selection: the analyzer classifies complexity
# and the pipeline routes to the BEST + FASTEST model available.
# Speed is king — a slow model is a broken model.
#
# Complexity tiers:
#   "standard"  — no upgrade needed (text, simple charts)
#   "moderate"  — structured data, multi-dataset charts
#   "high"      — complex viz (matrix, sankey, treemap), deep analysis
#   "reasoning" — multi-step math, logic chains, statistical analysis

# Speed scores: lower = faster = better
_SPEED_SCORE = {"fast": 0, "medium": 1, "slow": 2}

_MODEL_ROSTER: List[Dict[str, Any]] = [
    # Anthropic — stability & precision, natural tone, root-cause debugging
    {"provider": "anthropic", "model": "claude-sonnet-4-6",            "tier": 4, "tags": {"structured", "reasoning", "creative"}, "speed": "medium"},
    {"provider": "anthropic", "model": "claude-opus-4-6",              "tier": 4, "tags": {"structured", "reasoning", "creative"}, "speed": "medium"},
    {"provider": "anthropic", "model": "claude-sonnet-4-5-20250929",   "tier": 3, "tags": {"structured", "creative"},              "speed": "medium"},
    {"provider": "anthropic", "model": "claude-haiku-4-5-20251001",    "tier": 1, "tags": set(),                                   "speed": "fast"},
    # OpenAI GPT-5.1 — 2-3x faster than GPT-5, adaptive reasoning, 400K context, peak math/logic
    {"provider": "openai",   "model": "gpt-5.1",                      "tier": 4, "tags": {"structured", "reasoning"},              "speed": "fast"},
    {"provider": "openai",   "model": "gpt-5",                        "tier": 4, "tags": {"structured", "reasoning"},              "speed": "medium"},
    {"provider": "openai",   "model": "gpt-5-mini",                   "tier": 2, "tags": {"structured"},                           "speed": "medium"},
    # OpenAI — general purpose
    {"provider": "openai",   "model": "gpt-4.1",                      "tier": 2, "tags": set(),                                    "speed": "fast"},
    {"provider": "openai",   "model": "gpt-4.1-mini",                 "tier": 1, "tags": set(),                                    "speed": "fast"},
    # Gemini — strong multimodal + structured data, large context
    {"provider": "gemini",   "model": "gemini-3-pro-preview",         "tier": 3, "tags": {"structured", "reasoning"},              "speed": "medium"},
    {"provider": "gemini",   "model": "gemini-2.5-flash-preview-05-20", "tier": 1, "tags": set(),                                  "speed": "fast"},
]

# Build fast lookups
_ROSTER_BY_PROVIDER: Dict[str, List[Dict[str, Any]]] = {}
for _entry in _MODEL_ROSTER:
    _ROSTER_BY_PROVIDER.setdefault(_entry["provider"], []).append(_entry)

def _get_model_entry(provider_id: str, model_id: str) -> Optional[Dict[str, Any]]:
    """Return the roster entry for a model, or None."""
    for entry in _ROSTER_BY_PROVIDER.get(provider_id, []):
        if entry["model"] == model_id:
            return entry
    return None

def _get_model_tier(provider_id: str, model_id: str) -> int:
    """Return the tier (1-4) of a model, or 1 if unknown."""
    entry = _get_model_entry(provider_id, model_id)
    return entry["tier"] if entry else 1

# Complexity → minimum tier required, plus any tag requirements
_COMPLEXITY_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    "standard":  {"min_tier": 1, "tags": set()},
    "moderate":  {"min_tier": 2, "tags": set()},
    "high":      {"min_tier": 3, "tags": {"structured"}},
    "reasoning": {"min_tier": 3, "tags": {"reasoning"}},
}

_COMPLEX_COMPONENTS = frozenset({
    "chart_matrix", "chart_treemap", "chart_sankey",
    "chart_funnel",
})

_MODERATE_COMPONENTS = frozenset({
    "chart_scatter", "chart_radar",
})


def _derive_complexity(
    analyzer_complexity: str,
    component_hints: List[str],
) -> str:
    """Derive effective complexity from analyzer output + component hints."""
    hint_set = set(component_hints)

    if hint_set & _COMPLEX_COMPONENTS:
        return "high"
    if hint_set & _MODERATE_COMPONENTS and analyzer_complexity in ("standard",):
        return "moderate"

    return analyzer_complexity if analyzer_complexity in _COMPLEXITY_REQUIREMENTS else "standard"


def _find_best_model(
    current_provider_id: str,
    current_model: str,
    complexity: str,
    providers: Dict[str, "LLMProvider"],
) -> Optional[tuple]:
    """Find the best available model for the given complexity.

    Collects ALL candidates across ALL available providers, then picks
    the fastest one that meets the tier+tag requirement. Speed is the
    primary sort key — a slow same-provider model loses to a fast
    cross-provider model every time.

    Returns (provider_id, model_id) or None if current model is sufficient.
    """
    req = _COMPLEXITY_REQUIREMENTS.get(complexity)
    if not req:
        return None

    min_tier = req["min_tier"]
    required_tags = req["tags"]

    current_entry = _get_model_entry(current_provider_id, current_model)
    if current_entry:
        if (current_entry["tier"] >= min_tier
                and required_tags.issubset(current_entry["tags"])):
            return None  # Already sufficient

    # Collect candidates from ALL available providers
    candidates: List[Dict[str, Any]] = []
    for pid, prov in providers.items():
        if not prov.is_available():
            continue
        for entry in _ROSTER_BY_PROVIDER.get(pid, []):
            if (entry["tier"] >= min_tier
                    and required_tags.issubset(entry["tags"])
                    and not (entry["provider"] == current_provider_id
                             and entry["model"] == current_model)):
                candidates.append(entry)

    if not candidates:
        return None

    # Sort: fastest first, then lowest sufficient tier, then prefer same provider
    candidates.sort(key=lambda e: (
        _SPEED_SCORE.get(e["speed"], 2),     # speed first (fast=0, medium=1, slow=2)
        e["tier"],                            # lowest tier that still qualifies
        0 if e["provider"] == current_provider_id else 1,  # same-provider tiebreaker
    ))

    best = candidates[0]
    return (best["provider"], best["model"])


def _find_faster_model(
    current_provider_id: str,
    current_model: str,
    providers: Dict[str, "LLMProvider"],
) -> Optional[tuple]:
    """For standard-complexity tasks, find a faster model if the current one is slow.

    Only downgrades if the current model is medium or slow speed.
    Returns (provider_id, model_id) or None if already fast.
    """
    current_entry = _get_model_entry(current_provider_id, current_model)
    if not current_entry:
        return None

    current_speed = _SPEED_SCORE.get(current_entry["speed"], 0)
    if current_speed == 0:
        return None  # Already fast

    # Find the fastest tier-1+ model available (standard tasks need tier 1 minimum)
    candidates: List[Dict[str, Any]] = []
    for pid, prov in providers.items():
        if not prov.is_available():
            continue
        for entry in _ROSTER_BY_PROVIDER.get(pid, []):
            entry_speed = _SPEED_SCORE.get(entry["speed"], 2)
            if entry_speed < current_speed and entry["tier"] >= 1:
                candidates.append(entry)

    if not candidates:
        return None

    # Fastest first, then highest tier (prefer capable fast models), then same provider
    candidates.sort(key=lambda e: (
        _SPEED_SCORE.get(e["speed"], 2),
        -e["tier"],
        0 if e["provider"] == current_provider_id else 1,
    ))

    best = candidates[0]
    if best["provider"] == current_provider_id and best["model"] == current_model:
        return None
    return (best["provider"], best["model"])


# ── Service Layer ──────────────────────────────────────────────


class LLMService:
    """Orchestrates provider selection, web search, and response generation."""

    def __init__(self) -> None:
        self.providers: Dict[str, LLMProvider] = {
            "anthropic": AnthropicProvider(),
            "openai": OpenAIProvider(),
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
        """Return the current state of all configurable tools."""
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

    # ── Phase 1a: Intent Classifier ────────────────────────────

    async def _classify_intent(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        performance_mode: str = "auto",
    ) -> Optional[Dict[str, Any]]:
        """Classify user intent: style, search, location, search_query.

        Returns a dict or ``None`` on failure (caller falls back to regex).
        """
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

        prompt = _CLASSIFIER_PROMPT_TEMPLATE.format(
            descriptions=STYLE_DESCRIPTIONS,
            context_section=context_section,
            query=message[:500],
        )

        analyzer_models = _ANALYZER_MODELS_FAST if performance_mode == "optimized" else _ANALYZER_MODELS
        for provider_id, model_id in analyzer_models:
            provider = self.providers.get(provider_id)
            if not provider or not provider.is_available():
                continue

            try:
                if provider_id == "openai":
                    resp = await provider.client.chat.completions.create(
                        model=model_id,
                        messages=[
                            {"role": "system", "content": _make_classifier_system()},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=200,
                        temperature=0,
                    )
                    text = (resp.choices[0].message.content or "").strip()

                elif provider_id == "anthropic":
                    resp = await provider.client.messages.create(
                        model=model_id,
                        max_tokens=200,
                        system=_make_classifier_system(),
                        messages=[{"role": "user", "content": prompt}],
                    )
                    text = resp.content[0].text.strip()

                elif provider_id == "gemini":
                    import google.generativeai as genai
                    genai.configure(api_key=provider._api_key)
                    gen_model = genai.GenerativeModel(
                        model_name=model_id,
                        system_instruction=_make_classifier_system(),
                    )
                    resp = gen_model.generate_content(prompt)
                    text = resp.text.strip()
                else:
                    continue

                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\s*", "", text)
                    text = re.sub(r"\s*```$", "", text)

                result = json.loads(text)

                style = result.get("style", "").lower().strip()
                if style not in VALID_STYLE_IDS:
                    logger.warning("Classifier returned invalid style '%s' via %s/%s", style, provider_id, model_id)
                    continue

                classification = {
                    "style": style,
                    "search": bool(result.get("search", False)),
                    "location": bool(result.get("location", False)),
                    "search_query": str(result.get("search_query", "")),
                }

                logger.info(
                    "── CLASSIFY OK ──  %s via %s/%s  |  style=%s  search=%s  location=%s  query='%s'",
                    message[:50], provider_id, model_id,
                    classification["style"], classification["search"],
                    classification["location"], classification["search_query"][:60],
                )
                return classification

            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning("Classifier JSON parse failed (%s/%s): %s", provider_id, model_id, exc)
                continue
            except Exception as exc:
                logger.warning("Classifier failed (%s/%s): %s", provider_id, model_id, exc)
                continue

        return None

    # ── Phase 1b: Data Source Router ───────────────────────────

    async def _route_data_sources(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        performance_mode: str = "auto",
    ) -> List[Dict[str, Any]]:
        """Route query to relevant data sources.

        Returns a list of data source queries or empty list.
        """
        from data_sources import get_analyzer_context

        ds_context = get_analyzer_context()
        if not ds_context:
            return []

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

        data_sources_section = f"{ds_context}\n\n"

        prompt = _ROUTER_PROMPT_TEMPLATE.format(
            data_sources_section=data_sources_section,
            context_section=context_section,
            query=message[:500],
        )

        analyzer_models = _ANALYZER_MODELS_FAST if performance_mode == "optimized" else _ANALYZER_MODELS
        for provider_id, model_id in analyzer_models:
            provider = self.providers.get(provider_id)
            if not provider or not provider.is_available():
                continue

            try:
                if provider_id == "openai":
                    resp = await provider.client.chat.completions.create(
                        model=model_id,
                        messages=[
                            {"role": "system", "content": _make_router_system()},
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
                        system=_make_router_system(),
                        messages=[{"role": "user", "content": prompt}],
                    )
                    text = resp.content[0].text.strip()

                elif provider_id == "gemini":
                    import google.generativeai as genai
                    genai.configure(api_key=provider._api_key)
                    gen_model = genai.GenerativeModel(
                        model_name=model_id,
                        system_instruction=_make_router_system(),
                    )
                    resp = gen_model.generate_content(prompt)
                    text = resp.text.strip()
                else:
                    continue

                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\s*", "", text)
                    text = re.sub(r"\s*```$", "", text)

                result = json.loads(text)

                ds_queries = result.get("data_sources") or []
                if not isinstance(ds_queries, list):
                    ds_queries = []

                logger.info(
                    "── ROUTE OK ──  %s via %s/%s  |  data_sources=%d",
                    message[:50], provider_id, model_id, len(ds_queries),
                )
                return ds_queries

            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning("Router JSON parse failed (%s/%s): %s", provider_id, model_id, exc)
                continue
            except Exception as exc:
                logger.warning("Router failed (%s/%s): %s", provider_id, model_id, exc)
                continue

        return _fallback_data_sources(message)

    async def generate_stream(
        self,
        message: str,
        provider_id: str,
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
        user_location: Optional[Dict[str, Any]] = None,
        content_style: str = "auto",
        performance_mode: str = "auto",
        smart_routing: bool = True,
        enable_web_search: bool = True,
        enable_geolocation: bool = True,
        enable_data_sources: bool = True,
        data_context: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        data_source_overrides: Optional[Dict[str, Any]] = None,
        data_source_disabled: Optional[List[str]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Async generator that yields SSE events during response generation.

        Events emitted:
        - step       (id, status:start|done, label, detail?)  — pipeline progress
        - token      (delta)                                    — streaming text
        - complete   (full response dict)                       — final result
        - need_location (request_id)                            — geolocation request
        - error      (message)                                  — failure

        Pipeline (AI-first):
        Phase 1:  Parallel analysis (classifier + router via asyncio.gather)
        Skip?:    _can_skip_explorers check
        Phase 2:  Location pre-step, parallel explorers (search + data sources)
        Phase 2.5: _derive_hints_from_data, _refine_style_from_data
        Step 3:   Style prompt + micro-context + adaptive routing
        Step 4:   LLM generation (with token streaming + fallback)
        Step 5:   Post-processing (normalize, chart hints, hierarchy, metadata)
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

        # ── Security: sanitize input ──────────────────────────
        injection_hits = _detect_injection(message)
        if injection_hits:
            logger.warning("INJECTION DETECTED  patterns=%s  message=%.200s", injection_hits, message)
        message = _sanitize_for_prompt(message)

        if effective_history:
            for msg in effective_history:
                msg["content"] = _sanitize_for_prompt(msg["content"])

        logger.info(
            "== GENERATE START ==  provider=%s  model=%s  style=%s  perf=%s",
            provider_id, model, content_style, performance_mode,
        )
        logger.info("User message: %s", message[:200])
        logger.info(
            "Tool gates: web_search=%s  geolocation=%s  history=%s  ai_analyzer=%s  data_sources=%s",
            web_search_allowed, geolocation_allowed, history_active, classifier_active, data_sources_allowed,
        )

        perf = PERFORMANCE_MODES.get(performance_mode, PERFORMANCE_MODES["auto"])
        max_body_bytes: Optional[int] = WAF_MAX_BODY_BYTES

        yield {"event": "step", "data": {
            "id": "tools", "status": "done",
            "label": "Tools configured",
            "detail": f"search={web_search_allowed} geo={geolocation_allowed} history={history_active} ai={classifier_active} data={data_sources_allowed}",
        }}

        # ── Phase 1: Parallel Analysis (Classifier + Router) ──
        yield {"event": "step", "data": {"id": "analyzer", "status": "start", "label": "Analyzing intent"}}

        classification: Optional[Dict[str, Any]] = None
        ai_data_queries: List[Dict[str, Any]] = []
        ai_wants_search = False
        ai_wants_location = False
        ai_search_query = ""
        style_id = DEFAULT_STYLE
        style_was_auto = (content_style == "auto")

        if classifier_active:
            async def _noop_router() -> List[Dict[str, Any]]:
                return []

            classify_task = self._classify_intent(message, history=effective_history, performance_mode=performance_mode)
            route_task = self._route_data_sources(message, history=effective_history, performance_mode=performance_mode) if data_sources_allowed else _noop_router()

            classify_result, route_result = await asyncio.gather(
                classify_task,
                route_task,
                return_exceptions=True,
            )

            if isinstance(classify_result, dict):
                classification = classify_result
                if content_style == "auto":
                    style_id = classification["style"]
                else:
                    style_id = content_style
                ai_wants_search = classification["search"]
                ai_wants_location = classification["location"]
                ai_search_query = classification["search_query"]
            else:
                if isinstance(classify_result, Exception):
                    logger.warning("Classifier exception: %s", classify_result)
                if content_style != "auto":
                    style_id = content_style
                else:
                    from content_styles import classify_style
                    style_id = classify_style(message)
                ai_wants_search = should_search(message)
                logger.warning("Classifier failed -> regex fallback: style=%s search=%s", style_id, ai_wants_search)

            if isinstance(route_result, list):
                ai_data_queries = route_result
            elif isinstance(route_result, Exception):
                logger.warning("Router exception: %s — falling back to keywords", route_result)
                ai_data_queries = _fallback_data_sources(message)
        else:
            if content_style != "auto":
                style_id = content_style
            else:
                from content_styles import classify_style
                style_id = classify_style(message)
            ai_wants_search = should_search(message)
            if data_sources_allowed:
                ai_data_queries = _fallback_data_sources(message)
            logger.info("AI disabled -> regex: style=%s search=%s", style_id, ai_wants_search)

        do_search = ai_wants_search and web_search_allowed
        do_location = ai_wants_location and geolocation_allowed

        # ── Budget / performance style overrides ───────────────
        if content_style == "auto" and style_id != "quick":
            if performance_mode == "optimized":
                logger.info("Optimized mode -> downgrading %s -> quick", style_id)
                style_id = "quick"
            elif performance_mode == "auto" and max_body_bytes is not None:
                style_bytes = len(get_system_prompt(style_id).encode("utf-8"))
                if style_bytes > max_body_bytes * 0.75:
                    for fallback in ("content", "quick"):
                        fb_bytes = len(get_system_prompt(fallback).encode("utf-8"))
                        if fb_bytes <= max_body_bytes * 0.75:
                            logger.info("Budget-aware downgrade: %s -> %s", style_id, fallback)
                            style_id = fallback
                            break

        _style_names = {
            "analytical": "Analytical (data dashboards)",
            "content": "Content (narrative)",
            "comparison": "Comparison (side-by-side)",
            "dashboard": "Dashboard (KPI cards & charts)",
            "howto": "How-To (step-by-step)",
            "quick": "Quick Answer (concise)",
        }
        _reasoning_parts = [f"Presentation: {_style_names.get(style_id, style_id)}"]
        if do_search:
            _reasoning_parts.append(f"Web search needed — query: \"{ai_search_query[:80]}\"")
        else:
            _reasoning_parts.append("No web search required")
        if do_location:
            _reasoning_parts.append("Location context will be included")
        if ai_data_queries:
            _ds_names = [q.get("source", "?") for q in ai_data_queries]
            _reasoning_parts.append(f"Data sources: {', '.join(_ds_names)}")

        yield {"event": "step", "data": {
            "id": "analyzer", "status": "done",
            "label": "Intent analyzed",
            "detail": f"style={style_id} search={do_search} location={do_location}",
            "reasoning": " . ".join(_reasoning_parts),
            "result": {"style": style_id, "search": do_search, "location": do_location, "query": ai_search_query},
        }}

        # ── Phase 2 Skip Check ─────────────────────────────────
        skip_explorers = _can_skip_explorers(
            classification, ai_data_queries, content_style, bool(data_context),
        )
        if skip_explorers:
            logger.info("-- SKIP EXPLORERS -- Phase 2 not needed (no search/location/data)")

        # ── Phase 2: Location + Parallel Explorers ─────────────
        augmented_message = message
        search_metadata: Optional[Dict[str, Any]] = None
        search_results_raw: Optional[Dict[str, Any]] = None
        search_images: List[str] = []
        location_context = ""
        location_label = ""
        ds_context = ""
        ds_metadata: Optional[Dict[str, Any]] = None
        ds_active_results: List[Dict[str, Any]] = []

        if not skip_explorers:
            # ── Location pre-step ──────────────────────────────
            if do_location and user_location:
                location_label, location_context = _build_location_context(user_location)
                logger.info("-- LOCATION --  %s", location_label or f"{user_location.get('lat')},{user_location.get('lng')}")
            elif do_location and not user_location:
                loc_request_id = str(uuid.uuid4())
                pending = _PendingLocation()
                _pending_locations[loc_request_id] = pending

                yield {"event": "step", "data": {
                    "id": "geolocation", "status": "start",
                    "label": "Requesting your location",
                    "detail": "Waiting for browser location",
                }}
                yield {"event": "need_location", "data": {"request_id": loc_request_id}}

                try:
                    await asyncio.wait_for(pending.event.wait(), timeout=_LOCATION_TIMEOUT)
                    received_loc = pending.location
                    if received_loc:
                        location_label, location_context = _build_location_context(received_loc)
                        user_location = received_loc
                        yield {"event": "step", "data": {
                            "id": "geolocation", "status": "done",
                            "label": "Location received",
                            "detail": location_label or f"{received_loc.get('lat')}, {received_loc.get('lng')}",
                        }}
                    else:
                        yield {"event": "step", "data": {
                            "id": "geolocation", "status": "done",
                            "label": "Location unavailable",
                            "detail": "Continuing without location",
                        }}
                except asyncio.TimeoutError:
                    yield {"event": "step", "data": {
                        "id": "geolocation", "status": "done",
                        "label": "Location unavailable",
                        "detail": "Timed out",
                    }}
                finally:
                    _pending_locations.pop(loc_request_id, None)

            # ── Parallel explorers (search + data sources) ─────
            async def _explore_search() -> Tuple[Optional[Dict], Optional[Dict], List[str]]:
                """Run web search. Returns (metadata, raw_results, images)."""
                if not do_search:
                    return None, None, []

                search_query = ai_search_query or rewrite_search_query(message, location=location_label)
                if ai_search_query and location_label and location_label.lower() not in search_query.lower():
                    search_query = f"{search_query} {location_label}"

                if not web_search.is_available():
                    return {"searched": False, "reason": "not_configured"}, None, []

                try:
                    raw = await web_search.search(search_query)
                    ctx = web_search.format_for_context(raw)
                    if ctx:
                        imgs = raw.get("images", [])[:6]
                        return {
                            "searched": True, "success": True,
                            "results_count": len(raw.get("results", [])),
                            "images_count": len(imgs), "query": search_query,
                        }, raw, imgs
                    else:
                        return {
                            "searched": True, "success": False,
                            "error": raw.get("error", "unknown"), "query": search_query,
                        }, raw, []
                except Exception as exc:
                    logger.warning("-- SEARCH ERROR -- %s", exc)
                    return {
                        "searched": True, "success": False,
                        "error": "exception", "query": search_query,
                    }, None, []

            async def _explore_data_sources() -> Tuple[str, Optional[Dict], List[Dict]]:
                """Run data source queries. Returns (context, metadata, results)."""
                from data_sources import query_sources, format_results_for_context

                if data_context:
                    passive_blocks: List[str] = []
                    for dc in data_context:
                        label = _sanitize_label(dc.get("label") or dc.get("source") or "External Data")
                        serialized = json.dumps(dc.get("data", {}), default=str, ensure_ascii=False)
                        if len(serialized) > 12_000:
                            serialized = serialized[:12_000] + "\n... (truncated)"
                        passive_blocks.append(f"[Data Source: {label}]\n{serialized}")
                    ctx = "\n".join(passive_blocks)
                    ctx += (
                        "\n\n[INSTRUCTION: The data above comes from live API queries. Use ONLY this data. "
                        "Do NOT supplement with training knowledge or fabricate additional records.]"
                    )
                    return ctx, {"passive": True, "sources": len(data_context)}, []

                if ai_data_queries and data_sources_allowed:
                    results = await query_sources(ai_data_queries)
                    ctx = format_results_for_context(results)
                    successful = [r for r in results if r.get("success")]
                    failed = [r for r in results if not r.get("success")]
                    meta = {
                        "active": True,
                        "queries": len(ai_data_queries),
                        "successful": len(successful),
                        "failed": len(failed),
                    }
                    return ctx, meta, results

                return "", None, []

            if do_search:
                yield {"event": "step", "data": {
                    "id": "search", "status": "start",
                    "label": "Searching the web",
                    "detail": (ai_search_query or message)[:80],
                }}
            if ai_data_queries and data_sources_allowed:
                yield {"event": "step", "data": {
                    "id": "data_sources", "status": "start",
                    "label": "Querying data sources",
                    "detail": f"{len(ai_data_queries)} queries",
                }}

            search_result, ds_result = await asyncio.gather(
                _explore_search(),
                _explore_data_sources(),
                return_exceptions=True,
            )

            if isinstance(search_result, tuple):
                search_metadata, search_results_raw, search_images = search_result
                if search_results_raw and search_metadata and search_metadata.get("success"):
                    ctx = web_search.format_for_context(search_results_raw)
                    if ctx:
                        augmented_message = f"{ctx}\n\nUser question: {message}"
                    yield {"event": "step", "data": {
                        "id": "search", "status": "done",
                        "label": "Search complete",
                        "detail": f"{search_metadata.get('results_count', 0)} results",
                    }}
                elif do_search:
                    yield {"event": "step", "data": {
                        "id": "search", "status": "done",
                        "label": "Search returned no results",
                    }}
                    if search_metadata and not search_metadata.get("success") and search_metadata.get("searched"):
                        augmented_message = f"[SEARCH UNAVAILABLE: Web search failed. Answer from training knowledge only.]\n\n{augmented_message}"
            elif isinstance(search_result, Exception):
                logger.warning("Search explorer exception: %s", search_result)
                if do_search:
                    yield {"event": "step", "data": {"id": "search", "status": "done", "label": "Search failed"}}
                    augmented_message = f"[SEARCH UNAVAILABLE: Web search failed. Answer from training knowledge only.]\n\n{augmented_message}"

            if isinstance(ds_result, tuple):
                ds_context, ds_metadata, ds_active_results = ds_result
                if ds_context:
                    augmented_message = (
                        f"{ds_context}\n\n"
                        "[INSTRUCTION: The data above comes from live API queries. Use ONLY this data. "
                        "Do NOT supplement with training knowledge or fabricate additional records.]\n\n"
                        f"{augmented_message}"
                    )
                if ai_data_queries and data_sources_allowed:
                    successful_count = ds_metadata.get("successful", 0) if ds_metadata else 0
                    yield {"event": "step", "data": {
                        "id": "data_sources", "status": "done",
                        "label": f"Data received ({successful_count} sources)",
                        "detail": f"{sum(r.get('record_count', 0) for r in ds_active_results if r.get('success'))} records",
                    }}
                    if ds_metadata and ds_metadata.get("active") and ds_metadata.get("failed", 0) > 0 and ds_metadata.get("successful", 0) == 0:
                        augmented_message = f"[DATA UNAVAILABLE: All data source queries failed. Answer from training knowledge.]\n\n{augmented_message}"
                    elif ds_metadata and ds_metadata.get("active") and ds_metadata.get("failed", 0) > 0:
                        augmented_message = f"[DATA PARTIALLY UNAVAILABLE: Some data source queries failed.]\n\n{augmented_message}"
            elif isinstance(ds_result, Exception):
                logger.warning("Data source explorer exception: %s", ds_result)
                if ai_data_queries and data_sources_allowed:
                    yield {"event": "step", "data": {"id": "data_sources", "status": "done", "label": "Data sources failed"}}
                    augmented_message = f"[DATA UNAVAILABLE: Data source queries failed. Answer from training knowledge.]\n\n{augmented_message}"

        # ── Phase 2.5: Data-Driven Hints & Style Refinement ────
        from data_sources import get_rules_context

        ai_component_hints, ai_complexity = _derive_hints_from_data(ds_active_results, message)

        refined_style, refine_reason = _refine_style_from_data(
            style_id, ds_active_results, ai_component_hints, style_was_auto,
        )
        if refine_reason:
            logger.info("-- STYLE REFINED -- %s -> %s (%s)", style_id, refined_style, refine_reason)
            style_id = refined_style

        # ── Step 3b: Style prompt setup ───────────────────────
        system_prompt = get_system_prompt(style_id)
        component_priority = get_component_priority(style_id)
        logger.info("-- STYLE --  %s  |  prompt=%dB", style_id, len(system_prompt.encode("utf-8")))

        # ── Step 3c: Micro-context assembly ────────────────────
        from micro_contexts import assemble as assemble_micro_contexts, AVAILABLE_KEYS

        if ai_component_hints:
            valid_hints = [k for k in ai_component_hints if k in AVAILABLE_KEYS]
            if valid_hints:
                micro_budget = 1500 if max_body_bytes else None
                micro_block = assemble_micro_contexts(valid_hints, max_bytes=micro_budget)
                if micro_block:
                    system_prompt = f"{system_prompt}\n\n{micro_block}"
                    logger.info("-- MICRO-CONTEXT --  injected %d fragments: %s", len(valid_hints), valid_hints)

        if max_body_bytes is not None and performance_mode == "auto":
            prompt_bytes = len(system_prompt.encode("utf-8"))
            if prompt_bytes > max_body_bytes * _AUTO_DEGRADE_THRESHOLD:
                max_body_bytes = max(max_body_bytes, prompt_bytes + 1500)

        ds_rules = get_rules_context()
        if ds_rules:
            system_prompt = f"{system_prompt}\n\n{ds_rules}"

        if location_context:
            augmented_message = f"{location_context}{augmented_message}"

        # ── Step 3d: Adaptive model routing ───────────────────
        effective_provider_id = provider_id
        effective_model = model
        effective_provider = provider
        effective_complexity = ai_complexity

        if smart_routing and performance_mode in ("auto", "comprehensive"):
            effective_complexity = _derive_complexity(ai_complexity, ai_component_hints)

            if effective_complexity != "standard":
                route = _find_best_model(provider_id, model, effective_complexity, self.providers)
                if route:
                    new_pid, new_mid = route
                    new_provider = self.get_provider(new_pid)
                    if new_provider:
                        effective_provider_id = new_pid
                        effective_model = new_mid
                        effective_provider = new_provider
                        cross = " (cross-provider)" if new_pid != provider_id else ""
                        logger.info("-- MODEL ROUTE --  %s/%s -> %s/%s  complexity=%s%s",
                                    provider_id, model, new_pid, new_mid, effective_complexity, cross)
                        yield {"event": "step", "data": {
                            "id": "model_upgrade", "status": "start",
                            "label": f"Routing to stronger model ({effective_complexity})",
                            "detail": f"{provider_id}/{model} -> {new_pid}/{new_mid}",
                        }}
                        yield {"event": "step", "data": {
                            "id": "model_upgrade", "status": "done",
                            "label": f"Model routed for {effective_complexity} task",
                            "detail": f"{new_pid}/{new_mid}",
                            "reasoning": f"Task complexity is {effective_complexity}{cross}",
                        }}
            else:
                downgrade = _find_faster_model(provider_id, model, self.providers)
                if downgrade:
                    new_pid, new_mid = downgrade
                    new_provider = self.get_provider(new_pid)
                    if new_provider:
                        effective_provider_id = new_pid
                        effective_model = new_mid
                        effective_provider = new_provider
                        cross = " (cross-provider)" if new_pid != provider_id else ""
                        logger.info("-- MODEL ROUTE (fast) --  %s/%s -> %s/%s%s",
                                    provider_id, model, new_pid, new_mid, cross)
                        yield {"event": "step", "data": {
                            "id": "model_upgrade", "status": "start",
                            "label": "Optimizing for speed",
                            "detail": f"{provider_id}/{model} -> {new_pid}/{new_mid}",
                        }}
                        yield {"event": "step", "data": {
                            "id": "model_upgrade", "status": "done",
                            "label": "Using faster model for simple task",
                            "detail": f"{new_pid}/{new_mid}",
                            "reasoning": f"Standard-complexity task{cross}",
                        }}

        # ── Step 4: LLM generation (with token streaming) ─────
        _COMPLEXITY_TO_EFFORT = {
            "standard": None,
            "moderate": "medium",
            "high": "high",
            "reasoning": "high",
        }
        thinking_effort = _COMPLEXITY_TO_EFFORT.get(effective_complexity) if smart_routing and performance_mode in ("auto", "comprehensive") else None

        yield {"event": "step", "data": {
            "id": "llm", "status": "start",
            "label": "Generating response",
            "detail": f"{effective_provider_id}/{effective_model}" + (f" (thinking: {thinking_effort})" if thinking_effort else ""),
            "reasoning": f"Model: {effective_provider_id}/{effective_model}",
        }}

        logger.info("-- GENERATE --  sending to %s/%s  (%d chars)  effort=%s",
                     effective_provider_id, effective_model, len(augmented_message), thinking_effort)

        llm_t0 = time.time()
        response: Optional[Dict[str, Any]] = None

        # Try streaming first, fall back to non-streaming on error
        try:
            full_content = ""
            async for delta in effective_provider.generate_stream_tokens(
                augmented_message, effective_model, effective_history,
                system_prompt=system_prompt, effort=thinking_effort,
            ):
                full_content += delta
                yield {"event": "token", "data": {"delta": delta}}

            llm_elapsed = time.time() - llm_t0
            response = parse_llm_json(full_content)
        except LLMStreamError as stream_err:
            llm_elapsed = time.time() - llm_t0
            logger.warning("Stream error after %.1fs — using error response", llm_elapsed)
            response = stream_err.error_response
        except Exception as exc:
            llm_elapsed = time.time() - llm_t0
            logger.warning("Stream failed after %.1fs: %s — falling back to non-streaming", llm_elapsed, exc)
            try:
                response = await effective_provider.generate(
                    augmented_message, effective_model, effective_history,
                    system_prompt=system_prompt, effort=thinking_effort,
                )
                llm_elapsed = time.time() - llm_t0
            except Exception as gen_exc:
                llm_elapsed = time.time() - llm_t0
                logger.error("Non-streaming fallback also failed: %s", gen_exc)
                response = _error_response(
                    "Generation Failed",
                    "Both streaming and non-streaming generation failed. Please try again.",
                )

        # Model fallback: if generation produced an error, try a different model (max 1 retry)
        if response and response.get("_is_error") and smart_routing:
            logger.info("-- MODEL FALLBACK -- primary generation returned error, trying alternate model")
            alt_route = _find_best_model(effective_provider_id, effective_model, "standard", self.providers)
            if alt_route:
                alt_pid, alt_mid = alt_route
                alt_provider = self.get_provider(alt_pid)
                if alt_provider and (alt_pid != effective_provider_id or alt_mid != effective_model):
                    try:
                        response = await alt_provider.generate(
                            augmented_message, alt_mid, effective_history,
                            system_prompt=system_prompt,
                        )
                        effective_provider_id = alt_pid
                        effective_model = alt_mid
                        effective_provider = alt_provider
                        llm_elapsed = time.time() - llm_t0
                        logger.info("-- MODEL FALLBACK OK -- %s/%s succeeded", alt_pid, alt_mid)
                    except Exception as fb_exc:
                        logger.warning("Model fallback also failed: %s", fb_exc)

        logger.info(
            "-- RESPONSE --  text=%d chars  a2ui=%s  components=%d  elapsed=%.1fs",
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

        # Refusal guard
        response = await _retry_on_refusal(
            response, message,
            lambda msg, hist: effective_provider.generate(
                msg, effective_model, hist, system_prompt=system_prompt,
            ),
        )

        # ── Step 5: Post-processing ──────────────────────────
        response = _normalize_a2ui_components(response)
        response = _apply_chart_hints(response, ds_active_results)
        response = _normalize_suggestions(response)
        response = _enforce_visual_hierarchy(response, component_priority)

        if search_metadata:
            response["_search"] = search_metadata
            if search_results_raw and search_results_raw.get("results"):
                response["_sources"] = [
                    {"title": r.get("title", ""), "url": r.get("url", "")}
                    for r in search_results_raw["results"][:8]
                    if r.get("url")
                ]
        if user_location and do_location:
            response["_location"] = True

        if search_images and _wants_images(message):
            response["_images"] = search_images
        elif search_images:
            logger.info("-- IMAGES --  suppressed %d images (query not visual)", len(search_images))

        if ds_metadata:
            response["_data_sources"] = ds_metadata
            if ds_metadata.get("active") and ds_metadata.get("successful", 0) > 0:
                ds_source_entries = [
                    {"title": r.get("_source_name", r.get("_source_id", "Data")), "url": "", "type": "data"}
                    for r in ds_active_results if r.get("success")
                ]
                response.setdefault("_sources", []).extend(ds_source_entries)
            elif ds_metadata.get("passive"):
                passive_entries = [
                    {"title": dc.get("label") or dc.get("source", "Data"), "url": "", "type": "data"}
                    for dc in (data_context or [])
                ]
                response.setdefault("_sources", []).extend(passive_entries)

        response["_style"] = style_id
        response["_performance"] = performance_mode
        response["_model"] = effective_model
        response["_provider"] = effective_provider_id
        if effective_model != model or effective_provider_id != provider_id:
            response["_model_upgraded_from"] = model
            response["_provider_upgraded_from"] = provider_id

        # Remove internal flag before sending to client
        response.pop("_is_error", None)

        logger.info(
            "== GENERATE DONE ==  style=%s  model=%s/%s  keys=%s",
            style_id, effective_provider_id, effective_model, list(response.keys()),
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
        smart_routing: bool = True,
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
            smart_routing=smart_routing,
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


# ── Module-level singleton ─────────────────────────────────────

llm_service = LLMService()
