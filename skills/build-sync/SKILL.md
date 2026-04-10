---
description: Build a single .sync file that composes existing concepts. Only use existing actions; if the needed action is missing, say so and stop.
argument-hint: "<description of the cross-concept behavior>"
disable-model-invocation: true
allowed-tools: mcp__concept-lang__write_sync, mcp__concept-lang__read_sync, mcp__concept-lang__list_syncs, mcp__concept-lang__validate_sync, mcp__concept-lang__list_concepts, mcp__concept-lang__read_concept, mcp__concept-lang__validate_workspace, mcp__concept-lang__get_workspace_graph
---

I want to compose the following cross-concept behavior:

$ARGUMENTS

Your job is to produce a single `.sync` file that a concept-lang 0.2.0 validator will accept cleanly. A sync is a top-level file that says "when action A in concept X happens, and optionally where conditions Q hold, then action B in concept Y happens." You are writing a single sync that composes existing concepts. You may not modify any concept. If the needed actions don't exist, say so — don't invent them.

## Step 1: Discover the available surface

Before writing anything, you MUST learn the workspace surface. Call `list_concepts` to get every concept in the workspace. For each concept that is likely to appear in the sync (mentioned or implied by the user's description), call `read_concept(name=<Name>)` and read the `ast.actions` list carefully. Note each action's **name**, **input signature** (the `[ ... ]` before `=>`), and **output signature** (the `[ ... ]` after `=>`). These are the only actions you may reference — do not invent a new action name.

If a needed action does not exist in any concept, STOP and tell the user which concept is missing what action. Do not write the sync. The user needs to go run `/concept-lang:build` to add the action first.

Also call `list_syncs` to see what syncs already exist so you don't duplicate an existing wiring.

## Step 2: Teach yourself the v2 sync format (quick reference)

A 0.2.0 sync file has this shape (a SPARQL-like composition DSL):

```
sync <SyncName>

  when {
    <Concept>/<action>: [ <input_patterns> ] => [ <output_patterns> ]
    <Concept>/<action>: [ <input_patterns> ] => [ <output_patterns> ]
  }

  where {
    <Concept>: { ?<subject> <prop>: ?<obj> }
    bind (<expression> as ?<variable>)
    optional { <Concept>: { ?<subject> <prop>: ?<obj> } }
  }

  then {
    <Concept>/<action>: [ <arg_name>: ?<var> ]
    <Concept>/<action>: [ <arg_name>: ?<var> ]
  }
```

The three sections compose in order:

- **`when`** lists the trigger patterns. Each pattern is `Concept/action: [ inputs ] => [ outputs ]`. The pattern matches an action invocation in the runtime; variables prefixed with `?` (e.g., `?userId`, `?email`) are captured from either the input or the output side and are available to `where` and `then`.
- **`where`** is optional. It filters the trigger and can introduce new bindings. Three sub-forms:
  - **State query**: `Concept: { ?subject prop: ?obj }` — reads the concept's state by joining on a subject variable. The subject variable MUST be bound earlier (in `when` or an earlier `where` clause), otherwise S4 fires.
  - **`bind (expr as ?var)`** — introduces a fresh variable derived from an expression (e.g., `bind (fresh_uuid() as ?profileId)`). Useful when a downstream action needs a new identifier.
  - **`optional { ... }`** — wraps a state query whose absence is acceptable; variables it binds may or may not exist in `then`.
- **`then`** lists the downstream actions to invoke. Each clause is a strict action invocation: `Concept/action: [ name1: ?var1 ; name2: ?var2 ]`. Unlike `when`, `then` patterns do NOT match extension fields — they must match the action's real input signature exactly, and every argument must be a variable that was bound by `when` or `where`.

### Pattern-extension semantics (the subtle part)

`when` patterns and `then` patterns are NOT symmetric:

- **`when` patterns are extensible.** A gateway or runtime may observe extra fields on an action that aren't in the concept's declared input signature. For example, `Web/request` may be declared as `[ method: string ; path: string ]` in the concept, but when it fires at runtime the gateway also attaches `?username` and `?email`. A `when` pattern can reference `?username` and `?email` freely because the trigger payload carries them. This is how one concept's action becomes observable to syncs without the concept declaring every possible observer's needs upfront.
- **`then` patterns are strict.** A `then` invocation is a real call into the target concept's action, so it must match the action's declared input list exactly — no extension fields. The argument names on the left of each `:` must be real parameter names from the action's signature, and every `?var` on the right must be bound earlier in the sync (otherwise S3 fires).

A useful way to think about it: `when` is a pattern match against observed events, `then` is a typed function call.

### Validator rules

- **S1**: every concept and action referenced in the sync must exist in the workspace. Misspellings or stale references are an error.
- **S2**: every `then` pattern's inputs must come from actions/variables bound earlier in the sync — you can't reference a variable you haven't defined.
- **S3**: every free variable in `then` must be bound by a `when` output pattern, a `when` input pattern, or a `where bind (...)` clause. Free variables in `then` are a hard error.
- **S4**: every `where` state query that uses a subject variable must bind that subject earlier.
- **S5**: a single-concept sync (every reference is to the same concept) is a warning — it's usually a sign the behavior belongs inside the concept itself, or that the sync is unnecessary.

## Step 3: Work iteratively with the user

Propose, in order:

1. **Sync name.** Use a verb phrase that describes what the sync does (e.g., `RegisterDefaultProfile`, `DeletePostCascade`). Stop for user feedback.
2. **`when` clauses.** One clause per trigger. Show which variables each pattern captures. Stop for user feedback.
3. **`where` clauses (if any).** Only add these if the behavior needs to be filtered ("only when the user is not banned"), if a state lookup is needed ("find the profile whose owner is `?userId`"), or if a new variable needs to be synthesized ("generate a fresh UUID for the profile"). Stop for user feedback.
4. **`then` clauses.** One clause per downstream action. Reference only variables already bound in `when` or `where`. For each clause, verify that every argument name matches the real action signature you read in Step 1 — `then` is strict. Stop for user feedback.

Between steps, show the partial sync source and explain each new clause in one sentence.

## Step 4: Validate iteratively

Call `validate_sync` with the full source. Read the `diagnostics` list, fix any errors, call `validate_sync` again. Do not proceed until no `error`-severity diagnostics remain. The loop is: write → `validate_sync` → read diagnostics → fix → `validate_sync` → commit.

Common errors and their fixes:

- **S1 (unknown concept or action)** — the concept or action name does not exist. Recheck the `read_concept` output for the exact name. Do not invent.
- **S2 (unbound variable in then)** — a variable on the `then` side was never bound. Either it's new (add a `where bind (...)` clause), or it should come from a `when` pattern capture.
- **S3 (free variable in then)** — same family as S2. Every `?var` used in a `then` argument must have appeared earlier in `when` or `where`.
- **S4 (unbound state query subject)** — a `where` clause queries a concept's state using a variable that was never bound. Either bind it earlier or restructure the sync so the state query isn't needed.
- **S5 (single-concept sync)** — all references are to one concept. Either this is the wrong shape (the behavior belongs inside the concept, not in a sync), or you missed a sibling concept's action. Ask the user.

## Step 5: Write

Call `write_sync(name=<SyncName>, source=<full source>)`. The tool re-runs `validate_sync` against the current workspace and refuses to write if any `error`-severity diagnostic fires; the `written` field in the response is `false` and the `diagnostics` list tells you why. Fix and retry.

After writing, call `validate_workspace` once more. If any previously-passing sync now fails (because your new sync introduced a name collision or cycle), the workspace validator will surface it. Fix or undo as appropriate.

Finally, call `get_workspace_graph` to show the user the updated two-layer graph. The new sync appears as a labeled edge between the concepts it composes.

## What NOT to do

- **Do not invent actions.** If the required action does not exist in any concept, stop and tell the user to run `/concept-lang:build` first. Inventing an action silently produces an S1 error and wastes the iteration.
- **Do not modify any concept.** `build-sync` is read-only on concepts. If you find that an existing action has the wrong signature for the behavior, stop and tell the user — they need `/concept-lang:build` to evolve the concept.
- **Do not use extension fields in `then`.** Only `when` patterns may carry gateway-observed fields beyond the concept's declared signature. A `then` pattern is a strict action call; every argument must match the real signature.
- **Do not use the v1 single-line `when ... then` shorthand.** The 0.2.0 parser requires the multi-section `when { } where { } then { }` format shown above.
