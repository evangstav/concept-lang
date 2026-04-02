---
name: scaffold
description: Analyze an existing codebase and extract draft .concept specs from its domain models, services, and controllers.
argument-hint: "<source directory to analyze>"
allowed-tools: mcp__concept-lang__scaffold_concepts, mcp__concept-lang__write_concept, mcp__concept-lang__validate_concept, mcp__concept-lang__list_concepts
---

Use the `scaffold_concepts` tool to analyze the codebase at the following path and extract draft .concept specs:

$ARGUMENTS

The scaffold tool will scan the source directory for domain files (models, schemas, entities, services, controllers) and return a file payload with methodology context.

After receiving the scaffold output:
1. Analyze the source code to identify distinct concepts (each with a single, independent purpose)
2. Draft `.concept` specs following Daniel Jackson's methodology
3. Use `validate_concept` to check each draft
4. Use `write_concept` to save valid concepts to the workspace
5. Use `list_concepts` to verify the final set

Focus on extracting concepts that represent genuine domain abstractions, not implementation details.
