# concept-lang

A Claude Code plugin for designing software using [Daniel Jackson's concept
design methodology](https://essenceofsoftware.com/), aligned with [Meng &
Jackson, *What You See Is What It Does*, Onward! '25
(arXiv:2508.14511)](https://arxiv.org/abs/2508.14511).

Build, review, scaffold, and explore **concepts** (independent units of
state and behavior) and **syncs** (declarative rules that compose concepts
into whole applications).

## Install

```bash
# Add the marketplace
/plugin marketplace add evangstav/concept-lang

# Install the plugin
/plugin install concept-lang
```

Or for local development:

```bash
claude --plugin-dir /path/to/concept-lang
```

## Skills

| Skill | Command | Description |
|-------|---------|-------------|
| **build** | `/concept-lang:build <description>` | Generate a single `.concept` file from a natural-language description, iteratively validating until clean. |
| **build-sync** | `/concept-lang:build-sync <description>` | Generate a single `.sync` file that composes existing concepts. Will not invent actions that do not exist. |
| **review** | `/concept-lang:review [names]` | Validate the workspace and group findings by rule category (independence, completeness, sync) and the three legibility properties. |
| **scaffold** | `/concept-lang:scaffold <source-dir>` | Extract draft concepts and syncs from an existing codebase into a `proposed/` directory for review. |
| **explore** | `/concept-lang:explore` | Generate an interactive HTML explorer with a two-layer graph (concepts as nodes, syncs as labeled edges) and per-sync flow diagrams. |

## What's a concept?

A concept is a self-contained unit of software functionality with a purpose,
typed state, named actions, and an operational principle. Concepts are
**independent**: a concept's state, effects, and operational principle may
only reference the concept itself.

Example — a minimal counter:

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

## What's a sync?

A sync is a top-level `.sync` file that wires concepts together. It has a
`when` clause (one or more action patterns that trigger the sync), an
optional `where` clause (state queries and variable bindings), and a
`then` clause (action invocations). Syncs are the *only* place where
concepts meet.

Example — log every counter increment:

```sync
sync LogInc

  when
    Counter/inc: [ ] => [ total: ?total ]
  then
    Logger/write: [ msg: ?total ] => [ ]
```

Adding a second log sink is a new sync file. Adding a reset action to
`Counter` is a new action case in `Counter.concept`. Neither change
touches existing files.

## Directory layout

A concept-lang workspace is a directory containing `concepts/`, `syncs/`,
and optionally `apps/`:

```
my-workspace/
  concepts/
    Counter.concept
    Logger.concept
  syncs/
    log_inc.sync
  apps/                 (optional)
    my_app.app
```

- One concept per `.concept` file. Filenames use PascalCase and match the
  concept's declared name.
- One sync per `.sync` file. Filenames use snake_case; the sync's declared
  name inside the file uses PascalCase.
- App specs (`.app` files) live in `apps/` and are still on the v1 format
  pending a dedicated migration. The v2 MCP tooling continues to load them
  through a bridge.

The plugin ships with two example workspaces under `architecture-ide/`:

- `architecture-ide/.concepts/` — the self-hosting architecture-ide
  workspace (four concepts, three syncs, one app spec) laid out as
  `.concepts/concepts/`, `.concepts/syncs/`, and `.concepts/apps/`.
  Used as the canonical dogfood example and demonstrates the
  recommended `.concepts/` hidden-directory convention introduced
  in 0.3.1.
- `architecture-ide/tests/fixtures/realworld/` — six concepts and six
  syncs recreating the paper's canonical RealWorld case study.

## Why this format?

The paper argues that software becomes **legible** — readable, modifiable,
and trustworthy under LLM-driven development — when you factor it into
small independent concepts composed by explicit synchronization rules.
This delivers three properties:

- **Incrementality** — new features are delivered as new files, not edits.
- **Integrity** — existing behavior cannot silently regress.
- **Transparency** — every runtime action traces back through a causal flow.

Read the full primer at [`docs/methodology.md`](docs/methodology.md) or
jump straight to the paper at
[arXiv:2508.14511](https://arxiv.org/abs/2508.14511).

## Configuration

When installing, you'll be prompted for:

- **concepts_dir** — path to your workspace root (the directory containing
  `concepts/` and `syncs/`, e.g. `./my-workspace` or
  `~/projects/my-project`). The plugin also honors `WORKSPACE_DIR` as an
  alias for new installs.

## MCP Server

The plugin runs a Model Context Protocol server (`concept-lang`) powered
by a Python package in `architecture-ide/` and launched via `uv`. It
exposes tools for reading, writing, validating, and visualizing both
concepts and syncs. See `skills/*/SKILL.md` for the per-skill tool lists.

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md) for release notes. The current release
is **0.2.0 — paper alignment**, a breaking rewrite that migrates the DSL
to match the Meng & Jackson 2025 paper.

## License

MIT
