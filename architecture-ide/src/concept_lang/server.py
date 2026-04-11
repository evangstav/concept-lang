"""MCP server entry point for concept-lang 0.2.0."""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from .prompts import register_prompts
from .resources import register_resources
from .tools import (
    register_app_tools,
    register_concept_tools,
    register_diagram_tools,
    register_diff_tools,
    register_explorer_tools,
    register_scaffold_tools,
    register_sync_tools,
    register_workspace_tools,
)


def _resolve_workspace_root_arg(workspace_root: str | None) -> str:
    """
    Resolve the workspace root from the ctor arg, then env vars.

    Checks (in order):
      1. the `workspace_root` argument
      2. the `WORKSPACE_DIR` environment variable
      3. the legacy `CONCEPTS_DIR` environment variable (for back-compat
         with existing installations; the tool layer's
         `resolve_workspace_root` helper will walk up one level if the
         value ends in `/concepts` or `/syncs`)
      4. the literal string `.concepts` (the 0.3.1+ convention — a
         hidden directory at the project root containing `concepts/`,
         `syncs/`, and optionally `apps/` subdirectories)
    """
    if workspace_root is not None:
        return workspace_root
    env = os.environ.get("WORKSPACE_DIR")
    if env:
        return env
    env = os.environ.get("CONCEPTS_DIR")
    if env:
        return env
    return ".concepts"


def create_server(workspace_root: str | None = None) -> FastMCP:
    root = _resolve_workspace_root_arg(workspace_root)

    mcp = FastMCP("concept-lang")

    register_concept_tools(mcp, root)
    register_sync_tools(mcp, root)
    register_workspace_tools(mcp, root)
    register_diff_tools(mcp, root)
    register_diagram_tools(mcp, root)
    register_explorer_tools(mcp, root)
    register_scaffold_tools(mcp, root)
    register_app_tools(mcp, root)
    register_resources(mcp, root)
    register_prompts(mcp)

    return mcp


def main() -> None:
    mcp = create_server()
    mcp.run()


if __name__ == "__main__":
    main()
