---
name: build
description: Iteratively build a .concept spec from a natural language description using Daniel Jackson's concept design methodology.
argument-hint: "<description of the concept to build>"
allowed-tools: mcp__concept-lang__write_concept, mcp__concept-lang__read_concept, mcp__concept-lang__list_concepts, mcp__concept-lang__validate_concept, mcp__concept-lang__get_dependency_graph
---

I want to design a concept for the following functionality:

$ARGUMENTS

Please help me build a `.concept` spec following Daniel Jackson's concept design methodology.

First, use `list_concepts` to see what concepts already exist in the workspace so we can inform sync/dependency decisions.

A concept has:
- **name** and optional **type parameters** (e.g. `concept Session [User]`)
- **purpose**: one sentence stating the essential service this concept provides
- **state**: typed declarations using `set T` for sets and `A -> set B` for relations
- **actions**: each with a signature `name (param: Type)`, optional `pre:` conditions and `post:` effects using `+=` and `-=` on sets
- **sync**: operational composition using when/where/then pattern:
  - Single-line: `when OtherConcept.action (params) then local_action (params)`
  - Multi-line with conditions and multiple actions:
    ```
    when OtherConcept.action (params) -> result
      where condition_clause
      then local_action1 (params)
           local_action2 (params)
    ```

Key principles from Jackson:
1. Each concept must have a **single, independent purpose** — not a grab-bag of features
2. State should be minimal — only what's needed to define the action semantics
3. Actions should be **complete**: every action must have well-defined pre/post conditions
4. Concepts should be **independent**: avoid encoding other concepts' logic in state

Let's work iteratively. Start by proposing a concept name and purpose, then we'll refine state and actions together. When the design is ready, use `validate_concept` to check it and `write_concept` to save it.
