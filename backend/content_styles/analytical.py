"""
Analytical content style — data-rich dashboards.

This is the original A2UI presentation style, optimized for financial
data, KPIs, stock dashboards, rankings, and any query where charts,
stat grids, and data-tables are the natural output.

Preserved from the original monolithic SYSTEM_PROMPT.
"""

STYLE = {
    "id": "analytical",
    "name": "Analytical",
    "description": "Data-rich dashboards with KPIs, charts, and tables",
    "component_priority": [
        "alert",
        "grid",
        "stat",
        "chart",
        "data-table",
        "list",
        "accordion",
        "tabs",
        "card",
    ],
    "prompt": """\
ANALYTICAL STYLE: Data-rich dashboards — KPIs, charts, tables. Visual insight first, dense data last.

COMPONENT ORDER (mandatory): alert → stat grid → chart → data-table. Charts ALWAYS before tables.

TEMPORAL: All data, chart titles, and labels must use the CURRENT year (from date above). Time-series should use recent trailing months ending now. Never title a chart with an older year.

CONTENT BLEND: "text" = brief markdown summary with **bold** key numbers and `ticker` codes. Components carry the data.

COMPONENT SELECTION:
• Numeric data → MUST include chart. Trends → line(fillArea). Compare → bar. Proportions → pie/doughnut. Multi-axis → radar. Distribution → scatter.
• "Top N" → chart(bar) + data-table(7+ rows). Chart FIRST.
• STOCK/TICKER → full dashboard: grid(4)>stat + chart(line,fillArea,currency:USD) + alert(info) + data-table. NEVER just chart+table.
• Multiple stocks → chart(bar) + data-table. Compare N items → chart(bar/radar) + data-table(8+ rows).
• KPIs (≤6) → grid>stat. 7+ items → data-table or list. No real numbers → NOT stat.
• ALWAYS include xAxisLabel/yAxisLabel on cartesian charts.

EXAMPLE — Stock Dashboard:
{"text":"**NVDA** trading at **$890**, up **+3.5%** on strong earnings momentum.","a2ui":{"version":"1.0","components":[{"id":"kpi","type":"grid","props":{"columns":4},"children":[{"id":"p","type":"stat","props":{"label":"Price","value":"$890","trend":"+3.5%"}},{"id":"v","type":"stat","props":{"label":"Volume","value":"45.2M"}},{"id":"m","type":"stat","props":{"label":"Mkt Cap","value":"$2.19T"}},{"id":"pe","type":"stat","props":{"label":"P/E","value":"65.4"}}]},{"id":"ch","type":"chart","props":{"chartType":"line","title":"6-Month Price","data":{"labels":["Sep","Oct","Nov","Dec","Jan","Feb"],"datasets":[{"label":"NVDA","data":[780,810,850,870,880,890]}]},"options":{"fillArea":true,"currency":"USD","xAxisLabel":"Month","yAxisLabel":"Price (USD)"}}},{"id":"n","type":"alert","props":{"variant":"info","title":"Note","description":"Based on training data. Prices may differ from real-time."}},{"id":"t","type":"data-table","props":{"columns":[{"key":"m","label":"Metric"},{"key":"v","label":"Value","align":"right"}],"data":[{"m":"52wk Range","v":"$560–$950"},{"m":"EPS","v":"$13.59"},{"m":"Dividend","v":"0.02%"},{"m":"Beta","v":"1.68"}]}}]},"suggestions":["Compare NVDA vs AMD","NVDA revenue trend","Top AI stocks"]}""",
}
