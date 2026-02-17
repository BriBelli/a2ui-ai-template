"""
Comparison style — side-by-side analysis.

Optimized for "X vs Y", "compare A and B", pros/cons, and any query
where the user wants to evaluate options against each other.

Leads with a visual comparison chart, followed by a detailed feature
table, with optional takeaways.
"""

STYLE = {
    "id": "comparison",
    "name": "Comparison",
    "description": "Side-by-side analysis with charts and detail tables",
    "component_priority": [
        "alert",
        "chart",
        "data-table",
        "grid",
        "stat",
        "list",
        "accordion",
        "tabs",
        "card",
    ],
    "prompt": """\
COMPARISON STYLE: Side-by-side analysis emphasizing differences and similarities. Lead with visual comparison, then detailed breakdown.

COMPONENT ORDER: alert (if needed) → chart (visual comparison) → data-table (detailed feature breakdown) → list (key takeaways).

COMPONENT SELECTION:
• ALWAYS start with chart(bar) comparing key metrics or features on a shared scale (1-10 ratings, or normalized values). No mixed units on a single axis.
• Follow with data-table showing 8+ rows of detailed feature comparisons, one column per item being compared.
• Use grid>stat for 2-4 headline differentiators ONLY when comparing numeric values (price, specs, performance).
• Add list(bullet) for "bottom line" takeaways or recommendations.
• For subjective comparisons (iPhone vs Android), use 1-10 rating scale on the chart.
• For numeric comparisons (stocks, specs), use actual values with appropriate units.
• "suggestions" should explore deeper aspects. Examples: "iPhone 16 Pro camera deep-dive", "Compare battery life across all flagships".

EXAMPLE — Product Comparison:
{"text":"iPhone vs Android compared.","a2ui":{"version":"1.0","components":[{"id":"ch","type":"chart","props":{"chartType":"bar","title":"Feature Ratings (1-10)","data":{"labels":["Camera","Battery","Display","Performance","AI","Value"],"datasets":[{"label":"iPhone 16 Pro","data":[9,8,9,9,8,7]},{"label":"Galaxy S25 Ultra","data":[10,8,9,9,9,7]}]},"options":{"xAxisLabel":"Feature","yAxisLabel":"Rating (1-10)"}}},{"id":"t","type":"data-table","props":{"columns":[{"key":"f","label":"Feature"},{"key":"a","label":"iPhone"},{"key":"b","label":"Android"}],"data":[{"f":"OS","a":"iOS 18","b":"Android 15"},{"f":"Ecosystem","a":"Apple integrated","b":"Open, customizable"},{"f":"AI","a":"Apple Intelligence","b":"Google Gemini"},{"f":"Camera","a":"48MP ProRes","b":"200MP expert RAW"},{"f":"Price","a":"$799–$1599","b":"$199–$1799"},{"f":"Updates","a":"6+ years","b":"7 years (Samsung)"},{"f":"Security","a":"Face ID, Enclave","b":"Fingerprint, Knox"},{"f":"Charging","a":"MagSafe USB-C","b":"USB-C fast charge"}]}}]},"suggestions":["iPhone 16 Pro vs S25 Ultra camera","Best budget Androids 2025","iOS vs Android market share"]}""",
}
