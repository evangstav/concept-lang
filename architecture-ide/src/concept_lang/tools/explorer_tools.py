import os
import webbrowser

from mcp.server.fastmcp import FastMCP
from ..explorer import generate_explorer
from ._io import load_all_concepts


def register_explorer_tools(mcp: FastMCP, concepts_dir: str) -> None:

    @mcp.tool(
        description=(
            "Generate an interactive HTML concept explorer. "
            "Returns a self-contained HTML page with a clickable dependency graph, "
            "state machine and entity diagrams, action→sync tracing, and data flow "
            "visualization. Open the returned file path in a browser to explore."
        )
    )
    def get_interactive_explorer(open_browser: bool = True) -> str:
        concepts = load_all_concepts(concepts_dir)
        if not concepts:
            return "No concepts found in " + concepts_dir

        html = generate_explorer(concepts)

        # Write to a stable location alongside the concepts directory
        out_dir = os.path.dirname(os.path.abspath(concepts_dir))
        out_path = os.path.join(out_dir, "concept-explorer.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        if open_browser:
            webbrowser.open(f"file://{out_path}")

        return f"Explorer generated: {out_path}"

    @mcp.tool(
        description=(
            "Get the interactive explorer as raw HTML string. "
            "Use this when you want to embed the explorer or serve it differently "
            "rather than writing to a file."
        )
    )
    def get_explorer_html() -> str:
        concepts = load_all_concepts(concepts_dir)
        if not concepts:
            return "<!-- No concepts found -->"
        return generate_explorer(concepts)
