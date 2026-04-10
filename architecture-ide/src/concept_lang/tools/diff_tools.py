"""MCP tools for concept diff (v2 — consumes concept_lang.ast)."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from concept_lang.diff import diff_concepts_with_impact
from concept_lang.parse import parse_concept_source

from ._io import concepts_dir_for, load_workspace_from_root


def register_diff_tools(mcp: FastMCP, workspace_root: str) -> None:

    @mcp.tool(
        description=(
            "Compute a structural diff between two versions of a concept. "
            "Pass two concept source texts (old and new). Returns semantic "
            "changes (state, actions, operational principle) plus any "
            "downstream syncs in the workspace that the new version breaks."
        )
    )
    def diff_concept(old_source: str, new_source: str) -> str:
        try:
            old_ast = parse_concept_source(old_source)
        except Exception as exc:
            return json.dumps({"error": f"Failed to parse old source: {exc}"})
        try:
            new_ast = parse_concept_source(new_source)
        except Exception as exc:
            return json.dumps({"error": f"Failed to parse new source: {exc}"})

        workspace, _diags = load_workspace_from_root(workspace_root)
        result = diff_concepts_with_impact(old_ast, new_ast, workspace)
        return json.dumps(result.to_dict())

    @mcp.tool(
        description=(
            "Diff a concept's current on-disk version against a proposed "
            "new version. Pass the concept name and the new source text. "
            "Returns structural changes and any broken downstream syncs."
        )
    )
    def diff_concept_against_disk(name: str, new_source: str) -> str:
        path = concepts_dir_for(workspace_root) / f"{name}.concept"
        if not path.exists():
            return json.dumps({"error": f"Concept '{name}' not found on disk"})
        try:
            old_ast = parse_concept_source(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return json.dumps({"error": f"Failed to parse on-disk version: {exc}"})

        try:
            new_ast = parse_concept_source(new_source)
        except Exception as exc:
            return json.dumps({"error": f"Failed to parse new source: {exc}"})

        workspace, _diags = load_workspace_from_root(workspace_root)
        result = diff_concepts_with_impact(old_ast, new_ast, workspace)
        return json.dumps(result.to_dict())
