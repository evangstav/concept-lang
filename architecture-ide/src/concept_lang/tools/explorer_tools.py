"""MCP tools for the interactive HTML concept explorer (v2)."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from concept_lang.explorer import generate_explorer

from ._io import load_workspace_from_root, resolve_workspace_root


def register_explorer_tools(mcp: FastMCP, workspace_root: str) -> None:

    @mcp.tool(
        description=(
            "Generate an interactive HTML concept explorer for the current "
            "workspace. Returns a self-contained HTML page with a clickable "
            "concept graph (syncs as edges), per-concept state and entity "
            "diagrams, and per-sync flow diagrams. Open the returned file "
            "path in a browser to explore."
        )
    )
    def get_interactive_explorer(open_browser: bool = True) -> str:
        workspace, _diags = load_workspace_from_root(workspace_root)
        if not workspace.concepts and not workspace.syncs:
            return f"No concepts or syncs found in {workspace_root}"

        html = generate_explorer(workspace)

        root = resolve_workspace_root(workspace_root)
        out_path = root / "concept-explorer.html"
        out_path.write_text(html, encoding="utf-8")

        if open_browser:
            webbrowser.open(f"file://{out_path}")

        return f"Explorer generated: {out_path}"

    @mcp.tool(
        description=(
            "Get the interactive explorer as raw HTML string. Use this "
            "when you want to embed the explorer or serve it differently "
            "rather than writing it to a file."
        )
    )
    def get_explorer_html() -> str:
        workspace, _diags = load_workspace_from_root(workspace_root)
        if not workspace.concepts and not workspace.syncs:
            return "<!-- No concepts or syncs found -->"
        return generate_explorer(workspace)
