"""
Micro-contexts — small, composable prompt fragments for specific components.

The analyzer (Step 1) determines which components a response likely needs.
This module maps those hints to targeted instructions that get injected into
the system prompt for ONLY that request.  This keeps the base prompt lean
while giving the main LLM precise data-shape contracts when it needs them.

Public API
----------
- ``get_context(key)``       → single fragment string (or empty)
- ``assemble(keys)``         → combined fragment string for multiple keys
- ``AVAILABLE_KEYS``         → frozenset of all registered keys
"""

from typing import Dict, FrozenSet, List, Optional

# ── Registry ──────────────────────────────────────────────────

_CONTEXTS: Dict[str, str] = {}


def _register(key: str, context: str) -> None:
    _CONTEXTS[key] = context.strip()


# ── Chart: Matrix / Heatmap ───────────────────────────────────

_register("chart_matrix", """
MATRIX/HEATMAP — chartType:"matrix"
STRICT FORMAT:
  labels: string[] — ONLY x-axis column names. Nothing else.
  datasets:[{label:"Title", data:[{x:"col", y:"row", v:number}, ...]}]
RULES:
- ONE dataset. NOT one per row.
- x values MUST match labels[] exactly. y = row categories. Do NOT put y-values in labels[].
- v = color intensity value (auto-scaled cool→warm). Every x×y cell must exist.
- height:300+ for 5+ rows. Include xAxisLabel/yAxisLabel.
EXAMPLE (2×4=8 points):
  labels:["Jan","Feb","Mar","Apr"],
  datasets:[{label:"Temps",data:[
    {x:"Jan",y:"Miami",v:72},{x:"Feb",y:"Miami",v:74},{x:"Mar",y:"Miami",v:78},{x:"Apr",y:"Miami",v:82},
    {x:"Jan",y:"NYC",v:33},{x:"Feb",y:"NYC",v:36},{x:"Mar",y:"NYC",v:45},{x:"Apr",y:"NYC",v:57}
  ]}], options:{height:300,xAxisLabel:"Month",yAxisLabel:"City"}
""")

# ── Chart: Treemap ────────────────────────────────────────────

_register("chart_treemap", """
TREEMAP CHART — chartType:"treemap"
Data shape: ONE dataset with tree array. NO labels[] — tree IS the data.
  datasets:[{tree:[{value:number, group:"category", label:"item name"}, ...],
    key:"value", groups:["group"], labels:{display:true}}]
value = numeric size of each tile. group = category for grouping. label = display text.
CRITICAL: Do NOT use standard {labels,data[]} format. The tree array replaces it.
""")

# ── Chart: Sankey ─────────────────────────────────────────────

_register("chart_sankey", """
SANKEY FLOW CHART — chartType:"sankey"
Data shape: ONE dataset with flow objects. NO labels[] needed.
  datasets:[{data:[{from:"Source Node", to:"Target Node", flow:number}, ...]}]
from/to = node names (strings). flow = numeric magnitude of the connection.
Nodes are auto-created from unique from/to values. Use descriptive node names.
""")

# ── Chart: Funnel ─────────────────────────────────────────────

_register("chart_funnel", """
FUNNEL CHART — chartType:"funnel"
Data shape: Standard format with values in DESCENDING order (widest at top).
  labels:["Stage 1","Stage 2","Stage 3"], datasets:[{data:[1000,600,200]}]
Values must decrease top to bottom to form the funnel shape.
""")

# ── Chart: Radar ──────────────────────────────────────────────

_register("chart_radar", """
RADAR CHART — chartType:"radar"
labels = axis names (categories being scored). Each dataset = one entity being compared.
  labels:["Speed","Power","Defense","Range","Accuracy"],
  datasets:[{label:"Player A",data:[8,6,9,4,7]},{label:"Player B",data:[5,9,6,8,6]}]
Use 5-8 axes for best readability. Keep scales consistent (e.g. all 1-10).
""")

# ── Chart: Scatter / Bubble ───────────────────────────────────

_register("chart_scatter", """
SCATTER/BUBBLE CHART — chartType:"scatter" or "bubble"
Data shape: datasets with {x,y} or {x,y,r} point objects. NO labels[] needed.
  Scatter: datasets:[{label:"Group",data:[{x:1.5,y:3.2},{x:2.1,y:4.8},...]}]
  Bubble: datasets:[{label:"Group",data:[{x:1.5,y:3.2,r:10},{x:2.1,y:4.8,r:5},...]}]
r = bubble radius (bubble only). ALWAYS include xAxisLabel and yAxisLabel.
""")


# ── Chart: Choropleth (Geographic Map) ────────────────────────

_register("chart_choropleth", """
CHOROPLETH MAP — chartType:"choropleth"
Geographic map where region colors encode values. Map data is loaded automatically from CDN.
STRICT FORMAT:
  map: "world" | "us-states" — which map to render.
  datasets:[{label:"Title", data:[{feature:"Region Name", value:number}, ...]}]
RULES:
- ONE dataset. feature names MUST match the map's region names exactly.
  World map: use country names (e.g. "United States", "China", "Brazil").
  US states: use full state names (e.g. "California", "Texas", "New York").
- value = color intensity (auto-scaled). Only include regions you have data for — others default to 0.
- height:350+ recommended. Do NOT include labels[]; they are derived from the map.
EXAMPLE (US states):
  map:"us-states",
  datasets:[{label:"Population",data:[
    {feature:"California",value:39538223},{feature:"Texas",value:29145505},
    {feature:"Florida",value:21538187},{feature:"New York",value:20201249}
  ]}], options:{height:400}
""")

# ── Chart: BubbleMap (Geographic Bubble Map) ──────────────────

_register("chart_bubblemap", """
BUBBLE MAP — chartType:"bubbleMap"
Geographic map with circles at lat/long coordinates, sized by value.
STRICT FORMAT:
  map: "world" | "us-states" — which map outline to render.
  datasets:[{label:"Title", data:[{latitude:number, longitude:number, value:number, description:"Label"}, ...]}]
RULES:
- ONE dataset. Each point needs latitude, longitude, value, and description.
- value = circle size (auto-scaled). description = tooltip/label text.
- height:350+ recommended. Do NOT include labels[]; they are derived from descriptions.
EXAMPLE (US cities):
  map:"us-states",
  datasets:[{label:"Major Cities",data:[
    {latitude:40.7128,longitude:-74.006,value:8336817,description:"New York"},
    {latitude:34.0522,longitude:-118.2437,value:3979576,description:"Los Angeles"},
    {latitude:41.8781,longitude:-87.6298,value:2693976,description:"Chicago"}
  ]}], options:{height:400}
""")

# ── Public API ────────────────────────────────────────────────

AVAILABLE_KEYS: FrozenSet[str] = frozenset(_CONTEXTS.keys())


def get_context(key: str) -> str:
    """Return a single micro-context fragment, or empty string if not found."""
    return _CONTEXTS.get(key, "")


def assemble(keys: List[str], max_bytes: Optional[int] = None) -> str:
    """Combine multiple micro-context fragments into a single block.

    Fragments are joined with blank lines.  If ``max_bytes`` is set,
    fragments are added greedily until the budget is exhausted.
    """
    if not keys:
        return ""

    parts: List[str] = []
    total = 0

    for key in keys:
        fragment = _CONTEXTS.get(key)
        if not fragment:
            continue
        frag_bytes = len(fragment.encode("utf-8"))
        if max_bytes is not None and total + frag_bytes > max_bytes:
            break
        parts.append(fragment)
        total += frag_bytes

    if not parts:
        return ""

    return "\n\n".join(parts)
