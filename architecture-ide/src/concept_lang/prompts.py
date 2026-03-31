from mcp.server.fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:

    @mcp.prompt()
    def build_concept(description: str, existing_concepts: str = "") -> list[dict]:
        """
        Iteratively build a concept spec from a natural language description.
        Optionally pass existing concept names to inform sync/dependency decisions.
        """
        context = ""
        if existing_concepts:
            context = f"\n\nExisting concepts in this system: {existing_concepts}"

        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"""I want to design a concept for the following functionality:

{description}{context}

Please help me build a `.concept` spec following Daniel Jackson's concept design methodology.

A concept has:
- **name** and optional **type parameters** (e.g. `concept Session [User]`)
- **purpose**: one sentence stating the essential service this concept provides
- **state**: typed declarations using `set T` for sets and `A -> set B` for relations
- **actions**: each with a signature `name (param: Type)`, optional `pre:` conditions and `post:` effects using `+=` and `-=` on sets
- **sync**: operational composition with other concepts using `when OtherConcept.action (params) then local_action (params)`

Key principles from Jackson:
1. Each concept must have a **single, independent purpose** — not a grab-bag of features
2. State should be minimal — only what's needed to define the action semantics
3. Actions should be **complete**: every action must have well-defined pre/post conditions
4. Concepts should be **independent**: avoid encoding other concepts' logic in state

Let's work iteratively. Start by proposing a concept name and purpose, then we'll refine state and actions together.""",
                },
            }
        ]

    @mcp.prompt()
    def review_concepts(concept_names: str) -> list[dict]:
        """
        Review a set of concepts for coherence, independence, and completeness.
        Pass a comma-separated list of concept names.
        """
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"""Please review these concepts for design quality: {concept_names}

Use the `read_concept` tool to load each one, then evaluate:

1. **Independence**: Does each concept have a single, self-contained purpose? Could it exist without the others?
2. **Completeness**: Are all actions fully specified with pre/post conditions?
3. **Minimality**: Is the state model as small as it can be while still supporting all actions?
4. **Sync coherence**: Are the sync clauses appropriate? Do they represent genuine operational composition or are they papering over a missing concept?
5. **Naming**: Are concept, action, and state names clear and consistent with the domain?

For each issue found, suggest a specific improvement to the `.concept` source.

Also use `get_dependency_graph` to render the overall concept map and check for unexpected coupling.""",
                },
            }
        ]
