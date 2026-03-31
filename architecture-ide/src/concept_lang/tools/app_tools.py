"""MCP tools for app specs (concept composition layer)."""

import json
import os
from mcp.server.fastmcp import FastMCP
from ..app_parser import AppParseError, parse_app, parse_app_file
from ..app_validator import validate_app
from ..models import ConceptAST
from ..parser import ParseError, parse_file
from ..diagrams import concept_graph


def _load_declared_concepts(
    concepts_dir: str, concept_names: list[str]
) -> dict[str, ConceptAST]:
    """Load concept ASTs for the given names, returning what exists."""
    loaded: dict[str, ConceptAST] = {}
    for name in concept_names:
        path = os.path.join(concepts_dir, f"{name}.concept")
        try:
            loaded[name] = parse_file(path)
        except (FileNotFoundError, ParseError):
            pass
    return loaded


def register_app_tools(mcp: FastMCP, concepts_dir: str) -> None:

    @mcp.tool(description="List all .app files in the concepts directory")
    def list_apps() -> str:
        try:
            names = sorted(
                f[:-4] for f in os.listdir(concepts_dir) if f.endswith(".app")
            )
            return json.dumps(names)
        except FileNotFoundError:
            return json.dumps([])

    @mcp.tool(
        description=(
            "Read and parse an .app file. Returns the parsed app spec as JSON. "
            "Pass the app name without the .app extension."
        )
    )
    def read_app(name: str) -> str:
        path = os.path.join(concepts_dir, f"{name}.app")
        try:
            app = parse_app_file(path)
            return json.dumps({
                "name": app.name,
                "purpose": app.purpose,
                "concepts": [
                    {"name": c.name, "bindings": c.bindings}
                    for c in app.concepts
                ],
                "source": app.source,
            })
        except FileNotFoundError:
            return json.dumps({"error": f"App '{name}' not found"})
        except AppParseError as e:
            return json.dumps({"error": str(e)})

    @mcp.tool(
        description=(
            "Write or overwrite an .app file. Validates the source before writing. "
            "Pass app name (without extension) and the full source text."
        )
    )
    def write_app(name: str, source: str) -> str:
        try:
            parse_app(source)
        except AppParseError as e:
            return json.dumps({"error": f"Validation failed: {e}", "written": False})

        os.makedirs(concepts_dir, exist_ok=True)
        path = os.path.join(concepts_dir, f"{name}.app")
        with open(path, "w", encoding="utf-8") as f:
            f.write(source)
        return json.dumps({"written": True, "path": path})

    @mcp.tool(
        description=(
            "Validate an .app file against its concept definitions. "
            "Checks that all concepts exist, type bindings are correct, "
            "and sync dependencies are satisfied. "
            "Pass the app name without the .app extension."
        )
    )
    def validate_app_spec(name: str) -> str:
        path = os.path.join(concepts_dir, f"{name}.app")
        try:
            app = parse_app_file(path)
        except FileNotFoundError:
            return json.dumps({"error": f"App '{name}' not found"})
        except AppParseError as e:
            return json.dumps({"valid": False, "error": str(e)})

        concept_names = [c.name for c in app.concepts]
        loaded = _load_declared_concepts(concepts_dir, concept_names)
        errors = validate_app(app, loaded)

        return json.dumps({
            "valid": len([e for e in errors if e.level == "error"]) == 0,
            "errors": [e.to_dict() for e in errors if e.level == "error"],
            "warnings": [e.to_dict() for e in errors if e.level == "warning"],
            "concepts_declared": len(app.concepts),
            "concepts_loaded": len(loaded),
        })

    @mcp.tool(
        description=(
            "Generate a Mermaid dependency graph for an app spec, showing only "
            "the concepts declared in the app and their sync/param relationships. "
            "Pass the app name without the .app extension."
        )
    )
    def get_app_dependency_graph(name: str) -> str:
        path = os.path.join(concepts_dir, f"{name}.app")
        try:
            app = parse_app_file(path)
        except FileNotFoundError:
            return f"// Error: App '{name}' not found"
        except AppParseError as e:
            return f"// Error: {e}"

        concept_names = [c.name for c in app.concepts]
        loaded = _load_declared_concepts(concepts_dir, concept_names)

        if not loaded:
            return "// No concept files found for this app"

        # Build the graph from loaded concepts
        concepts_list = list(loaded.values())
        declared_set = {c.name for c in app.concepts}

        lines = [f"graph TD"]
        lines.append(f'    subgraph {app.name}["{app.name}"]')

        for binding in app.concepts:
            label = binding.name
            if binding.bindings:
                label += f"[{', '.join(binding.bindings)}]"
            lines.append(f'        {binding.name}["{label}"]')

        # Add edges from loaded concepts
        for ast in concepts_list:
            # Param binding edges
            binding = next(b for b in app.concepts if b.name == ast.name)
            for bound_to in binding.bindings:
                if bound_to in declared_set:
                    lines.append(f"        {ast.name} -->|param| {bound_to}")

            # Sync edges
            seen_sync: set[str] = set()
            for clause in ast.sync:
                dep = clause.trigger_concept
                if dep not in seen_sync and dep in declared_set:
                    seen_sync.add(dep)
                    lines.append(f"        {ast.name} -.->|sync| {dep}")

        lines.append("    end")

        # Add external dependencies (concepts referenced but not in app)
        for ast in concepts_list:
            for clause in ast.sync:
                if clause.trigger_concept not in declared_set:
                    lines.append(
                        f'    {clause.trigger_concept}["{clause.trigger_concept} ❓"]:::external'
                    )
                    lines.append(
                        f"    {ast.name} -.->|sync| {clause.trigger_concept}"
                    )

        lines.append("    classDef external fill:#21262d,stroke:#484f58,stroke-dasharray:5")

        return "\n".join(lines)
