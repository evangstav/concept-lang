"""MCP tools for per-concept Mermaid diagrams (v2)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from concept_lang.ast import ConceptAST
from concept_lang.diagrams import entity_diagram, state_machine
from concept_lang.explorer import _to_v1_concept
from concept_lang.parse import parse_concept_file

from ._io import concepts_dir_for


def register_diagram_tools(mcp: FastMCP, workspace_root: str) -> None:

    def _load(name: str) -> ConceptAST:
        path = concepts_dir_for(workspace_root) / f"{name}.concept"
        if not path.exists():
            raise FileNotFoundError(f"Concept '{name}' not found")
        return parse_concept_file(path)

    @mcp.tool(
        description=(
            "Generate a Mermaid stateDiagram-v2 for a concept. "
            "Shows how actions transition entities through the concept's "
            "principal set. Pass to "
            "mcp__claude_ai_Mermaid_Chart__validate_and_render_mermaid_diagram "
            "to render."
        )
    )
    def get_state_machine(name: str) -> str:
        try:
            return state_machine(_to_v1_concept(_load(name)))
        except FileNotFoundError as e:
            return f"// Error: {e}"
        except Exception as e:
            return f"// Error: {e}"

    @mcp.tool(
        description=(
            "Generate a Mermaid classDiagram for a concept. "
            "Shows the concept's state model: sets as classes, relations "
            "as associations. Pass to "
            "mcp__claude_ai_Mermaid_Chart__validate_and_render_mermaid_diagram "
            "to render."
        )
    )
    def get_entity_diagram(name: str) -> str:
        try:
            return entity_diagram(_to_v1_concept(_load(name)))
        except FileNotFoundError as e:
            return f"// Error: {e}"
        except Exception as e:
            return f"// Error: {e}"
