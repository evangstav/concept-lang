---
description: Review a concept-lang 0.2.0 workspace for rule violations and design-quality issues. Groups findings by rule category and walks the paper's three legibility properties.
argument-hint: "[concept or sync names, comma-separated]"
allowed-tools: mcp__concept-lang__validate_workspace, mcp__concept-lang__list_concepts, mcp__concept-lang__list_syncs, mcp__concept-lang__read_concept, mcp__concept-lang__read_sync, mcp__concept-lang__get_workspace_graph, mcp__concept-lang__get_state_machine, mcp__concept-lang__get_entity_diagram, mcp__concept-lang__get_explorer_html
---

Please review the concept-lang workspace for design quality: $ARGUMENTS

If `$ARGUMENTS` is empty, review the whole workspace. If it lists specific concept or sync names, focus your fix proposals on those but still run the full workspace validation — some issues only surface when the whole workspace is considered together.

## Step 1: Structural review via `validate_workspace`

Call `validate_workspace` with no arguments. The response JSON has a top-level `diagnostics` list, a `valid` boolean, and a `summary` block. The diagnostics list is your structural ground truth — every validator rule (`C1`–`C9`, `S1`–`S5`, `P0`) produces a diagnostic with a `code`, a `severity`, a `message`, a `file`, and optionally a `line` and `column`.

### Handling missing line and column positions

Some workspace-level rules deliberately surface with `line=None` / `column=None` because the rule fires against a whole file rather than a specific AST node. When you render a diagnostic whose `line` or `column` field is `null` (JSON) or `None` (Python), do **NOT** print `:None:None` or `:null:null`. Render it in the short form instead:

```
<file>: <message>
```

Only include the `(line <line>, col <col>)` suffix when both fields are present and non-null.

### Category map (pin for the paper-aligned rule set)

Group every diagnostic into one of these five categories, and within each category sub-group by file so that a reviewer of a large workspace sees their problems clustered usefully.

- **Independence** — rules that enforce "a concept is a self-contained story."
  - `C1` unknown type in a state or action signature
  - `C4` inline sync section embedded inside a concept (syncs live in separate files in 0.2.0)
- **Completeness** — rules that enforce "a concept is fully specified."
  - `C5` empty purpose
  - `C6` no actions declared
  - `C7` action case issues (malformed signatures, missing success case)
  - `C9` no operational principle steps
- **Action cross-references inside a concept** — rules that enforce "actions talk about their own concept's state and their own effects."
  - `C2` effect on a field that does not exist in the concept's state
  - `C3` operational principle step references an action that is not declared
- **Sync** — rules that enforce "syncs compose real actions and bind every variable they use."
  - `S1` unknown concept or action referenced from a sync
  - `S2` pattern field does not exist on the referenced action
  - `S3` free variable in a `then` clause (used but never bound)
  - `S4` unbound subject in a `where` state query
  - `S5` single-concept sync (warning — usually a hint the behavior belongs inside the concept itself)
- **Parse** — rules that block every other check when a file fails to parse.
  - `P0` parse failure (grammar mismatch, unclosed bracket, unexpected token)

If a diagnostic's `code` does not appear in this map, render it under an **Other** category and flag it as "rule added after the skill was last updated — please check docs/methodology.md". Do not silently drop unknown codes.

### Rendering format

For each category with at least one diagnostic, render:

```
### <Category name>

**<file path>**
- `<code>` [<severity>] <message>  (line <line>, col <col>)
- `<code>` [<severity>] <message>   ← omit the parenthetical when line or column is null

**<another file>**
- ...
```

Skip categories that have zero diagnostics — do not print an empty heading. At the very end of Step 1, print a one-line summary: `X errors, Y warnings, Z info across N files`, computed from the aggregate counts across all categories.

### For each finding, propose a concrete fix

A diagnostic on its own is a signal, not a solution. For every **error**-severity finding, also propose a concrete edit to the file and cite the paper's rationale in one sentence. Examples:

- `C1` on `concept User` field `perms: Permission` — "The type `Permission` is not declared. Either add it as a type parameter on the concept (`concept User [Permission]`) or split `Permission` into its own concept. The paper says concepts are independent of each other's types; a bare external type reference is usually a hint that the field belongs in a different concept."
- `S1` on `sync RegisterDefaultProfile` referencing `Profle/register` — "The concept name `Profle` does not exist — did you mean `Profile`? Syncs compose real actions; the validator refuses to resolve typo'd names so that renames stay safe."
- `C2` on `concept Session` action `logout` effecting field `user_id` — "The concept's state block does not declare `user_id`. Either add the field to state (if the action really needs to clear it) or remove the effect (if the action is meant to terminate without touching that field)."

If the user passed specific names in `$ARGUMENTS`, propose fixes only for findings in those files. Still print the full category summary across every file so that the user sees the overall workspace health, not just the scope they asked about.

## Step 2: Design-quality review via the paper's three legibility properties

After the structural review, walk the workspace through the three legibility properties from Daniel Jackson's paper. These are heuristic — the validator does not enforce them — so this section is a set of questions you ask by *reading the source*, not by calling a rule.

Frame each property as a lens: you are asking "would a new reader, opening this workspace for the first time, actually be able to read it?"

### Incrementality

> A concept spec should be understandable one concept at a time, without reading the whole workspace.

For each concept in scope, ask:

- Does the `purpose` line stand on its own? If a reader has to already know what `Article` is in order to understand what `Profile` is FOR, that is an incrementality leak — the purpose is smuggling in shared context.
- Can the reader understand what each action does from the action body alone, without cross-referencing another concept's state or actions?
- Does the operational principle tell a story that uses **only this concept's actions**, or does it hint at behavior that really belongs in a sync file?

For every incrementality issue, propose both (i) what to delete or reword inside the concept, and (ii) what to add as a top-level `.sync` file if the cross-concept dependency is real and was just hiding in the wrong place.

### Integrity

> The behavior described in the concept matches what a faithful implementation will actually do.

Call `get_state_machine(name=<Concept>)` for each concept in scope and look at the Mermaid state-machine render:

- For each state transition the diagram shows, check that it corresponds to at least one action in the concept. If the diagram shows a state that the actions never reach, you have dead state — either remove the state or add the missing action.
- If there are actions whose effects the diagram does not reflect, the action bodies are lying about what they do. Ask the user to reconcile — either the bodies are wrong or the state shape is.

Call `get_entity_diagram(name=<Concept>)` for each concept in scope and look at the relation shapes:

- Fields declared as `set T` should appear as entity boxes.
- Fields declared as `A -> set B` should appear as associations between entities.
- A mismatch between the state declaration and the diagram usually means the state shape is wrong at the source.

### Transparency

> The reader can see the whole system at a glance without drilling into any single concept.

Call `get_workspace_graph` and look at the Mermaid `graph TD` output. Nodes are concepts; edges are the syncs that connect them, labeled with the sync name.

- Are there **orphan nodes** — concepts with neither incoming nor outgoing edges? If yes, either the concept is genuinely standalone (which is fine — note it as intentional) or it is unreachable from any user-visible surface (a bug: either delete the concept or add the sync file that exercises it).
- Are there **hub nodes** — concepts that are the target of many syncs? If yes, check whether the hub is a legitimate bootstrap concept (`Web`, `CLI`, `Event`) or a regular concept accidentally acting as one. A regular concept with many incoming syncs is usually a missed abstraction — propose either splitting it or extracting a bootstrap concept to sit in front of it.
- Are there sync names that are too vague to tell what they do from the edge label alone? A sync named `sync1` or `handler` is a transparency smell; propose a rename.

Print the workspace graph verbatim in the review output so the user can see what you saw.

## Step 3: Summarize

End the review with three sections:

1. **Blocking issues** — every `error`-severity diagnostic from Step 1 plus every Step 2 finding that you (the reviewer) think is important enough to block a release.
2. **Warnings** — `warning`-severity diagnostics from Step 1 plus soft Step 2 findings that the user should address but that do not block shipping.
3. **Things the reviewer liked** — concrete positive observations about the workspace. Be specific: "the sync file `RegisterDefaultProfile` is a clean example of bootstrap composition" is useful; "nice work overall" is not.

## Scope narrowing

If the user passed a comma-separated list of names in `$ARGUMENTS`:

- Still call `validate_workspace` with no arguments (workspace-level rules need the whole picture).
- Still render every category in Step 1 so the user sees total health.
- But only propose concrete fixes for findings whose `file` matches one of the requested names, and only walk the legibility properties (Step 2) for concepts in the requested set.

## What NOT to do

- Do not call the deprecated workspace-graph alias. Use `get_workspace_graph` — it is the canonical tool in 0.2.0.
- Do not call any app-spec tool. The v1 app-spec format is out of scope for this skill; the 0.2.0 workspace is `concepts/` + `syncs/` only.
- Do not invent new rule codes. If `validate_workspace` returns a `code` that is not in the category map above, render it under "Other" and point the user at `docs/methodology.md`.
- Do not attempt to auto-fix anything. This skill is advisory — the user decides which fixes to apply by running `/concept-lang:build` for concept edits or `/concept-lang:build-sync` for sync edits.
- Do not look for inline sync blocks nested inside a concept file. That was the v1 shape; the 0.2.0 workspace keeps syncs in their own files, and `C4` will flag any leftover inline blocks automatically.
