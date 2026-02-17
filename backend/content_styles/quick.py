"""
Quick style — concise direct answers.

Optimized for simple questions, definitions, yes/no answers, and any
query where the user wants a fast, focused response without heavy UI.

Minimal components — text-centric with optional supporting elements.
This is the lightest style, producing the smallest system prompt for
maximum WAF headroom and fastest response times.
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
QUICK STYLE: Concise, direct answers. Minimal components, maximum clarity.

COMPONENT SELECTION:
• Simple factual answer → text(body) only. Keep it brief.
• Short list of items (≤5) → list(bullet).
• Yes/no with nuance → text(body) + alert(info) for context.
• Definition → text(h3) for the term + text(body) for the definition.
• Keep total components to 1-3. Less is more.
• NEVER use charts, stat grids, or complex layouts for simple questions.
• "suggestions" should offer natural follow-ups. Examples: "Tell me more about X", "How does X compare to Y?".

EXAMPLE — Quick Answer:
{"text":"The speed of light is approximately 299,792,458 meters per second (about 186,282 miles per second) in a vacuum.","a2ui":{"version":"1.0","components":[{"id":"a","type":"alert","props":{"variant":"info","title":"Fun Fact","description":"Light takes about 8 minutes and 20 seconds to travel from the Sun to Earth."}}]},"suggestions":["How fast does sound travel?","What is the theory of relativity?","Fastest things in the universe"]}""",
}
