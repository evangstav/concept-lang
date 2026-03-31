"""
Generate a Mermaid graph TD showing dependencies between concepts.

Dependency edges come from:
1. Generic params: concept Session [User, Resource] → Session depends on User, Resource
2. Sync blocks: when Auth.login → Session depends on Auth
"""

from ..models import ConceptAST


def concept_graph(concepts: list[ConceptAST]) -> str:
    lines = ["graph TD"]

    for concept in concepts:
        lines.append(f'    {concept.name}["{concept.name}"]')

    concept_names = {c.name for c in concepts}

    for concept in concepts:
        # Edges from generic params
        for param in concept.params:
            if param in concept_names:
                lines.append(f"    {concept.name} --> {param}")
            else:
                # External type — show as a plain node
                lines.append(f"    {concept.name} -.-> {param}")

        # Edges from sync blocks
        seen_sync_deps: set[str] = set()
        for clause in concept.sync:
            dep = clause.trigger_concept
            if dep not in seen_sync_deps:
                seen_sync_deps.add(dep)
                arrow = "-->" if dep in concept_names else "-.->"
                lines.append(f"    {concept.name} {arrow}|sync| {dep}")

    return "\n".join(lines)
