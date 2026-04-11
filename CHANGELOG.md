# Changelog

All notable changes to `concept-lang` are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_No changes yet._

## [0.3.0] — 2026-04-10 — v1 deletion

`0.3.0` deletes the v1 code that was kept alongside the new v2 code as
a safety net since `0.2.0`. There are no new features and no new user-
facing API surface — this is a cleanup release that makes the v2 code
path the only code path.

### Removed

- `concept_lang.validator` — the v1 hand-written validator. The v2
  validator lives at `concept_lang.validate` and is the only supported
  surface for validation.
- `concept_lang.codegen/` — the v1 code-generation subpackage
  (`python`, `typescript`, `go` backends) and the `codegen_tools` MCP
  wrapper. These were dead code since `0.2.0` because the MCP server
  stopped registering `codegen_tools` in P4. A paper-aligned code
  generator is a possible future workstream but is not in any
  committed roadmap.
- `concept_lang.explorer._to_v1_concept` — the temporary v2 → v1
  adapter function. Its callers (`concept_lang.tools.diagram_tools`
  and `concept_lang.explorer._generate_html`) now consume the v2 AST
  directly.
- `get_dependency_graph` MCP tool — the back-compat alias introduced
  in `0.2.0` when the whole-workspace Mermaid graph moved from
  `diagram_tools` to `workspace_tools`. Use `get_workspace_graph`
  directly.
- `tests/test_validator.py` — the v1 test file. Its coverage has been
  replaced by `tests/test_validate.py` and `tests/test_parse.py`
  across P2 and P3.
- `tests/test_explorer.py::TestV1Adapter` — the three tests that
  pinned the `_to_v1_concept` adapter contract.

### Changed

- `concept_lang.diagrams.state_machine` and
  `concept_lang.diagrams.entity_diagram` are rewritten to consume
  `concept_lang.ast.ConceptAST` directly. The semantic contract is
  unchanged: multi-case actions still use the first case's effects as
  the canonical transition source. A new `tests/test_diagrams.py`
  pins the behavior against `Counter` and `Auth` fixture concepts.
- Plugin version bumped from `0.2.0` to `0.3.0` in
  `.claude-plugin/plugin.json` and `architecture-ide/pyproject.toml`.

### Legacy v1 subsystem (retained, fenced)

The v1 `.app` format is still supported in `0.3.0`. The four modules
that back it (`concept_lang.parser`, `concept_lang.models`,
`concept_lang.app_parser`, `concept_lang.app_validator`) are retained
and each carries a top-of-file docstring beginning **"LEGACY FENCE
(0.3.0):"**. The single consumer of this fenced subsystem is
`concept_lang.tools.app_tools`, whose docstring begins **"LEGACY
BRIDGE (0.3.0):"**, and which exposes the app-spec MCP tools
(`list_apps`, `read_app`, `write_app`, `validate_app_spec`,
`get_app_dependency_graph`). A follow-up plan will migrate the `.app`
format to a v2 AST and delete the entire legacy subsystem. Until
then, do not import from these modules from anywhere other than the
app-spec bridge.

### References

- Paper: [Meng & Jackson, *What You See Is What It Does: A Structural
  Pattern for Legible Software*, Onward! '25
  (arXiv:2508.14511)](https://arxiv.org/abs/2508.14511)
- Primer: [`docs/methodology.md`](docs/methodology.md)
- Previous release: [`[0.2.0]`](#020--2026-04-10--paper-alignment)

## [0.2.0] — 2026-04-10 — Paper alignment

This is a breaking change that aligns `concept-lang` with Meng & Jackson,
*What You See Is What It Does: A Structural Pattern for Legible Software*,
Onward! '25 ([arXiv:2508.14511](https://arxiv.org/abs/2508.14511)).

### Added

- New concept specification format with named input/output action
  signatures, multi-case actions, natural-language bodies, optional
  `effects:` subsections, and required `operational principle` sections.
- New top-level `.sync` files with `when` / `where` / `then` clauses,
  SPARQL-ish state queries, optional clauses, variable binding, and
  aggregation via `?_eachthen`.
- New MCP tools: `read_sync`, `write_sync`, `list_syncs`, `validate_sync`,
  `validate_workspace`.
- New validator rules: independence rules `C1`–`C4`, completeness rules
  `C5`–`C9`, sync rules `S1`–`S5`. `C8` (warning-only, unreferenced state)
  is deferred to a follow-up release.
- New `build-sync` skill for single-sync construction. The plugin now
  ships five skills: `build`, `build-sync`, `review`, `scaffold`,
  `explore`.
- New paper-aligned fixture workspaces at
  `architecture-ide/tests/fixtures/architecture_ide/` and
  `architecture-ide/tests/fixtures/realworld/`, the latter recreating
  six of the paper's canonical case-study concepts and syncs.
- New documentation: `docs/methodology.md` (paper-to-DSL primer) and
  `CHANGELOG.md` (this file).
- New runtime dogfood test at `architecture-ide/tests/test_runtime_dogfood.py`
  that loads the plugin's own example workspace and asserts zero
  error-level diagnostics.
- Source position threading on every AST node so validator diagnostics
  report real line and column numbers.

### Changed

- `get_dependency_graph` MCP tool renamed to `get_workspace_graph`. The
  old name is preserved as a back-compat alias and will be removed in a
  future release.
- File organization: concepts and syncs now live in sibling directories
  (`concepts/` and `syncs/`) under a workspace root. The MCP server's
  configuration now points at the workspace root, not at a bare
  `concepts/` directory; the legacy `CONCEPTS_DIR=./concepts` layout is
  still accepted via a parent-root heuristic.
- All five skill markdown files rewritten to teach the new format and
  reference the new tool names. Skill-lint test pins the contract.
- `README.md` rewritten with v2 examples, the five-skill table, and the
  new directory layout.
- Plugin version bumped from `0.1.x` to `0.2.0` in `.claude-plugin/plugin.json`
  and `architecture-ide/pyproject.toml`.

### Removed

- Nothing is physically removed in `0.2.0`. The v1 hand-written regex
  parser, validator, diff engine, and explorer are no longer reachable
  from the MCP tool layer or from any skill, but remain on disk to back
  the v1 app-spec bridge. Full deletion is scheduled for a follow-up
  release (P7).

### Migration

`0.2.0` is a hard break. There is no automated migration tool. To port
an existing workspace:

1. Create `<workspace>/concepts/` and `<workspace>/syncs/` directories.
2. Rewrite each `.concept` file in the new format — see
   [`docs/methodology.md`](docs/methodology.md) for the structural
   pattern and [`skills/build/SKILL.md`](skills/build/SKILL.md) for a
   worked example.
3. For every inline sync block that used to live inside a concept,
   extract it into a standalone `.sync` file in `<workspace>/syncs/`.
   Rewrite the body in the new `when` / `where` / `then` form. See
   [`skills/build-sync/SKILL.md`](skills/build-sync/SKILL.md) for the
   sync DSL.
4. If you have `.app` files, move them into `<workspace>/apps/`. The
   v1 `.app` format is still accepted in `0.2.0`; a v2 app format is
   planned for a follow-up release.
5. Run `/concept-lang:review` against the migrated workspace. The rule
   categories map cleanly onto the paper's independence, completeness,
   and sync properties.

Worked example — a counter concept, before and after. The v1 version
below is shown in a `legacy` fenced block so docs-lint tooling knows
to exempt it from forbidden-phrase checks.

Before (v1):

```legacy
concept Counter
  purpose count things

  state
    total: int

  actions
    inc ()
      pre: true
      post: total += 1
```

After (v2):

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

The v2 version names the input and output signatures explicitly, drops
`pre:` / `post:` in favor of a natural-language body plus an optional
`effects:` subsection, and adds a required `operational principle`
section that shows what the concept does from an observer's point of
view.

### References

- Paper: [Meng & Jackson, *What You See Is What It Does: A Structural
  Pattern for Legible Software*, Onward! '25
  (arXiv:2508.14511)](https://arxiv.org/abs/2508.14511)
- Primer: [`docs/methodology.md`](docs/methodology.md)
- Fixture workspaces:
  `architecture-ide/tests/fixtures/architecture_ide/`,
  `architecture-ide/tests/fixtures/realworld/`

[Unreleased]: https://github.com/evangstav/concept-lang/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/evangstav/concept-lang/releases/tag/v0.3.0
[0.2.0]: https://github.com/evangstav/concept-lang/releases/tag/v0.2.0
