from mcp.server.fastmcp import FastMCP
from ..parser import ParseError, parse_file
from ..diagrams import concept_graph, entity_diagram, state_machine
from ._io import load_all_concepts


def register_diagram_tools(mcp: FastMCP, concepts_dir: str) -> None:

    def _load(name: str):
        try:
            return parse_file(f"{concepts_dir}/{name}.concept")
        except FileNotFoundError:
            raise FileNotFoundError(f"Concept '{name}' not found")

    @mcp.tool(
        description=(
            "Generate a Mermaid stateDiagram-v2 for a concept. "
            "Shows how actions transition entities through the concept's principal set. "
            "Pass to mcp__claude_ai_Mermaid_Chart__validate_and_render_mermaid_diagram to render."
        )
    )
    def get_state_machine(name: str) -> str:
        try:
            return state_machine(_load(name))
        except (FileNotFoundError, ParseError) as e:
            return f"// Error: {e}"

    @mcp.tool(
        description=(
            "Generate a Mermaid classDiagram for a concept. "
            "Shows the concept's state model: sets as classes, relations as associations. "
            "Pass to mcp__claude_ai_Mermaid_Chart__validate_and_render_mermaid_diagram to render."
        )
    )
    def get_entity_diagram(name: str) -> str:
        try:
            return entity_diagram(_load(name))
        except (FileNotFoundError, ParseError) as e:
            return f"// Error: {e}"

    @mcp.tool(
        description=(
            "Generate a Mermaid graph TD showing dependencies between all concepts. "
            "Edges come from generic params and sync blocks. "
            "Pass to mcp__claude_ai_Mermaid_Chart__validate_and_render_mermaid_diagram to render."
        )
    )
    def get_dependency_graph() -> str:
        try:
            concepts = load_all_concepts(concepts_dir)
            if not concepts:
                return "// No concepts found"
            return concept_graph(concepts)
        except Exception as e:
            return f"// Error: {e}"
