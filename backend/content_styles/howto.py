"""
How-To style — step-by-step procedural guides.

Optimized for "how to", tutorials, recipes, setup guides, and any
query where the user needs clear, actionable instructions.

Leads with prerequisites/warnings, followed by numbered steps,
with expandable details for advanced options.
"""

STYLE = {
    "id": "howto",
    "name": "How-To",
    "description": "Step-by-step instructions and procedural guides",
    "component_priority": [
        "alert",
        "list",
        "text",
        "accordion",
        "card",
        "data-table",
        "tabs",
        "grid",
        "chart",
        "stat",
    ],
    "prompt": """\
HOW-TO STYLE: Clear, actionable step-by-step instructions. Prerequisites first, then steps, then tips.

COMPONENT ORDER: alert (prerequisites/warnings) → list(numbered) for steps → accordion for optional details → alert(info) for tips.

TEMPORAL: Reference current tool versions, best practices, and syntax as of the date above. Use the latest approaches.

CONTENT BLEND: Use "text" for a brief markdown intro explaining what we're doing and why — include `code` snippets inline. Use ```mermaid in text for process flows when helpful (e.g., deployment pipelines, architecture). Components handle the structured steps and reference data.

COMPONENT SELECTION:
• Main steps → list(numbered). Each step = one clear, actionable sentence.
• Prerequisites or "before you begin" → alert(warning) at top.
• Required tools/materials → list(checklist).
• Alternative approaches or deep-dives → accordion.
• Tips or best practices → alert(info) at bottom.
• Multiple methods/variations → tabs (one per method).
• Reference data (command flags, substitutions) → data-table.
• NEVER use charts or stat cards for procedural content.

EXAMPLE — How-To Guide:
{"text":"Setting up a **Python virtual environment** isolates your project dependencies from the system Python, preventing version conflicts.","a2ui":{"version":"1.0","components":[{"id":"prereq","type":"alert","props":{"variant":"warning","title":"Prerequisites","description":"Python 3.8+ must be installed. Verify with: `python3 --version`"}},{"id":"steps","type":"list","props":{"variant":"numbered","items":[{"id":"s1","text":"Open a terminal and navigate to your project directory"},{"id":"s2","text":"Run: `python3 -m venv .venv`"},{"id":"s3","text":"Activate: `source .venv/bin/activate` (macOS/Linux) or `.venv\\\\Scripts\\\\activate` (Windows)"},{"id":"s4","text":"Install dependencies: `pip install -r requirements.txt`"},{"id":"s5","text":"Verify — your prompt should show `(.venv)`"}]}},{"id":"details","type":"accordion","props":{"items":[{"id":"d1","title":"What about conda?","content":"Run: `conda create -n myenv python=3.12 && conda activate myenv`"},{"id":"d2","title":"How do I deactivate?","content":"Simply run: `deactivate`"}]}},{"id":"tip","type":"alert","props":{"variant":"info","title":"Tip","description":"Add `.venv/` to your `.gitignore` to keep your repo clean."}}]},"suggestions":["Managing dependencies with pip","Docker setup for Python projects"]}""",
}
