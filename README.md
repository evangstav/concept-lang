# concept-lang

A Claude Code plugin for designing software using [Daniel Jackson's concept design methodology](https://essenceofsoftware.com/).

Build, review, scaffold, and explore `.concept` specs — a lightweight DSL for expressing software concepts with state, actions, and operational composition.

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
| **build** | `/concept-lang:build <description>` | Iteratively design a `.concept` spec from a natural language description |
| **review** | `/concept-lang:review [names]` | Review concepts for coherence, independence, completeness, and quality |
| **scaffold** | `/concept-lang:scaffold <source-dir>` | Extract draft `.concept` specs from an existing codebase |
| **explore** | `/concept-lang:explore` | Generate an interactive HTML explorer with dependency graphs and diagrams |

## What's a concept?

A concept is a self-contained unit of software functionality with:

- **Purpose** — one sentence stating the essential service
- **State** — typed declarations (sets and relations)
- **Actions** — operations with pre/post conditions
- **Sync** — operational composition with other concepts

Example:

```
concept Reservation [User, Resource]
  purpose allow users to reserve resources for future use

  state
    reservations: User -> set Resource
    available: set Resource

  actions
    reserve (u: User, r: Resource)
      pre: r in available
      post: reservations[u] += r, available -= r

    cancel (u: User, r: Resource)
      pre: r in reservations[u]
      post: reservations[u] -= r, available += r
```

## Configuration

When installing, you'll be prompted for:

- **concepts_dir** — Path to your `.concept` files directory (e.g., `./concepts`)

## MCP Server

The plugin runs a Model Context Protocol server (`concept-lang`) that provides tools for reading, writing, validating, and visualizing concept specs. It's powered by a Python package in `architecture-ide/` and launched via `uv`.

## License

MIT
