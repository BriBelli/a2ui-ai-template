"""
A2UI Data Sources — registry and public API.

Loads source definitions from ``config.yaml`` at import time and
provides a typed registry the pipeline uses to discover, query,
and format external data.

Public API:
    get_available_sources()  — list of source dicts for /api/data-sources
    get_source(id)           — get a DataSource by id
    get_all_sources()        — all loaded DataSource instances
    get_analyzer_context()   — compact summary for the AI analyzer prompt
    get_rules_context()      — LLM rules aggregated from all sources
    query_sources(queries)   — execute multiple source queries in parallel
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import yaml

from ._base import DataSource

logger = logging.getLogger(__name__)

# ── Source registry ───────────────────────────────────────────

_SOURCES: Dict[str, DataSource] = {}
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def _load_config() -> None:
    """Parse config.yaml and instantiate source objects."""
    global _SOURCES

    if not os.path.exists(_CONFIG_PATH):
        logger.info("No data sources config found at %s", _CONFIG_PATH)
        return

    try:
        with open(_CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.warning("Failed to parse data sources config: %s", exc)
        return

    entries = cfg.get("sources") or []
    if not entries:
        logger.info("Data sources config loaded — 0 sources defined")
        return

    for entry in entries:
        src_id = entry.get("id")
        src_type = entry.get("type", "rest")
        if not src_id:
            logger.warning("Skipping data source with no 'id'")
            continue

        try:
            source = _create_source(src_type, entry)
            _SOURCES[src_id] = source
            logger.info(
                "Registered data source: %s (%s) available=%s",
                src_id, src_type, source.is_available(),
            )
        except Exception as exc:
            logger.warning(
                "Failed to create data source '%s': %s", src_id, exc,
            )

    logger.info(
        "Data sources loaded: %d total, %d available",
        len(_SOURCES),
        sum(1 for s in _SOURCES.values() if s.is_available()),
    )


def _create_source(src_type: str, cfg: Dict[str, Any]) -> DataSource:
    """Factory: create the right DataSource subclass."""
    if src_type == "rest":
        from .rest import RESTDataSource
        return RESTDataSource(cfg)
    elif src_type == "databricks":
        from .databricks import DatabricksDataSource
        return DatabricksDataSource(cfg)
    else:
        raise ValueError(f"Unknown data source type: {src_type}")


# ── Public API ────────────────────────────────────────────────


def get_source(source_id: str) -> Optional[DataSource]:
    """Get a specific source by ID."""
    return _SOURCES.get(source_id)


def get_all_sources() -> List[DataSource]:
    """Return all loaded sources (regardless of availability)."""
    return list(_SOURCES.values())


def get_available_sources() -> List[Dict[str, Any]]:
    """Serializable list of sources for the /api/data-sources endpoint."""
    return [s.to_dict() for s in _SOURCES.values()]


def get_analyzer_context() -> str:
    """Compact summary of available sources for the AI analyzer prompt.

    Returns an empty string if no sources are available (the analyzer
    will skip the data_sources decision entirely).
    """
    available = [s for s in _SOURCES.values() if s.is_available()]
    if not available:
        return ""

    lines = ["Available data sources:"]
    for s in available:
        lines.append(s.get_analyzer_summary())
    return "\n".join(lines)


def get_rules_context() -> str:
    """Aggregate LLM rules from all available sources.

    Injected into the system prompt so the LLM knows HOW and WHEN
    to interpret data from each source.
    """
    available = [s for s in _SOURCES.values() if s.is_available() and s.rules]
    if not available:
        return ""

    lines = ["[Data Source Rules]"]
    for s in available:
        lines.append(f"• {s.name}: {s.rules.strip()}")
    return "\n".join(lines)


async def query_sources(
    queries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Execute multiple data source queries in parallel.

    Each query dict should have:
        {"source": "source-id", "endpoint": "/path", "params": {...}}

    Returns a list of result dicts (one per query).
    """
    tasks = []
    for q in queries:
        source = _SOURCES.get(q.get("source", ""))
        if not source or not source.is_available():
            tasks.append(_skip_result(q))
            continue
        tasks.append(_execute_query(source, q))

    return await asyncio.gather(*tasks)


async def _execute_query(
    source: DataSource,
    query: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute a single source query with error handling."""
    try:
        result = await source.query(
            endpoint=query.get("endpoint", ""),
            params=query.get("params"),
            method=query.get("method", "GET"),
        )
        result["_source_id"] = source.id
        result["_source_name"] = source.name
        return result
    except Exception as exc:
        logger.warning("Data source query failed (%s): %s", source.id, exc)
        return {
            "success": False,
            "error": str(exc),
            "_source_id": source.id,
            "_source_name": source.name,
        }


async def _skip_result(query: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "success": False,
        "error": "source_unavailable",
        "_source_id": query.get("source", "unknown"),
        "_source_name": query.get("source", "unknown"),
    }


def format_results_for_context(results: List[Dict[str, Any]]) -> str:
    """Combine multiple source results into a single LLM context block."""
    blocks: List[str] = []
    for r in results:
        source = _SOURCES.get(r.get("_source_id", ""))
        if source and r.get("success"):
            block = source.format_for_context(r, label=r.get("_source_name"))
            if block:
                blocks.append(block)
    return "\n".join(blocks)


# ── Load on import ────────────────────────────────────────────
_load_config()
