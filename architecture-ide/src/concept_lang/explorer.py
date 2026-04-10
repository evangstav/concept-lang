"""
Generate a self-contained interactive HTML concept explorer (v2 — new AST).

Produces a single HTML file with embedded CSS and JavaScript that renders:
- A clickable concept graph: nodes are concepts, edges are syncs
- State machine diagram for selected concept (via v1 diagrams, temporarily)
- Entity/state detail panel
- Action browser (multi-case)
- Per-sync flow diagram (when → where → then)

Uses D3.js for force-directed graph layout and Mermaid for diagram rendering.
All workspace data is embedded as JSON so the page works offline.
"""

from __future__ import annotations

import json

from concept_lang.ast import (
    ActionPattern,
    ConceptAST,
    PatternField,
    SyncAST,
    Workspace,
)


# --- concept JSON payload for the HTML ---------------------------------------


def _concept_to_dict(c: ConceptAST) -> dict:
    return {
        "name": c.name,
        "params": c.params,
        "purpose": c.purpose,
        "state": [{"name": s.name, "type_expr": s.type_expr} for s in c.state],
        "actions": [
            {
                "name": a.name,
                "cases": [
                    {
                        "inputs": [
                            {"name": tn.name, "type_expr": tn.type_expr}
                            for tn in case.inputs
                        ],
                        "outputs": [
                            {"name": tn.name, "type_expr": tn.type_expr}
                            for tn in case.outputs
                        ],
                        "body": case.body,
                        "effects": [e.raw for e in case.effects],
                    }
                    for case in a.cases
                ],
            }
            for a in c.actions
        ],
        "operational_principle": [
            {
                "keyword": step.keyword,
                "action_name": step.action_name,
                "inputs": step.inputs,
                "outputs": step.outputs,
            }
            for step in c.operational_principle.steps
        ],
    }


def _sync_to_dict(s: SyncAST) -> dict:
    return {
        "name": s.name,
        "when": [_pattern_to_dict(p) for p in s.when],
        "where": _where_to_dict(s),
        "then": [_pattern_to_dict(p) for p in s.then],
    }


def _pattern_to_dict(p: ActionPattern) -> dict:
    return {
        "concept": p.concept,
        "action": p.action,
        "input_pattern": [_field_to_dict(f) for f in p.input_pattern],
        "output_pattern": [_field_to_dict(f) for f in p.output_pattern],
    }


def _field_to_dict(f: PatternField) -> dict:
    return {"name": f.name, "kind": f.kind, "value": f.value}


def _where_to_dict(s: SyncAST) -> dict | None:
    if s.where is None:
        return None
    return {
        "queries": [
            {
                "concept": q.concept,
                "is_optional": q.is_optional,
                "triples": [
                    {"subject": t.subject, "predicate": t.predicate, "object": t.object}
                    for t in q.triples
                ],
            }
            for q in s.where.queries
        ],
        "binds": [
            {"expression": b.expression, "variable": b.variable}
            for b in s.where.binds
        ],
    }


# --- graph data: syncs as edges ---------------------------------------------


def _build_graph_data(workspace: Workspace) -> dict:
    """
    Build nodes and edges for the dependency graph.

    Nodes: one per concept. External references (a sync mentioning a
    concept that is not in the workspace) become ``{external: True}``
    nodes so dangling references stay visible.

    Edges: one per ``(sync, when_concept, then_concept)`` triple. Each
    edge carries the sync name so the UI can link the edge back to its
    source file. Self-loops are allowed.
    """
    concept_names = set(workspace.concepts)
    nodes: list[dict] = []
    seen: set[str] = set()

    def add_node(name: str, *, external: bool = False) -> None:
        if name in seen:
            return
        seen.add(name)
        if external:
            nodes.append({"id": name, "external": True})
            return
        c = workspace.concepts[name]
        nodes.append({
            "id": name,
            "purpose": c.purpose,
            "stateCount": len(c.state),
            "actionCount": len(c.actions),
        })

    for name in sorted(concept_names):
        add_node(name)

    edges: list[dict] = []

    for sync_name in sorted(workspace.syncs):
        sync = workspace.syncs[sync_name]
        if not sync.when:
            continue
        when_concepts = sorted({p.concept for p in sync.when})
        then_concepts = sorted({p.concept for p in sync.then})

        for src in when_concepts:
            if src not in concept_names:
                add_node(src, external=True)
            for dst in then_concepts:
                if dst not in concept_names:
                    add_node(dst, external=True)
                edges.append({
                    "source": src,
                    "target": dst,
                    "type": "sync",
                    "syncName": sync_name,
                    "internal": src in concept_names and dst in concept_names,
                })

    return {"nodes": nodes, "edges": edges}


def _build_sync_index(workspace: Workspace) -> dict:
    """
    Build an index keyed by ``concept.action`` string, mapping to the
    syncs that mention that action in either ``when`` or ``then``.
    """
    index: dict[str, list[dict]] = {}
    for sync_name, sync in workspace.syncs.items():
        for role, patterns in (("when", sync.when), ("then", sync.then)):
            for pat in patterns:
                key = f"{pat.concept}.{pat.action}"
                index.setdefault(key, []).append({
                    "sync": sync_name,
                    "role": role,
                })
    return index


# --- graph mermaid for the top-level view ------------------------------------


def _workspace_graph_mermaid(workspace: Workspace) -> str:
    """Mermaid ``graph TD`` for the workspace: concepts + syncs-as-edges."""
    lines = ["graph TD"]

    concept_names = set(workspace.concepts)
    external_refs: set[str] = set()

    for name in sorted(concept_names):
        lines.append(f'    {name}["{name}"]')

    for sync_name in sorted(workspace.syncs):
        sync = workspace.syncs[sync_name]
        when_concepts = sorted({p.concept for p in sync.when})
        then_concepts = sorted({p.concept for p in sync.then})
        for src in when_concepts:
            if src not in concept_names:
                external_refs.add(src)
            for dst in then_concepts:
                if dst not in concept_names:
                    external_refs.add(dst)
                lines.append(f"    {src} -->|sync {sync_name}| {dst}")

    for ext in sorted(external_refs):
        lines.append(f'    {ext}["{ext} ?"]:::external')

    if external_refs:
        lines.append(
            "    classDef external fill:#21262d,stroke:#484f58,stroke-dasharray:5"
        )

    return "\n".join(lines)


# --- top-level entry point ---------------------------------------------------


def generate_explorer(workspace: Workspace) -> str:
    """
    Generate a self-contained interactive HTML explorer for the given
    workspace (concepts + syncs).
    """
    concept_data = {
        name: _concept_to_dict(c) for name, c in workspace.concepts.items()
    }
    sync_data = {
        name: _sync_to_dict(s) for name, s in workspace.syncs.items()
    }
    graph_data = _build_graph_data(workspace)
    sync_index = _build_sync_index(workspace)

    # Per-concept Mermaid diagrams (v2 — consume ConceptAST directly).
    from concept_lang.diagrams import entity_diagram, state_machine
    mermaid_diagrams: dict[str, dict[str, str]] = {}
    for name, c in workspace.concepts.items():
        mermaid_diagrams[name] = {
            "state_machine": state_machine(c),
            "entity_diagram": entity_diagram(c),
        }

    dep_graph_mermaid = (
        _workspace_graph_mermaid(workspace)
        if workspace.concepts or workspace.syncs
        else "graph TD\n    empty[No concepts]"
    )

    return _HTML_TEMPLATE.replace(
        "/*__CONCEPT_DATA__*/{}", json.dumps(concept_data, indent=2)
    ).replace(
        '/*__SYNC_DATA__*/{}', json.dumps(sync_data, indent=2)
    ).replace(
        '/*__GRAPH_DATA__*/{"nodes":[],"edges":[]}', json.dumps(graph_data, indent=2)
    ).replace(
        "/*__SYNC_INDEX__*/{}", json.dumps(sync_index, indent=2)
    ).replace(
        "/*__MERMAID_DIAGRAMS__*/{}", json.dumps(mermaid_diagrams, indent=2)
    ).replace(
        '/*__DEP_GRAPH_MERMAID__*/"graph TD"', json.dumps(dep_graph_mermaid)
    )


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Concept Explorer</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
:root {
  --bg: #0d1117;
  --surface: #161b22;
  --border: #30363d;
  --text: #c9d1d9;
  --text-dim: #8b949e;
  --accent: #58a6ff;
  --accent-dim: #1f6feb;
  --green: #3fb950;
  --orange: #d29922;
  --red: #f85149;
  --purple: #bc8cff;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  height: 100vh;
  overflow: hidden;
}
#app {
  display: grid;
  grid-template-columns: 280px 1fr 360px;
  grid-template-rows: 48px 1fr;
  height: 100vh;
}
header {
  grid-column: 1 / -1;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 16px;
}
header h1 { font-size: 16px; font-weight: 600; color: var(--accent); }
header .stats { font-size: 12px; color: var(--text-dim); }
#sidebar {
  background: var(--surface);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  padding: 12px;
}
#sidebar h2 {
  font-size: 12px;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 8px;
  letter-spacing: 0.5px;
}
.concept-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 2px;
  transition: background 0.15s;
}
.concept-item:hover { background: rgba(88, 166, 255, 0.1); }
.concept-item.active { background: rgba(88, 166, 255, 0.15); border-left: 2px solid var(--accent); }
.concept-item .name { font-size: 14px; font-weight: 500; }
.concept-item .purpose { font-size: 11px; color: var(--text-dim); margin-top: 2px; }
.concept-item .badges { display: flex; gap: 6px; margin-top: 4px; }
.badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 10px;
  background: var(--bg);
  color: var(--text-dim);
}
#main {
  overflow: hidden;
  position: relative;
}
#graph-container {
  width: 100%;
  height: 100%;
}
#graph-container svg { width: 100%; height: 100%; }
.view-toggle {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  gap: 4px;
  z-index: 10;
}
.view-toggle button {
  padding: 6px 12px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-dim);
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s;
}
.view-toggle button:hover { color: var(--text); border-color: var(--accent); }
.view-toggle button.active { background: var(--accent-dim); color: #fff; border-color: var(--accent); }
#mermaid-view {
  width: 100%;
  height: 100%;
  overflow: auto;
  display: none;
  padding: 24px;
}
#mermaid-view .mermaid-render {
  background: var(--surface);
  border-radius: 8px;
  padding: 24px;
  min-height: 200px;
}
#detail {
  background: var(--surface);
  border-left: 1px solid var(--border);
  overflow-y: auto;
  padding: 16px;
}
#detail h2 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--accent);
}
#detail .empty-state {
  color: var(--text-dim);
  font-size: 13px;
  text-align: center;
  margin-top: 40px;
}
.detail-section {
  margin-bottom: 16px;
}
.detail-section h3 {
  font-size: 11px;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 6px;
  letter-spacing: 0.5px;
}
.detail-section .purpose-text {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text);
}
.state-item, .action-item, .sync-item {
  padding: 6px 8px;
  margin-bottom: 4px;
  border-radius: 4px;
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  background: var(--bg);
  cursor: pointer;
  transition: background 0.15s;
}
.state-item:hover, .action-item:hover, .sync-item:hover {
  background: rgba(88, 166, 255, 0.1);
}
.action-item.highlighted {
  background: rgba(63, 185, 80, 0.15);
  border-left: 2px solid var(--green);
}
.sync-item {
  border-left: 2px solid var(--purple);
}
.action-params { color: var(--text-dim); }
.action-clauses {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 2px;
  padding-left: 8px;
}
.sync-chain {
  background: var(--bg);
  border-radius: 6px;
  padding: 12px;
  margin-top: 8px;
}
.sync-chain h4 {
  font-size: 11px;
  color: var(--orange);
  margin-bottom: 8px;
}
.sync-chain-item {
  font-size: 12px;
  padding: 4px 0;
  display: flex;
  align-items: center;
  gap: 6px;
}
.sync-chain-item .arrow { color: var(--purple); }
.sync-chain-item .concept-link {
  color: var(--accent);
  cursor: pointer;
  text-decoration: underline;
}
.sync-chain-item .concept-link:hover { color: #fff; }
/* D3 graph styles */
.node circle {
  stroke-width: 2px;
  cursor: pointer;
  transition: r 0.15s;
}
.node text {
  font-size: 12px;
  fill: var(--text);
  pointer-events: none;
}
.node.external circle { stroke-dasharray: 4; }
.link {
  fill: none;
  stroke-width: 1.5px;
}
.link.param { stroke: var(--text-dim); }
.link.sync { stroke: var(--purple); stroke-dasharray: 6 3; }
.link-label {
  font-size: 10px;
  fill: var(--text-dim);
}
marker { fill: var(--text-dim); }
marker.sync-marker { fill: var(--purple); }
</style>
</head>
<body>
<div id="app">
  <header>
    <h1>Concept Explorer</h1>
    <span class="stats" id="stats"></span>
  </header>
  <div id="sidebar">
    <h2>Concepts</h2>
    <div id="concept-list"></div>
  </div>
  <div id="main">
    <div class="view-toggle">
      <button id="btn-graph" class="active" onclick="setView('graph')">Graph</button>
      <button id="btn-state" onclick="setView('state')">State Machine</button>
      <button id="btn-entity" onclick="setView('entity')">Entity Diagram</button>
      <button id="btn-deps" onclick="setView('deps')">Dependencies</button>
    </div>
    <div id="graph-container"></div>
    <div id="mermaid-view"><div class="mermaid-render" id="mermaid-render"></div></div>
  </div>
  <div id="detail">
    <div class="empty-state">Select a concept to explore</div>
  </div>
</div>

<script>
// Embedded concept data
const CONCEPTS = /*__CONCEPT_DATA__*/{};
const SYNC_DATA = /*__SYNC_DATA__*/{};
const GRAPH = /*__GRAPH_DATA__*/{"nodes":[],"edges":[]};
const SYNC_INDEX = /*__SYNC_INDEX__*/{};
const MERMAID = /*__MERMAID_DIAGRAMS__*/{};
const DEP_GRAPH = /*__DEP_GRAPH_MERMAID__*/"graph TD";

let selectedConcept = null;
let highlightedAction = null;
let currentView = 'graph';
let simulation = null;

// Init mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    darkMode: true,
    background: '#161b22',
    primaryColor: '#1f6feb',
    primaryTextColor: '#c9d1d9',
    lineColor: '#30363d',
  }
});

// --- Sidebar ---
function renderSidebar() {
  const list = document.getElementById('concept-list');
  const names = Object.keys(CONCEPTS).sort();
  document.getElementById('stats').textContent =
    `${names.length} concepts | ${GRAPH.edges.length} dependencies`;

  list.innerHTML = names.map(name => {
    const c = CONCEPTS[name];
    return `
      <div class="concept-item ${selectedConcept === name ? 'active' : ''}"
           onclick="selectConcept('${name}')">
        <div class="name">${name}</div>
        <div class="purpose">${truncate(c.purpose, 60)}</div>
        <div class="badges">
          <span class="badge">${c.actions.length} actions</span>
          <span class="badge">${c.state.length} state</span>
          ${c.sync.length ? `<span class="badge">${c.sync.length} sync</span>` : ''}
        </div>
      </div>`;
  }).join('');
}

function truncate(s, n) { return s.length > n ? s.slice(0, n) + '...' : s; }

// --- Detail panel ---
function renderDetail(name) {
  const panel = document.getElementById('detail');
  if (!name || !CONCEPTS[name]) {
    panel.innerHTML = '<div class="empty-state">Select a concept to explore</div>';
    return;
  }
  const c = CONCEPTS[name];
  let html = `<h2>${name}</h2>`;

  // Purpose
  html += `<div class="detail-section">
    <h3>Purpose</h3>
    <div class="purpose-text">${c.purpose}</div>
  </div>`;

  // Params
  if (c.params.length) {
    html += `<div class="detail-section">
      <h3>Parameters</h3>
      ${c.params.map(p => `<div class="state-item">${p}</div>`).join('')}
    </div>`;
  }

  // State
  html += `<div class="detail-section">
    <h3>State</h3>
    ${c.state.map(s => `<div class="state-item">${s.name}: ${s.type_expr}</div>`).join('')}
  </div>`;

  // Actions
  html += `<div class="detail-section">
    <h3>Actions</h3>
    ${c.actions.map(a => {
      const key = `${name}.${a.name}`;
      const syncs = SYNC_INDEX[key] || [];
      const hasSyncs = syncs.length > 0;
      const isHighlighted = highlightedAction === key;
      return `
        <div class="action-item ${isHighlighted ? 'highlighted' : ''}"
             onclick="highlightAction('${key}')">
          <div>
            <strong>${a.name}</strong><span class="action-params">(${a.params.join(', ')})</span>
            ${hasSyncs ? ` <span class="badge" style="background:rgba(188,140,255,0.2);color:var(--purple);">${syncs.length} sync</span>` : ''}
          </div>
          ${a.pre ? `<div class="action-clauses">pre: ${a.pre.clauses.join(', ')}</div>` : ''}
          ${a.post ? `<div class="action-clauses">post: ${a.post.clauses.join(', ')}</div>` : ''}
        </div>`;
    }).join('')}
  </div>`;

  // Sync (this concept reacts to)
  if (c.sync.length) {
    html += `<div class="detail-section">
      <h3>Sync (reacts to)</h3>
      ${c.sync.map(s => `
        <div class="sync-item" onclick="selectConcept('${s.trigger_concept}')">
          when <span class="concept-link">${s.trigger_concept}</span>.${s.trigger_action}(${s.trigger_params.join(', ')})${s.trigger_result ? ' → ' + s.trigger_result : ''}
          ${s.where_clauses && s.where_clauses.length ? '<br>&nbsp;&nbsp;where ' + s.where_clauses.join(', ') : ''}
          <br>&nbsp;&nbsp;then ${s.invocations.map(i => i.action + '(' + i.params.join(', ') + ')').join(', ')}
        </div>`).join('')}
    </div>`;
  }

  // Sync chain (when an action is highlighted)
  if (highlightedAction) {
    const syncs = SYNC_INDEX[highlightedAction] || [];
    if (syncs.length > 0) {
      html += `<div class="sync-chain">
        <h4>Sync chain: ${highlightedAction}</h4>
        ${syncs.map(s => `
          <div class="sync-chain-item">
            <span class="arrow">→</span>
            <span class="concept-link" onclick="selectConcept('${s.reactor}')">${s.reactor}</span>.${s.local_action}(${s.local_params.join(', ')})
          </div>`).join('')}
      </div>`;

      // Trace deeper: do the local_actions themselves trigger further syncs?
      const deeper = [];
      for (const s of syncs) {
        const nextKey = `${s.reactor}.${s.local_action}`;
        const nextSyncs = SYNC_INDEX[nextKey] || [];
        for (const ns of nextSyncs) {
          deeper.push({ from: s.reactor, action: s.local_action, ...ns });
        }
      }
      if (deeper.length) {
        html += `<div class="sync-chain">
          <h4>Cascading syncs</h4>
          ${deeper.map(d => `
            <div class="sync-chain-item">
              <span class="arrow">→→</span>
              ${d.from}.${d.action} triggers
              <span class="concept-link" onclick="selectConcept('${d.reactor}')">${d.reactor}</span>.${d.local_action}
            </div>`).join('')}
        </div>`;
      }
    }
  }

  panel.innerHTML = html;
}

// --- Graph (D3 force-directed) ---
function renderGraph() {
  const container = document.getElementById('graph-container');
  container.innerHTML = '';
  const width = container.clientWidth;
  const height = container.clientHeight;

  const svg = d3.select(container).append('svg')
    .attr('width', width)
    .attr('height', height);

  // Arrow markers
  const defs = svg.append('defs');
  defs.append('marker')
    .attr('id', 'arrow')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 28)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', '#8b949e');

  defs.append('marker')
    .attr('id', 'arrow-sync')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 28)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto')
    .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', '#bc8cff');

  // Force simulation
  const nodes = GRAPH.nodes.map(d => ({...d}));
  const edges = GRAPH.edges.map(d => ({...d}));

  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(120))
    .force('charge', d3.forceManyBody().strength(-400))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(40));

  const link = svg.append('g').selectAll('line')
    .data(edges).enter().append('line')
    .attr('class', d => `link ${d.type}`)
    .attr('marker-end', d => d.type === 'sync' ? 'url(#arrow-sync)' : 'url(#arrow)');

  const linkLabel = svg.append('g').selectAll('text')
    .data(edges.filter(d => d.type === 'sync')).enter().append('text')
    .attr('class', 'link-label')
    .text('sync');

  const node = svg.append('g').selectAll('g')
    .data(nodes).enter().append('g')
    .attr('class', d => `node ${d.external ? 'external' : ''}`)
    .call(d3.drag()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended));

  node.append('circle')
    .attr('r', d => d.external ? 14 : 22)
    .attr('fill', d => {
      if (d.external) return '#21262d';
      if (selectedConcept === d.id) return '#1f6feb';
      return '#161b22';
    })
    .attr('stroke', d => {
      if (d.external) return '#484f58';
      if (selectedConcept === d.id) return '#58a6ff';
      return '#58a6ff';
    });

  node.append('text')
    .attr('dy', d => d.external ? -20 : -28)
    .attr('text-anchor', 'middle')
    .text(d => d.id);

  // Action count inside circle for internal concepts
  node.filter(d => !d.external).append('text')
    .attr('dy', 4)
    .attr('text-anchor', 'middle')
    .attr('font-size', '10px')
    .attr('fill', '#8b949e')
    .text(d => d.actionCount ? `${d.actionCount}a` : '');

  node.on('click', (event, d) => {
    if (!d.external) selectConcept(d.id);
  });

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);

    linkLabel
      .attr('x', d => (d.source.x + d.target.x) / 2)
      .attr('y', d => (d.source.y + d.target.y) / 2);

    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });

  function dragstarted(event) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    event.subject.fx = event.subject.x;
    event.subject.fy = event.subject.y;
  }
  function dragged(event) {
    event.subject.fx = event.x;
    event.subject.fy = event.y;
  }
  function dragended(event) {
    if (!event.active) simulation.alphaTarget(0);
    event.subject.fx = null;
    event.subject.fy = null;
  }
}

// --- Mermaid rendering ---
async function renderMermaid(code, elementId) {
  const el = document.getElementById(elementId);
  try {
    const { svg } = await mermaid.render('mermaid-svg-' + Date.now(), code);
    el.innerHTML = svg;
  } catch (e) {
    el.innerHTML = `<pre style="color:var(--red)">${e.message}\n\n${code}</pre>`;
  }
}

// --- View switching ---
function setView(view) {
  currentView = view;
  document.querySelectorAll('.view-toggle button').forEach(b => b.classList.remove('active'));

  const graphEl = document.getElementById('graph-container');
  const mermaidEl = document.getElementById('mermaid-view');

  if (view === 'graph') {
    document.getElementById('btn-graph').classList.add('active');
    graphEl.style.display = '';
    mermaidEl.style.display = 'none';
  } else if (view === 'state' && selectedConcept && MERMAID[selectedConcept]) {
    document.getElementById('btn-state').classList.add('active');
    graphEl.style.display = 'none';
    mermaidEl.style.display = '';
    renderMermaid(MERMAID[selectedConcept].state_machine, 'mermaid-render');
  } else if (view === 'entity' && selectedConcept && MERMAID[selectedConcept]) {
    document.getElementById('btn-entity').classList.add('active');
    graphEl.style.display = 'none';
    mermaidEl.style.display = '';
    renderMermaid(MERMAID[selectedConcept].entity_diagram, 'mermaid-render');
  } else if (view === 'deps') {
    document.getElementById('btn-deps').classList.add('active');
    graphEl.style.display = 'none';
    mermaidEl.style.display = '';
    renderMermaid(DEP_GRAPH, 'mermaid-render');
  } else {
    // Fallback to graph if no concept selected for diagram views
    document.getElementById('btn-graph').classList.add('active');
    graphEl.style.display = '';
    mermaidEl.style.display = 'none';
  }
}

// --- Selection ---
function selectConcept(name) {
  selectedConcept = name;
  highlightedAction = null;
  renderSidebar();
  renderDetail(name);
  updateGraphHighlight();
  // If currently in a diagram view, refresh it
  if (currentView === 'state' || currentView === 'entity') {
    setView(currentView);
  }
}

function highlightAction(key) {
  highlightedAction = highlightedAction === key ? null : key;
  renderDetail(selectedConcept);
  updateGraphHighlight();
}

function updateGraphHighlight() {
  d3.selectAll('.node circle')
    .attr('fill', d => {
      if (d.external) return '#21262d';
      if (selectedConcept === d.id) return '#1f6feb';
      return '#161b22';
    })
    .attr('stroke', d => {
      if (d.external) return '#484f58';
      if (selectedConcept === d.id) return '#58a6ff';
      // Highlight sync-connected concepts
      if (highlightedAction) {
        const syncs = SYNC_INDEX[highlightedAction] || [];
        if (syncs.some(s => s.reactor === d.id)) return '#3fb950';
      }
      return '#58a6ff';
    })
    .attr('stroke-width', d => {
      if (highlightedAction) {
        const syncs = SYNC_INDEX[highlightedAction] || [];
        if (syncs.some(s => s.reactor === d.id)) return 3;
      }
      return 2;
    });
}

// --- Init ---
renderSidebar();
renderGraph();
</script>
</body>
</html>
"""
