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
COMPARISON STYLE: Side-by-side analysis emphasizing differences and similarities. Visual comparison first, detailed breakdown second.

COMPONENT ORDER: alert (if needed) → chart (visual comparison) → data-table (feature breakdown) → list (takeaways).

TEMPORAL: All comparisons must use CURRENT-year products, versions, specs, and pricing (from date above). Reference the latest models/versions. If uncertain about current specs, use most recent known and note it.

CONTENT BLEND: Use "text" for a markdown summary with **bold** key takeaways — give the user the bottom line up front. Radar charts work well for multi-dimensional comparisons. Use data-table for detailed feature-by-feature breakdowns.

COMPONENT SELECTION:
• ALWAYS start with chart comparing key metrics: bar for direct comparison, radar for multi-dimensional profiles. Shared scale (1-10 ratings, or normalized values). No mixed units.
• Follow with data-table: 8+ rows of detailed feature comparisons, one column per item.
• grid>stat for 2-4 headline differentiators ONLY for numeric values (price, specs, performance).
• list(bullet) for "bottom line" takeaways or recommendations.
• Subjective comparisons → 1-10 rating scale. Numeric comparisons → actual values with units.

EXAMPLE — Product Comparison:
{"text":"**iPhone vs Android**: iPhone leads in ecosystem integration and privacy; Android dominates in customization and value range.","a2ui":{"version":"1.0","components":[{"id":"ch","type":"chart","props":{"chartType":"bar","title":"Feature Ratings (1-10)","data":{"labels":["Camera","Battery","Display","Performance","AI","Value"],"datasets":[{"label":"iPhone (latest Pro)","data":[9,8,9,9,8,7]},{"label":"Android (latest flagship)","data":[10,8,9,9,9,7]}]},"options":{"xAxisLabel":"Feature","yAxisLabel":"Rating (1-10)"}}},{"id":"t","type":"data-table","props":{"columns":[{"key":"f","label":"Feature"},{"key":"a","label":"iPhone"},{"key":"b","label":"Android"}],"data":[{"f":"OS","a":"Latest iOS","b":"Latest Android"},{"f":"Ecosystem","a":"Apple integrated","b":"Open, customizable"},{"f":"AI","a":"Apple Intelligence","b":"Google Gemini"},{"f":"Camera","a":"48MP ProRes","b":"200MP expert RAW"},{"f":"Price Range","a":"$799–$1599","b":"$199–$1799"},{"f":"Update Support","a":"6+ years","b":"7 years (Samsung)"},{"f":"Security","a":"Face ID, Secure Enclave","b":"Fingerprint, Knox"},{"f":"Charging","a":"MagSafe USB-C","b":"USB-C fast charge"}]}}]},"suggestions":["iPhone Pro vs Galaxy Ultra camera comparison","Best budget Android phones"]}""",
}
