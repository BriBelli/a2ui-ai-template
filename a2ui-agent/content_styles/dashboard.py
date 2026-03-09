"""
Dashboard content style — modern analytical dashboard layout.

Optimized for visual, card-based dashboard presentations where KPI stat
cards sit in a hero row at the top, followed by prominent charts, and
optional detail tables at the bottom.  Minimal narrative text — the
components *are* the answer.

Differs from "analytical" by emphasizing grid/card layout, multiple
chart panels, and a polished dashboard aesthetic over text summaries.
"""

STYLE = {
    "id": "dashboard",
    "name": "Dashboard",
    "description": "Modern analytical dashboard with KPI cards, charts, and clean grid layout",
    "component_priority": [
        "grid",
        "stat",
        "chart",
        "card",
        "data-table",
        "alert",
        "list",
        "accordion",
        "tabs",
    ],
    "prompt": """\
DASHBOARD STYLE: KPI hero row + charts + tables. Components ARE the answer.
Order: grid>stat(3-4 KPIs) → chart(s) → data-table(detail). "text" = one headline sentence max.
Trends → line(fillArea). Breakdowns → doughnut. No multi-paragraph prose.""",
}
