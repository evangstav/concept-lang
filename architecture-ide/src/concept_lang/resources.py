import json
import os
from mcp.server.fastmcp import FastMCP
from .tools._io import load_all_concepts


def register_resources(mcp: FastMCP, concepts_dir: str) -> None:

    @mcp.resource("concept://all")
    def all_concepts() -> str:
        """All parsed concepts as a JSON list."""
        result = [ast.model_dump(exclude={"source"}) for ast in load_all_concepts(concepts_dir)]
        return json.dumps(result, indent=2)

    @mcp.resource("concept://{name}")
    def get_concept(name: str) -> str:
        """Raw source of a single concept file."""
        path = os.path.join(concepts_dir, f"{name}.concept")
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return f"// Concept '{name}' not found"
