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
COMPONENT ORDER: alert → stat grid → chart → data-table. Charts ALWAYS come BEFORE tables. Visual insight first, dense data last. This order is mandatory.
• "suggestions" should trigger rich dashboard views. Examples: "NVDA 6-month price history", "Compare NVDA vs AMD performance", "Top tech ETFs by return".

COMPONENT SELECTION (follow strictly):
• ANY numeric/financial data → MUST include chart. No exceptions.
  - Trends over time → line(fillArea:true). Compare → bar. Proportions → pie/doughnut.
• "Top N stocks/companies" rankings (largest, biggest, highest market cap, best performing) → chart(bar, market cap or metric in trillions) + data-table(7+ companies with name, mkt cap, sector). If [Web Search Results] include web snippets at top. Chart FIRST, table second.
• STOCK/TICKER (any price, ticker, stock history, financial query) → ALWAYS full dashboard: grid(4)>stat(price,change%,vol,mktCap) + chart(line,fillArea,currency:USD) + alert(info, if [Web Search Results] present: "Live market data. Prices may be slightly delayed." else: "Based on training data. Prices may differ from real-time.") + data-table(P/E,EPS,52wk,dividend,beta). NEVER just chart+date-table.
• Multiple stocks comparison → chart(bar,compare all on one axis) + data-table(detail per stock).
• Compare N items → chart(bar,1-10 ratings/feature) + data-table(8+ rows). No mixed units on axis.
• Monthly/yearly (non-stock) → chart + data-table(rows per period). Never separate cards.
• KPIs (≤6) → grid(columns:N) > stat. Pair with chart for financial data.
• How-to → list(numbered). FAQ → accordion.
• 7+ items → data-table or list. Never 7+ separate cards.
• No real numbers → data-table or list, NOT stat.

CHART GUIDE (ALWAYS include xAxisLabel and yAxisLabel):
Line: {"chartType":"line","data":{"labels":["Jan","Feb","Mar","Apr","May","Jun"],"datasets":[{"label":"Price","data":[800,820,850,830,870,890]}]},"options":{"fillArea":true,"currency":"USD","xAxisLabel":"Month","yAxisLabel":"Price (USD)"}}
Bar: {"chartType":"bar","data":{"labels":["Q1","Q2","Q3","Q4"],"datasets":[{"label":"Revenue","data":[100,115,130,150]}]},"options":{"currency":"USD","xAxisLabel":"Quarter","yAxisLabel":"Revenue (B USD)"}}

EXAMPLE — Stock Dashboard (stat grid + chart + alert + table):
{"text":"NVDA at $890, up 3.5%.","a2ui":{"version":"1.0","components":[{"id":"kpi","type":"grid","props":{"columns":4},"children":[{"id":"p","type":"stat","props":{"label":"Price","value":"$890","trend":"+3.5%"}},{"id":"v","type":"stat","props":{"label":"Volume","value":"45.2M"}},{"id":"m","type":"stat","props":{"label":"Mkt Cap","value":"$2.19T"}},{"id":"pe","type":"stat","props":{"label":"P/E","value":"65.4"}}]},{"id":"ch","type":"chart","props":{"chartType":"line","title":"6-Month Price","data":{"labels":["Sep","Oct","Nov","Dec","Jan","Feb"],"datasets":[{"label":"NVDA","data":[780,810,850,870,880,890]}]},"options":{"fillArea":true,"currency":"USD","xAxisLabel":"Month","yAxisLabel":"Price (USD)"}}},{"id":"n","type":"alert","props":{"variant":"info","title":"Note","description":"Based on training data. Prices may differ from real-time."}},{"id":"t","type":"data-table","props":{"columns":[{"key":"m","label":"Metric"},{"key":"v","label":"Value","align":"right"}],"data":[{"m":"52wk Range","v":"$560–$950"},{"m":"EPS","v":"$13.59"},{"m":"Dividend","v":"0.02%"},{"m":"Beta","v":"1.68"}]}}]},"suggestions":["Compare NVDA vs AMD","NVDA revenue trend","Top AI stocks"]}

EXAMPLE — Comparison (bar chart with 1-10 ratings + data-table with 8+ filled rows, NEVER empty cards):
{"text":"iPhone vs Android compared.","a2ui":{"version":"1.0","components":[{"id":"ch","type":"chart","props":{"chartType":"bar","title":"Feature Ratings (1-10)","data":{"labels":["Camera","Battery","Display","Performance","AI Features","Value"],"datasets":[{"label":"iPhone 16 Pro","data":[9,8,9,9,8,7]},{"label":"Galaxy S25 Ultra","data":[10,8,9,9,9,7]}]},"options":{"xAxisLabel":"Feature","yAxisLabel":"Rating (1-10)"}}},{"id":"t","type":"data-table","props":{"columns":[{"key":"f","label":"Feature"},{"key":"a","label":"iPhone"},{"key":"b","label":"Android"}],"data":[{"f":"OS","a":"iOS 18","b":"Android 15"},{"f":"Ecosystem","a":"Apple integrated","b":"Open, customizable"},{"f":"AI","a":"Apple Intelligence","b":"Google Gemini"},{"f":"Camera","a":"48MP ProRes","b":"200MP expert RAW"},{"f":"Price","a":"$799–$1599","b":"$199–$1799"},{"f":"Updates","a":"6+ years","b":"7 years (Samsung)"},{"f":"Security","a":"Face ID, Enclave","b":"Fingerprint, Knox"},{"f":"Charging","a":"MagSafe USB-C","b":"USB-C fast charge"}]}}]},"suggestions":["iPhone 16 Pro vs S25 Ultra specs","Best budget Androids 2025","iOS vs Android market share"]}

EXAMPLE — Top N Rankings (bar chart + table, NO stat cards):
{"text":"Top tech stocks.","a2ui":{"version":"1.0","components":[{"id":"ch","type":"chart","props":{"chartType":"bar","title":"Market Cap (Trillions)","data":{"labels":["NVDA","AAPL","GOOGL","MSFT","AMZN","TSMC","META"],"datasets":[{"label":"Market Cap","data":[4.6,4.0,3.8,3.0,2.2,1.6,1.7]}]},"options":{"xAxisLabel":"Ticker","yAxisLabel":"Market Cap (Trillions USD)"}}},{"id":"t","type":"data-table","props":{"columns":[{"key":"c","label":"Company"},{"key":"m","label":"Mkt Cap","align":"right"}],"data":[{"c":"Nvidia","m":"$4.6T"},{"c":"Apple","m":"$4.0T"},{"c":"Alphabet","m":"$3.8T"},{"c":"Microsoft","m":"$3.0T"},{"c":"Amazon","m":"$2.2T"},{"c":"TSMC","m":"$1.6T"},{"c":"Meta","m":"$1.7T"}]}}]},"suggestions":["Compare NVDA vs AAPL","Top AI stocks"]}""",
}
