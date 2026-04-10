"""MCP tools for whole-workspace operations (v2 — new)."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from concept_lang.ast import Workspace
from concept_lang.validate import validate_workspace as _validate_workspace

from ._io import load_workspace_from_root


def _diag_list(diags) -> list[dict]:
    return [d.model_dump(mode="json") for d in diags]


def _workspace_graph_mermaid(workspace: Workspace) -> str:
    """
    Build a Mermaid `graph TD` where nodes are concepts and edges are
    syncs. Each sync contributes one `(when_concept, then_concept)` edge
    labeled with the sync's declared name.
    """
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


def register_workspace_tools(mcp: FastMCP, workspace_root: str) -> None:

    @mcp.tool(
        description=(
            "Validate every .concept and .sync file in the workspace. "
            "Runs C1..C9 (minus C8) plus S1..S5, plus per-file parse "
            "diagnostics. Returns the combined diagnostic list and a "
            "top-level `valid` boolean."
        )
    )
    def validate_workspace() -> str:
        ws, load_diags = load_workspace_from_root(workspace_root)
        rule_diags = _validate_workspace(ws)
        diagnostics = list(load_diags) + list(rule_diags)
        return json.dumps({
            "valid": not any(d.severity == "error" for d in diagnostics),
            "diagnostics": _diag_list(diagnostics),
            "concept_count": len(ws.concepts),
            "sync_count": len(ws.syncs),
        })

    @mcp.tool(
        description=(
            "Generate a Mermaid graph TD for the whole workspace. "
            "Nodes are concepts; edges are syncs labeled with their "
            "declared name. Pass to "
            "mcp__claude_ai_Mermaid_Chart__validate_and_render_mermaid_diagram "
            "to render. Replaces the old `get_dependency_graph`."
        )
    )
    def get_workspace_graph() -> str:
        ws, _diags = load_workspace_from_root(workspace_root)
        if not ws.concepts and not ws.syncs:
            return "// No concepts or syncs found"
        return _workspace_graph_mermaid(ws)

    @mcp.tool(
        description=(
            "Deprecated: use get_workspace_graph. Returns the same Mermaid "
            "string. Removed in P7."
        )
    )
    def get_dependency_graph() -> str:
        return get_workspace_graph()
