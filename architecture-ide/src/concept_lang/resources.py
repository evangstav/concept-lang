"""MCP resources for concept-lang 0.2.0."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from .tools._io import concepts_dir_for, load_workspace_from_root, syncs_dir_for


def register_resources(mcp: FastMCP, workspace_root: str) -> None:

    @mcp.resource("concept://all")
    def all_concepts() -> str:
        """All parsed concepts as a JSON list."""
        workspace, _diags = load_workspace_from_root(workspace_root)
        result = [
            ast.model_dump(exclude={"source"})
            for ast in workspace.concepts.values()
        ]
        return json.dumps(result, indent=2)

    @mcp.resource("sync://all")
    def all_syncs() -> str:
        """All parsed syncs as a JSON list."""
        workspace, _diags = load_workspace_from_root(workspace_root)
        result = [
            ast.model_dump(exclude={"source"})
            for ast in workspace.syncs.values()
        ]
        return json.dumps(result, indent=2)

    @mcp.resource("concept://{name}")
    def get_concept(name: str) -> str:
        """Raw source of a single concept file."""
        path = concepts_dir_for(workspace_root) / f"{name}.concept"
        if not path.exists():
            return f"// Concept '{name}' not found"
        return path.read_text(encoding="utf-8")

    @mcp.resource("sync://{name}")
    def get_sync(name: str) -> str:
        """Raw source of a single sync file."""
        path = syncs_dir_for(workspace_root) / f"{name}.sync"
        if not path.exists():
            return f"// Sync '{name}' not found"
        return path.read_text(encoding="utf-8")
