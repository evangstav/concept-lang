---
description: Analyze an existing codebase and extract draft .concept and .sync files into a proposed/ directory for the user to review and move into place.
argument-hint: "<source directory to analyze>"
disable-model-invocation: true
allowed-tools: mcp__concept-lang__scaffold_concepts, mcp__concept-lang__validate_concept, mcp__concept-lang__validate_sync, mcp__concept-lang__validate_workspace, mcp__concept-lang__list_concepts, mcp__concept-lang__list_syncs, mcp__concept-lang__read_concept, mcp__concept-lang__read_sync, mcp__concept-lang__get_workspace_graph
---

Analyze the codebase at:

$ARGUMENTS

Your job is to extract **draft** `.concept` and `.sync` files that represent the domain abstractions already living in the code, and write them into a review directory that the user can inspect and promote. You are NOT committing these drafts to the authoritative workspace — the user does that manually after reviewing the report you generate.

## Step 1: Gather source-code context

Call `scaffold_concepts(source_dir=<path>)`. The tool returns a JSON payload with:

- `files_analysed` — how many source files it sampled
- `file_list` — the relative paths of those files
- `concepts_dir` — the workspace path the authoritative `concepts/` directory lives at
- `source_code` — a concatenated payload of the sampled files
- `methodology` — a short methodology reminder block. **Treat it as a sanity check, not as the source of truth.** The tool's internal reminder block predates the 0.2.0 rewrite and may reference the v1 format. The authoritative format rules for this skill are the ones described below — derive the `.concept` and `.sync` shapes from the design principles in this document, not from the tool's embedded methodology string.

If the response contains an `error` field, stop and report it — the tool could not read the source directory.

## Step 2: Identify extraction candidates

Walk the source payload and classify each file into one or more of these buckets.

### (a) Concept candidates

A concept is a **cohesive unit of state and operations** — roughly, "a thing the system has opinions about that has a lifecycle or a set of rules." Look for:

- Domain model classes, schema files, entities, table definitions
- Service modules that own a particular kind of data
- Record types / type definitions that are central to the domain vocabulary
- Reducers and stores that manage a distinct slice of state

Ignore: utility helpers, type-level abstractions, infrastructure glue (DB connection pools, loggers), test doubles.

For each concept candidate, determine:

- A **name** (PascalCase, singular)
- A **purpose** (one sentence)
- A **state shape** (the fields and their types, in v2 format — `set T`, `A -> set B`, `A -> B`)
- An **action list** with at least one success case and one error case per action
- An **operational principle** that walks through a typical use

### (b) Bootstrap concept candidates

A bootstrap concept is the thing that **drives** the system from the outside world — HTTP requests, CLI commands, cron events, message queue deliveries. Look for:

- HTTP route handlers, Express/FastAPI/Flask routers, controller classes
- CLI entry points (`argparse`, `click`, `commander`, `cobra`)
- Event listeners (`on('message', ...)`, event-handler decorators, Kafka consumers)
- Job schedulers (scheduled-task decorators, cron configs)

For each bootstrap candidate, create a concept named after the transport (`Web`, `CLI`, `Event`, `Job`) with:

- Actions that represent the external trigger shape (`request [ method: string ; path: string ; body: json ] => [ response: json ]`)
- An operational principle that walks through "a request arrives, the system processes it, a response leaves"
- State that holds anything the bootstrap needs to know about open connections or pending work (often empty for stateless bootstraps)

Bootstrap concepts are the anchor points for top-level composition files — without them, there is no way for external events to trigger domain actions.

### (c) Composition candidates (`.sync` files)

A composition file captures a **cross-cutting "when X happens, also do Y" pattern**. Look for:

- Event emitters that trigger side-effects (`user.save()` followed by `emailService.send(welcome)`)
- Lifecycle hooks (post-save callbacks, on-create callbacks, after-commit callbacks)
- Cascade deletes, soft-delete propagation, audit log writes
- Middleware chains that run before/after a route handler
- Message-queue fan-out where one event produces N downstream actions

For each composition candidate, produce:

- A `when` clause referencing the concept action that triggers the rule
- An optional `where` clause if the rule is conditional or needs to bind a fresh variable
- One or more `then` clauses referencing the downstream actions

Composition patterns are often spread across multiple files — a save handler in one file plus an event listener in another plus a queue consumer in a third. Draw the connection explicitly in your report.

## Step 3: Write drafts to `proposed/`

Create a `proposed/` directory as a sibling of the workspace's `concepts/` and `syncs/` directories. (Use `concepts_dir` from the tool response to find the workspace root — the parent of `concepts_dir` is the workspace root.) Inside `proposed/`, create:

- `proposed/concepts/<Name>.concept` — one file per concept candidate
- `proposed/syncs/<rule_name>.sync` — one file per composition candidate
- `proposed/REPORT.md` — a human-readable report (see Step 5)

Use Claude's built-in `Write` tool to put these files on disk. **Do NOT use the MCP writer tools for drafts** — they validate against the authoritative workspace and would either refuse to write (cross-reference errors against the still-empty authoritative directories) or mix drafts into authoritative state. The MCP writer tools are not listed in this skill's `allowed-tools` for exactly that reason. Only after the user reviews and moves a file into place should any writer tool touch it.

## Step 4: Self-test drafts

For each concept draft, call `validate_concept(source=<draft source>)` and note the diagnostics. For each composition draft, call `validate_sync(source=<draft source>)`. If a draft fails a rule, try to fix it in-place (e.g., add a missing operational principle step, fix a typo in a type name). If you cannot fix it without more context, write the draft anyway but flag it in the REPORT as "needs manual work" with the specific diagnostic.

## Step 5: Generate `proposed/REPORT.md`

Write a report that lists, in this order:

1. **Summary** — how many concepts, composition files, and bootstrap concepts were drafted, and what fraction of them validated cleanly
2. **Concepts** — one section per draft concept, with:
   - A one-line description ("extracted from src/models/user.py + src/services/user_service.py")
   - The validator status (clean / N diagnostics)
   - A link to the draft file (`proposed/concepts/<Name>.concept`)
   - The source files it was derived from
   - A "what I noticed" paragraph describing tradeoffs you made or things the user should verify
3. **Bootstrap concepts** — same structure as regular concepts, flagged as bootstraps
4. **Composition files** — one section per draft, same structure plus the triggering event and downstream actions
5. **Orphaned patterns** — code that looked like a concept or composition rule but couldn't be extracted cleanly. List the source file and the problem ("the user controller seems to mix authentication and profile management — can't tell which concept owns which state")
6. **Next steps** — a concrete instruction block for the user:
   - Review `proposed/concepts/*.concept` one at a time; if happy, `mv proposed/concepts/<Name>.concept concepts/` and run `validate_workspace`
   - Review `proposed/syncs/*.sync` one at a time; if happy, `mv proposed/syncs/<rule>.sync syncs/` and run `validate_workspace`
   - Any draft marked "needs manual work" should be opened in an editor and fixed before `mv`

## Step 6: Stop

Do NOT write into `concepts/` or `syncs/` directly. Do NOT move any file out of `proposed/`. The user explicitly drives the promotion step — the skill's job is to produce the drafts and the report, nothing more.

## What NOT to do

- Do not invent domain concepts that aren't reflected in the source. If the code has no `Subscription` class, do not draft a `Subscription.concept`.
- Do not produce v1-format drafts. The hybrid action body, the multi-case signatures, the top-level composition files — everything in the drafts must be v2.
- Do not skip the error cases. Every action in a draft concept should have at least one error case, even if the extractor has to guess at the error condition.
- Do not list any deprecated dependency-graph alias or any app-spec tool in frontmatter. Use `get_workspace_graph` if you need a graph view.
- Do not write to `concepts/` or `syncs/` directly — only `proposed/`.
