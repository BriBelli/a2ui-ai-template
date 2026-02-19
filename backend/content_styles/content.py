"""
Content style — narrative/editorial presentation.

Optimized for knowledge queries, explanations, and topics where flowing
text with structured sections is more appropriate than dashboards.
Think: "what are elephants", "history of the internet", "explain quantum
computing".

Uses cards with headings for sections, lists for key facts, tables for
structured data, and accordion for FAQs.  Charts and stats are used
sparingly — only when they genuinely enhance understanding.
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
CONTENT STYLE: Narrative structure with headings, sections, and flowing text. Lead with key information, then organize into logical sections.

COMPONENT ORDER: alert (if important) → card sections with text headings → supporting data (tables, lists) → expandable details (accordion, tabs).

COMPONENT SELECTION:
• Use card with text(h2) headings to create clear sections (Overview, Key Facts, etc.).
• Key facts or characteristics → list(bullet) with substantive items.
• Structured comparisons (species, types, categories) → data-table with descriptive columns.
• Expandable Q&A or deep-dives → accordion.
• Multiple perspectives or sub-topics → tabs.
• Use stat cards ONLY for genuinely numeric highlights (population, size, dates). Do NOT force numeric framing on non-numeric topics.
• Use chart ONLY when quantitative comparison genuinely helps (e.g., size/weight comparison across categories). Never force a chart for non-numeric content.
• 7+ items → data-table or list. Never 7+ separate cards.
• "suggestions" should lead to deeper exploration. Examples: "Compare African vs Asian elephants", "Elephant intelligence and behavior", "Most endangered animals".

EXAMPLE — Content Topic ("What are elephants"):
{"text":"Elephants are the largest living land mammals, belonging to the family Elephantidae.","a2ui":{"version":"1.0","components":[{"id":"overview","type":"card","props":{"title":"Overview"},"children":[{"id":"ov-text","type":"text","props":{"content":"Elephants are keystone species that shape their ecosystems. They live in complex matriarchal families, communicate over long distances using low-frequency rumbles, and use their versatile trunks for breathing, grasping, and vocalizing.","variant":"body"}}]},{"id":"facts","type":"card","props":{"title":"Key Facts"},"children":[{"id":"facts-list","type":"list","props":{"variant":"bullet","items":[{"id":"f1","text":"Three living species: African savanna, African forest, and Asian elephant"},{"id":"f2","text":"Largest land animals — up to 13,000 lbs and 13 ft at the shoulder"},{"id":"f3","text":"Highly intelligent — tool use, problem-solving, strong memory"},{"id":"f4","text":"Herbivores eating 200–600 lbs of vegetation daily"},{"id":"f5","text":"Lifespan of 60–70 years in the wild"}]}}]},{"id":"species","type":"data-table","props":{"columns":[{"key":"s","label":"Species"},{"key":"r","label":"Range"},{"key":"t","label":"Key Traits"},{"key":"c","label":"IUCN Status"}],"data":[{"s":"African Savanna","r":"Sub-Saharan Africa","t":"Largest; large fan-shaped ears","c":"Endangered"},{"s":"African Forest","r":"Central & West African rainforests","t":"Smaller; straighter tusks","c":"Critically Endangered"},{"s":"Asian","r":"South & Southeast Asia","t":"Smaller ears; one trunk finger","c":"Endangered"}]}},{"id":"faq","type":"accordion","props":{"items":[{"id":"q1","title":"How do elephants communicate?","content":"Through vocalizations, touch, chemical cues, and infrasound that can travel over long distances."},{"id":"q2","title":"Why are elephants endangered?","content":"Habitat loss, human-elephant conflict, and poaching for ivory are the primary threats."}]}}]},"suggestions":["Compare African vs Asian elephants","Elephant intelligence and behavior","Most endangered animals"]}""",
}
