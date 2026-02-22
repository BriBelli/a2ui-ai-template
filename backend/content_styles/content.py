"""
Content style — narrative/editorial presentation.

Optimized for knowledge queries, explanations, and topics where flowing
text with structured sections is more appropriate than dashboards.
Think: "what are elephants", "history of the internet", "explain quantum
computing".

Uses rich markdown for narrative with structured components for
data, FAQs, and interactive elements.
"""

STYLE = {
    "id": "content",
    "name": "Content",
    "description": "Rich editorial content with sections, lists, and structured narrative",
    "component_priority": [
        "alert",
        "text",
        "card",
        "list",
        "data-table",
        "accordion",
        "tabs",
        "grid",
        "chart",
        "stat",
    ],
    "prompt": """\
CONTENT STYLE: Rich narrative blending markdown and components. Informative, well-structured, engaging.

COMPONENT ORDER: alert (if important) → rich text/card sections → supporting data (tables, lists) → expandable details (accordion, tabs).

TEMPORAL: Present all information as current to today's date (from date above). Use current terminology, status, and figures. Only reference past dates for historical context.

CONTENT BLEND: Leans MOST on markdown. Rich flowing "text" with **bold**, *italic*, headings, blockquotes, `code`, [links](url), ```mermaid for flows/diagrams. Components supplement — data-table for comparisons, list for facts, accordion for deep-dives, chart ONLY when data warrants it.

COMPONENT SELECTION:
• card with text(h2) headings for sections. Key facts → list(bullet). Structured data → data-table.
• Deep-dives → accordion. Multiple perspectives → tabs.
• stat ONLY for genuinely numeric highlights. chart ONLY when quantitative comparison helps.
• 7+ items → data-table or list. Never 7+ cards.

EXAMPLE — Content Topic:
{"text":"**Elephants** are the largest living land mammals, belonging to the family *Elephantidae*. They are keystone species that shape their ecosystems through their feeding habits and movement patterns.\n\nElephants live in **complex matriarchal families**, communicate over long distances using low-frequency rumbles, and demonstrate remarkable intelligence including tool use and problem-solving.","a2ui":{"version":"1.0","components":[{"id":"facts","type":"list","props":{"variant":"bullet","items":[{"id":"f1","text":"**Three living species**: African savanna, African forest, and Asian elephant"},{"id":"f2","text":"Largest land animals — up to **13,000 lbs** and **13 ft** at the shoulder"},{"id":"f3","text":"Herbivores eating **200–600 lbs** of vegetation daily"},{"id":"f4","text":"Lifespan of **60–70 years** in the wild"}]}},{"id":"species","type":"data-table","props":{"columns":[{"key":"s","label":"Species"},{"key":"r","label":"Range"},{"key":"t","label":"Key Traits"},{"key":"c","label":"IUCN Status"}],"data":[{"s":"African Savanna","r":"Sub-Saharan Africa","t":"Largest; large fan-shaped ears","c":"Endangered"},{"s":"African Forest","r":"Central & West African rainforests","t":"Smaller; straighter tusks","c":"Critically Endangered"},{"s":"Asian","r":"South & Southeast Asia","t":"Smaller ears; one trunk finger","c":"Endangered"}]}},{"id":"faq","type":"accordion","props":{"items":[{"id":"q1","title":"How do elephants communicate?","content":"Through vocalizations, touch, chemical cues, and **infrasound** that can travel over long distances."},{"id":"q2","title":"Why are elephants endangered?","content":"Habitat loss, human-elephant conflict, and poaching for ivory are the primary threats."}]}}]},"suggestions":["Compare African vs Asian elephants","Elephant intelligence and behavior"]}""",
}
