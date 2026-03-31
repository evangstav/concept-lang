import json
import os
from mcp.server.fastmcp import FastMCP
from ..parser import ParseError, parse_concept, parse_file
from ..validator import validate_concept as _validate_ast, validate_workspace
from ._io import list_concept_names, load_all_concepts


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
            "Checks syntax, internal consistency (state refs, action clauses, sync invocations), "
            "and optionally cross-concept consistency when workspace concepts are available. "
            "Returns validation result with any errors and warnings."
        )
    )
    def validate_concept(source: str) -> str:
        try:
            ast = parse_concept(source)
        except ParseError as e:
            return json.dumps({"valid": False, "error": str(e)})

        # Single-concept static validation
        single_result = _validate_ast(ast)

        # Cross-concept validation if workspace has other concepts
        all_concepts = load_all_concepts(concepts_dir)
        # Replace or add the current concept being validated
        other_concepts = [c for c in all_concepts if c.name != ast.name]
        workspace_concepts = other_concepts + [ast]

        if len(workspace_concepts) > 1:
            workspace_result = validate_workspace(workspace_concepts)
            issues = workspace_result.to_dict()["issues"]
        else:
            issues = single_result.to_dict()["issues"]

        has_errors = any(i["severity"] == "error" for i in issues)

        return json.dumps({
            "valid": not has_errors,
            "name": ast.name,
            "params": ast.params,
            "action_count": len(ast.actions),
            "state_count": len(ast.state),
            "issues": issues,
        })
