"""
Databricks Genie data source connector.

Connects to a Databricks Genie space to query enterprise data via natural
language.  The AI analyzer sends the user's question directly to Genie,
and the tabular/text result is injected into LLM context.

Config example:

.. code-block:: yaml

    - id: databricks-genie
      type: databricks
      name: Enterprise Analytics
      config:
        workspace_url_env: DATABRICKS_WORKSPACE_URL
        token_env: DATABRICKS_TOKEN
        space_id: "your-genie-space-id"
      description: Enterprise data warehouse — customer analytics, KPIs
      rules: Use for deep analytical questions about internal data
"""

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from ._base import DataSource

logger = logging.getLogger(__name__)


def _env(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    return os.getenv(key)


class DatabricksDataSource(DataSource):
    """Query a Databricks Genie space."""

    def __init__(self, cfg: Dict[str, Any]) -> None:
        super().__init__(
            id=cfg["id"],
            name=cfg.get("name", cfg["id"]),
            description=cfg.get("description", ""),
            rules=cfg.get("rules", ""),
            enabled=cfg.get("enabled", True),
        )
        conf = cfg.get("config") or {}
        self._workspace_url = (
            _env(conf.get("workspace_url_env"))
            or conf.get("workspace_url", "")
        ).rstrip("/")
        self._token = _env(conf.get("token_env")) or conf.get("token", "")
        self._space_id = conf.get("space_id", "")

    def is_available(self) -> bool:
        return bool(
            self.enabled
            and self._workspace_url
            and self._token
            and self._space_id
        )

    async def query(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> Dict[str, Any]:
        """Send a natural-language question to Genie.

        ``endpoint`` is treated as the question text (Genie doesn't have
        traditional REST endpoints — it accepts natural language).
        ``params`` can optionally include ``{"question": "..."}`` which
        takes precedence over ``endpoint``.
        """
        question = (params or {}).get("question", endpoint)
        if not question:
            return {"success": False, "error": "No question provided"}

        url = (
            f"{self._workspace_url}/api/2.0/genie/spaces"
            f"/{self._space_id}/start-conversation"
        )
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        body = {"content": question}

        logger.info(
            "── DATABRICKS GENIE ──  space=%s  question='%s'",
            self._space_id, question[:80],
        )

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, json=body, headers=headers)

                if resp.status_code >= 400:
                    logger.warning(
                        "Genie returned %d: %s",
                        resp.status_code, resp.text[:200],
                    )
                    return {
                        "success": False,
                        "error": f"HTTP {resp.status_code}",
                    }

                result = resp.json()
                conversation_id = result.get("conversation_id", "")
                message_id = result.get("message_id", "")

                # Poll for completion (Genie is async)
                if conversation_id and message_id:
                    data = await self._poll_result(
                        client, headers, conversation_id, message_id,
                    )
                    if data is not None:
                        record_count = (
                            len(data) if isinstance(data, list) else 1
                        )
                        logger.info(
                            "── GENIE OK ──  %d records", record_count,
                        )
                        return {
                            "success": True,
                            "data": data,
                            "record_count": record_count,
                            "source": self.id,
                        }

                # Fallback: return the raw response
                return {
                    "success": True,
                    "data": result,
                    "record_count": 1,
                    "source": self.id,
                }

        except httpx.TimeoutException:
            logger.warning("Genie timed out for '%s'", self.id)
            return {"success": False, "error": "timeout"}
        except Exception as exc:
            logger.warning("Genie error for '%s': %s", self.id, exc)
            return {"success": False, "error": str(exc)}

    async def _poll_result(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        conversation_id: str,
        message_id: str,
        max_polls: int = 15,
    ) -> Optional[Any]:
        """Poll Genie for a completed result."""
        import asyncio

        poll_url = (
            f"{self._workspace_url}/api/2.0/genie/spaces"
            f"/{self._space_id}/conversations/{conversation_id}"
            f"/messages/{message_id}"
        )

        for i in range(max_polls):
            await asyncio.sleep(2)
            resp = await client.get(poll_url, headers=headers)
            if resp.status_code != 200:
                continue

            msg = resp.json()
            status = msg.get("status", "")

            if status == "COMPLETED":
                # Extract tabular or text result
                for attachment in msg.get("attachments") or []:
                    if attachment.get("type") == "QUERY_RESULT":
                        return attachment.get("query_result", {}).get("data")
                    if attachment.get("type") == "TEXT":
                        return attachment.get("text", {}).get("content")
                return msg.get("content")

            if status in ("FAILED", "CANCELLED"):
                logger.warning("Genie message %s: %s", status, msg.get("error", ""))
                return None

        logger.warning("Genie poll exhausted after %d attempts", max_polls)
        return None

    def get_endpoints_summary(self) -> str:
        return "  Accepts natural language questions about enterprise data"
