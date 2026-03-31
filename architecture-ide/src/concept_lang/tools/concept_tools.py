import json
import os
from mcp.server.fastmcp import FastMCP
from ..parser import ParseError, parse_concept, parse_file
from ._io import list_concept_names


def register_concept_tools(mcp: FastMCP, concepts_dir: str) -> None:

    @mcp.tool(description="List all .concept files in the concepts directory")
    def list_concepts() -> str:
        return json.dumps(list_concept_names(concepts_dir))

    @mcp.tool(
        description=(
            "Read and parse a .concept file. Returns the raw source and the parsed AST as JSON. "
            "Pass the concept name without the .concept extension."
        )
    )
    def read_concept(name: str) -> str:
        path = os.path.join(concepts_dir, f"{name}.concept")
        try:
            ast = parse_file(path)
            return json.dumps({"source": ast.source, "ast": ast.model_dump(exclude={"source"})})
        except FileNotFoundError:
            return json.dumps({"error": f"Concept '{name}' not found"})
        except ParseError as e:
            return json.dumps({"error": str(e)})

    @mcp.tool(
        description=(
            "Write or overwrite a .concept file. Validates the source before writing. "
            "Pass concept name (without extension) and the full source text."
        )
    )
    def write_concept(name: str, source: str) -> str:
        try:
            parse_concept(source)
        except ParseError as e:
            return json.dumps({"error": f"Validation failed: {e}", "written": False})

        os.makedirs(concepts_dir, exist_ok=True)
        path = os.path.join(concepts_dir, f"{name}.concept")
        with open(path, "w", encoding="utf-8") as f:
            f.write(source)
        return json.dumps({"written": True, "path": path})

    @mcp.tool(
        description=(
            "Validate .concept source text without writing to disk. "
            "Returns 'valid' or a list of parse errors."
        )
    )
    def validate_concept(source: str) -> str:
        try:
            ast = parse_concept(source)
            return json.dumps({
                "valid": True,
                "name": ast.name,
                "params": ast.params,
                "action_count": len(ast.actions),
                "state_count": len(ast.state),
            })
        except ParseError as e:
            return json.dumps({"valid": False, "error": str(e)})
