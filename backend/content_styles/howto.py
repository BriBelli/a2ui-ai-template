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
HOW-TO STYLE: Clear, actionable step-by-step instructions. Lead with prerequisites, then numbered steps, then tips.

COMPONENT ORDER: alert (prerequisites or warnings) → list(numbered) for steps → accordion for optional details → alert(info) for tips.

COMPONENT SELECTION:
• Main steps → list(numbered) with clear, concise action items. Each step should be one actionable sentence.
• Prerequisites, warnings, or "before you begin" → alert(warning) at the top.
• Required tools or materials → list(checklist).
• Optional deep-dives or alternative approaches → accordion with expandable sections.
• Tips, best practices, or "pro tips" → alert(info) at the bottom.
• Multiple methods or variations → tabs (one tab per method).
• Reference data (command flags, ingredient substitutions) → data-table.
• NEVER use charts or stat cards for procedural content.
• "suggestions" should lead to related guides. Examples: "Advanced Git branching strategies", "Troubleshoot common Docker errors".

EXAMPLE — How-To Guide:
{"text":"How to set up a Python virtual environment.","a2ui":{"version":"1.0","components":[{"id":"prereq","type":"alert","props":{"variant":"warning","title":"Prerequisites","description":"Python 3.8+ must be installed. Verify with: python3 --version"}},{"id":"steps","type":"list","props":{"variant":"numbered","items":[{"id":"s1","text":"Open a terminal and navigate to your project directory"},{"id":"s2","text":"Run: python3 -m venv .venv"},{"id":"s3","text":"Activate the environment: source .venv/bin/activate (macOS/Linux) or .venv\\\\Scripts\\\\activate (Windows)"},{"id":"s4","text":"Install dependencies: pip install -r requirements.txt"},{"id":"s5","text":"Verify activation — your prompt should show (.venv)"}]}},{"id":"details","type":"accordion","props":{"items":[{"id":"d1","title":"What about conda?","content":"If you use Anaconda, run: conda create -n myenv python=3.11 && conda activate myenv"},{"id":"d2","title":"How do I deactivate?","content":"Simply run: deactivate"}]}},{"id":"tip","type":"alert","props":{"variant":"info","title":"Tip","description":"Add .venv/ to your .gitignore to avoid committing the virtual environment."}}]},"suggestions":["Managing Python dependencies with pip","Docker setup for Python projects","Python project structure best practices"]}""",
}
