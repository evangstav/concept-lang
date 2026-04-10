from mcp.server.fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:

    @mcp.prompt()
    def build_concept(description: str, existing_concepts: str = "") -> list[dict]:
        """
        Iteratively build a concept spec from a natural language description.
        Optionally pass existing concept names to inform independence checks.
        """
        context = ""
        if existing_concepts:
            context = f"\n\nExisting concepts in this workspace: {existing_concepts}"

        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"""I want to design a concept for the following functionality:

{description}{context}

Please help me build a `.concept` spec in concept-lang 0.2.0 format (Daniel Jackson's paper-aligned methodology).

A 0.2.0 concept file has exactly these sections, in order:

    concept <Name> [<TypeParam>, ...]

      purpose
        <one sentence>

      state
        <field>: <type-expression>

      actions
        <action_name> [ <in>: <T> ] => [ <out>: <U> ]
          <natural-language body>
          effects: <optional += / -= on state>

        <action_name> [ <in>: <T> ] => [ error: string ]
          <describe the error case>

      operational principle
        after <action> [...] => [...]
        and   <action> [...] => [...]
        then  <action> [...] => [...]

Rules:
1. Each concept has a single, independent purpose.
2. Every action has at least one success case AND at least one error case.
3. No inline sync section — syncs live in separate .sync files now.
4. Do not reference other concepts in state, effects, or operational principle.
5. Use `validate_concept` iteratively and `write_concept` to save.

Work iteratively: propose name+purpose first, then state, then action list, then one action at a time, then the operational principle. Validate with `validate_concept` before writing.""",
                },
            }
        ]

    @mcp.prompt()
    def review_concepts(concept_names: str = "") -> list[dict]:
        """
        Review a set of concepts (or the whole workspace) for rule violations
        and design-quality issues. Pass a comma-separated list of concept names,
        or leave empty to review the whole workspace.
        """
        scope = concept_names if concept_names else "the whole workspace"
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"""Please review {scope} for design quality.

1. Call `validate_workspace` and group the diagnostics by rule category:
   - Independence (C1, C4)
   - Completeness (C5, C6, C7, C9)
   - Action cross-references (C2, C3)
   - Sync (S1, S2, S3, S4, S5)
   - Parse (P0)
   Sub-group by file within each category. For diagnostics with
   line=None or column=None, render as `<file>: <message>` without
   a position suffix.

2. For each error-severity finding, propose a concrete fix citing
   the paper's rationale in one sentence.

3. Walk the workspace through the three legibility properties from
   Daniel Jackson's paper:
   - Incrementality: can each concept be understood on its own?
   - Integrity: do the actions match the state-machine shape?
   - Transparency: can the whole system be seen at a glance via
     `get_workspace_graph`?

4. End with a blocking-issues / warnings / positive-observations
   summary.

Do not touch any app-spec tool.""",
                },
            }
        ]
