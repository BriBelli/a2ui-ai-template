#!/usr/bin/env python3
"""
Data Sources — Quick Test Script

Run from the backend directory while the server is running:
    python3 data_sources/test_data_sources.py

Tests both passive and active data source modes against your local API.
"""

import asyncio
import json
import sys

import httpx

BASE = "http://localhost:8000"
PROVIDER = "openai"
MODEL = "gpt-4.1-mini"

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def heading(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{'═' * 60}")
    print(f"  {text}")
    print(f"{'═' * 60}{RESET}\n")


def result(label: str, value: str) -> None:
    print(f"  {YELLOW}{label:20s}{RESET}  {value}")


def print_response(resp: dict) -> None:
    result("Style", resp.get("_style", "?"))
    result("Data Sources", json.dumps(resp.get("_data_sources", "none")))
    result("Text", (resp.get("text") or "")[:120])

    a2ui = resp.get("a2ui")
    if a2ui:
        comps = a2ui.get("components", [])
        result("Components", f"{len(comps)} total")
        for c in comps[:4]:
            ctype = c.get("type", "?")
            props_preview = str(c.get("props", {}))[:80]
            print(f"                        → {GREEN}{ctype}{RESET}: {props_preview}")
    else:
        result("Components", "0 (text only)")
    print()


async def test_health() -> bool:
    heading("Test 0: Health Check")
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.get(f"{BASE}/api/data-sources")
            data = r.json()
            sources = data.get("sources", [])
            print(f"  {GREEN}✓ Server is running{RESET}")
            print(f"  {GREEN}✓ /api/data-sources returned {len(sources)} source(s){RESET}")
            for s in sources:
                avail = f"{GREEN}available{RESET}" if s["available"] else f"{RED}unavailable{RESET}"
                print(f"    • {s['name']} ({s['id']}) — {avail}")
            return True
        except Exception as e:
            print(f"  {RED}✗ Server not reachable: {e}{RESET}")
            print(f"  {RED}  Start it with: cd backend && python3 app.py{RESET}")
            return False


async def test_passive() -> None:
    heading("Test 1: Passive Data Injection")
    print("  Sending pre-fetched sales data via dataContext...\n")

    body = {
        "message": "Summarize this Q1 sales performance",
        "provider": PROVIDER,
        "model": MODEL,
        "enableWebSearch": False,
        "enableDataSources": True,
        "dataContext": [
            {
                "source": "sales-api",
                "label": "Q1 2026 Sales Report",
                "data": {
                    "quarter": "Q1 2026",
                    "total_revenue": 2_450_000,
                    "deals_closed": 47,
                    "average_deal_size": 52_128,
                    "top_performer": "Sarah Chen",
                    "pipeline_value": 8_900_000,
                    "win_rate": 0.34,
                    "monthly_breakdown": [
                        {"month": "January", "revenue": 720_000, "deals": 14},
                        {"month": "February", "revenue": 830_000, "deals": 16},
                        {"month": "March", "revenue": 900_000, "deals": 17},
                    ],
                },
            }
        ],
    }

    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(f"{BASE}/api/chat", json=body)
        resp = r.json()

    if r.status_code == 200 and resp.get("_data_sources", {}).get("passive"):
        print(f"  {GREEN}✓ Passive injection worked!{RESET}")
    else:
        print(f"  {RED}✗ Unexpected response (status={r.status_code}){RESET}")

    print_response(resp)


async def test_passive_multi() -> None:
    heading("Test 1b: Passive — Multiple Data Sources")
    print("  Sending 3 different data sources in one request...\n")

    body = {
        "message": "Compare our sales performance across all regions and show customer satisfaction trends",
        "provider": PROVIDER,
        "model": MODEL,
        "enableWebSearch": False,
        "enableDataSources": True,
        "dataContext": [
            {
                "source": "sales-api",
                "label": "Regional Sales",
                "data": [
                    {"region": "North America", "revenue": 1_200_000, "growth": 0.12},
                    {"region": "Europe", "revenue": 890_000, "growth": 0.08},
                    {"region": "Asia Pacific", "revenue": 650_000, "growth": 0.22},
                ],
            },
            {
                "source": "crm-api",
                "label": "Customer Satisfaction",
                "data": [
                    {"quarter": "Q1", "nps": 72, "csat": 4.3, "churn_rate": 0.04},
                    {"quarter": "Q2", "nps": 75, "csat": 4.5, "churn_rate": 0.03},
                    {"quarter": "Q3", "nps": 68, "csat": 4.1, "churn_rate": 0.05},
                    {"quarter": "Q4", "nps": 80, "csat": 4.6, "churn_rate": 0.02},
                ],
            },
            {
                "source": "hr-api",
                "label": "Team Headcount",
                "data": {"sales_reps": 24, "account_managers": 8, "support": 12},
            },
        ],
    }

    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(f"{BASE}/api/chat", json=body)
        resp = r.json()

    ds = resp.get("_data_sources", {})
    count = ds.get("sources", 0)
    if r.status_code == 200 and ds.get("passive") and count == 3:
        print(f"  {GREEN}✓ Multi-source passive worked! ({count} sources injected){RESET}")
    elif r.status_code == 200 and ds.get("passive"):
        print(f"  {GREEN}✓ Passive worked with {count} source(s){RESET}")
    else:
        print(f"  {RED}✗ Unexpected response{RESET}")

    print_response(resp)


async def test_active() -> None:
    heading("Test 2: Active Data Source Query (AI-Decided)")
    print("  Asking about users — AI should query JSONPlaceholder /users...\n")

    body = {
        "message": "Show me all users from the sample database with their companies",
        "provider": PROVIDER,
        "model": MODEL,
        "enableWebSearch": False,
        "enableDataSources": True,
    }

    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(f"{BASE}/api/chat", json=body)
        resp = r.json()

    ds = resp.get("_data_sources", {})
    if r.status_code == 200 and ds.get("active") and ds.get("successful", 0) > 0:
        print(f"  {GREEN}✓ Active query worked! ({ds['successful']}/{ds['queries']} queries succeeded){RESET}")
    else:
        print(f"  {YELLOW}⚠ AI may not have routed to data source (status={r.status_code}){RESET}")
        print(f"    _data_sources = {ds}")

    print_response(resp)


async def test_disabled() -> None:
    heading("Test 3: Data Sources Disabled (Tool Gate)")
    print("  Same query but with enableDataSources=false...\n")

    body = {
        "message": "Show me all users from the sample database",
        "provider": PROVIDER,
        "model": MODEL,
        "enableWebSearch": False,
        "enableDataSources": False,
    }

    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(f"{BASE}/api/chat", json=body)
        resp = r.json()

    ds = resp.get("_data_sources")
    if ds is None:
        print(f"  {GREEN}✓ Data sources correctly skipped (tool disabled){RESET}")
    else:
        print(f"  {RED}✗ Data sources ran despite being disabled: {ds}{RESET}")

    print_response(resp)


async def test_active_todos() -> None:
    heading("Test 4: Active Query — Todos (Different Endpoint)")
    print("  Asking about task completion — AI should query /todos...\n")

    body = {
        "message": "How many sample todos are completed vs still pending? Show the breakdown.",
        "provider": PROVIDER,
        "model": MODEL,
        "enableWebSearch": False,
        "enableDataSources": True,
    }

    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(f"{BASE}/api/chat", json=body)
        resp = r.json()

    ds = resp.get("_data_sources", {})
    if r.status_code == 200 and ds.get("active") and ds.get("successful", 0) > 0:
        print(f"  {GREEN}✓ Active query worked! ({ds['successful']}/{ds['queries']} queries succeeded){RESET}")
    else:
        print(f"  {YELLOW}⚠ AI may not have routed to data source{RESET}")

    print_response(resp)


async def main() -> None:
    print(f"\n{BOLD}{'─' * 60}")
    print(f"  A2UI Data Sources — Test Suite")
    print(f"{'─' * 60}{RESET}")
    print(f"  Server:   {BASE}")
    print(f"  Provider: {PROVIDER}/{MODEL}")

    if not await test_health():
        sys.exit(1)

    await test_passive()
    await test_passive_multi()
    await test_active()
    await test_disabled()
    await test_active_todos()

    heading("All Tests Complete ✓")


if __name__ == "__main__":
    asyncio.run(main())
