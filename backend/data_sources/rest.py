"""
Generic REST API data source with optional OpenAPI/Swagger discovery.

Supports:
- Static endpoint definitions from config
- Auto-discovery from OpenAPI 3.x / Swagger 2.x specs
- Bearer token, API key header, or no auth
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from ._base import DataSource

logger = logging.getLogger(__name__)


class _Endpoint:
    """Parsed endpoint metadata."""

    __slots__ = ("path", "method", "description", "params")

    def __init__(
        self,
        path: str,
        method: str = "GET",
        description: str = "",
        params: Optional[List[str]] = None,
    ) -> None:
        self.path = path
        self.method = method.upper()
        self.description = description
        self.params = params or []

    def summary_line(self) -> str:
        parts = [f"  {self.method} {self.path}"]
        if self.description:
            parts[0] += f" — {self.description}"
        if self.params:
            parts.append(f"    params: {', '.join(self.params)}")
        return "\n".join(parts)


def _resolve_env(val: Optional[str]) -> Optional[str]:
    """If *val* looks like an env-var name, resolve it; else return as-is."""
    if val and val.endswith("_ENV"):
        return os.getenv(val)
    if val and val.startswith("$"):
        return os.getenv(val[1:])
    return val


class RESTDataSource(DataSource):
    """Connect to any REST API.

    Config keys (from ``data_sources/config.yaml``):

    .. code-block:: yaml

        - id: sales-api
          type: rest
          name: Sales Dashboard
          base_url: https://api.example.com/v1
          auth:
            type: bearer          # bearer | api_key | none
            token_env: SALES_TOKEN
          openapi_spec: ./specs/sales.yaml
          endpoints:              # optional manual endpoint list
            - path: /revenue
              method: GET
              description: Revenue by quarter
              params: [period, year]
          description: Sales data including revenue and pipeline
          rules: Always use date ranges with /revenue
    """

    def __init__(self, cfg: Dict[str, Any]) -> None:
        super().__init__(
            id=cfg["id"],
            name=cfg.get("name", cfg["id"]),
            description=cfg.get("description", ""),
            rules=cfg.get("rules", ""),
            enabled=cfg.get("enabled", True),
        )
        self.base_url = (cfg.get("base_url") or "").rstrip("/")
        self._endpoints: List[_Endpoint] = []

        # Auth
        auth = cfg.get("auth") or {}
        self._auth_type = auth.get("type", "none")
        self._auth_token = _resolve_env(auth.get("token_env") or auth.get("token"))
        self._auth_header = auth.get("header", "Authorization")

        # Parse manually defined endpoints
        for ep in cfg.get("endpoints") or []:
            self._endpoints.append(_Endpoint(
                path=ep["path"],
                method=ep.get("method", "GET"),
                description=ep.get("description", ""),
                params=ep.get("params", []),
            ))

        # Parse OpenAPI spec (file path or URL resolved at init)
        spec_path = cfg.get("openapi_spec")
        if spec_path:
            self._load_openapi_spec(spec_path)

    # ── Auth helpers ──────────────────────────────────────────

    def _auth_headers(self) -> Dict[str, str]:
        if self._auth_type == "bearer" and self._auth_token:
            return {"Authorization": f"Bearer {self._auth_token}"}
        if self._auth_type == "api_key" and self._auth_token:
            return {self._auth_header: self._auth_token}
        return {}

    # ── OpenAPI parsing ───────────────────────────────────────

    def _load_openapi_spec(self, path: str) -> None:
        """Parse an OpenAPI 3.x or Swagger 2.x spec into endpoints."""
        import yaml

        try:
            if path.startswith("http"):
                resp = httpx.get(path, timeout=10)
                spec = yaml.safe_load(resp.text) if resp.status_code == 200 else {}
            else:
                resolved = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "..", path
                )
                with open(resolved) as f:
                    spec = yaml.safe_load(f)
        except Exception as exc:
            logger.warning("Failed to load OpenAPI spec '%s': %s", path, exc)
            return

        if not spec:
            return

        paths = spec.get("paths") or {}
        for route, methods in paths.items():
            for method, detail in methods.items():
                if method.lower() not in ("get", "post", "put", "patch", "delete"):
                    continue
                params = [
                    p.get("name", "")
                    for p in (detail.get("parameters") or [])
                    if p.get("in") in ("query", "path")
                ]
                ep = _Endpoint(
                    path=route,
                    method=method.upper(),
                    description=(detail.get("summary") or detail.get("description") or "")[:120],
                    params=params,
                )
                # Avoid duplicates from manual + spec overlap
                if not any(e.path == ep.path and e.method == ep.method for e in self._endpoints):
                    self._endpoints.append(ep)

        logger.info(
            "Loaded %d endpoints from OpenAPI spec for '%s'",
            len(self._endpoints), self.id,
        )

    # ── DataSource interface ──────────────────────────────────

    def is_available(self) -> bool:
        if not self.base_url:
            return False
        if self._auth_type != "none" and not self._auth_token:
            return False
        return self.enabled

    def _is_allowed_endpoint(self, endpoint: str, method: str) -> bool:
        """Check if the endpoint is in the configured whitelist."""
        if not self._endpoints:
            return True
        normalized = endpoint.rstrip("/")
        for ep in self._endpoints:
            if ep.path.rstrip("/") == normalized and ep.method == method.upper():
                return True
            if ep.path.rstrip("/") == normalized and method.upper() == "GET":
                return True
        return False

    async def query(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> Dict[str, Any]:
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        if ".." in endpoint or "://" in endpoint:
            logger.warning("Blocked path traversal/injection: %s", endpoint)
            return {"success": False, "error": "invalid_endpoint"}

        if not self._is_allowed_endpoint(endpoint, method):
            logger.warning(
                "Blocked non-whitelisted endpoint: %s %s (source: %s)",
                method, endpoint, self.id,
            )
            return {"success": False, "error": "endpoint_not_allowed"}

        url = f"{self.base_url}{endpoint}"
        headers = {**self._auth_headers(), "Accept": "application/json"}

        logger.info(
            "── DATA SOURCE ──  %s %s  params=%s",
            method.upper(), url, params,
        )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if method.upper() == "GET":
                    resp = await client.get(url, params=params, headers=headers)
                else:
                    resp = await client.request(
                        method.upper(), url, json=params, headers=headers,
                    )

                if resp.status_code >= 400:
                    logger.warning(
                        "Data source '%s' returned %d: %s",
                        self.id, resp.status_code, resp.text[:200],
                    )
                    return {
                        "success": False,
                        "error": f"HTTP {resp.status_code}",
                        "status_code": resp.status_code,
                    }

                try:
                    data = resp.json()
                except Exception:
                    data = resp.text

                record_count = len(data) if isinstance(data, list) else 1
                logger.info(
                    "── DATA SOURCE OK ──  %s  %d records  %d bytes",
                    self.id, record_count, len(resp.text),
                )
                return {
                    "success": True,
                    "data": data,
                    "record_count": record_count,
                    "source": self.id,
                }

        except httpx.TimeoutException:
            logger.warning("Data source '%s' timed out", self.id)
            return {"success": False, "error": "timeout"}
        except Exception as exc:
            logger.warning("Data source '%s' error: %s", self.id, exc)
            return {"success": False, "error": str(exc)}

    def get_endpoints_summary(self) -> str:
        if not self._endpoints:
            return ""
        return "\n".join(ep.summary_line() for ep in self._endpoints)
