---
description: Review concept specs for coherence, independence, completeness, and design quality. Pass concept names or use without args to review all.
argument-hint: "[concept names, comma-separated]"
allowed-tools: mcp__concept-lang__read_concept, mcp__concept-lang__list_concepts, mcp__concept-lang__validate_concept, mcp__concept-lang__get_dependency_graph, mcp__concept-lang__get_state_machine, mcp__concept-lang__get_entity_diagram
---

Please review these concepts for design quality: $ARGUMENTS

If no concept names were provided above, use `list_concepts` to discover all concepts in the workspace and review them all.

Use the `read_concept` tool to load each one, then evaluate:

1. **Independence**: Does each concept have a single, self-contained purpose? Could it exist without the others?
2. **Completeness**: Are all actions fully specified with pre/post conditions?
3. **Minimality**: Is the state model as small as it can be while still supporting all actions?
4. **Sync coherence**: Are the sync clauses appropriate? Do they represent genuine operational composition or are they papering over a missing concept?
5. **Naming**: Are concept, action, and state names clear and consistent with the domain?

For each issue found, suggest a specific improvement to the `.concept` source.

Also use `get_dependency_graph` to render the overall concept map and check for unexpected coupling. Use `get_state_machine` and `get_entity_diagram` for individual concepts to verify state model correctness.
