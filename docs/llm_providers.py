"""
LLM Providers for A2UI

Enterprise LiteLLM gateway (Exploration Lab) — the ONLY provider
for this project.  All models (Claude via Bedrock, GPT, o-series)
are accessed through the LiteLLM OpenAI-compatible gateway.

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

import httpx
import openai

from content_styles import (
    CONTENT_STYLES,
    DEFAULT_STYLE,
    STYLE_DESCRIPTIONS,
    VALID_STYLE_IDS,
    get_component_priority,
    get_system_prompt,
)

logger = logging.getLogger(__name__)


# ── Pending-location store ─────────────────────────────────────
# When the analyzer decides location is needed but the frontend hasn't
# provided it, the pipeline emits a `need_location` SSE event and pauses
# on an asyncio.Event.  The frontend POSTs the location to
# /api/provide-location/{request_id}, which sets the event and stores the
# result here so the pipeline can resume.

_LOCATION_TIMEOUT = 15  # seconds to wait for frontend to provide location

class _PendingLocation:
    """Holds an asyncio.Event + optional location dict for one request."""
    __slots__ = ("event", "location")
    def __init__(self) -> None:
        self.event = asyncio.Event()
        self.location: Optional[Dict[str, Any]] = None

# request_id → _PendingLocation
_pending_locations: Dict[str, _PendingLocation] = {}


def provide_location(request_id: str, location: Optional[Dict[str, Any]]) -> bool:
    """Called from the /api/provide-location endpoint to unblock the pipeline."""
    pending = _pending_locations.get(request_id)
    if not pending:
        return False
    pending.location = location
    pending.event.set()
    return True


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


# ── Utilities ──────────────────────────────────────────────────


def _build_messages(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    max_body_bytes: Optional[int] = None,
    system_prompt: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Build an OpenAI-style messages array with history trimming.

    When ``max_body_bytes`` is set, history is trimmed oldest-first
    to fit within the budget.  The system prompt and user message
    are NEVER truncated — they should be kept lean at the source.

    ``None`` (default) = unlimited, no trimming.
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
    # Infrastructure errors (403, timeout, etc.) are NOT refusals — skip them.
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
        "_is_error": True,  # infrastructure error — NOT an LLM refusal
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


# ── Type aliases the LLM frequently uses instead of canonical A2UI types ──
_TYPE_ALIASES = {
    "table": "data-table", "datatable": "data-table",
    "stats": "stats", "stat-grid": "stats", "stat_grid": "stats", "statgrid": "stats", "stats_grid": "stats", "stats-grid": "stats",
}


def _normalize_a2ui_components(result: Dict[str, Any]) -> Dict[str, Any]:
    """Fix common LLM output quirks in A2UI components **in-place**.

    Runs after LLM generation, before the response is sent to the client.
    Keeps the frontend renderer dumb and simple.

    Fixes applied:
    1. Type aliases (table → data-table)
    2. Missing ``props`` wrapper — lift top-level keys into props
    3. Chart semantic data → Chart.js {labels, datasets} format
    4. data-table missing ``columns`` → auto-generate from data keys
    5. Alert ``message`` → ``description``
    6. ``stats`` type → individual ``stat`` children in a ``grid``
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

    # ── Ensure props exists (LLM sometimes uses "config" instead) ──
    props = comp.get("props")
    if not props or not isinstance(props, dict):
        props = comp.get("config") or {}
        if not isinstance(props, dict):
            props = {}
        # Lift any other top-level keys into props
        for k, v in list(comp.items()):
            if k not in _RESERVED_KEYS and k != "config":
                props[k] = v
        comp["props"] = props
        comp.pop("config", None)

    # ── Lift children out of props (LLM nests them incorrectly) ──
    if "children" in props and "children" not in comp:
        comp["children"] = props.pop("children")

    # ── Chip: text → label (LLM often uses "text" instead of "label") ──
    if ctype == "chip" and props.get("text") and not props.get("label"):
        props["label"] = props.pop("text")

    # ── Alert: message → description ──
    if ctype == "alert" and props.get("message") and not props.get("description"):
        props["description"] = props.pop("message")

    # ── data-table: normalize columns/data ──
    if ctype == "data-table":
        # Handle headers+rows (array-of-arrays) → columns+data (array-of-objects)
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
                # Auto-generate columns from data keys when missing
                props["columns"] = [{"key": k, "label": k} for k in rows[0].keys()]
            elif isinstance(columns, list) and columns:
                # FIX: LLM generated columns with keys that don't match the
                # actual data row keys (e.g. columns say "claim_number" but
                # data rows use "ClaimNumber"). Re-derive columns from data.
                col_keys = {(c.get("key") if isinstance(c, dict) else c) for c in columns}
                if not col_keys & data_keys:
                    # Zero overlap → columns are useless, regenerate from data
                    props["columns"] = [{"key": k, "label": k.replace("_", " ").replace("-", " ").title()} for k in rows[0].keys()]

    # ── stats → expand to stat children inside a grid ──
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

    # ── Chart: semantic data → Chart.js ──
    if ctype == "chart":
        _normalize_chart_data(props)

    # ── Recurse into children ──────────────────────────────────
    # Grid, card, container children all need the same normalization
    # (type aliases, prop fixes, chart data). Without this, nested
    # components like pillar-card sparklines never get normalized.
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
    """Convert semantic chart rows into Chart.js {labels, datasets} format.

    Supports two LLM patterns:
      A) props.data = [{row}, ...], props.xAxis/yAxisLeft/yAxisRight
      B) props.data = {series:[...], data:[...], x_axis:{field}}
    Skips if data already has ``datasets`` (already Chart.js format).
    """
    raw = props.get("data")
    if not raw:
        return

    # Already Chart.js?
    if isinstance(raw, dict) and isinstance(raw.get("datasets"), list):
        return

    rows: Optional[List[Dict]] = None
    series: List[Dict] = []
    x_field = ""

    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        # Format A: flat row array at props.data
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
        # Format B: nested data object
        rows = raw.get("data") if isinstance(raw.get("data"), list) else None
        series = raw.get("series", [])
        xa = raw.get("x_axis") or raw.get("xAxis") or {}
        x_field = xa.get("field", "") if isinstance(xa, dict) else ""
        if raw.get("title") and not props.get("title"):
            props["title"] = raw["title"]

    if not rows:
        return

    # Auto-detect x-axis field (first string column)
    if not x_field:
        for k, v in rows[0].items():
            if isinstance(v, str):
                x_field = k
                break
    if not x_field:
        return

    # Auto-detect series (all numeric columns) if none provided
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

    # Set chartType
    ct = str(props.get("type", "bar"))
    if "line" in ct and "bar" not in ct:
        props["chartType"] = props.get("chartType", "line")
    else:
        props["chartType"] = props.get("chartType", "bar")

    # Dual-axis options
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

    # Clean semantic keys
    for k in ("xAxis", "x_axis", "yAxisLeft", "y_axis_left", "yAxisRight", "y_axis_right", "series"):
        props.pop(k, None)


# ── Chart-hint enforcement ────────────────────────────────────────────
def _apply_chart_hints(
    response: Dict[str, Any],
    ds_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Use ``chart_hint`` from data-source responses to build/fix charts.

    The LLM is non-deterministic — sometimes it creates a dual-axis bar+line
    combo chart, sometimes just a line chart.  If the data source response
    contains a ``chart_hint``, we **deterministically** build the correct
    Chart.js data and replace whatever the LLM produced.
    """
    if not ds_results:
        return response

    # Collect all chart_hints + their associated data rows
    hints: List[Dict[str, Any]] = []
    for r in ds_results:
        if not r.get("success"):
            continue
        payload = r.get("data")
        if not isinstance(payload, dict):
            continue
        hint = payload.get("chart_hint")
        rows = payload.get("data")
        if hint and isinstance(hint, dict) and isinstance(rows, list) and rows:
            hints.append({"hint": hint, "rows": rows})

    if not hints:
        return response

    a2ui = response.get("a2ui")
    if not a2ui or not isinstance(a2ui, dict):
        return response

    components = a2ui.get("components")
    if not isinstance(components, list):
        return response

    for h in hints:
        hint = h["hint"]
        rows = h["rows"]

        x_axis = hint.get("x_axis") or {}
        x_field = x_axis.get("field", "")
        x_label = x_axis.get("label", "")
        if not x_field:
            continue

        labels = [str(row.get(x_field, "")) for row in rows]
        datasets: List[Dict[str, Any]] = []

        # Left-axis bars
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
        # Left-axis single field (no stacked_bars)
        if not datasets and y_left.get("field"):
            datasets.append({
                "label": y_left_label or y_left["field"].replace("_", " ").title(),
                "data": [row.get(y_left["field"], 0) for row in rows],
                "yAxisID": "y",
            })

        # Right-axis line
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

        # Find and replace existing chart, or append a new one
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
    """Ensure ``suggestions`` is always a flat list of strings.

    The LLM sometimes emits objects like ``{"text":"...","label":"..."}``
    instead of plain strings — this causes ``[object Object]`` on the frontend.
    """
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
        # Skip non-string, non-dict items
    response["suggestions"] = normalized
    return response


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
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Generate a response for the given message with optional history.

        Args:
            effort: Thinking effort level for models that support adaptive
                    thinking ("low", "medium", "high", "max"). None = provider default.
            max_tokens: Override the default max output tokens.
                Hybrid-tier dashboards pass a lower value for speed.
            temperature: Override the default temperature (0.7).
                Hybrid-tier uses 0.0 for deterministic, faster output.
        """

    async def generate_stream_tokens(
        self,
        message: str,
        model: str,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        effort: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
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
            max_tokens=max_tokens, temperature=temperature,
        )
        if result.get("_is_error"):
            raise LLMStreamError(result)
        # Yield the entire raw JSON as one chunk (non-streaming fallback)
        yield json.dumps(result)
        return  # noqa: B901 — explicit return in async generator


# ── Provider Implementations ──────────────────────────────────


class LiteLLMProvider(LLMProvider):
    """Exploration Lab provider — OpenAI SDK pointed at the LiteLLM gateway."""

    name = "Exploration Lab"

    # Enterprise gateway WAF rejects JSON request bodies >~8 KB with a bare
    # HTML 403.  This limit is checked AFTER JSON serialization (not on raw
    # content bytes) so that escape-character overhead is included.
    _GATEWAY_MAX_BODY_BYTES = 7500  # Actual WAF rejects at ~7,950; safe margin

    # ⚠️ Model IDs must match the enterprise LiteLLM gateway catalog.
    # If a model returns "Empty Response", the ID doesn't match the gateway.
    # Check gateway /models endpoint for exact IDs.
    # ⚠️ These IDs are verified against the enterprise LiteLLM gateway
    # via: curl -sk $BASE_URL/models -H "Authorization: Bearer $KEY"
    # Claude first: better token efficiency (prompt caching, adaptive thinking),
    # structured JSON output, and competitive reasoning — preferred for Auto mode.
    models = [
        # Claude via Bedrock gateway (efficient token usage, adaptive thinking)
        {"id": "us.anthropic.claude-sonnet-4-20250514-v1:0", "name": "Claude 4 Sonnet"},
        {"id": "claude-sonnet-4-5-20250929", "name": "Claude 4.5 Sonnet"},
        {"id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0", "name": "Claude 3.7 Sonnet"},
        {"id": "us.anthropic.claude-3-5-sonnet-20240620-v1:0", "name": "Claude 3.5 Sonnet"},
        {"id": "us.anthropic.claude-3-5-haiku-20241022-v1:0", "name": "Claude 3.5 Haiku (Fast)"},
        # GPT-4.1 Series
        {"id": "gpt-4.1", "name": "GPT-4.1"},
        {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini (Fast)"},
        {"id": "gpt-4.1-nano", "name": "GPT-4.1 Nano (Fast)"},
        # GPT-4o Series
        {"id": "gpt-4o", "name": "GPT-4o"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini (Fast)"},
        # Reasoning models
        {"id": "o4-mini", "name": "o4 Mini (Reasoning)"},
        {"id": "o3", "name": "o3 (Reasoning)"},
        {"id": "o3-mini", "name": "o3 Mini (Reasoning)"},
    ]

    BASE_URL = "https://litellm.ai-coe-test.aws.evernorthcloud.com/v1"

    def __init__(self) -> None:
        self._api_key = os.getenv("LITELLM_API_KEY")
        self._client: Optional[openai.AsyncOpenAI] = None

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def warm_up(self) -> None:
        """Fire a lightweight GET /models to wake up the enterprise gateway.

        The LiteLLM Bedrock gateway has a cold-start latency of 10-40 s.
        Hitting /models on startup warms the TLS connection and the gateway's
        internal routing so the first real LLM call doesn't pay that penalty.
        """
        if not self.is_available():
            return
        import httpx
        try:
            async with httpx.AsyncClient(verify=False, timeout=15.0) as c:
                resp = await c.get(
                    f"{self.BASE_URL}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                logger.info(
                    "Gateway warm-up: GET /models → %d (%d models)",
                    resp.status_code,
                    len(resp.json().get("data", [])) if resp.status_code == 200 else 0,
                )
        except Exception as exc:
            logger.warning("Gateway warm-up failed (non-blocking): %s", exc)

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
                timeout=120.0,
                max_retries=0,
                http_client=httpx.AsyncClient(verify=False, timeout=120.0),
            )
        return self._client

    _MAX_403_RETRIES = 2
    _RETRY_DELAYS = (1.0, 3.0)  # seconds between retries

    async def _call_llm(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens_override: Optional[int] = None,
        temperature_override: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Make a single LLM call and return parsed JSON or error dict.

        Retries up to ``_MAX_403_RETRIES`` times on transient 403 errors from
        the gateway (which are intermittent when the VPN connection is flaky).

        Args:
            max_tokens_override: If set, use this instead of the default 4000.
                Hybrid-tier dashboards pass style-specific values (4096-8192)
                to ensure output is NEVER truncated.
            temperature_override: If set, use this instead of the default 0.7.
                Hybrid-tier uses 0.0 for deterministic output and lower latency.
        """
        # Claude models don't support response_format parameter
        # Gateway uses Bedrock-style IDs like "us.anthropic.claude-..."
        is_claude = "claude" in model.lower()
        # o-series reasoning models don't support temperature and use max_completion_tokens
        is_reasoning = model.startswith("o1") or model.startswith("o3") or model.startswith("o4")
        # GPT-5+ uses max_completion_tokens and only supports temperature=1
        is_gpt5 = model.startswith("gpt-5")

        call_params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        # Reasoning models & GPT-5: no temperature, use max_completion_tokens
        if is_reasoning or is_gpt5:
            call_params["max_completion_tokens"] = 16384
        else:
            call_params["temperature"] = temperature_override if temperature_override is not None else 0.7
            call_params["max_tokens"] = max_tokens_override or 4000

        # Only add response_format for non-Claude, non-reasoning models
        # GPT-5 DOES support json_object (OpenAI provider uses it successfully)
        if not is_claude and not is_reasoning:
            call_params["response_format"] = {"type": "json_object"}

        # ── Log body size for monitoring (no truncation) ──
        _body_size = self._json_body_size(call_params)
        _waf_limit = self._GATEWAY_MAX_BODY_BYTES
        logger.info("Exploration Lab body size: %d bytes (gateway limit: %d)", _body_size, _waf_limit)
        if _body_size > _waf_limit:
            logger.warning(
                "⚠️ Body exceeds WAF limit by %d bytes — will likely 403. "
                "Reduce system prompt or user context instead of truncating.",
                _body_size - _waf_limit,
            )

        for attempt in range(1 + self._MAX_403_RETRIES):
            try:
                logger.info("Exploration Lab request: model=%s, params=%s%s",
                            model,
                            {k: v for k, v in call_params.items() if k != "messages"},
                            f"  (retry {attempt})" if attempt > 0 else "")
                response = await self.client.chat.completions.create(**call_params)
                logger.info("Exploration Lab raw response: model=%s, choices=%d, finish_reason=%s",
                            model, len(response.choices) if response.choices else 0,
                            response.choices[0].finish_reason if response.choices else "N/A")
                break  # success — fall through to response handling
            except openai.PermissionDeniedError as exc:
                exc_body = str(exc)
                is_waf = "<html>" in exc_body.lower() or "403 forbidden" in exc_body.lower()

                if is_waf:
                    # WAF body-size block — retries won't help, fail immediately
                    logger.error(
                        "Exploration Lab WAF 403 (%s) — request body %d bytes likely exceeds gateway limit (%d). "
                        "Reduce prompt/message size.",
                        model, _body_size, _waf_limit,
                    )
                    return _error_response(
                        "Gateway Capacity Limit Reached",
                        "Your request exceeded the enterprise gateway's size limit. "
                        "This typically happens when there is too much conversation history or context data. "
                        "Try starting a new conversation or asking a shorter question. "
                        "This is an infrastructure limitation, not an issue with your query.",
                        variant="warning",
                    )

                if attempt < self._MAX_403_RETRIES:
                    delay = self._RETRY_DELAYS[attempt]
                    logger.warning(
                        "Exploration Lab 403 (%s) — transient, retrying in %.1fs  (attempt %d/%d)",
                        model, delay, attempt + 1, self._MAX_403_RETRIES,
                    )
                    await asyncio.sleep(delay)
                    continue
                # All retries exhausted
                logger.error("Exploration Lab 403 (%s) — all %d retries exhausted: %s",
                             model, self._MAX_403_RETRIES, exc)
                return _error_response(
                    "Model Access Restricted",
                    f"The model '{model}' is temporarily unavailable on the enterprise gateway. "
                    "This may be due to access policies or gateway maintenance. "
                    "Try selecting a different model from the dropdown.",
                )
            except openai.AuthenticationError as exc:
                logger.error("Exploration Lab auth error (%s): %s", model, exc)
                return _error_response(
                    "Authentication Error",
                    "Your Exploration Lab API key is invalid or expired. Please check LITELLM_API_KEY.",
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
        else:
            # for/else: loop completed without break — all retries exhausted
            logger.error("Exploration Lab exhausted retries (%s)", model)
            return _error_response(
                "Access Denied",
                f"The model '{model}' is not available on the Exploration Lab gateway after retries. "
                "Try a different model, or check that you're on the corporate network/VPN.",
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

    # ── Streaming variant of _call_llm ─────────────────────────────

    async def _call_llm_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens_override: Optional[int] = None,
        temperature_override: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming variant of ``_call_llm`` — yields token deltas.

        Same parameter construction and error handling as ``_call_llm``,
        but adds ``stream=True`` and yields each content delta as a ``str``.

        Raises ``LLMStreamError`` on any provider / gateway error.
        """
        is_claude = "claude" in model.lower()
        is_reasoning = model.startswith("o1") or model.startswith("o3") or model.startswith("o4")
        is_gpt5 = model.startswith("gpt-5")

        call_params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        if is_reasoning or is_gpt5:
            call_params["max_completion_tokens"] = 16384
        else:
            call_params["temperature"] = temperature_override if temperature_override is not None else 0.7
            call_params["max_tokens"] = max_tokens_override or 4000

        if not is_claude and not is_reasoning:
            call_params["response_format"] = {"type": "json_object"}

        _body_size = self._json_body_size({k: v for k, v in call_params.items() if k != "stream"})
        _waf_limit = self._GATEWAY_MAX_BODY_BYTES
        logger.info("Exploration Lab STREAM body size: %d bytes (gateway limit: %d)", _body_size, _waf_limit)
        if _body_size > _waf_limit:
            logger.warning(
                "⚠️ Body exceeds WAF limit by %d bytes — will likely 403.",
                _body_size - _waf_limit,
            )

        # ── Establish the stream (retries only apply to connection errors) ──
        stream = None
        for attempt in range(1 + self._MAX_403_RETRIES):
            try:
                logger.info(
                    "Exploration Lab STREAM request: model=%s, params=%s%s",
                    model,
                    {k: v for k, v in call_params.items() if k not in ("messages", "stream")},
                    f"  (retry {attempt})" if attempt > 0 else "",
                )
                stream = await self.client.chat.completions.create(**call_params)
                break
            except openai.PermissionDeniedError as exc:
                exc_body = str(exc)
                is_waf = "<html>" in exc_body.lower() or "403 forbidden" in exc_body.lower()
                if is_waf:
                    raise LLMStreamError(_error_response(
                        "Gateway Capacity Limit Reached",
                        "Your request exceeded the enterprise gateway's size limit. "
                        "Try starting a new conversation or asking a shorter question.",
                        variant="warning",
                    ))
                if attempt < self._MAX_403_RETRIES:
                    await asyncio.sleep(self._RETRY_DELAYS[attempt])
                    continue
                raise LLMStreamError(_error_response(
                    "Model Access Restricted",
                    f"The model '{model}' is temporarily unavailable on the enterprise gateway. "
                    "Try selecting a different model.",
                ))
            except openai.AuthenticationError:
                raise LLMStreamError(_error_response(
                    "Authentication Error",
                    "Your Exploration Lab API key is invalid or expired. Please check LITELLM_API_KEY.",
                ))
            except openai.NotFoundError:
                raise LLMStreamError(_error_response(
                    "Model Not Found",
                    f"The model '{model}' was not found on the Exploration Lab gateway. Try a different model.",
                ))
            except openai.RateLimitError:
                raise LLMStreamError(_error_response(
                    "Rate Limited",
                    "Too many requests. Please wait a moment and try again.",
                    variant="warning",
                ))
            except openai.APITimeoutError:
                raise LLMStreamError(_error_response(
                    "Request Timeout",
                    "The model took too long to respond. Try again or switch to a faster model.",
                    variant="warning",
                ))
            except openai.APIError:
                raise LLMStreamError(_error_response(
                    "Something Went Wrong",
                    "The AI service returned an error. Please try again in a moment.",
                ))

        if stream is None:
            raise LLMStreamError(_error_response(
                "Access Denied",
                f"The model '{model}' is not available after retries. "
                "Try a different model, or check that you're on the corporate network/VPN.",
            ))

        # ── Yield token deltas from the stream ──
        try:
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:
            logger.error("Exploration Lab stream interrupted (%s): %s", model, exc)
            raise LLMStreamError(_error_response(
                "Stream Interrupted",
                "The response stream was interrupted. Please try again.",
                variant="warning",
            ))

    # ── Post-serialization body enforcement ──────────────────────
    @staticmethod
    def _json_body_size(call_params: Dict[str, Any]) -> int:
        """Return the byte length of the JSON-serialized request body."""
        return len(json.dumps(call_params).encode("utf-8"))

    # NOTE: _enforce_gateway_limit was REMOVED.
    # Instead of truncating content to fit under the WAF limit, we now keep
    # system prompts lean (~2 KB) and only send relevant context/data.
    # The WAF limit is the limit — if we hit it, we need to optimize what
    # we're sending, not silently destroy it.

    async def generate(
        self,
        message: str,
        model: str = "us.anthropic.claude-sonnet-4-20250514-v1:0",
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        effort: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        # Build messages WITHOUT a raw-byte budget — the post-serialization
        # check below (_enforce_gateway_limit) handles size correctly.
        messages = _build_messages(message, history, system_prompt=system_prompt)
        result = await self._call_llm(messages, model, max_tokens_override=max_tokens, temperature_override=temperature)

        # Refusal guard — retry with stronger nudge (no history to save space)
        return await _retry_on_refusal(
            result, message,
            lambda msg, hist: self._call_llm(
                _build_messages(msg, hist, system_prompt=system_prompt),
                model,
                max_tokens_override=max_tokens,
                temperature_override=temperature,
            ),
        )

    async def generate_stream_tokens(
        self,
        message: str,
        model: str = "us.anthropic.claude-sonnet-4-20250514-v1:0",
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        effort: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """Yield raw token deltas from the LLM as they arrive.

        The caller is responsible for accumulating the full content,
        parsing JSON, and running post-processing.

        Raises ``LLMStreamError`` on provider errors.
        """
        messages = _build_messages(message, history, system_prompt=system_prompt)
        async for delta in self._call_llm_stream(
            messages, model,
            max_tokens_override=max_tokens,
            temperature_override=temperature,
        ):
            yield delta


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
#   1. Intent Classifier  — style, search, location, components, complexity
#   2. Data Source Router  — which data sources / endpoints / params to query
#
# Each has its own system prompt, user prompt template, and max_tokens.
# Both share the same model list (_ANALYZER_MODELS) and temperature=0.


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
    # ⚠️ LiteLLM gateway ONLY — no direct OpenAI/Anthropic providers.
    # Verified working on enterprise gateway (2026-02-27):
    #   - claude-sonnet-4       ✅ 200 OK  (preferred — consistent structured JSON)
    #   - gpt-4.1               ✅ 200 OK
    # 403 Forbidden on the gateway:
    #   - claude-3-5-haiku      ❌ 403 (inconsistent)
    #   - gpt-4.1-mini          ❌ 403
    #   - gpt-4o-mini           ❌ 403
    # To re-check: curl -H "Authorization: Bearer $LITELLM_API_KEY" \
    #   https://litellm.ai-coe-test.aws.evernorthcloud.com/models
    ("litellm", "us.anthropic.claude-sonnet-4-20250514-v1:0"),    # Claude Sonnet 4 — best structured JSON
    ("litellm", "gpt-4.1"),                                       # GPT-4.1 fallback
]


def _fallback_data_sources(message: str) -> List[Dict[str, Any]]:
    """Keyword-based data source matching — safety net when the AI analyzer fails.

    Scans the registered REST data sources for endpoint keywords that match
    the user's query.  Returns a list of query dicts in the same format the
    AI analyzer would produce:
        [{"source": "...", "endpoint": "/...", "params": {}}]

    Only the BEST matching endpoint per source is returned (highest keyword
    overlap) to avoid flooding the pipeline with irrelevant queries.

    When the user explicitly mentions "genie" (case-insensitive), the Genie
    endpoint receives a large score boost so it always wins over other matches.
    """
    from data_sources import get_all_sources
    from data_sources.rest import RESTDataSource

    query_lower = message.lower()
    results: List[Dict[str, Any]] = []

    genie_mentioned = "genie" in query_lower

    for source in get_all_sources():
        if not source.is_available() or not isinstance(source, RESTDataSource):
            continue

        best_ep = None
        best_score = 0

        for ep in source._endpoints:
            if not ep.keywords:
                continue
            score = sum(1 for kw in ep.keywords if kw.lower() in query_lower)

            if genie_mentioned and any(k.lower() == "genie" for k in ep.keywords):
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
                "── DATA SOURCE FALLBACK ──  matched %s %s %s  (score=%d keywords%s)",
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
# Speed is king — a slow model is a broken model. Cross-provider
# routing via LiteLLM is preferred over slow same-provider models.
#
# Complexity tiers:
#   "standard"  — no upgrade needed (text, simple charts)
#   "moderate"  — structured data, multi-dataset charts
#   "high"      — complex viz (matrix, sankey, treemap), deep analysis
#   "reasoning" — multi-step math, logic chains, statistical analysis

# Speed scores: lower = faster = better
_SPEED_SCORE = {"fast": 0, "medium": 1, "slow": 2}

_MODEL_ROSTER: List[Dict[str, Any]] = [
    # ⚠️ LiteLLM gateway ONLY — all models accessed through the enterprise gateway.
    #
    # ── Claude models first: better token efficiency (prompt caching,
    # adaptive thinking with effort levels), strong structured JSON,
    # and competitive reasoning. Preferred for Auto mode routing. ──
    {"provider": "litellm",  "model": "us.anthropic.claude-sonnet-4-20250514-v1:0",   "tier": 4, "tags": {"structured", "reasoning", "creative"}, "speed": "medium"},
    {"provider": "litellm",  "model": "claude-sonnet-4-5-20250929",                   "tier": 4, "tags": {"structured", "reasoning", "creative"}, "speed": "medium"},
    {"provider": "litellm",  "model": "us.anthropic.claude-3-7-sonnet-20250219-v1:0", "tier": 3, "tags": {"structured", "reasoning", "creative"}, "speed": "medium"},
    {"provider": "litellm",  "model": "us.anthropic.claude-3-5-sonnet-20240620-v1:0", "tier": 2, "tags": {"structured"},                           "speed": "medium"},
    {"provider": "litellm",  "model": "us.anthropic.claude-3-5-haiku-20241022-v1:0",  "tier": 1, "tags": set(),                                    "speed": "fast"},

    # ── GPT models: fast speed, good for simple tasks ──
    {"provider": "litellm",  "model": "gpt-4.1",                                      "tier": 2, "tags": set(),                                    "speed": "fast"},
    {"provider": "litellm",  "model": "gpt-4o",                                       "tier": 2, "tags": set(),                                    "speed": "fast"},
    {"provider": "litellm",  "model": "gpt-4.1-mini",                                 "tier": 1, "tags": set(),                                    "speed": "fast"},
    {"provider": "litellm",  "model": "gpt-4.1-nano",                                 "tier": 1, "tags": set(),                                    "speed": "fast"},
    {"provider": "litellm",  "model": "gpt-4o-mini",                                  "tier": 1, "tags": set(),                                    "speed": "fast"},

    # ── Reasoning specialists (o-series) ──
    {"provider": "litellm",  "model": "o3",                                            "tier": 3, "tags": {"reasoning"},                            "speed": "medium"},
    {"provider": "litellm",  "model": "o4-mini",                                       "tier": 3, "tags": {"reasoning"},                            "speed": "medium"},
    {"provider": "litellm",  "model": "o3-mini",                                       "tier": 3, "tags": {"reasoning"},                            "speed": "medium"},
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


# ── Data-Aware Hint Derivation ─────────────────────────────────
#
# Instead of guessing component hints and complexity blindly in the
# classifier (before data is fetched), we derive them deterministically
# from the actual data source responses.  This means:
#   • chart_hint metadata from data analysts drives micro-context injection
#   • Complexity is based on real data characteristics, not query text
#   • For non-data queries, regex catches explicit exotic chart keywords
#   • Zero extra LLM calls — pure dict inspection, ~0ms

# chart_hint.chart_type → micro-context key mapping.
# None = standard chart type, no exotic micro-context needed.
_CHART_TYPE_TO_HINT: Dict[str, Optional[str]] = {
    # Standard types (handled by base prompt, no micro-context needed)
    "stacked_bar_with_line": None,
    "bar_with_line":         None,
    "bar":                   None,
    "stacked_bar":           None,
    "line":                  None,
    "multi_line":            None,
    "donut":                 None,
    "table":                 None,
    "horizontal_grouped_bar": None,
    # Exotic types that DO need micro-contexts
    "matrix":      "chart_matrix",
    "heatmap":     "chart_matrix",
    "treemap":     "chart_treemap",
    "sankey":      "chart_sankey",
    "funnel":      "chart_funnel",
    "radar":       "chart_radar",
    "scatter":     "chart_scatter",
    "bubble":      "chart_scatter",
}

# Regex patterns for exotic chart keywords in non-data queries
_EXOTIC_CHART_PATTERNS: Dict[str, re.Pattern] = {
    "chart_matrix":  re.compile(r"\b(?:heatmap|heat\s*map|matrix|correlation\s*matrix)\b", re.IGNORECASE),
    "chart_treemap": re.compile(r"\b(?:treemap|tree\s*map)\b", re.IGNORECASE),
    "chart_sankey":  re.compile(r"\b(?:sankey|flow\s*diagram|alluvial)\b", re.IGNORECASE),
    "chart_funnel":  re.compile(r"\b(?:funnel|conversion\s*funnel|sales\s*pipeline)\b", re.IGNORECASE),
    "chart_radar":   re.compile(r"\b(?:radar|spider\s*chart|star\s*chart)\b", re.IGNORECASE),
    "chart_scatter": re.compile(r"\b(?:scatter|bubble\s*chart|correlation\s*plot)\b", re.IGNORECASE),
}


def _derive_hints_from_data(
    ds_results: List[Dict[str, Any]],
    query: str,
) -> Tuple[List[str], str]:
    """Derive component hints and complexity from ACTUAL data, not blind guessing.

    For data-source queries: inspects ``chart_hint`` metadata from API
    responses to determine which exotic micro-contexts are needed and how
    complex the visualization is.

    For non-data queries (no ``ds_results``): falls back to regex detection
    of exotic chart keywords in the query text.

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

        # Map chart_type to micro-context key
        if chart_type in _CHART_TYPE_TO_HINT:
            micro_key = _CHART_TYPE_TO_HINT[chart_type]
            if micro_key and micro_key not in hints:
                hints.append(micro_key)

        # Detect complexity from data characteristics
        y_left = chart_hint.get("y_axis_left") or {}
        stacked = y_left.get("stacked_bars") or []
        if isinstance(stacked, list) and len(stacked) > 2:
            has_multi_dataset = True
        if chart_hint.get("y_axis_right"):
            has_multi_dataset = True  # dual-axis = moderate+

        rows = payload.get("data", [])
        if isinstance(rows, list) and len(rows) > 50:
            has_complex_structure = True

    # If no data source results, fall back to regex for exotic chart keywords
    if not ds_results:
        for key, pattern in _EXOTIC_CHART_PATTERNS.items():
            if pattern.search(query) and key not in hints:
                hints.append(key)

    # Derive complexity
    if hints:  # exotic components present
        complexity = "high"
    elif has_complex_structure or has_multi_dataset:
        complexity = "moderate"
    else:
        complexity = "standard"

    return hints, complexity


# ── Phase 2 Skip Logic ────────────────────────────────────────
#
# After Phase 1 completes FULLY (both Classifier + Router), check
# whether Phase 2 (explorers) and Phase 2.5 (hints/refinement) can
# be skipped entirely.  Both agents MUST finish before this decision
# — the Router's output is essential context even when it returns
# empty, because content styles will evolve to provide their own
# routing (making the Router trivially empty for those pages).
#
# When skippable, the pipeline jumps directly from Phase 1 merge
# to style prompt setup → LLM generator.

# Styles that are inherently data-oriented.  Even when the Router
# returns empty, these styles may have frontend-injected dataContext
# or future built-in routing, so Phase 2 should still run.
_DATA_ORIENTED_STYLES = frozenset({
    "analytical", "comparison", "dashboard",
    "alerts-dashboard", "alert-detail", "scorecard",
})


def _can_skip_explorers(
    classification: Optional[Dict[str, Any]],
    routing: Optional[List[Dict[str, Any]]],
    content_style: str,
    has_data_context: bool,
) -> bool:
    """Decide whether Phase 2 (explorers) can be skipped.

    Called AFTER Phase 1 completes fully — both Classifier and Router
    have finished.  Returns ``True`` when no enrichment is needed.

    Skip conditions (ALL must be true):
    - Classifier says ``search = False``
    - Classifier says ``location = False``
    - Router returned no data source queries (empty list)
    - No passive ``dataContext`` from the frontend
    - Resolved style is not data-oriented
    """
    # If classifier failed entirely, don't skip — play it safe
    if not classification:
        return False

    if classification.get("search"):
        return False
    if classification.get("location"):
        return False

    # Router identified data sources to query
    if routing:
        return False

    # Frontend injected data — Phase 2.5 still needs to derive hints
    if has_data_context:
        return False

    # Determine the effective style
    style = content_style if content_style != "auto" else classification.get("style", "content")
    if style in _DATA_ORIENTED_STYLES:
        return False

    return True


# ── Post-Data Style Refinement ─────────────────────────────────
#
# After data sources return (Phase 2.5), re-evaluate the content
# style based on what the data actually looks like.  This catches
# cases where Phase 1 picked a generic style but the data warrants
# a dashboard layout.
#
# Only refines when content_style was "auto" (explicit styles are
# never changed).

def _refine_style_from_data(
    current_style: str,
    ds_results: List[Dict[str, Any]],
    component_hints: List[str],
    style_was_auto: bool,
) -> Tuple[str, Optional[str]]:
    """Refine content style based on actual data source responses.

    Called in Phase 2.5 after data returns.  Only modifies style when
    the user left content_style on ``"auto"`` (explicit styles are
    never changed).

    Returns ``(refined_style, reason)`` — reason is ``None`` if unchanged.
    """
    if not style_was_auto:
        return current_style, None

    if not ds_results:
        return current_style, None

    successful = [r for r in ds_results if r.get("success")]
    if not successful:
        return current_style, None

    # Already data-appropriate — no change needed
    if current_style in ("analytical", "dashboard"):
        return current_style, None

    # Inspect data characteristics
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

    # Decision matrix: upgrade style when data warrants it
    if has_chart_hints or has_metrics_metadata:
        return "analytical", f"data has chart_hint/metrics_metadata → analytical"

    if total_records > 20:
        return "analytical", f"{total_records} records → analytical"

    if total_records > 0 and current_style == "quick":
        return "content", f"data returned ({total_records} records) → content"

    return current_style, None


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


def _find_cheapest_model(
    current_provider_id: str,
    current_model: str,
    providers: Dict[str, "LLMProvider"],
) -> Optional[tuple]:
    """For hybrid-tier strict-shape JSON, find the fastest lightweight model.

    Hybrid pages only need tier-1 models since the output shape is fixed.
    Prefers Claude Haiku (best structured JSON quality at tier 1) over GPT
    mini/nano.  Falls back to any available tier-1 fast model.
    Returns (provider_id, model_id) or None if already optimal.
    """
    current_entry = _get_model_entry(current_provider_id, current_model)
    if not current_entry:
        return None

    # Already tier 1 — already lightweight
    if current_entry["tier"] <= 1:
        return None

    # Collect all tier-1 fast models from available providers
    candidates: List[Dict[str, Any]] = []
    for pid, prov in providers.items():
        if not prov.is_available():
            continue
        for entry in _ROSTER_BY_PROVIDER.get(pid, []):
            if entry["tier"] == 1 and entry["speed"] == "fast":
                candidates.append(entry)

    if not candidates:
        return None

    # Preference order: Claude Haiku first (best structured JSON at tier 1),
    # then any Claude, then same-provider models, then anything else.
    def _preference(e: Dict[str, Any]) -> tuple:
        is_haiku = 1 if "haiku" in e["model"] else 0
        is_claude = 1 if "claude" in e["model"] else 0
        is_same_provider = 1 if e["provider"] == current_provider_id else 0
        # Sort: higher preference first (negate for ascending sort)
        return (-is_haiku, -is_claude, -is_same_provider, e["model"])

    candidates.sort(key=_preference)

    best = candidates[0]
    if best["provider"] == current_provider_id and best["model"] == current_model:
        return None
    return (best["provider"], best["model"])


def _find_faster_model(
    current_provider_id: str,
    current_model: str,
    providers: Dict[str, "LLMProvider"],
    max_tier: Optional[int] = None,
) -> Optional[tuple]:
    """For standard-complexity tasks, find a faster model if the current one is slow.

    Only downgrades if the current model is medium or slow speed.
    If max_tier is set, only consider models at or below that tier.
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
            tier_ok = max_tier is None or entry["tier"] <= max_tier
            if entry_speed < current_speed and entry["tier"] >= 1 and tier_ok:
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
            "litellm": LiteLLMProvider(),
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

    # ── Phase 1a: Intent Classifier ──────────────────────────────

    async def _classify_intent(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Classify user intent: style, search, location, components, complexity.

        This is the lightweight half of the analysis phase.  It does NOT
        receive the data source catalog — that is handled in parallel by
        ``_route_data_sources``.

        Returns a dict like::

            {"style": "content", "search": True, "location": False,
             "search_query": "...", "components": [...], "complexity": "standard"}

        or ``None`` on failure (caller falls back to regex).
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

        system_text = _make_classifier_system()

        _est_size = len(json.dumps({"model": "x", "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": prompt},
        ], "max_tokens": 200}).encode())
        logger.info("── CLASSIFY ──  estimated body: %d bytes  (WAF limit: 7500)", _est_size)

        for provider_id, model_id in _ANALYZER_MODELS:
            provider = self.providers.get(provider_id)
            if not provider or not provider.is_available():
                continue

            try:
                resp = await provider.client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_text},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=200,
                    temperature=0,
                )
                text = (resp.choices[0].message.content or "").strip()

                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\s*", "", text)
                    text = re.sub(r"\s*```$", "", text)

                result = json.loads(text)

                style = result.get("style", "").lower().strip()
                if style not in VALID_STYLE_IDS:
                    logger.warning(
                        "Classifier returned invalid style '%s' via %s/%s",
                        style, provider_id, model_id,
                    )
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
                    classification["style"],
                    classification["search"], classification["location"],
                    classification["search_query"][:60],
                )
                return classification

            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning(
                    "Classifier JSON parse failed (%s/%s): %s — raw: %.100s",
                    provider_id, model_id, exc, locals().get("text", "?"),
                )
                continue
            except Exception as exc:
                logger.warning(
                    "Classifier failed (%s/%s): %s",
                    provider_id, model_id, exc,
                )
                continue

        return None

    # ── Phase 1b: Data Source Router ──────────────────────────────

    async def _route_data_sources(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """Decide which data sources / endpoints / params to query.

        This is the domain-aware half of the analysis phase.  It receives
        the full data source catalog and focuses solely on routing.

        Returns a list of query dicts like::

            [{"source": "claims-insights", "endpoint": "/api/v1/...", "params": {...}}]

        or ``None`` on failure (caller falls back to keyword matching).
        """
        from data_sources import get_analyzer_context

        ds_context = get_analyzer_context()
        if not ds_context:
            # No data sources registered — nothing to route
            logger.info("── ROUTE ──  no data sources available, skipping")
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

        system_text = _make_router_system()

        _est_size = len(json.dumps({"model": "x", "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": prompt},
        ], "max_tokens": 300}).encode())
        logger.info("── ROUTE ──  estimated body: %d bytes  (WAF limit: 7500)", _est_size)

        for provider_id, model_id in _ANALYZER_MODELS:
            provider = self.providers.get(provider_id)
            if not provider or not provider.is_available():
                continue

            try:
                resp = await provider.client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_text},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=300,
                    temperature=0,
                )
                text = (resp.choices[0].message.content or "").strip()

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
                for i, dsq in enumerate(ds_queries):
                    logger.info(
                        "── ROUTE OK ──  data_source[%d]: source='%s'  endpoint='%s'  params=%s",
                        i, dsq.get("source", "?"), dsq.get("endpoint", "?"), dsq.get("params", {}),
                    )
                return ds_queries

            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning(
                    "Router JSON parse failed (%s/%s): %s — raw: %.100s",
                    provider_id, model_id, exc, locals().get("text", "?"),
                )
                continue
            except Exception as exc:
                logger.warning(
                    "Router failed (%s/%s): %s",
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
        smart_routing: bool = True,
        enable_web_search: bool = True,
        enable_geolocation: bool = True,
        enable_data_sources: bool = True,
        data_context: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        data_source_overrides: Optional[List[str]] = None,
        data_source_disabled: Optional[List[str]] = None,
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

        # ── Security: sanitize input ──────────────────────────
        injection_hits = _detect_injection(message)
        if injection_hits:
            logger.warning(
                "⚠ INJECTION DETECTED ⚠  patterns=%s  message=%.200s",
                injection_hits, message,
            )
        message = _sanitize_for_prompt(message)

        if effective_history:
            for msg in effective_history:
                msg["content"] = _sanitize_for_prompt(msg["content"])

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

        # ── Step 1: Parallel Analysis ─────────────────────────
        #
        # Two focused agents run in parallel via asyncio.gather:
        #   1. Intent Classifier  — style, search, location, search_query
        #   2. Data Source Router  — which data sources / endpoints / params
        #
        # Component hints and complexity are derived LATER from actual data
        # source responses (see Phase 2.5 / _derive_hints_from_data).
        #
        # Tool gates (env/user) are applied AFTER AI decides.
        # If user disabled search, AI's "search=true" is overridden.
        #
        # Regex/keyword fallbacks fire independently for each agent on failure.

        ai_wants_search = False
        ai_wants_location = False
        ai_search_query = ""
        ai_data_queries: List[Dict[str, Any]] = []
        ai_component_hints: List[str] = []  # populated in Phase 2.5
        ai_complexity: str = "standard"     # populated in Phase 2.5
        style_id = DEFAULT_STYLE

        # ── Strict-shape fast path ────────────────────────────
        # Request-level detection: when the frontend explicitly sets a
        # content style AND disables all enrichment tools (web search,
        # geolocation, data sources), the classifier and router are
        # redundant.  This is the case for page-level hybrid dashboards
        # (alerts-dashboard, scorecard) that send HYBRID_TOOL_OVERRIDES.
        #
        # Styles like alert-detail are forced by the frontend but keep
        # enrichment tools enabled, so they still run the full pipeline.
        _style_def = CONTENT_STYLES.get(content_style, {})
        _is_strict_shape = bool(
            content_style != "auto"
            and _style_def.get("strict_shape")
            and not web_search_allowed
            and not data_sources_allowed
        )

        if _is_strict_shape:
            style_id = content_style
            # All tool flags stay False — no search, no geo, no data sources
            logger.info(
                "── ANALYZE ──  strict-shape fast path: style='%s' — skipping classifier + router",
                style_id,
            )
            yield {"event": "step", "data": {"id": "classifier", "status": "done", "label": "Strict shape — skipped"}}
            yield {"event": "step", "data": {"id": "router", "status": "done", "label": "Strict shape — skipped"}}

        elif classifier_active:
            # ── Phase 1: Parallel analysis (both MUST complete) ──
            #
            # Both agents run concurrently.  We ALWAYS wait for both
            # to finish — the Router's output is essential context
            # even when it returns empty (content styles will evolve
            # to provide their own routing, so knowing the Router
            # found nothing is itself a signal).
            #
            # After both complete, _can_skip_explorers() decides
            # whether Phase 2 (explorers) is needed.
            yield {"event": "step", "data": {"id": "classifier", "status": "start", "label": "Classifying intent"}}
            yield {"event": "step", "data": {"id": "router", "status": "start", "label": "Routing data sources"}}

            classify_task = self._classify_intent(message, history=effective_history)
            route_task = self._route_data_sources(message, history=effective_history)
            classification, routing = await asyncio.gather(
                classify_task, route_task, return_exceptions=True,
            )

            # Handle exceptions from either agent
            if isinstance(classification, Exception):
                logger.warning("Classifier raised exception: %s", classification)
                classification = None
            if isinstance(routing, Exception):
                logger.warning("Router raised exception: %s", routing)
                routing = None

            # ── Merge classifier result ────────────────────────
            if classification:
                if content_style != "auto":
                    # User explicitly chose a style — honour it
                    style_id = content_style
                else:
                    style_id = classification["style"]
                ai_wants_search = classification["search"]
                ai_wants_location = classification["location"]
                ai_search_query = classification["search_query"]
                # NOTE: components and complexity are no longer in the
                # classifier output.  They are derived from actual data
                # source responses in Phase 2.5 (_derive_hints_from_data).
                logger.info(
                    "── CLASSIFY MERGED ──  style=%s  search=%s  location=%s  query='%s'",
                    style_id, ai_wants_search, ai_wants_location,
                    ai_search_query[:60],
                )
                yield {"event": "step", "data": {
                    "id": "classifier", "status": "done",
                    "label": "Intent classified",
                    "detail": f"style={style_id} search={ai_wants_search} location={ai_wants_location}",
                }}
            else:
                # Classifier failed — regex fallback
                from content_styles import classify_style
                if content_style != "auto":
                    style_id = content_style
                else:
                    style_id = classify_style(message)
                ai_wants_search = should_search(message)
                logger.warning(
                    "── CLASSIFY ──  AI failed → regex fallback: style=%s  search=%s  location=%s",
                    style_id, ai_wants_search, ai_wants_location,
                )
                yield {"event": "step", "data": {
                    "id": "classifier", "status": "done",
                    "label": "⚠ Classifier unavailable — using keyword matching",
                    "detail": "Falling back to regex-based style classification",
                }}

            # ── Merge router result ────────────────────────────
            if routing is not None:
                ai_data_queries = routing
                if ai_data_queries:
                    logger.info("── ROUTE MERGED ──  %d data source queries", len(ai_data_queries))
                yield {"event": "step", "data": {
                    "id": "router", "status": "done",
                    "label": f"Data sources routed ({len(ai_data_queries)} queries)" if ai_data_queries else "No data sources needed",
                    "detail": ", ".join(q.get("source", "?") for q in ai_data_queries) if ai_data_queries else None,
                }}
            else:
                # Router failed — keyword fallback
                ai_data_queries = _fallback_data_sources(message)
                logger.warning(
                    "── ROUTE ──  AI failed → keyword fallback: data_sources=%d",
                    len(ai_data_queries),
                )
                for i, dsq in enumerate(ai_data_queries):
                    logger.info(
                        "── ROUTE FALLBACK ──  data_source[%d]: source='%s'  endpoint='%s'  params=%s",
                        i, dsq.get("source", "?"), dsq.get("endpoint", "?"), dsq.get("params", {}),
                    )
                yield {"event": "step", "data": {
                    "id": "router", "status": "done",
                    "label": "⚠ Router unavailable — using keyword matching",
                    "detail": f"{len(ai_data_queries)} sources matched by keywords" if ai_data_queries else "No sources matched",
                }}

            # If BOTH agents failed, surface a combined warning
            if classification is None and routing is None:
                yield {"event": "step", "data": {
                    "id": "analyzer_warning", "status": "done",
                    "label": "⚠ AI analysis unavailable — using fallback matching",
                    "detail": "The enterprise gateway may be limiting requests.",
                }}

            # ── Phase 1 complete: check if Phase 2 can be skipped ──
            _skip_explorers = _can_skip_explorers(
                classification, ai_data_queries, content_style,
                has_data_context=bool(data_context),
            )
            if _skip_explorers:
                logger.info(
                    "── PHASE 1 COMPLETE ──  both agents agree: no enrichment needed — skipping Phase 2",
                )
                yield {"event": "step", "data": {
                    "id": "phase2_skip", "status": "done",
                    "label": "Phase 2 skipped — no enrichment needed",
                }}

            # ── Apply user data source overrides ─────────────────
            # Remove disabled sources
            if data_source_disabled:
                before = len(ai_data_queries)
                ai_data_queries = [
                    q for q in ai_data_queries
                    if q.get("source") not in data_source_disabled
                ]
                removed = before - len(ai_data_queries)
                if removed:
                    logger.info("── DS OVERRIDE ──  removed %d user-disabled sources", removed)

            # Add user-override sources that aren't already queried
            if data_source_overrides:
                existing_sources = {q.get("source") for q in ai_data_queries}
                for override_id in data_source_overrides:
                    if override_id not in existing_sources:
                        # Add a basic query for the overridden source
                        ai_data_queries.append({
                            "source": override_id,
                            "endpoint": "default",
                            "params": {"question": message},
                            "_user_override": True,
                        })
                        logger.info("── DS OVERRIDE ──  added user-requested source: %s", override_id)

            # If data source queries were found but style is generic, upgrade
            if ai_data_queries and style_id in ("content", "quick"):
                style_id = "analytical"
                logger.info("── ANALYZE ──  data source match → upgrading style to analytical")

        else:
            # AI disabled — pure regex/keyword fallbacks
            from content_styles import classify_style
            if content_style != "auto":
                style_id = content_style
            else:
                style_id = classify_style(message)
            ai_wants_search = should_search(message)
            ai_data_queries = _fallback_data_sources(message)
            logger.info(
                "── ANALYZE ──  AI disabled → regex: style=%s  search=%s  location=%s  data_sources=%d",
                style_id, ai_wants_search, ai_wants_location, len(ai_data_queries),
            )
            yield {"event": "step", "data": {"id": "classifier", "status": "done", "label": "AI disabled — regex fallback"}}
            yield {"event": "step", "data": {"id": "router", "status": "done", "label": "AI disabled — keyword fallback"}}

            if ai_data_queries and style_id in ("content", "quick"):
                style_id = "analytical"
                logger.info("── ANALYZE ──  data source match → upgrading style to analytical")

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

        # Build reasoning prose for chain-of-thought display.
        # NOTE: component hints and complexity are not yet known here —
        # they will be derived from actual data source responses in Phase 2.5.
        _style_names = {
            "analytical": "Analytical (data dashboards)",
            "content": "Content (narrative)",
            "comparison": "Comparison (side-by-side)",
            "howto": "How-To (step-by-step)",
            "quick": "Quick Answer (concise)",
        }
        _reasoning_parts = [
            f"Presentation: {_style_names.get(style_id, style_id)}",
        ]
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
            "label": "Analysis complete",
            "detail": f"style={style_id} search={do_search} location={do_location}",
            "reasoning": " · ".join(_reasoning_parts),
            "result": {
                "style": style_id,
                "search": do_search,
                "location": do_location,
                "query": ai_search_query,
            },
        }}

        # ── Step 2: Location context (pre-step) ─────────────────
        # Location is resolved FIRST because:
        # a) It may require browser interaction (SSE pause)
        # b) The search query may need location context appended
        # Once resolved, search + data sources run in parallel.
        location_context = ""
        location_label = ""
        if do_location and user_location:
            # Location already in the request (cached from a previous trigger)
            location_label, location_context = _build_location_context(user_location)
            logger.info("── LOCATION ──  %s", location_label or f"{user_location.get('lat')},{user_location.get('lng')}")

        elif ai_wants_location and not geolocation_allowed:
            logger.info("── LOCATION ──  AI requested but tool disabled")

        elif do_location and not user_location:
            # Analyzer wants location but frontend hasn't provided it yet.
            # Emit need_location and PAUSE until the frontend POSTs it back (or times out).
            loc_request_id = str(uuid.uuid4())
            pending = _PendingLocation()
            _pending_locations[loc_request_id] = pending
            logger.info("── LOCATION ──  AI requested, pausing for frontend (request_id=%s)", loc_request_id)

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
                    user_location = received_loc  # propagate to response metadata
                    logger.info("── LOCATION ──  Received from frontend: %s", location_label or f"{received_loc.get('lat')},{received_loc.get('lng')}")
                    yield {"event": "step", "data": {
                        "id": "geolocation", "status": "done",
                        "label": "Location received",
                        "detail": location_label or f"{received_loc.get('lat')}, {received_loc.get('lng')}",
                    }}
                else:
                    logger.info("── LOCATION ──  Frontend returned no location (denied?)")
                    yield {"event": "step", "data": {
                        "id": "geolocation", "status": "done",
                        "label": "Location unavailable",
                        "detail": "Continuing without location",
                    }}
            except asyncio.TimeoutError:
                logger.info("── LOCATION ──  Timed out waiting for frontend (%ds)", _LOCATION_TIMEOUT)
                yield {"event": "step", "data": {
                    "id": "geolocation", "status": "done",
                    "label": "Location unavailable",
                    "detail": "Timed out — continuing without location",
                }}
            finally:
                _pending_locations.pop(loc_request_id, None)

        # ── Step 3: Parallel Explorers — Web Search + Data Sources ──
        #
        # Both explorers run concurrently via asyncio.gather.
        # Pure async work is extracted into inner coroutines; SSE
        # events are yielded after both complete.

        from data_sources import (
            query_sources,
            format_results_for_context,
            get_rules_context,
        )

        augmented_message = message
        search_metadata: Optional[Dict[str, Any]] = None
        search_results_raw: Optional[Dict[str, Any]] = None
        search_images: List[str] = []
        ds_context = ""
        ds_metadata: Optional[Dict[str, Any]] = None
        ds_active_results: List[Dict[str, Any]] = []

        # ── Define explorer coroutines ────────────────────────

        async def _explore_search() -> Dict[str, Any]:
            """Explorer: Web Search — pure async, returns result dict."""
            _search_query = ai_search_query or rewrite_search_query(
                message, location=location_label,
            )
            if ai_search_query and location_label and location_label.lower() not in _search_query.lower():
                _search_query = f"{_search_query} {location_label}"

            if not web_search.is_available():
                logger.info("── SEARCH ──  not configured (no API key)")
                return {"status": "not_configured", "query": _search_query}

            logger.info(
                "── SEARCH ──  query: \"%s\"  (original: \"%s\")",
                _search_query[:100], message[:60],
            )
            try:
                raw = await web_search.search(_search_query)
                ctx = web_search.format_for_context(raw)
                if ctx:
                    imgs = raw.get("images", [])[:6]
                    logger.info(
                        "── SEARCH OK ──  %d results, %d images, answer=%s",
                        len(raw.get("results", [])), len(imgs), bool(raw.get("answer")),
                    )
                    for i, r in enumerate(raw.get("results", [])[:3]):
                        logger.info(
                            "  result[%d]: %s — %.100s",
                            i, r.get("title", "")[:50], r.get("content", "")[:100],
                        )
                    return {
                        "status": "ok",
                        "context": ctx,
                        "raw": raw,
                        "images": imgs,
                        "query": _search_query,
                    }
                else:
                    error_type = raw.get("error", "unknown")
                    logger.warning("── SEARCH FAILED ── (%s)", error_type)
                    return {"status": "failed", "error": error_type, "query": _search_query}
            except Exception as exc:
                logger.warning("── SEARCH ERROR ── %s", exc)
                return {"status": "exception", "error": str(exc), "query": _search_query}

        async def _explore_data_sources() -> Dict[str, Any]:
            """Explorer: Data Sources — pure async, returns result dict."""
            results = await query_sources(ai_data_queries)
            ctx = format_results_for_context(results)
            successful = [r for r in results if r.get("success")]
            failed = [r for r in results if not r.get("success")]
            logger.info(
                "── DATA SOURCES OK ──  %d/%d queries succeeded, context=%d chars",
                len(successful), len(ai_data_queries), len(ctx),
            )
            for r in successful:
                logger.info(
                    "  source[%s]: %d records",
                    r.get("_source_id", "?"), r.get("record_count", 0),
                )
            return {
                "results": results,
                "context": ctx,
                "successful": successful,
                "failed": failed,
            }

        # ── Passive data injection (no async work needed) ─────
        if data_context:
            passive_blocks: List[str] = []
            for dc in data_context:
                label = _sanitize_label(dc.get("label") or dc.get("source") or "External Data")
                import json as _json
                raw_data = dc.get("data", {})
                max_chars = 12_000
                if isinstance(raw_data, list):
                    serialized = _json.dumps(raw_data, default=str, ensure_ascii=False)
                    if len(serialized) > max_chars:
                        original_len = len(raw_data)
                        truncated = list(raw_data)
                        while truncated and len(_json.dumps(truncated, default=str, ensure_ascii=False)) > max_chars:
                            remove_count = max(1, len(truncated) // 4)
                            truncated = truncated[:-remove_count]
                        serialized = _json.dumps(truncated, default=str, ensure_ascii=False)
                        serialized += f"\n(truncated {original_len}→{len(truncated)} items)"
                elif isinstance(raw_data, dict):
                    serialized = _json.dumps(raw_data, default=str, ensure_ascii=False)
                    if len(serialized) > max_chars:
                        serialized = serialized[:max_chars] + "\n... (truncated)"
                else:
                    serialized = _json.dumps(raw_data, default=str, ensure_ascii=False)
                passive_blocks.append(f"[Data Source: {label}]\n{serialized}")
            ds_context = "\n".join(passive_blocks)
            ds_metadata = {"passive": True, "sources": len(data_context)}
            logger.info(
                "── DATA SOURCES ──  passive injection: %d sources, %d chars",
                len(data_context), len(ds_context),
            )

        # ── Deploy explorers in parallel ──────────────────────
        _want_search_explorer = do_search
        _want_ds_explorer = bool(ai_data_queries) and data_sources_allowed and not data_context

        if _want_search_explorer or _want_ds_explorer:
            # Emit start events for active explorers
            if _want_search_explorer:
                _sq = ai_search_query or message[:80]
                yield {"event": "step", "data": {
                    "id": "search", "status": "start",
                    "label": "Searching the web",
                    "detail": _sq[:80],
                }}
            if _want_ds_explorer:
                yield {"event": "step", "data": {
                    "id": "data_sources", "status": "start",
                    "label": "Querying data sources",
                    "detail": f"{len(ai_data_queries)} queries",
                }}

            # Gather parallel work
            _explorer_keys: List[str] = []
            _explorer_coros: List[Any] = []
            if _want_search_explorer:
                _explorer_keys.append("search")
                _explorer_coros.append(_explore_search())
            if _want_ds_explorer:
                _explorer_keys.append("data_sources")
                _explorer_coros.append(_explore_data_sources())

            _explorer_results = await asyncio.gather(*_explorer_coros, return_exceptions=True)
            _explorer_map = dict(zip(_explorer_keys, _explorer_results))

            # ── Process search results ────────────────────────
            if "search" in _explorer_map:
                sr = _explorer_map["search"]
                if isinstance(sr, Exception):
                    logger.warning("── SEARCH EXPLORER ── exception: %s", sr)
                    sr = {"status": "exception", "error": str(sr), "query": ai_search_query}

                if sr["status"] == "ok":
                    augmented_message = f"{sr['context']}\n\nUser question: {message}"
                    search_results_raw = sr["raw"]
                    search_images = sr["images"]
                    search_metadata = {
                        "searched": True,
                        "success": True,
                        "results_count": len(search_results_raw.get("results", [])),
                        "images_count": len(search_images),
                        "query": sr["query"],
                    }
                    yield {"event": "step", "data": {
                        "id": "search", "status": "done",
                        "label": "Search complete",
                        "detail": f"{search_metadata['results_count']} results",
                    }}
                elif sr["status"] == "not_configured":
                    search_metadata = {"searched": False, "reason": "not_configured"}
                    augmented_message = (
                        "[SEARCH_UNAVAILABLE — web search is not configured on this server. "
                        "If this query requires real-time data (prices, stocks, scores, trending, current events), "
                        "use alert(warning) stating data is unavailable — do NOT fabricate numbers or lists. "
                        "If training knowledge suffices (concepts, comparisons, stable facts), "
                        "answer fully and include alert(info) disclosing training data was used.]\n\n"
                        f"{message}"
                    )
                    yield {"event": "step", "data": {"id": "search", "status": "done", "label": "Search unavailable"}}
                else:
                    # failed or exception
                    search_metadata = {
                        "searched": True,
                        "success": False,
                        "error": sr.get("error", "unknown"),
                        "query": sr.get("query", ""),
                    }
                    augmented_message = (
                        "[SEARCH_UNAVAILABLE — web search failed to retrieve results. "
                        "If this query requires real-time data (prices, stocks, scores, trending, current events), "
                        "use alert(warning) stating data is unavailable — do NOT fabricate numbers or lists. "
                        "If training knowledge suffices (concepts, comparisons, stable facts), "
                        "answer fully and include alert(info) disclosing training data was used.]\n\n"
                        f"{message}"
                    )
                    yield {"event": "step", "data": {
                        "id": "search", "status": "done",
                        "label": "Search returned no results" if sr["status"] == "failed" else "Search failed",
                    }}

            # ── Process data source results ───────────────────
            if "data_sources" in _explorer_map:
                dr = _explorer_map["data_sources"]
                if isinstance(dr, Exception):
                    logger.warning("── DS EXPLORER ── exception: %s", dr)
                    dr = {"results": [], "context": "", "successful": [], "failed": []}

                ds_active_results = dr["results"]
                ds_context = dr["context"]
                successful = dr["successful"]
                failed = dr["failed"]

                ds_metadata = {
                    "active": True,
                    "queries": len(ai_data_queries),
                    "successful": len(successful),
                    "failed": len(failed),
                }

                if not successful and failed:
                    failed_names = [r.get("_source_id", "unknown") for r in failed]
                    ds_context = (
                        f"[DATA UNAVAILABLE: {', '.join(failed_names)}]\n"
                        "The system attempted to query the following data sources but ALL requests failed. "
                        "Do NOT fabricate data. Tell the user the data could not be retrieved and suggest trying again."
                    )
                    yield {"event": "step", "data": {
                        "id": "data_sources", "status": "done",
                        "label": f"⚠ Data sources unavailable ({len(failed)} failed)",
                        "detail": "Could not reach the data API. The response will not include live data.",
                    }}
                elif failed:
                    failed_names = [r.get("_source_id", "unknown") for r in failed]
                    ds_context += (
                        f"\n\n[DATA PARTIALLY UNAVAILABLE: {', '.join(failed_names)}]\n"
                        "Some data sources could not be reached. Use ONLY the data provided above. "
                        "Do NOT fill gaps with training knowledge. Mention which data is missing."
                    )
                    yield {"event": "step", "data": {
                        "id": "data_sources", "status": "done",
                        "label": f"Data received ({len(successful)} sources, {len(failed)} failed)",
                        "detail": f"{sum(r.get('record_count', 0) for r in successful)} records — some sources unavailable",
                    }}
                else:
                    yield {"event": "step", "data": {
                        "id": "data_sources", "status": "done",
                        "label": f"Data received ({len(successful)} sources)",
                        "detail": f"{sum(r.get('record_count', 0) for r in successful)} records",
                    }}

        # ── Handle non-explorer search/ds cases ───────────────
        if not _want_search_explorer:
            if ai_wants_search and not web_search_allowed:
                logger.info("── SEARCH ──  AI requested but tool disabled by user/env")
                augmented_message = (
                    "[SEARCH_UNAVAILABLE — web search is currently disabled. "
                    "If this query requires real-time data (prices, stocks, scores, trending, current events), "
                    "use alert(warning) stating data is unavailable — do NOT fabricate numbers or lists. "
                    "If training knowledge suffices (concepts, comparisons, stable facts), "
                    "answer fully and include alert(info) disclosing training data was used.]\n\n"
                    f"{message}"
                )
            elif not do_search:
                logger.info("── SEARCH ──  not needed (AI decided)")

        if not _want_ds_explorer:
            if ai_data_queries and not data_sources_allowed:
                logger.info("── DATA SOURCES ──  AI requested but tool disabled by user/env")
            elif not ai_data_queries:
                logger.info("── DATA SOURCES ──  not needed")

        # ── Data-driven query with NO data context → inject unavailability ──
        # If the router or keyword fallback identified data source queries
        # but we ended up with empty ds_context (e.g. all failed, or data
        # sources disabled), the LLM needs to know data was expected.
        _data_was_expected = bool(ai_data_queries) and not ds_context
        if _data_was_expected and data_sources_allowed:
            ds_context = (
                "[DATA UNAVAILABLE]\n"
                "The system identified this as a data-driven query and attempted to "
                "retrieve live data, but no results were returned. "
                "Do NOT fabricate numbers or metrics from training data. "
                "Inform the user that the data is currently unavailable and suggest trying again."
            )
            logger.warning("── DATA SOURCES ──  data expected but empty → injecting DATA UNAVAILABLE block")

        if ds_context:
            augmented_message = (
                f"{ds_context}\n\n"
                "[INSTRUCTION: The above data was retrieved from live API queries. "
                "Use ONLY this data in your response — do NOT supplement with training knowledge. "
                "If a DATA UNAVAILABLE block is present, inform the user clearly.]\n\n"
                f"{augmented_message}"
            )

        # Data source rules (injected into system prompt context)
        ds_rules = get_rules_context()

        # ── Phase 2.5: Data-Aware Hint Derivation (deterministic, 0ms) ──
        # Derive component hints and complexity from ACTUAL data source
        # responses instead of blind guessing.  For non-data queries,
        # falls back to regex detection of exotic chart keywords.
        ai_component_hints, ai_complexity = _derive_hints_from_data(
            ds_active_results, message,
        )
        logger.info(
            "── DATA HINTS ──  components=%s  complexity=%s  (from %d data results)",
            ai_component_hints, ai_complexity, len(ds_active_results),
        )
        if ai_component_hints or ai_complexity != "standard":
            yield {"event": "step", "data": {
                "id": "data_hints", "status": "done",
                "label": "Data-driven hints derived",
                "detail": f"components={ai_component_hints} complexity={ai_complexity}",
            }}

        # ── Phase 2.5b: Post-Data Style Refinement (deterministic, 0ms) ──
        # Now that we've seen the actual data, re-evaluate whether the
        # content style chosen in Phase 1 is appropriate.  E.g., if the
        # classifier picked "content" but data returned chart_hint metadata,
        # upgrade to "analytical" for a dashboard-quality response.
        _style_was_auto = (content_style == "auto")
        _pre_refine_style = style_id
        style_id, _refine_reason = _refine_style_from_data(
            style_id, ds_active_results, ai_component_hints, _style_was_auto,
        )
        if _refine_reason:
            logger.info(
                "── STYLE REFINE ──  %s → %s  reason: %s",
                _pre_refine_style, style_id, _refine_reason,
            )
            yield {"event": "step", "data": {
                "id": "style_refine", "status": "done",
                "label": f"Style refined: {_pre_refine_style} → {style_id}",
                "detail": _refine_reason,
            }}

        # ── Step 3b: Style prompt setup ───────────────────────
        system_prompt = get_system_prompt(style_id)
        component_priority = get_component_priority(style_id)
        logger.info(
            "── STYLE ──  %s  |  prompt=%dB  |  priority=%s",
            style_id,
            len(system_prompt.encode("utf-8")),
            list(component_priority)[:5],
        )

        # ── Step 3c: Micro-context assembly ────────────────────
        # Inject detailed component instructions based on data-driven hints.
        # Only adds context for the specific components this request needs.
        from micro_contexts import assemble as assemble_micro_contexts, AVAILABLE_KEYS

        if ai_component_hints:
            valid_hints = [k for k in ai_component_hints if k in AVAILABLE_KEYS]
            if valid_hints:
                micro_budget = 1500 if max_body_bytes else None
                micro_block = assemble_micro_contexts(valid_hints, max_bytes=micro_budget)
                if micro_block:
                    system_prompt = f"{system_prompt}\n\n{micro_block}"
                    logger.info(
                        "── MICRO-CONTEXT ──  injected %d fragments (%dB): %s",
                        len(valid_hints), len(micro_block.encode("utf-8")), valid_hints,
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

        # ── Step 3d: Adaptive model routing ───────────────────
        # Derive effective complexity from data-driven component hints
        # (Phase 2.5), then find the best model that meets the requirement.
        # Hybrid-tier styles use the user-selected model as-is (no routing overhead).
        effective_provider_id = provider_id
        effective_model = model
        effective_provider = provider
        effective_complexity = "standard"

        if _is_strict_shape:
            # Strict-shape dashboards use the selected model as-is (no downgrade).
            # The enterprise LiteLLM gateway's cold-start latency dominates
            # over model-level speed differences, so downgrading to Haiku/mini
            # doesn't actually help — and those tier-1 models are unreliable
            # on the gateway (intermittent 403s).  Sonnet 4 is both reliable
            # and produces better structured JSON for strict-shape pages.
            logger.info(
                "── MODEL ROUTE ──  strict-shape: using %s/%s as-is (no auto-downgrade)",
                provider_id, model,
            )
        elif smart_routing and performance_mode in ("auto", "comprehensive"):
            effective_complexity = _derive_complexity(ai_complexity, ai_component_hints)

            if effective_complexity != "standard":
                route = _find_best_model(
                    provider_id, model, effective_complexity, self.providers,
                )
                if route:
                    new_pid, new_mid = route
                    new_provider = self.get_provider(new_pid)
                    if new_provider:
                        effective_provider_id = new_pid
                        effective_model = new_mid
                        effective_provider = new_provider

                        cross = " (cross-provider)" if new_pid != provider_id else ""
                        logger.info(
                            "── MODEL ROUTE ──  %s/%s → %s/%s  complexity=%s  components=%s%s",
                            provider_id, model, new_pid, new_mid,
                            effective_complexity, ai_component_hints, cross,
                        )
                        yield {"event": "step", "data": {
                            "id": "model_upgrade", "status": "start",
                            "label": f"Routing to stronger model ({effective_complexity})",
                            "detail": f"{provider_id}/{model} → {new_pid}/{new_mid}",
                        }}
                        yield {"event": "step", "data": {
                            "id": "model_upgrade", "status": "done",
                            "label": f"Model routed for {effective_complexity} task",
                            "detail": f"{new_pid}/{new_mid}",
                            "reasoning": f"Task complexity is {effective_complexity} — {provider_id}/{model} was upgraded to {new_pid}/{new_mid} for better results{cross}",
                        }}
                else:
                    logger.info(
                        "── MODEL ROUTE ──  %s/%s already meets %s requirements",
                        provider_id, model, effective_complexity,
                    )
            else:
                # Standard task — respect performance mode tier preferences
                current_entry = _get_model_entry(provider_id, model)
                current_tier = current_entry["tier"] if current_entry else 1
                
                if performance_mode == "optimized":
                    # Optimized: prefer lighter models (tier 4 or lower)
                    # Only downgrade if current is above tier 4
                    if current_tier > 4:
                        downgrade = _find_faster_model(provider_id, model, self.providers, max_tier=4)
                        if downgrade:
                            new_pid, new_mid = downgrade
                            new_provider = self.get_provider(new_pid)
                            if new_provider:
                                effective_provider_id = new_pid
                                effective_model = new_mid
                                effective_provider = new_provider
                                logger.info(
                                    "── MODEL ROUTE (optimized) ──  %s/%s → %s/%s (tier ≤4)",
                                    provider_id, model, new_pid, new_mid,
                                )
                elif performance_mode == "comprehensive":
                    # Comprehensive: prefer premium models (tier 4 or higher)
                    # Upgrade if current is below tier 4
                    if current_tier < 4:
                        route = _find_best_model(provider_id, model, "moderate", self.providers)
                        if route:
                            new_pid, new_mid = route
                            new_entry = _get_model_entry(new_pid, new_mid)
                            if new_entry and new_entry["tier"] >= 4:
                                new_provider = self.get_provider(new_pid)
                                if new_provider:
                                    effective_provider_id = new_pid
                                    effective_model = new_mid
                                    effective_provider = new_provider
                                    logger.info(
                                        "── MODEL ROUTE (comprehensive) ──  %s/%s → %s/%s (tier ≥4)",
                                        provider_id, model, new_pid, new_mid,
                                    )
                else:  # auto mode
                    # Auto: prefer tier 4+ (Claude 4.5 Sonnet or higher)
                    # Only downgrade if result is still tier 4+
                    downgrade = _find_faster_model(provider_id, model, self.providers)
                    if downgrade:
                        new_pid, new_mid = downgrade
                        new_entry = _get_model_entry(new_pid, new_mid)
                        if new_entry and new_entry["tier"] >= 4:
                            new_provider = self.get_provider(new_pid)
                            if new_provider:
                                effective_provider_id = new_pid
                                effective_model = new_mid
                                effective_provider = new_provider
                                cross = " (cross-provider)" if new_pid != provider_id else ""
                                logger.info(
                                    "── MODEL ROUTE (fast) ──  %s/%s → %s/%s  standard task, using faster model%s",
                                    provider_id, model, new_pid, new_mid, cross,
                                )
                                yield {"event": "step", "data": {
                                    "id": "model_upgrade", "status": "start",
                                    "label": "Optimizing for speed",
                                    "detail": f"{provider_id}/{model} → {new_pid}/{new_mid}",
                                }}
                                yield {"event": "step", "data": {
                                    "id": "model_upgrade", "status": "done",
                                    "label": "Using faster model for simple task",
                                    "detail": f"{new_pid}/{new_mid}",
                                    "reasoning": f"This is a standard-complexity task — switching from {provider_id}/{model} to the faster {new_pid}/{new_mid}{cross}",
                                }}
        elif not smart_routing:
            logger.info(
                "── MODEL ROUTE ──  smart_routing=off, using selected %s/%s as-is",
                provider_id, model,
            )

        # ── Step 4: LLM generation ────────────────────────────
        # Map task complexity → adaptive thinking effort level
        _COMPLEXITY_TO_EFFORT = {
            "standard": None,       # No thinking needed
            "moderate": "medium",   # Light reasoning
            "high": "high",         # Deep structured data work
            "reasoning": "high",    # Multi-step logic
        }
        thinking_effort = _COMPLEXITY_TO_EFFORT.get(effective_complexity) if smart_routing and performance_mode in ("auto", "comprehensive") else None

        _llm_reasoning_parts = [f"Model: {effective_provider_id}/{effective_model}"]
        if thinking_effort:
            _llm_reasoning_parts.append(f"Thinking effort: {thinking_effort}")
        if effective_provider_id != provider_id or effective_model != model:
            _llm_reasoning_parts.append(f"Original selection: {provider_id}/{model}")
        yield {"event": "step", "data": {
            "id": "llm", "status": "start",
            "label": "Generating response",
            "detail": f"{effective_provider_id}/{effective_model}" + (f" (thinking: {thinking_effort})" if thinking_effort else ""),
            "reasoning": " · ".join(_llm_reasoning_parts),
        }}
        # Hybrid-tier max_tokens: use the style's declared limit, or a
        # generous default.  Output must NEVER be truncated — an incomplete
        # JSON response is worse than a slightly larger token budget.
        _style_max_tokens = CONTENT_STYLES.get(content_style, {}).get("max_tokens")
        strict_max_tokens = (_style_max_tokens or 4096) if _is_strict_shape else None

        # Strict-shape: temperature=0 for deterministic, faster output
        # Regular chat: use user-supplied temperature, or None → _call_llm default (0.7)
        effective_temperature: Optional[float] = 0.0 if _is_strict_shape else temperature

        logger.info(
            "── GENERATE ──  sending to %s/%s  (%d chars)  effort=%s%s%s",
            effective_provider_id, effective_model, len(augmented_message), thinking_effort,
            f"  max_tokens={strict_max_tokens}" if strict_max_tokens else "",
            f"  temp={effective_temperature}" if effective_temperature is not None else "",
        )
        llm_t0 = time.time()

        # ── Token-level streaming: yield deltas as they arrive ──
        # The frontend shows text progressively instead of a 30-60s spinner.
        # After the stream completes, we parse the JSON and run post-processing.
        _stream_content = ""
        _stream_error: Optional[Dict[str, Any]] = None
        try:
            async for delta in effective_provider.generate_stream_tokens(
                augmented_message, effective_model, effective_history,
                system_prompt=system_prompt, effort=thinking_effort,
                max_tokens=strict_max_tokens,
                temperature=effective_temperature,
            ):
                _stream_content += delta
                yield {"event": "token", "data": {"delta": delta}}
        except LLMStreamError as exc:
            logger.warning("Stream error from %s/%s: %s", effective_provider_id, effective_model, exc)
            _stream_error = exc.error_response

        llm_elapsed = time.time() - llm_t0

        if _stream_error:
            # Stream failed — use the error response dict (fallback logic below will handle it)
            response = _stream_error
        elif not _stream_content.strip():
            logger.warning("Exploration Lab %s returned empty stream", effective_model)
            response = _error_response(
                "Empty Response",
                "The AI returned an empty response. Please try again or switch models.",
                variant="warning",
            )
        else:
            # Parse the accumulated content into a structured response
            logger.debug("Stream complete (%d chars): %.500s", len(_stream_content), _stream_content)
            response = parse_llm_json(_stream_content)

            # Safety net: ensure we have text or components
            has_text = bool(response.get("text"))
            has_components = bool((response.get("a2ui") or {}).get("components"))
            if not has_text and not has_components:
                logger.warning("Stream %s: parsed JSON has no text/components", effective_model)
                response = {
                    "text": _stream_content[:1000] if len(_stream_content) > 20
                        else "The AI response could not be parsed. Please try again.",
                    "a2ui": {
                        "version": "1.0",
                        "components": [{
                            "id": "parse-warn", "type": "alert",
                            "props": {
                                "variant": "warning",
                                "title": "Response Format Issue",
                                "description": "The AI response didn't match the expected format. Showing raw output.",
                            },
                        }],
                    },
                }

            # Refusal guard — retry with non-streaming generate (simpler, one attempt)
            if _is_refusal(response):
                logger.info("Refusal detected in streamed response — retrying non-streaming")
                response = await _retry_on_refusal(
                    response, message,
                    lambda msg, hist: effective_provider._call_llm(
                        _build_messages(msg, hist, system_prompt=system_prompt),
                        effective_model,
                        max_tokens_override=strict_max_tokens,
                        temperature_override=effective_temperature,
                    ),
                )

        # ── Model fallback (max 2 extra attempts): if the provider returned
        # an error (403, timeout, etc.), try up to 2 alternatives then stop.
        _MAX_FALLBACK_ATTEMPTS = 2
        if response.get("_is_error") and smart_routing:
            fallback_attempts = 0
            fallback_found = False

            # Strategy 1: same model, different provider (1 attempt max)
            for fb_pid, fb_prov in self.providers.items():
                if fallback_attempts >= _MAX_FALLBACK_ATTEMPTS:
                    break
                if fb_pid == effective_provider_id or not fb_prov.is_available():
                    continue
                fb_model_ids = [m["id"] for m in fb_prov.models]
                if effective_model in fb_model_ids:
                    fallback_attempts += 1
                    logger.info("── FALLBACK %d/%d ──  trying %s/%s (cross-provider)",
                                fallback_attempts, _MAX_FALLBACK_ATTEMPTS, fb_pid, effective_model)
                    yield {"event": "step", "data": {
                        "id": "fallback", "status": "start",
                        "label": f"Retrying with {fb_prov.name} ({fallback_attempts}/{_MAX_FALLBACK_ATTEMPTS})",
                    }}
                    fb_response = await fb_prov.generate(
                        augmented_message, effective_model, effective_history,
                        system_prompt=system_prompt, effort=thinking_effort,
                    )
                    if not fb_response.get("_is_error"):
                        response, effective_provider_id, effective_provider = fb_response, fb_pid, fb_prov
                        llm_elapsed = time.time() - llm_t0
                        logger.info("── FALLBACK OK ──  %s/%s (%.1fs)", fb_pid, effective_model, llm_elapsed)
                        yield {"event": "step", "data": {"id": "fallback", "status": "done",
                               "label": f"Using {fb_prov.name}/{effective_model}"}}
                        fallback_found = True
                        break

            # Strategy 2: different model, same provider (remaining attempts)
            if not fallback_found and fallback_attempts < _MAX_FALLBACK_ATTEMPTS:
                current_entry = _get_model_entry(effective_provider_id, effective_model)
                current_tier = current_entry["tier"] if current_entry else 2
                alt_models = [m["id"] for m in effective_provider.models if m["id"] != effective_model]
                roster_lookup = {e["model"]: e for e in _ROSTER_BY_PROVIDER.get(effective_provider_id, [])}
                alt_models.sort(key=lambda mid: (abs((roster_lookup.get(mid, {}).get("tier", 1)) - current_tier),
                                                  -(roster_lookup.get(mid, {}).get("tier", 1))))

                for alt_mid in alt_models:
                    if fallback_attempts >= _MAX_FALLBACK_ATTEMPTS:
                        break
                    fallback_attempts += 1
                    logger.info("── FALLBACK %d/%d ──  trying %s/%s (alt model)",
                                fallback_attempts, _MAX_FALLBACK_ATTEMPTS, effective_provider_id, alt_mid)
                    yield {"event": "step", "data": {
                        "id": "fallback", "status": "start",
                        "label": f"Trying {alt_mid} ({fallback_attempts}/{_MAX_FALLBACK_ATTEMPTS})",
                    }}
                    fb_response = await effective_provider.generate(
                        augmented_message, alt_mid, effective_history,
                        system_prompt=system_prompt, effort=thinking_effort,
                    )
                    if not fb_response.get("_is_error"):
                        response, effective_model = fb_response, alt_mid
                        llm_elapsed = time.time() - llm_t0
                        logger.info("── FALLBACK OK ──  %s/%s (%.1fs)", effective_provider_id, alt_mid, llm_elapsed)
                        yield {"event": "step", "data": {"id": "fallback", "status": "done",
                               "label": f"Using {effective_provider.name}/{alt_mid}"}}
                        fallback_found = True
                        break
                    else:
                        logger.warning("── FALLBACK ──  %s/%s also failed", effective_provider_id, alt_mid)

            if not fallback_found and fallback_attempts > 0:
                logger.error("── FALLBACK ──  %d attempts exhausted, returning original error", fallback_attempts)
                # Surface the error class to the user via step event
                err_title = response.get("a2ui", {}).get("components", [{}])[0].get("props", {}).get("title", "Error")
                is_gateway = "gateway" in err_title.lower() or "capacity" in err_title.lower()
                yield {"event": "step", "data": {
                    "id": "generation_error", "status": "done",
                    "label": f"⚠ {'Gateway capacity limit reached' if is_gateway else 'Model generation failed'}",
                    "detail": err_title,
                }}

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
        response = _normalize_a2ui_components(response)
        response = _apply_chart_hints(response, ds_active_results)
        response = _normalize_suggestions(response)
        # Strict-shape styles define EXACT component order in the prompt.
        # Reordering would break the designed layout (e.g. moving the
        # pillar grid away from the overall score card).
        if not _is_strict_shape:
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
            logger.info("── IMAGES ──  attached %d images (query is visual)", len(search_images))
        elif search_images:
            logger.info("── IMAGES ──  suppressed %d images (query not visual)", len(search_images))

        if ds_metadata:
            response["_data_sources"] = ds_metadata
            if ds_metadata.get("active") and ds_metadata.get("successful", 0) > 0:
                seen_sources: dict = {}
                for r in ds_active_results:
                    if r.get("success"):
                        name = r.get("_source_name", r.get("_source_id", "Data"))
                        if name not in seen_sources:
                            seen_sources[name] = {"title": name, "url": "", "type": "data"}
                ds_source_entries = list(seen_sources.values())
                response.setdefault("_sources", []).extend(ds_source_entries)
            elif ds_metadata.get("passive"):
                seen_passive: dict = {}
                for dc in (data_context or []):
                    name = dc.get("label") or dc.get("source", "Data")
                    if name not in seen_passive:
                        seen_passive[name] = {"title": name, "url": "", "type": "data"}
                passive_entries = list(seen_passive.values())
                response.setdefault("_sources", []).extend(passive_entries)

        response["_style"] = style_id
        response["_performance"] = performance_mode
        response["_model"] = effective_model
        response["_provider"] = effective_provider_id
        if effective_model != model or effective_provider_id != provider_id:
            response["_model_upgraded_from"] = model
            response["_provider_upgraded_from"] = provider_id

        logger.info(
            "══ GENERATE DONE ══  style=%s  model=%s/%s  keys=%s",
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
        temperature: Optional[float] = None,
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
            temperature=temperature,
        ):
            if event["event"] == "complete":
                result = event["data"]
            elif event["event"] == "error":
                raise ValueError(event["data"].get("message", "Unknown error"))
        return result or {"text": "No response generated"}


# ── Module-level singleton ─────────────────────────────────────

llm_service = LLMService()
