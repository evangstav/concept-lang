---
description: Generate an interactive HTML explorer with dependency graphs, state machines, entity diagrams, and action tracing for all concepts.
disable-model-invocation: true
allowed-tools: mcp__concept-lang__get_interactive_explorer, mcp__concept-lang__get_explorer_html, mcp__concept-lang__list_concepts, mcp__concept-lang__get_dependency_graph
---

Use the `get_interactive_explorer` tool to generate a self-contained HTML explorer for all concepts in the workspace.

The explorer provides:
- **Clickable dependency graph** showing relationships between concepts
- **State machine diagrams** for each concept's action transitions
- **Entity diagrams** showing state models (sets as classes, relations as associations)
- **Action-to-sync tracing** to follow operational composition chains
- **Data flow visualization** across the concept system

The tool will write the explorer to a file and optionally open it in the browser. Report the file path back to the user.
