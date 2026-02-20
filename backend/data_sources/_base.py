"""
Abstract base class for all A2UI data sources.

Every connector (REST, Databricks, etc.) implements this interface.
The registry loads sources from config and exposes them to the pipeline.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class DataSource(ABC):
    """A queryable external data source."""

    def __init__(
        self,
        id: str,
        name: str,
        description: str = "",
        rules: str = "",
        enabled: bool = True,
    ) -> None:
        self.id = id
        self.name = name
        self.description = description
        self.rules = rules
        self.enabled = enabled

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the source is configured and reachable."""
        ...

    @abstractmethod
    async def query(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> Dict[str, Any]:
        """Execute a query against this data source.

        Returns:
            {"success": True, "data": ..., "record_count": N}
            or {"success": False, "error": "..."}
        """
        ...

    def get_endpoints_summary(self) -> str:
        """Compact summary of available endpoints for the AI analyzer.

        Override in subclasses that support endpoint discovery.
        Returns empty string if no endpoint metadata is available.
        """
        return ""

    def get_analyzer_summary(self) -> str:
        """Full context block for the AI analyzer prompt.

        Combines name, description, and endpoint summary.
        """
        parts = [f"{self.id}: {self.name}"]
        if self.description:
            parts[0] += f" — {self.description}"
        endpoints = self.get_endpoints_summary()
        if endpoints:
            parts.append(endpoints)
        return "\n".join(parts)

    def format_for_context(
        self,
        results: Dict[str, Any],
        label: Optional[str] = None,
    ) -> str:
        """Format query results as LLM context.

        Produces a ``[Data Source: ...]`` block that gets prepended to
        the user message, identical to how ``[Web Search Results]`` works.
        """
        if not results.get("success"):
            return ""

        data = results.get("data")
        if data is None:
            return ""

        tag = label or self.name
        import json
        if isinstance(data, (dict, list)):
            serialized = json.dumps(data, default=str, ensure_ascii=False)
            # Truncate very large payloads to keep context reasonable
            if len(serialized) > 12_000:
                serialized = serialized[:12_000] + "\n... (truncated)"
        else:
            serialized = str(data)

        return f"[Data Source: {tag}]\n{serialized}\n"

    def to_dict(self) -> Dict[str, Any]:
        """Serializable representation for the /api/data-sources endpoint."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "available": self.is_available(),
            "has_rules": bool(self.rules),
            "endpoints": self.get_endpoints_summary() or None,
        }
