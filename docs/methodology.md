# concept-lang methodology

A short primer on what `concept-lang` teaches and how its DSL maps to the
structural pattern described in Meng & Jackson's 2025 paper.

## What this plugin is

`concept-lang` is a Claude Code plugin for designing software using Daniel
Jackson's concept-design methodology. It gives you a small DSL for writing
**concepts** (independent units of state and behavior) and **syncs**
(declarative rules that compose concepts into whole applications), plus a
validator, an explorer, and a set of skills that help you build, review,
scaffold, and explore concept-based systems end to end.

This document is a primer. The deeper treatment lives in the paper and in
the individual skills under `skills/`.

## The paper

> Eagon Meng & Daniel Jackson, *What You See Is What It Does: A Structural
> Pattern for Legible Software*, Onward! '25.
> [arXiv:2508.14511](https://arxiv.org/abs/2508.14511)

The paper's central claim is that software becomes **legible** — readable,
modifiable, and trustworthy under LLM-driven development — when you factor
it into small independent concepts composed by explicit synchronization
rules. `concept-lang` is a reference implementation of that idea at the
specification level: you write concepts and syncs as text files, and the
plugin's tooling tells you whether they form a legible design.

## Concepts: independence

A **concept** is a self-contained unit of software functionality. It has:

- a **purpose** stated in one sentence,
- a **state** declared as typed sets and relations,
- a set of **actions**, each with a named input/output signature, a
  natural-language body, and an optional `effects:` subsection that lists
  formal state deltas,
- an **operational principle** — a short archetypal scenario expressed in
  the concept's own action syntax, showing how the state evolves.

The load-bearing rule is **independence**: a concept's state, effects, and
operational principle may only reference the concept itself. No concept
names another concept. No action body manipulates another concept's state.
The validator enforces this through rules C1 through C4.

This discipline is what makes concepts composable. A `Counter` concept
knows nothing about a `Logger` concept; both can be written, tested, and
reasoned about in isolation. Composition happens one level up, in syncs.

## Syncs: composition

A **sync** is a top-level file in `syncs/` that declaratively wires
concepts together. It has three clauses:

- `when` — one or more action patterns that trigger the sync,
- `where` — optional state queries and variable bindings,
- `then` — one or more action invocations that fire when the pattern
  matches.

Syncs are the *only* place where concepts meet. The paper compares them to
SPARQL queries: each `when` pattern matches against the live action graph,
the `where` clause enriches the match with state queries, and the `then`
clause invokes downstream actions with bound variables. Because every
cross-concept reference lives in a sync file, adding a new feature
usually means *adding a new sync file* rather than editing an existing
concept.

## Three legibility properties

The paper justifies the structural pattern with three properties:

- **Incrementality** — new features are delivered as new files, not edits
  to existing ones. A new sync adds behavior without touching any concept.
- **Integrity** — existing behavior cannot silently regress when a new
  sync is added. Each concept's operational principle still holds; the
  new sync only *adds* triggers, never removes them.
- **Transparency** — at runtime, every observable action traces back
  through a causal flow. The `when` → `then` chain is the flow, and it
  is inspectable end to end.

The `review` skill uses these three properties as heuristic questions
while walking a workspace.

## A complete example: Counter + Logger

This is the smallest working concept-lang workspace. It lives at
`architecture-ide/tests/fixtures/mcp/clean/` and is exercised by the
MCP tool integration tests, so the files below are guaranteed to stay
correct.

`concepts/Counter.concept`:

```concept
concept Counter

  purpose
    count things

  state
    total: int

  actions
    inc [ ] => [ total: int ]

  operational principle
    after inc [ ] => [ total: 1 ]
```

`concepts/Logger.concept`:

```concept
concept Logger

  purpose
    log events to an append-only list

  state
    entries: set string

  actions
    write [ msg: string ] => [ ]

  operational principle
    after write [ msg: "hello" ] => [ ]
```

`syncs/log.sync`:

```sync
sync LogInc

  when
    Counter/inc: [ ] => [ total: ?total ]
  then
    Logger/write: [ msg: ?total ] => [ ]
```

Two concepts, neither of which knows about the other. One sync that
composes them: whenever `Counter/inc` fires, also invoke `Logger/write`
with the new total. Adding a second log sink would be a new sync file;
adding a reset action to `Counter` would be a new action case in
`Counter.concept`. Neither change touches existing files.

## Where to go next

| Skill | Command | What it does |
|---|---|---|
| `build` | `/concept-lang:build <description>` | Generate a single `.concept` file from a natural-language description. |
| `build-sync` | `/concept-lang:build-sync <description>` | Generate a single `.sync` file that composes existing concepts. |
| `review` | `/concept-lang:review [names]` | Validate the workspace and group findings by rule category and legibility property. |
| `scaffold` | `/concept-lang:scaffold <source-dir>` | Extract draft concepts and syncs from an existing codebase into `proposed/`. |
| `explore` | `/concept-lang:explore` | Render the workspace as an interactive HTML explorer with per-sync flow diagrams. |

## Further reading

- The paper: [arXiv:2508.14511](https://arxiv.org/abs/2508.14511)
- The RealWorld fixtures at `architecture-ide/tests/fixtures/realworld/`
  recreate six of the paper's canonical examples (User, Password,
  Profile, Article, Web, JWT) and six syncs that wire them together.
- The individual `skills/*/SKILL.md` files under `skills/` teach the
  specific invocation patterns and rule categories in depth.
- `CHANGELOG.md` at the repo root documents the 0.2.0 paper-alignment
  release.
