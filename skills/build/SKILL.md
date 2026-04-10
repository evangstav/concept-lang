---
description: Iteratively build a single .concept file from a natural-language description, using Daniel Jackson's concept design methodology as rewritten for concept-lang 0.2.0.
argument-hint: "<description of the concept to build>"
disable-model-invocation: true
allowed-tools: mcp__concept-lang__write_concept, mcp__concept-lang__read_concept, mcp__concept-lang__list_concepts, mcp__concept-lang__validate_concept, mcp__concept-lang__validate_workspace, mcp__concept-lang__get_workspace_graph
---

I want to design a concept for the following functionality:

$ARGUMENTS

Your job is to produce a single `.concept` file that a concept-lang 0.2.0 validator will accept cleanly, following Daniel Jackson's paper-aligned format.

## Step 1: Understand the surrounding workspace

Before proposing a shape, call `list_concepts` to see what concepts already exist. You do NOT need to coordinate state with other concepts — concepts are independent — but you should check for naming collisions and for whether the user's request is already partly modelled somewhere.

If the user's description names a concept that already exists on disk, call `read_concept` for it and ask whether they want to **replace it** or **evolve it**. Do not silently overwrite existing work.

## Step 2: Teach yourself the v2 format (quick reference)

A 0.2.0 concept file has exactly these sections, in this order:

```
concept <Name> [<TypeParam1>, <TypeParam2>, ...]

  purpose
    <one sentence stating the essential service this concept provides>

  state
    <field>: <type-expression>
    <field>: <type-expression>
    ...

  actions
    <action_name> [ <in1>: <T1> ; <in2>: <T2> ] => [ <out1>: <U1> ]
      <hybrid natural-language body, 1-4 lines>
      effects: <optional += / -= statements on state fields>

    <action_name> [ <in1>: <T1> ; <in2>: <T2> ] => [ error: string ]
      <same action, the error case>
      <describe when this case fires>

    ... (at least one success case AND at least one error case per action name)

  operational principle
    after <action_name> [ <in>: <val> ] => [ <out>: <val> ]
    and   <action_name> [ <in>: <val> ] => [ <out>: <val> ]
    then  <action_name> [ <in>: <val> ] => [ <out>: <val> ]
```

Key shape rules the v2 parser enforces (you will see these in validator diagnostics if you get them wrong):

- **Named inputs and outputs.** Every action case has square-bracket input and output lists. The inputs list may be empty (`[]`) for a pure factory. The outputs list may not — every action returns something, even if it is `[ ok: unit ]` for a pure side-effect action.
- **Multiple cases per action.** A real action almost always has a success case AND at least one error case. The paper-aligned format encodes error as a separate case with the same name and the same inputs but a different output shape (`[ error: string ]`). Do NOT smuggle errors into the success case as a conditional return.
- **Operational principle is its own section**, not a comment inside `actions`. Each step is `after|and|then <action_name> [ <ins> ] => [ <outs> ]`. The steps form a small scenario that demonstrates what the concept is FOR.
- **No inline syncs.** Syncs live in separate `.sync` files now. Writing a v1 inline sync section inside the concept file is a C4 validation error. If the concept needs to react to another concept's action, that is a sync, not part of the concept — use `/concept-lang:build-sync` after this skill finishes.
- **Independence rule.** The concept file must stand on its own. Do not reference other concepts in state, effects, or the operational principle. You MAY mention other concepts in the natural-language body of an action ("when a user registers...") but only as prose — never as a type, a field, or a parameter. The validator's C1 rule will flag unknown type names; the independence rule is stricter than what the validator enforces, so follow it deliberately even when the validator is silent.

## Step 3: Work iteratively with the user

Propose, in order:

1. **Name and purpose.** One line each. Stop for user feedback.
2. **State shape.** List the fields and their types. Stop for user feedback.
3. **Action list (names only).** No signatures yet — just the action names. Stop for user feedback.
4. **Action cases, one action at a time.** For each action, write the success case first, then at least one error case. Walk through what the inputs and outputs mean. Stop for user feedback after each action.
5. **Operational principle.** A 2-4 step scenario that exercises the most important action pair. Stop for user feedback.

Between each step, do not dump the whole file — dump only what changed.

## Step 4: Validate iteratively

When the user is satisfied, construct the full `.concept` source and call `validate_concept` with it. The tool returns a JSON response with a `diagnostics` list; for every diagnostic with `severity: "error"`, read the `code` (e.g., `C1`, `C5`, `C7`) and the `message`, fix the source, and call `validate_concept` again. Do not proceed until the error list is empty (warning / info entries may remain if the user chooses to accept them).

Common errors and their fixes:

- **C1 (unknown type)** — the state or an action signature references a type the parser doesn't know. Either it's a typo (e.g., `Sring`), or you wrote a concept name where a type parameter belongs (`User` instead of `[U]`). Fix: use the concept's type parameters (`concept Session [User]` means `User` is a bound type inside Session).
- **C4 (inline sync section forbidden)** — you wrote an old-style inline sync block inside the concept. Delete it; the user should call `/concept-lang:build-sync` separately if the cross-concept behaviour matters.
- **C5 (empty purpose)** — you skipped the purpose line or left it blank. Every concept must have a purpose.
- **C6 (no actions)** — you wrote only state. A concept without actions is a data structure, not a concept. Ask the user what the concept is supposed to do.
- **C7 (action case issues)** — an action case's input or output list is malformed, or the action has cases with inconsistent names. Every case block for the same action must share the same action name.
- **C9 (no operational principle)** — you skipped the `operational principle` section. Every concept needs at least one OP step.

The loop is: write → `validate_concept` → read diagnostics → fix → `validate_concept` → commit.

## Step 5: Write

Once validation is clean, call `write_concept(name=<Name>, source=<full source>)`. The tool re-runs `validate_concept` plus cross-reference rules before writing; if it refuses, the `written` field in the response is `false` and the `diagnostics` list tells you why. Fix and retry.

After writing, call `validate_workspace` once to confirm the wider workspace still loads without errors — a new concept can surface a latent name collision. Then call `get_workspace_graph` to show the user how the new concept relates to the existing ones. The graph's nodes are concepts and its edges are syncs, so the new concept will appear as an unconnected node until a sync (built separately with `/concept-lang:build-sync`) wires it up.

## What NOT to do

- Do not list any app-spec tool in frontmatter. Those are out of scope for v2 concept skills.
- Do not write inline sync sections inside the concept. Direct the user to `/concept-lang:build-sync` for that work.
- Do not reference other concepts as types. The v2 format uses bare type parameters (`[U]`, `[Article]`) that are bound at the concept level, not imports.
- Do not collapse multiple cases into a single case with conditional return values. Every distinct outcome is its own case block.
