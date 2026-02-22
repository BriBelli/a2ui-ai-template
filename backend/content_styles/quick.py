"""
Quick style — concise direct answers.

Optimized for simple questions, definitions, yes/no answers, and any
query where the user wants a fast, focused response without heavy UI.

Markdown-first with minimal components. This is the lightest style,
producing the smallest system prompt for maximum WAF headroom and
fastest response times.
"""

STYLE = {
    "id": "quick",
    "name": "Quick Answer",
    "description": "Concise direct answers for simple questions",
    "component_priority": [
        "alert",
        "text",
        "list",
        "chip",
        "card",
        "data-table",
        "accordion",
        "stat",
        "chart",
        "grid",
        "tabs",
    ],
    "prompt": """\
QUICK STYLE: Concise, direct answers. Markdown-first, minimal components.

TEMPORAL: Answer based on current knowledge as of the date above. Use current dates, figures, and versions.

CONTENT BLEND: This style is MOST markdown-heavy. Use "text" as the primary response — rich markdown with **bold** key facts, *italic* for emphasis, `code` for technical terms, [links](url) for references. Only add a component if it genuinely adds value (e.g., an alert for an important caveat). Most quick answers need NO components at all.

COMPONENT SELECTION:
• Simple answer → "text" only with rich markdown. No components needed.
• Short list (≤5 items) → list(bullet) OR just markdown bullets in "text".
• Important caveat or fun fact → alert(info).
• Definition → **bold term** in "text" with explanation. No component needed.
• Total components: 0-2. Less is more.
• NEVER use charts, stat grids, or complex layouts for simple questions.

EXAMPLE — Quick Answer:
{"text":"The speed of light is approximately **299,792,458 meters per second** (about *186,282 miles per second*) in a vacuum. It's the universal speed limit — nothing with mass can reach it.","a2ui":{"version":"1.0","components":[{"id":"a","type":"alert","props":{"variant":"info","title":"Fun Fact","description":"Light takes about **8 minutes and 20 seconds** to travel from the Sun to Earth."}}]},"suggestions":["How fast does sound travel?","What is the theory of relativity?"]}""",
}
