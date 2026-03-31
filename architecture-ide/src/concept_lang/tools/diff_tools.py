import json
import os
from mcp.server.fastmcp import FastMCP
from ..parser import ParseError, parse_concept, parse_file
from ..diff import diff_concepts_with_impact
from ._io import load_all_concepts


def register_diff_tools(mcp: FastMCP, concepts_dir: str) -> None:

    @mcp.tool(
        description=(
            "Compute a structural diff between two versions of a concept. "
            "Pass two concept source texts (old and new). Returns semantic changes: "
            "state added/removed/renamed, actions changed, sync clauses modified. "
            "Optionally detects broken syncs in downstream workspace concepts."
        )
    )
    def diff_concept(old_source: str, new_source: str) -> str:
        try:
            old_ast = parse_concept(old_source)
        except ParseError as e:
            return json.dumps({"error": f"Failed to parse old source: {e}"})

        try:
            new_ast = parse_concept(new_source)
        except ParseError as e:
            return json.dumps({"error": f"Failed to parse new source: {e}"})

        workspace = load_all_concepts(concepts_dir)
        result = diff_concepts_with_impact(old_ast, new_ast, workspace)
        return json.dumps(result.to_dict())

    @mcp.tool(
        description=(
            "Diff a concept's current on-disk version against a proposed new version. "
            "Pass the concept name and the new source text. Returns structural changes "
            "and any broken downstream syncs."
        )
    )
    def diff_concept_against_disk(name: str, new_source: str) -> str:
        path = os.path.join(concepts_dir, f"{name}.concept")
        try:
            old_ast = parse_file(path)
        except FileNotFoundError:
            return json.dumps({"error": f"Concept '{name}' not found on disk"})
        except ParseError as e:
            return json.dumps({"error": f"Failed to parse on-disk version: {e}"})

        try:
            new_ast = parse_concept(new_source)
        except ParseError as e:
            return json.dumps({"error": f"Failed to parse new source: {e}"})

        workspace = load_all_concepts(concepts_dir)
        result = diff_concepts_with_impact(old_ast, new_ast, workspace)
        return json.dumps(result.to_dict())
