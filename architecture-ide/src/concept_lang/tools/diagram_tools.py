"""MCP tools for per-concept Mermaid diagrams (v2)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from concept_lang.ast import ConceptAST
from concept_lang.diagrams import entity_diagram, state_machine
from concept_lang.parse import parse_concept_file

from ._io import concepts_dir_for


# TEMP STUB — replaced post-merge by import from concept_lang.explorer
# Stream A's feat-p1-parser branch introduces `_to_v1_concept` as a
# public adapter in `concept_lang.explorer`. This stub lets diagram_tools
# stay functional on the P4 branch until that lands; at merge time the
# local definition here is dropped in favour of the imported symbol.
def _to_v1_concept(concept: ConceptAST):
    """Convert a new-AST ConceptAST into a v1 ConceptAST shell for diagrams.

    Only the fields consumed by `state_machine` and `entity_diagram`
    (state/actions with pre/post clauses, name, params, purpose, source)
    are populated. Action cases collapse into a single v1 action whose
    `post.clauses` are built from the first case's effects.
    """
    from concept_lang.models import (
        Action as V1Action,
        ConceptAST as V1ConceptAST,
        PrePost as V1PrePost,
        StateDecl as V1StateDecl,
    )

    v1_state = [
        V1StateDecl(name=decl.name, type_expr=decl.type_expr)
        for decl in concept.state
    ]

    v1_actions: list[V1Action] = []
    for action in concept.actions:
        first_case = action.cases[0] if action.cases else None
        params: list[str] = []
        post_clauses: list[str] = []
        if first_case is not None:
            params = [f"{i.name}: {i.type_expr}" for i in first_case.inputs]
            post_clauses = [e.raw for e in first_case.effects]
        post = V1PrePost(clauses=post_clauses) if post_clauses else None
        v1_actions.append(
            V1Action(name=action.name, params=params, pre=None, post=post)
        )

    return V1ConceptAST(
        name=concept.name,
        params=list(concept.params),
        purpose=concept.purpose,
        state=v1_state,
        actions=v1_actions,
        sync=[],
        source=concept.source,
    )


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
