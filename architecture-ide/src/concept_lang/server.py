import os
from mcp.server.fastmcp import FastMCP
from .tools import register_concept_tools, register_diagram_tools, register_scaffold_tools
from .resources import register_resources
from .prompts import register_prompts


def create_server(concepts_dir: str | None = None) -> FastMCP:
    if concepts_dir is None:
        concepts_dir = os.environ.get("CONCEPTS_DIR", "./concepts")

    mcp = FastMCP("concept-lang")

    register_concept_tools(mcp, concepts_dir)
    register_diagram_tools(mcp, concepts_dir)
    register_scaffold_tools(mcp, concepts_dir)
    register_resources(mcp, concepts_dir)
    register_prompts(mcp)

    return mcp


def main() -> None:
    mcp = create_server()
    mcp.run()


if __name__ == "__main__":
    main()
