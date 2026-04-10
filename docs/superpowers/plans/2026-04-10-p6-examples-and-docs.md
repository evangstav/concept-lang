# concept-lang 0.2.0 — P6: Examples + Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the user-facing documentation and the runtime example workspace for the 0.2.0 paper-alignment release. At the end of this plan, the plugin's own `architecture-ide/concepts/` directory is migrated from v1 format to v2 (four v2 `.concept` files plus a sibling `architecture-ide/syncs/` directory with three v2 sync files), the v1 app-spec file is relocated to `architecture-ide/apps/` so it is distinct from the concept files but still loadable by the v1 `register_app_tools` bridge, a new `docs/methodology.md` primer ties the DSL to Meng & Jackson's paper with the canonical RealWorld-style Counter + Logger example, `README.md` is rewritten to teach v2 (new concept + sync examples, updated skill table listing all five skills, new directory layout, links to the methodology doc and the paper), a new `CHANGELOG.md` at the repo root follows the Keep a Changelog format with a 0.2.0 entry linking to the paper and methodology doc, a new dedicated dogfood test (`tests/test_runtime_dogfood.py`) loads the runtime `architecture-ide/` workspace via `load_workspace` and asserts zero errors so the plugin validates its own example workspace, and a docs-lint sweep catches any lingering v1 references, broken links, or stale tool names across the documentation surface. P6 closes the 0.2.0 documentation gap; P7 then deletes the v1 code.

**Architecture:** P6 is a pure documentation + examples phase — no Python module is rewritten, no grammar is changed, no validator rule is added, no MCP tool is created. The runtime example migration is done by *copying* the v2 fixtures that already exist at `architecture-ide/tests/fixtures/architecture_ide/` (created in P1 Task 13) into `architecture-ide/concepts/` and `architecture-ide/syncs/`, then deleting the v1 `.concept` files from `architecture-ide/concepts/`. The v1 app-spec file moves from `architecture-ide/concepts/architecture_ide.app` to a new sibling `architecture-ide/apps/architecture_ide.app` so it is not co-located with v2 concept files. The documentation work is three new or rewritten markdown files: `docs/methodology.md` (new, at the repo root under `docs/`), `README.md` (rewritten at the repo root), `CHANGELOG.md` (new, at the repo root). A small docs-lint test (`tests/test_docs.py`) walks those files and enforces a curated list of required markers (paper citation, methodology link, v2 syntax in code blocks) and forbidden phrases (v1 `sync` section, v1 `pre:` / `post:`, deprecated `get_dependency_graph` in skill column). A runtime-dogfood test (`tests/test_runtime_dogfood.py`) loads the migrated `architecture-ide/` workspace via `concept_lang.loader.load_workspace` and asserts no error-level diagnostics fire. Both new tests run in the normal `uv run pytest` pass. The v1 code is still untouched — P7 deletes it.

**Tech Stack:** Python 3.10+, Lark (already in deps), Pydantic 2, pytest, uv, `pyyaml` (already a dev dep from P5 for skill-lint). No new runtime dependencies. No new dev dependencies.

**Scope note:** This plan covers **P6 only**.

- In scope: copy v2 fixtures into `architecture-ide/concepts/` + new `architecture-ide/syncs/` (with deletion of the v1 `.concept` files), relocate `architecture_ide.app` from `architecture-ide/concepts/` to `architecture-ide/apps/`, write `docs/methodology.md` (800–1200 words, Counter + Logger walkthrough, paper citation), rewrite `README.md` (v2 examples, five-skill table, new layout, methodology link), create `CHANGELOG.md` (Keep a Changelog 1.1.0 format, 0.2.0 + Unreleased sections), add `tests/test_runtime_dogfood.py` (runtime workspace loads clean), add `tests/test_docs.py` (docs-lint contract), and the P6 gate + tag `p6-examples-and-docs-complete`.
- Out of scope: v1 code deletion — P7 removes `parser.py`, `models.py`, `validator.py`, `app_parser.py`, `app_validator.py`, the v1 `codegen/` tree, the v1 `diagrams/` tree that still consumes `models.py`, and the `get_dependency_graph` back-compat alias. App-spec format v2 — the `.app` file stays on v1, the v1 `app_parser` / `app_validator` pair still loads it through `register_app_tools`, and the migration to a v2 app format is deferred to a post-P7 dedicated plan. New MCP tools, new skills, new validator rules, new grammar, new AST types — stable surface. Publishing to the marketplace, screenshots, videos, demo GIFs — release distribution is manual and user-driven. Spec amendment — the spec at `docs/superpowers/specs/2026-04-10-paper-alignment-design.md` is frozen; if P6 execution discovers a gap it is flagged in "What's next", not patched inline. P5 skill rewrites, `scaffold_tools._METHODOLOGY` rewrite, `prompts.py` rewrite, skill-lint test — already done in P5 and not re-touched in P6. P3 line-tightening for the remaining negative fixtures (T20) — still deferred. `OPStep.inputs/outputs` tuple-shape cleanup — still deferred per the P3, P4, P5 "what's next" sections.

**Spec reference:** [`docs/superpowers/specs/2026-04-10-paper-alignment-design.md`](../specs/2026-04-10-paper-alignment-design.md) §5.4 (Documentation updates), §6.4 P6 row ("`architecture-ide/concepts/` rewritten in-place, `README.md` and `docs/methodology.md`"), §6.5 (plugin versioning — `CHANGELOG.md` 0.2.0 entry).

**Starting state:** Branch `feat/p1-parser`, HEAD at tag `p5-skills-rewrite-complete` (`4c3a23c`), also on `main` as `28aebda` with tag `v0.2.0`. `concept_lang.ast`, `concept_lang.parse`, `concept_lang.validate`, `concept_lang.loader`, `concept_lang.diff`, `concept_lang.explorer`, the full MCP tool layer, and all five rewritten skills exist. `uv run pytest` reports **297 passing** (P5 baseline). `plugin.json` and `pyproject.toml` are both at `0.2.0`. The runtime directory `architecture-ide/concepts/` still contains five v1 files:

```
architecture-ide/concepts/
  architecture_ide.app              # v1 app-spec file
  concept.concept                   # v1 format, lowercase filename
  design_session.concept            # v1 format, lowercase filename
  diagram.concept                   # v1 format, lowercase filename
  workspace.concept                 # v1 format, lowercase filename
```

The v2 equivalents already exist as test fixtures at `architecture-ide/tests/fixtures/architecture_ide/`:

```
architecture-ide/tests/fixtures/architecture_ide/
  concepts/
    Concept.concept                 # v2, PascalCase filename
    DesignSession.concept           # v2, PascalCase filename
    Diagram.concept                 # v2, PascalCase filename
    Workspace.concept               # v2, PascalCase filename
  syncs/
    session_introduces.sync         # v2
    specify_draws_diagram.sync      # v2
    workspace_tracks_concept.sync   # v2
```

There is currently no `architecture-ide/syncs/` directory, no `architecture-ide/apps/` directory, no `docs/methodology.md`, no `CHANGELOG.md` at the repo root. `README.md` at the repo root still teaches v1 format (has a `pre:` / `post:` example and lists only four skills).

---

## File structure (what this plan creates, modifies, moves, or deletes)

```
<repo_root>/                                         # one level above architecture-ide/
  README.md                                          # REWRITE: v2 examples, five-skill table, new layout
  CHANGELOG.md                                       # CREATE: Keep a Changelog 0.2.0 entry
  docs/
    methodology.md                                   # CREATE: DSL-to-paper primer with Counter+Logger walk
    superpowers/
      plans/
        2026-04-10-p6-examples-and-docs.md           # CREATE: this file
architecture-ide/
  concepts/
    Concept.concept                                  # CREATE: copy from fixtures/architecture_ide/concepts/
    DesignSession.concept                            # CREATE: copy from fixtures/architecture_ide/concepts/
    Diagram.concept                                  # CREATE: copy from fixtures/architecture_ide/concepts/
    Workspace.concept                                # CREATE: copy from fixtures/architecture_ide/concepts/
    concept.concept                                  # DELETE: v1 file
    design_session.concept                           # DELETE: v1 file
    diagram.concept                                  # DELETE: v1 file
    workspace.concept                                # DELETE: v1 file
    architecture_ide.app                             # MOVE: to architecture-ide/apps/architecture_ide.app
  syncs/                                             # CREATE: new sibling directory
    session_introduces.sync                          # CREATE: copy from fixtures/architecture_ide/syncs/
    specify_draws_diagram.sync                       # CREATE: copy from fixtures/architecture_ide/syncs/
    workspace_tracks_concept.sync                    # CREATE: copy from fixtures/architecture_ide/syncs/
  apps/                                              # CREATE: new sibling directory
    architecture_ide.app                             # MOVE-DESTINATION: from concepts/
  tests/
    test_runtime_dogfood.py                          # CREATE: loads architecture-ide/ via load_workspace
    test_docs.py                                     # CREATE: docs-lint contract tests
    fixtures/
      architecture_ide/                              # UNCHANGED: test fixtures stay decoupled
        concepts/
          Concept.concept
          DesignSession.concept
          Diagram.concept
          Workspace.concept
        syncs/
          session_introduces.sync
          specify_draws_diagram.sync
          workspace_tracks_concept.sync
    # v1 tests STILL UNTOUCHED until P7
```

**All commands below assume the working directory is `architecture-ide/`** (the package root with `pyproject.toml`) *except* for edits to `README.md`, `CHANGELOG.md`, `docs/methodology.md`, and any commands that touch `../concepts/` or `../syncs/` (no wait — `architecture-ide/concepts/` **is** under the Python package root). To be explicit:

- `architecture-ide/concepts/`, `architecture-ide/syncs/`, `architecture-ide/apps/`, `architecture-ide/tests/` are inside the package root and every command operates on them with paths like `concepts/…`, `syncs/…`, `apps/…`, `tests/…`.
- `README.md`, `CHANGELOG.md`, `docs/methodology.md` live at the **repo root**, one level above `architecture-ide/`. Commands that touch them use absolute paths or `../README.md` / `../CHANGELOG.md` / `../docs/methodology.md` depending on whether the shell sits in the repo root or in `architecture-ide/`.

A helper alias used in a few commands below:

```bash
# From architecture-ide/, the repo root is ..
REPO_ROOT=$(git rev-parse --show-toplevel)
```

**Heredoc reminder (P6 execution gotcha).** The `Edit` and `Write` tools have been sandbox-blocked on some worktree paths in prior phases (notably when the executor ran inside a sub-skill session). The reliable fallback is `cat > path <<'EOF' … EOF` for new files and `sed -i` (or `cat >> path <<'EOF' … EOF` for appending) for edits. When a task below says "create this file" or "append this section" and the `Write` / `Edit` tool is refused, fall back to the heredoc pattern. Single-quoted delimiters (`<<'EOF'`) pass markdown, backticks, and `$` through literally — always use single quotes for documentation heredocs.

---

**Design decisions (made and justified up front; later tasks reference them by letter):**

- **(A) Runtime fixture source is a copy, not a move.** The v2 fixtures at `architecture-ide/tests/fixtures/architecture_ide/` stay exactly where they are. P6 copies them into `architecture-ide/concepts/` and `architecture-ide/syncs/` as the new runtime example. The alternatives were (i) *move* the fixtures to `architecture-ide/concepts/` and update every test that references the fixture path (rejected: tests and runtime state should be decoupled — a future plan that adds more fixtures should not have to worry about the runtime example) and (ii) rewrite the runtime files in place from scratch, keeping them textually different from the fixtures (rejected: duplication with no benefit — the fixtures are already paper-aligned, already validate clean, and the runtime example and the test fixture should teach the same thing). The copy semantics mean the two locations can drift in the future if needed, but for the 0.2.0 release they are byte-for-byte identical. Rationale: "exactly one canonical version of the self-hosting architecture-ide model" with the test fixtures as the immutable source of truth and the runtime directory as the user-visible dogfood copy.

- **(B) App-spec file moves to `architecture-ide/apps/`.** The v1 app-spec file `architecture_ide.app` currently sits inside `architecture-ide/concepts/`, co-located with the v1 `.concept` files. After P6, the `concepts/` directory contains only v2 `.concept` files (one per file, PascalCase names), and the `.app` file moves to a new sibling directory `architecture-ide/apps/architecture_ide.app`. The alternatives were (i) delete the `.app` file (rejected: the v1 `register_app_tools` bridge from P4 still operates on `.app` files and `scaffold`, `explore`, and `review` skills all have meaningful behavior against an app-spec file — removing it would lose dogfood coverage for `app_tools`), (ii) keep it unchanged in place (rejected: the new `concepts/` directory should contain only `.concept` files so the `load_workspace` directory walk is clean; mixing `.app` files into `concepts/` is sloppy and would confuse a first-time reader), (iii) move it to `architecture-ide/apps/architecture_ide.app` (chosen: matches the spec §3.3 "file organization" section which explicitly shows `apps/` as a sibling of `concepts/` and `syncs/`, and matches the v1 `app_tools.py` API which already accepts a `workspace_root` and looks for `.app` files under it). The v1 bridge still works because `app_tools.py` from P4 does not hard-code the `concepts/` subdirectory — it uses `_resolve_workspace_root` to find the root and then globs for `*.app` files under it.

- **(C) `docs/methodology.md` targets 800–1200 words.** The rationale is that a first-time reader needs enough context to understand concepts vs. syncs, the paper's three legibility properties, and how the DSL maps to the paper's syntax, but should not be reading the paper itself — the paper is 20+ pages and is linked at the top of the doc for anyone who wants the full treatment. The doc has eight sections: (1) what this plugin is, ~80 words, (2) paper citation and link, ~40 words, (3) concepts: independence, ~150 words, (4) syncs: composition, ~150 words, (5) the three legibility properties (incrementality, integrity, transparency), ~200 words, (6) a complete Counter + Logger walkthrough with both files inlined as fenced code blocks, ~250 words of prose plus ~30 lines of source, (7) where to go next: skills table with one-line descriptions and slash-command references, ~100 words, (8) further reading: link to the paper, the RealWorld fixtures, the `skills/` directory. Total prose is roughly 970 words plus ~30 lines of embedded source. The alternative (~2000+ words covering every rule and every sync construct) was rejected because spec §5.4 explicitly frames the doc as an "explainer" and "primer", not a reference — and the five rewritten `SKILL.md` files in P5 already carry the teaching load.

- **(D) The methodology example is Counter + Logger from `tests/fixtures/mcp/clean/`.** This example was added in P4 for the MCP tool integration tests (`tests/test_mcp_tools.py`). It is the smallest working workspace that still demonstrates all three paper primitives: a concept with state and an action (Counter), a concept with state and an action (Logger, explicitly a "side-effect" concept in the paper's terminology), and a sync that composes them (`log.sync` — "when Counter/inc fires, also Logger/write"). The alternatives were (i) the RealWorld fixture at `tests/fixtures/realworld/` (rejected: too large — six concepts and six syncs, overwhelming for a first-read), (ii) the architecture-ide fixture (rejected: self-referential — the user is about to read the architecture-ide concepts as the runtime example, so using the same example in the methodology doc is redundant), (iii) a hand-rolled brand-new example just for the methodology doc (rejected: an extra thing to maintain and drift from reality). Counter + Logger is tiny, it is referenced by running tests so it cannot silently drift, and the user can literally open `architecture-ide/tests/fixtures/mcp/clean/` and see the three files to continue exploring. The methodology doc quotes the source verbatim via fenced code blocks so the reader does not need to leave the document to understand the walkthrough.

- **(E) `CHANGELOG.md` follows the Keep a Changelog 1.1.0 format.** The alternatives were (i) Keep a Changelog (chosen: https://keepachangelog.com/en/1.1.0/ — widely adopted, clear section ordering, has a canonical "Unreleased" placeholder for post-0.2.0 work), (ii) Conventional Changelog (rejected: ties the format to commit message conventions which concept-lang does not strictly enforce), (iii) freeform prose (rejected: harder for tooling and humans to parse, loses the "added / changed / removed / fixed / security" discipline). The file has a top-level header, a link to keepachangelog.com, a link to semver.org, an "[Unreleased]" section (empty but present so post-0.2.0 changes have a home), and a "[0.2.0] — 2026-04-10" section with five subheadings: **Added** (new DSL sections, new MCP tools, new skill, new validator rules, paper-aligned fixtures, methodology doc, changelog), **Changed** (renamed tool, reorganized file layout, bumped plugin version), **Removed** (v1 `sync` section inside concepts, v1 `pre:` / `post:` keywords in action bodies, v1 hand-written regex parser — actually partially — v1 code is still in the tree until P7 so the "Removed" section notes "v1 surface is no longer reachable from the MCP tool layer; full deletion in P7"), **Migration** (a short paragraph telling users to rewrite their `.concept` files and move them into the new `concepts/` / `syncs/` layout; links to `docs/methodology.md`), and **References** (link to the paper, link to `docs/methodology.md`). The "[0.2.0]" header's compare-link follows keepachangelog convention: `https://github.com/evangstav/concept-lang/releases/tag/v0.2.0`. The file is rendered at the repo root, not inside `architecture-ide/`, because it documents the *plugin* not the Python package.

- **(F) Smoke test is a dedicated test file, not a shell assertion.** The alternatives were (i) spin up the MCP tools against the runtime directory via `create_server('architecture-ide')` and call `validate_workspace` over the wire (rejected: heavy, slow, couples the dogfood check to the FastMCP surface, already covered by the P5 MCP protocol smoke test against a different fixture), (ii) shell out to `uv run python -c "from concept_lang.loader import load_workspace; …"` from the gate task (rejected: not actually a test, not part of `pytest`, easy to forget to run), (iii) add a dedicated `tests/test_runtime_dogfood.py` (chosen: lives in the normal test suite, runs on every `uv run pytest`, bisects cleanly, one test function asserts zero error-level diagnostics with a clear failure message listing offending rules + files). The test has three assertions: (a) the workspace loads without raising (load errors would be `L0` or `P0` diagnostics), (b) the concept set is exactly the four expected names (`Concept`, `DesignSession`, `Diagram`, `Workspace`) — guards against silent migration drift, (c) `validate_workspace(ws)` returns zero error-level diagnostics (warnings are fine; a `C8` warning about unreferenced state is documented and allowed). The test file is ~40 lines including imports and docstring.

- **(G) Docs-lint is a small, targeted test, not a grep-based shell script.** The alternatives were (i) a shell script (`scripts/docs-lint.sh`) that runs `grep` / `rg` for forbidden patterns (rejected: lives outside the test suite, not run in CI by default, hard to bisect), (ii) extend `tests/test_skills.py`'s `FORBIDDEN_PHRASES` list to cover docs files (rejected: conflates skill-lint and docs-lint — the two surfaces have different failure modes and different required markers), (iii) a new `tests/test_docs.py` (chosen: pytest native, runs on every suite pass, bisects cleanly, has its own focused assertions and failure messages). The test has four assertion classes: (a) `test_readme_has_v2_code_block` — the README contains at least one fenced code block tagged `concept` whose body has the new `purpose` / `state` / `actions` / `operational principle` structure and no v1 `pre:` / `post:`, (b) `test_readme_lists_all_five_skills` — the README's skill table has exactly five rows referencing `build`, `build-sync`, `review`, `scaffold`, `explore`, (c) `test_methodology_links_to_paper` — `docs/methodology.md` contains the arXiv link `arXiv:2508.14511` (or the full URL) and at least one `Counter` + `Logger` reference, (d) `test_changelog_has_0_2_0_entry` — `CHANGELOG.md` contains a `## [0.2.0]` header and a paper reference. The forbidden-phrase list for docs is tiny: `get_dependency_graph` outside a "legacy" context, the literal `pre:` and `post:` keywords inside a fenced code block tagged `concept`. Both are enforced with `re.search` on file contents with an explicit "skip fenced blocks tagged `legacy`" carve-out so the CHANGELOG's migration section can safely show a v1 → v2 before/after. The test file is ~80 lines.

- **(H) No `apps/` directory for the runtime workspace gets an auto-index.** The `architecture-ide/apps/` directory contains exactly one file (`architecture_ide.app`) after P6 and no `README.md` or `index.md`. The alternative (auto-generate an index listing every `.app` file) was rejected as over-engineering for a one-file directory. The directory is discovered by `register_app_tools` via filesystem glob, not via an index.

- **(I) Runtime workspace lowercase filenames are renamed to PascalCase during the copy.** The v1 runtime files are lowercase (`concept.concept`, `design_session.concept`, `diagram.concept`, `workspace.concept`) because v1 did not enforce a naming convention. The P1 fixtures at `tests/fixtures/architecture_ide/concepts/` are PascalCase (`Concept.concept`, `DesignSession.concept`, `Diagram.concept`, `Workspace.concept`) because the paper's examples use PascalCase concept names and the parser validates that the concept's declared name matches the file name's stem (P1 Task 13 introduced this convention). P6's copy task uses the PascalCase filenames because they match the fixture source; the deletion task removes the lowercase v1 files explicitly by name. The `load_workspace` directory walker is case-sensitive on Linux and macOS; Windows case-insensitive filesystems are flagged as a known gotcha in the gate task.

- **(J) No README screenshot, no README asciicast, no demo GIF.** Spec §5.4 does not call for them, and the user has explicitly marked them out of scope. The README relies on text and code blocks only.

- **(K) README length target is 150–300 lines.** The current README is 73 lines and too thin; a README that teaches v2 end-to-end needs ~200 lines with sections: header, install, quickstart (3-line "concept + sync + validate"), the five-skill table, a complete concept example (inlined from `Counter.concept`), a complete sync example (inlined from `log.sync`), the new directory layout as an ASCII tree, a "why this format" section with a link to `docs/methodology.md`, a paper citation, a changelog link, and the license. Going longer than 300 lines would duplicate `docs/methodology.md`; going shorter than 150 would not teach enough. The P6 execution picks a concrete length within the band.

- **(L) Deletions use `git rm`, not bare `rm`.** Every task that removes a file uses `git rm <path>` so the deletion is staged in the same commit as the replacement. The alternative (`rm` followed by `git add -u`) works but is two steps and easier to leave inconsistent. Heredoc reminder applies: if `Edit` / `Write` is blocked, `git rm` from bash is always available.

- **(M) The runtime dogfood test asserts the concept set verbatim.** Decision (F) introduces the runtime dogfood test. Its assertion set includes `assert set(ws.concepts.keys()) == {"Concept", "DesignSession", "Diagram", "Workspace"}` so if a future cleanup accidentally drops or renames a concept, the test fires with a clear message. The same applies to the sync set (`{"SessionIntroduces", "SpecifyDrawsDiagram", "WorkspaceTracksConcept"}`). The names assertion would need a corresponding update if a new concept / sync is added, which is exactly what we want — adding a new concept should be a deliberate change that requires updating the dogfood pin.

- **(N) Docs-lint v1-reference regexes use word boundaries and respect fenced block context.** A naive grep for `pre:` fires on phrases like "Preserve the v1…" or a URL query string. The test uses `re.compile(r"^\s*pre\s*:", re.MULTILINE)` for the pre/post forbidden phrases and splits the file into fenced / non-fenced regions by running a single-pass state machine that tracks ```` ``` ```` fences. The carve-out: lines inside a fenced block tagged `legacy` (i.e., `` ```legacy`` ... `` ``` ``) are exempt so the CHANGELOG can show a before/after. The exemption is narrow — no other fence tag is exempt.

- **(O) README paper citation uses the arXiv URL, not the DOI.** Spec §1 cites the paper as `arXiv:2508.14511`. The README and methodology doc both link to `https://arxiv.org/abs/2508.14511`. The alternative (DOI via `https://doi.org/...`) was rejected because the paper is an arXiv preprint with no DOI; the arXiv URL is the canonical link.

- **(P) No grammar changes, no validator rule changes, no AST changes, no MCP tool changes, no skill changes.** P6 is docs + examples only. If a task finds that the rule set or the AST is missing something the docs want to teach, flag it in the "What's next" section at the bottom of this plan instead of patching in place. Rationale: P6 should be reviewable as a single documentation drop; adding code changes would bloat the review surface.

- **(Q) Test count floor instead of exact count.** P6 adds two test files (`test_runtime_dogfood.py`, `test_docs.py`) with roughly 1 + 4 = 5 test functions. The gate task asserts the test count is at least `297 + 5 = 302`. It does not hard-code an exact count because pytest parametrization can expand the counts in ways that drift without breaking anything. The P5 plan used the same "floor, not exact" discipline.

**No-Placeholder discipline (pinned here, referenced by every task):** Every file this plan creates has its full, ready-to-paste contents embedded in the task body below. The only thing a task may leave as a placeholder is the exact date string in `CHANGELOG.md` (`2026-04-10` is today per the environment's `# currentDate`) and the exact commit hashes in the gate task's expected output (they drift by definition). No task says "similar to above" — the runtime dogfood test and the docs-lint test have their full Python source below.

---

## Task 1: Copy the v2 fixture concepts into the runtime concepts directory

The v2 fixtures at `architecture-ide/tests/fixtures/architecture_ide/concepts/` are already paper-aligned and already validate clean. This task copies all four into `architecture-ide/concepts/` under their PascalCase fixture filenames. This is decision (A).

**Files:**
- Create: `architecture-ide/concepts/Concept.concept` (copy from fixture)
- Create: `architecture-ide/concepts/DesignSession.concept` (copy from fixture)
- Create: `architecture-ide/concepts/Diagram.concept` (copy from fixture)
- Create: `architecture-ide/concepts/Workspace.concept` (copy from fixture)

- [ ] **Step 1.1: Confirm the fixture source exists**

Run: `ls architecture-ide/tests/fixtures/architecture_ide/concepts/`

Expected: `Concept.concept`, `DesignSession.concept`, `Diagram.concept`, `Workspace.concept`. Four files, no others.

If any file is missing, abort the task and investigate — the P1 fixture set is the immutable source of truth for P6 and its absence means P5 or an earlier merge lost the fixture.

- [ ] **Step 1.2: Copy each fixture file into the runtime concepts directory**

Run (from the repo root or `architecture-ide/` — the paths below are absolute to `architecture-ide/`):

```bash
cp architecture-ide/tests/fixtures/architecture_ide/concepts/Concept.concept        architecture-ide/concepts/Concept.concept
cp architecture-ide/tests/fixtures/architecture_ide/concepts/DesignSession.concept  architecture-ide/concepts/DesignSession.concept
cp architecture-ide/tests/fixtures/architecture_ide/concepts/Diagram.concept        architecture-ide/concepts/Diagram.concept
cp architecture-ide/tests/fixtures/architecture_ide/concepts/Workspace.concept      architecture-ide/concepts/Workspace.concept
```

Expected: four new files in `architecture-ide/concepts/` with byte-for-byte identical contents to the fixtures.

- [ ] **Step 1.3: Verify the copies parse**

Run: `cd architecture-ide && uv run python -c "from concept_lang.parse import parse_concept_file; from pathlib import Path; [print(parse_concept_file(p).name) for p in sorted(Path('concepts').glob('*.concept'))]"`

Expected: four lines printed in some order:
```
Concept
DesignSession
Diagram
Workspace
```

(Plus the lowercase v1 files will also appear as failed parses — they get deleted in Task 2. This step only asserts the copies parse; the mixed state is resolved by Task 2.)

If any copy fails to parse, diff it against the fixture source — the copies should be identical, and the fixtures were proven to parse in P1.

- [ ] **Step 1.4: Do not commit yet**

The v1 files are still on disk; the runtime directory is in a mixed state. Task 2 deletes the v1 files and Task 4 commits the whole migration in one logical step. Do not run `git commit` in this task.

---

## Task 2: Delete the v1 runtime concept files

The four lowercase v1 `.concept` files are stale after Task 1 and must be removed so `load_workspace` only sees the v2 PascalCase files. This task uses `git rm` per decision (L).

**Files:**
- Delete: `architecture-ide/concepts/concept.concept`
- Delete: `architecture-ide/concepts/design_session.concept`
- Delete: `architecture-ide/concepts/diagram.concept`
- Delete: `architecture-ide/concepts/workspace.concept`

- [ ] **Step 2.1: Confirm the v1 files still exist**

Run: `ls architecture-ide/concepts/`

Expected: the four lowercase v1 files (`concept.concept`, `design_session.concept`, `diagram.concept`, `workspace.concept`), the four new v2 PascalCase files from Task 1 (`Concept.concept`, `DesignSession.concept`, `Diagram.concept`, `Workspace.concept`), and the v1 app-spec file (`architecture_ide.app`).

- [ ] **Step 2.2: Stage the v1 deletions**

Run:

```bash
git rm architecture-ide/concepts/concept.concept
git rm architecture-ide/concepts/design_session.concept
git rm architecture-ide/concepts/diagram.concept
git rm architecture-ide/concepts/workspace.concept
```

Expected: `git status` now shows four staged deletions and four unstaged new files. The `architecture_ide.app` file is still in place — it moves in Task 3.

- [ ] **Step 2.3: Confirm the mixed state**

Run: `git status architecture-ide/concepts/`

Expected: four deleted files staged, four new files untracked. No errors.

- [ ] **Step 2.4: Do not commit yet**

The commit for Tasks 1–4 happens in Task 4 after the app-spec move and the `syncs/` directory creation. Do not commit in this task.

---

## Task 3: Move the v1 app-spec file to `architecture-ide/apps/`

Per decision (B), the `architecture_ide.app` file moves from `architecture-ide/concepts/` to `architecture-ide/apps/`. The v1 `register_app_tools` bridge (from P4) still reads `.app` files from the workspace root; it does not care which subdirectory they live in as long as the workspace root is correct, but the spec §3.3 layout puts `apps/` as a sibling of `concepts/` and `syncs/`.

**Files:**
- Create: `architecture-ide/apps/` (new directory)
- Move: `architecture-ide/concepts/architecture_ide.app` → `architecture-ide/apps/architecture_ide.app`

- [ ] **Step 3.1: Create the new apps directory**

Run: `mkdir -p architecture-ide/apps`

Expected: the directory exists and is empty.

- [ ] **Step 3.2: Move the file with `git mv`**

Run: `git mv architecture-ide/concepts/architecture_ide.app architecture-ide/apps/architecture_ide.app`

Expected: `git status` now shows the file as a rename (`renamed: architecture-ide/concepts/architecture_ide.app -> architecture-ide/apps/architecture_ide.app`), preserving history.

If `git mv` refuses because the target directory is empty and untracked, first `git add` a `.gitkeep` file: no — `git mv` creates the target directory automatically. If it still refuses for any reason (it has happened on some WSL setups), fall back to `mv architecture-ide/concepts/architecture_ide.app architecture-ide/apps/architecture_ide.app` followed by `git add -u`.

- [ ] **Step 3.3: Verify the move**

Run: `ls architecture-ide/apps/ && ls architecture-ide/concepts/*.app 2>&1`

Expected: `architecture-ide/apps/architecture_ide.app` exists; the `ls` of `.app` files in `concepts/` produces "No such file or directory" (the glob matches nothing).

- [ ] **Step 3.4: Do not commit yet**

Task 4 creates the `syncs/` directory and then the whole migration commits as one logical step.

---

## Task 4: Create the `syncs/` directory, copy the three v2 sync fixtures, and commit the migration

The runtime workspace needs a `syncs/` directory to match the spec §3.3 layout. The three v2 sync fixtures from P1 go into the new directory via a copy (per decision (A)). This task finishes the migration and commits Tasks 1–4 as one logical change.

**Files:**
- Create: `architecture-ide/syncs/` (new directory)
- Create: `architecture-ide/syncs/session_introduces.sync` (copy from fixture)
- Create: `architecture-ide/syncs/specify_draws_diagram.sync` (copy from fixture)
- Create: `architecture-ide/syncs/workspace_tracks_concept.sync` (copy from fixture)

- [ ] **Step 4.1: Create the syncs directory**

Run: `mkdir -p architecture-ide/syncs`

Expected: the directory exists and is empty.

- [ ] **Step 4.2: Copy each fixture sync file**

Run:

```bash
cp architecture-ide/tests/fixtures/architecture_ide/syncs/session_introduces.sync       architecture-ide/syncs/session_introduces.sync
cp architecture-ide/tests/fixtures/architecture_ide/syncs/specify_draws_diagram.sync    architecture-ide/syncs/specify_draws_diagram.sync
cp architecture-ide/tests/fixtures/architecture_ide/syncs/workspace_tracks_concept.sync architecture-ide/syncs/workspace_tracks_concept.sync
```

Expected: three new files in `architecture-ide/syncs/` with byte-for-byte identical contents to the fixtures.

- [ ] **Step 4.3: Verify the copies parse**

Run: `cd architecture-ide && uv run python -c "from concept_lang.parse import parse_sync_file; from pathlib import Path; [print(parse_sync_file(p).name) for p in sorted(Path('syncs').glob('*.sync'))]"`

Expected:
```
SessionIntroduces
SpecifyDrawsDiagram
WorkspaceTracksConcept
```

- [ ] **Step 4.4: Confirm the full migration state via git status**

Run (from the repo root): `git status`

Expected:
- Deleted (staged): `architecture-ide/concepts/concept.concept`, `architecture-ide/concepts/design_session.concept`, `architecture-ide/concepts/diagram.concept`, `architecture-ide/concepts/workspace.concept`
- Renamed (staged): `architecture-ide/concepts/architecture_ide.app → architecture-ide/apps/architecture_ide.app`
- Untracked: `architecture-ide/concepts/Concept.concept`, `architecture-ide/concepts/DesignSession.concept`, `architecture-ide/concepts/Diagram.concept`, `architecture-ide/concepts/Workspace.concept`, `architecture-ide/syncs/session_introduces.sync`, `architecture-ide/syncs/specify_draws_diagram.sync`, `architecture-ide/syncs/workspace_tracks_concept.sync`

- [ ] **Step 4.5: Stage the new files**

Run:

```bash
git add architecture-ide/concepts/Concept.concept \
        architecture-ide/concepts/DesignSession.concept \
        architecture-ide/concepts/Diagram.concept \
        architecture-ide/concepts/Workspace.concept \
        architecture-ide/syncs/session_introduces.sync \
        architecture-ide/syncs/specify_draws_diagram.sync \
        architecture-ide/syncs/workspace_tracks_concept.sync
```

Expected: `git status` now has no unstaged or untracked files in `architecture-ide/concepts/`, `architecture-ide/syncs/`, or `architecture-ide/apps/`.

- [ ] **Step 4.6: Run the existing test suite to confirm nothing broke**

Run: `cd architecture-ide && uv run pytest -q`

Expected: 297 passed (the P5 baseline). The P1 fixtures are untouched so every fixture-dependent test still passes; the runtime dogfood test does not exist yet (Task 5).

- [ ] **Step 4.7: Commit the migration**

```bash
git commit -m "$(cat <<'EOF'
docs(runtime): migrate architecture-ide workspace to v2 layout

- Copy four v2 concept fixtures from tests/fixtures/architecture_ide/concepts/
  into architecture-ide/concepts/ as Concept, DesignSession, Diagram, Workspace.
- Create sibling architecture-ide/syncs/ directory with three v2 sync fixtures.
- Delete four lowercase v1 concept files that were left over from the
  pre-paper-alignment era.
- Move architecture_ide.app from concepts/ to new sibling apps/ directory so
  concepts/ contains only v2 .concept files. The v1 register_app_tools bridge
  still loads it via load_workspace's parent-root convention.

The runtime directory now matches spec §3.3 file organization and validates
clean against the P2 rule set. Test fixtures at tests/fixtures/architecture_ide/
stay decoupled as the immutable source of truth; the runtime copies are the
user-visible dogfood example.
EOF
)"
```

Expected: one commit with 4 deletions, 7 additions, and 1 rename.

---

## Task 5: Add the runtime workspace dogfood test

Per decision (F), a dedicated test file loads the newly migrated `architecture-ide/` workspace and asserts zero error-level diagnostics. This is the dogfooding check that catches silent regressions in future migrations.

**Files:**
- Create: `architecture-ide/tests/test_runtime_dogfood.py`

- [ ] **Step 5.1: Create the test file**

Create `architecture-ide/tests/test_runtime_dogfood.py`:

```python
"""
Runtime dogfood test (concept-lang 0.2.0 — P6).

This test loads the plugin's own example workspace at
architecture-ide/ and asserts that it is a valid v2 workspace
according to the P2 validator rule set.

It is the dogfooding check that makes sure the canonical runtime
example stays paper-aligned. If this test fails, a recent change
either broke the example workspace (e.g., a new concept was added
that references another concept's state) or broke the validator
(unlikely because the positive fixture tests would catch that).

The test deliberately does NOT import any fixture path helper.
It walks up from this file to find the package root and loads
`<package_root>/concepts/` and `<package_root>/syncs/` directly
so a future move of the test fixtures does not affect this test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from concept_lang.loader import load_workspace
from concept_lang.validate import validate_workspace


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


EXPECTED_CONCEPTS = {"Concept", "DesignSession", "Diagram", "Workspace"}
EXPECTED_SYNCS = {
    "SessionIntroduces",
    "SpecifyDrawsDiagram",
    "WorkspaceTracksConcept",
}


def test_runtime_workspace_loads() -> None:
    """The runtime workspace parses without any P0 / L0 errors."""
    ws, diagnostics = load_workspace(PACKAGE_ROOT)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert errors == [], f"Runtime workspace failed to load: {errors}"


def test_runtime_concept_set_matches_expected() -> None:
    """The runtime workspace has exactly the expected four concepts."""
    ws, _ = load_workspace(PACKAGE_ROOT)
    assert set(ws.concepts.keys()) == EXPECTED_CONCEPTS, (
        f"Unexpected runtime concept set: {sorted(ws.concepts.keys())}. "
        f"If you added or removed a concept, update EXPECTED_CONCEPTS."
    )


def test_runtime_sync_set_matches_expected() -> None:
    """The runtime workspace has exactly the expected three syncs."""
    ws, _ = load_workspace(PACKAGE_ROOT)
    assert set(ws.syncs.keys()) == EXPECTED_SYNCS, (
        f"Unexpected runtime sync set: {sorted(ws.syncs.keys())}. "
        f"If you added or removed a sync, update EXPECTED_SYNCS."
    )


def test_runtime_workspace_validates_clean() -> None:
    """The runtime workspace produces zero error-level diagnostics."""
    ws, load_diagnostics = load_workspace(PACKAGE_ROOT)
    validate_diagnostics = validate_workspace(ws)
    all_diagnostics = list(load_diagnostics) + list(validate_diagnostics)
    errors = [d for d in all_diagnostics if d.severity == "error"]
    assert errors == [], (
        "Runtime workspace has error-level diagnostics:\n"
        + "\n".join(
            f"  {d.code} {d.file}:{d.line}: {d.message}" for d in errors
        )
    )
```

- [ ] **Step 5.2: Run the new test in isolation**

Run: `cd architecture-ide && uv run pytest tests/test_runtime_dogfood.py -v`

Expected: four tests pass — `test_runtime_workspace_loads`, `test_runtime_concept_set_matches_expected`, `test_runtime_sync_set_matches_expected`, `test_runtime_workspace_validates_clean`.

If `test_runtime_workspace_validates_clean` fails with one or more errors, the migrated runtime directory has a real validation issue — investigate the specific rule codes. If the fixtures pass (which they do, per P2), the runtime copy should pass too because it is a byte-for-byte copy. Any mismatch means the copy drifted.

- [ ] **Step 5.3: Run the full suite**

Run: `uv run pytest -q`

Expected: 301 passed (297 baseline + 4 new runtime dogfood tests).

- [ ] **Step 5.4: Commit**

```bash
git add architecture-ide/tests/test_runtime_dogfood.py
git commit -m "test(dogfood): runtime workspace loads and validates clean"
```

---

## Task 6: Write `docs/methodology.md`

Per decision (C), the methodology doc is 800–1200 words plus a ~30-line embedded Counter + Logger example, structured as eight sections. Per decision (D), the example is Counter + Logger from `tests/fixtures/mcp/clean/`.

**Files:**
- Create: `docs/methodology.md` (at the repo root)

- [ ] **Step 6.1: Confirm the Counter + Logger source is still at `tests/fixtures/mcp/clean/`**

Run: `ls architecture-ide/tests/fixtures/mcp/clean/concepts/ architecture-ide/tests/fixtures/mcp/clean/syncs/`

Expected: `concepts/Counter.concept`, `concepts/Logger.concept`, `syncs/log.sync`. If any file is missing, the P4 fixture set has drifted — abort and investigate.

- [ ] **Step 6.2: Read the three source files verbatim**

Run (from `architecture-ide/`):

```bash
cat tests/fixtures/mcp/clean/concepts/Counter.concept
cat tests/fixtures/mcp/clean/concepts/Logger.concept
cat tests/fixtures/mcp/clean/syncs/log.sync
```

Expected output (used as the authoritative text for the embedded code blocks below):

```
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

```
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

```
sync LogInc

  when
    Counter/inc: [ ] => [ total: ?total ]
  then
    Logger/write: [ msg: ?total ] => [ ]
```

If the files differ from the above verbatim, update Step 6.3's embedded blocks to match. The methodology doc must quote the actual test-fixture source so it cannot drift.

- [ ] **Step 6.3: Create `docs/methodology.md`**

Create the file at the **repo root** path `docs/methodology.md` (not inside `architecture-ide/docs/`). The repo root's `docs/` directory currently holds only `docs/superpowers/` — this task adds `docs/methodology.md` as a sibling of `docs/superpowers/`.

From the repo root, run:

```bash
cat > docs/methodology.md <<'METHODOLOGY_EOF'
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
METHODOLOGY_EOF
```

- [ ] **Step 6.4: Verify the file was written**

Run (from the repo root): `wc -w docs/methodology.md && wc -l docs/methodology.md`

Expected: roughly 900–1100 words, roughly 190–220 lines. If the word count is outside the 800–1200 band (decision (C)), adjust the prose. The embedded source blocks count toward the line total but not toward the word count because the code blocks are source, not prose.

Run: `head -5 docs/methodology.md`

Expected:
```
# concept-lang methodology

A short primer on what `concept-lang` teaches and how its DSL maps to the
structural pattern described in Meng & Jackson's 2025 paper.

```

- [ ] **Step 6.5: Verify the embedded Counter + Logger source is byte-identical to the fixture**

Run (from the repo root):

```bash
diff <(sed -n '/^```concept/,/^```$/p' docs/methodology.md | head -n 15) architecture-ide/tests/fixtures/mcp/clean/concepts/Counter.concept
```

(The `sed` range captures the first fenced `concept` block, which is `Counter`. This is a sanity check — if the fixture ever changes and this step fires, update the methodology doc's embedded source to match.)

Expected: no diff output — the embedded Counter source matches the fixture. If there is diff output, it is a sign that the fixture has been edited since the doc was written; update the doc's embedded block in place.

- [ ] **Step 6.6: Run the full test suite to confirm nothing broke**

Run (from `architecture-ide/`): `uv run pytest -q`

Expected: 301 passed (unchanged from Task 5). The methodology doc is pure documentation; no test depends on it yet. Task 8 adds the docs-lint test that does depend on it.

- [ ] **Step 6.7: Commit**

```bash
git add docs/methodology.md
git commit -m "docs(methodology): add paper-aligned DSL primer with Counter+Logger walk"
```

---

## Task 7: Rewrite `README.md` for v2

Per decision (K), the new README is 150–300 lines. It teaches v2 exclusively, lists all five skills, shows the new directory layout, and links to the methodology doc.

**Files:**
- Rewrite: `README.md` (at the repo root)

- [ ] **Step 7.1: Read the current README to understand what to keep**

Run: `wc -l README.md && head -80 README.md`

Expected: 73 lines, header + install + four-skill table + v1 concept example + configuration + MCP server section + license.

Elements to keep:
- Header + elevator pitch (the first three lines).
- Install section (the `/plugin marketplace add` and `/plugin install` commands).
- MCP server section (lightly updated).
- License line.

Elements to rewrite:
- The four-skill table → five-skill table including `build-sync`.
- The v1 concept example → a v2 concept example using `Counter.concept` from the fixtures.
- Add a v2 sync example using `log.sync` from the fixtures.
- Add a new directory layout section.
- Add a "Why this format?" section with a one-paragraph pitch and a link to `docs/methodology.md`.
- Add a paper citation.
- Add a link to `CHANGELOG.md`.
- Remove the old `pre:` / `post:` example entirely.

- [ ] **Step 7.2: Rewrite the file**

From the repo root:

```bash
cat > README.md <<'README_EOF'
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

- `architecture-ide/concepts/` + `architecture-ide/syncs/` + `architecture-ide/apps/`
  — the self-hosting architecture-ide workspace (four concepts, three
  syncs, one app spec). Used as the canonical dogfood example.
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
README_EOF
```

- [ ] **Step 7.3: Verify the new README**

Run (from the repo root):

```bash
wc -l README.md
```

Expected: between 150 and 300 lines (decision (K)). The content above is roughly 155 lines.

Run:

```bash
grep -c 'build-sync' README.md
```

Expected: at least 2 (one in the install table, one in the skill command column). If it is 0 or 1, the `build-sync` row is missing or has a typo.

Run:

```bash
grep -c 'arxiv.org/abs/2508.14511' README.md
```

Expected: at least 2 (one in the header citation, one in the "Why this format?" section).

Run:

```bash
grep -E '^\s*(pre|post):' README.md
```

Expected: no output. The v1 `pre:` / `post:` keywords are forbidden in the new README.

- [ ] **Step 7.4: Run the existing test suite**

Run: `cd architecture-ide && uv run pytest -q`

Expected: 301 passed (unchanged from Task 6). The README is pure documentation; the docs-lint test that will assert on it is added in Task 8.

- [ ] **Step 7.5: Commit**

```bash
git add README.md
git commit -m "docs(readme): rewrite for v2 format and five-skill layout"
```

---

## Task 8: Create `CHANGELOG.md`

Per decision (E), the changelog follows Keep a Changelog 1.1.0 with an `[Unreleased]` placeholder and a `[0.2.0]` release section.

**Files:**
- Create: `CHANGELOG.md` (at the repo root)

- [ ] **Step 8.1: Confirm no existing changelog**

Run (from the repo root): `ls CHANGELOG.md 2>&1 || echo "absent"`

Expected: `absent`. If the file already exists, back it up to `CHANGELOG.md.bak` and proceed — Task 8 is authoring the canonical 0.2.0 entry.

- [ ] **Step 8.2: Create the file**

From the repo root:

```bash
cat > CHANGELOG.md <<'CHANGELOG_EOF'
# Changelog

All notable changes to `concept-lang` are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_No changes yet._

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

- The `sync` section inside concept files is gone. Syncs are now top-level
  `.sync` files. The validator rule `C4` fires on any lingering inline
  sync block.
- The v1 `pre:` and `post:` keywords in action bodies are gone. Use the
  new hybrid format — natural-language body plus optional `effects:`
  subsection.
- The v1 hand-written regex parser, validator, diff engine, and explorer
  are no longer reachable from the MCP tool layer or from any skill.
  The full deletion of those modules is scheduled for a follow-up
  release; in `0.2.0` they remain on disk only to back the v1 app-spec
  bridge, which is reached through `register_app_tools` and is scheduled
  for its own dedicated migration.

### Migration

`0.2.0` is a hard break. There is no automated migration tool. To port
an existing workspace:

1. Create `<workspace>/concepts/` and `<workspace>/syncs/` directories.
2. Rewrite each `.concept` file in the new format — see
   [`docs/methodology.md`](docs/methodology.md) for the structural
   pattern and [`skills/build/SKILL.md`](skills/build/SKILL.md) for a
   worked example.
3. For every `sync` section that used to live inside a concept, extract
   it into a standalone `.sync` file in `<workspace>/syncs/`. Rewrite
   the body in the new `when` / `where` / `then` form. See
   [`skills/build-sync/SKILL.md`](skills/build-sync/SKILL.md) for the
   sync DSL.
4. If you have `.app` files, move them into `<workspace>/apps/`. The
   v1 `.app` format is still accepted in `0.2.0`; a v2 app format is
   planned for a follow-up release.
5. Run `/concept-lang:review` against the migrated workspace. The rule
   categories map cleanly onto the paper's independence, completeness,
   and sync properties.

### References

- Paper: [Meng & Jackson, *What You See Is What It Does: A Structural
  Pattern for Legible Software*, Onward! '25
  (arXiv:2508.14511)](https://arxiv.org/abs/2508.14511)
- Primer: [`docs/methodology.md`](docs/methodology.md)
- Fixture workspaces:
  `architecture-ide/tests/fixtures/architecture_ide/`,
  `architecture-ide/tests/fixtures/realworld/`

[Unreleased]: https://github.com/evangstav/concept-lang/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/evangstav/concept-lang/releases/tag/v0.2.0
CHANGELOG_EOF
```

- [ ] **Step 8.3: Verify the file**

Run (from the repo root):

```bash
wc -l CHANGELOG.md
grep -c '^## \[' CHANGELOG.md
grep -c 'arxiv.org/abs/2508.14511' CHANGELOG.md
```

Expected:
- Roughly 100 lines.
- `^## \[` count: 2 (one for `[Unreleased]`, one for `[0.2.0]`).
- `arxiv.org/abs/2508.14511` count: 2 (one in the 0.2.0 section body, one in the References section).

- [ ] **Step 8.4: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): add 0.2.0 paper-alignment release notes"
```

---

## Task 9: Add the docs-lint test

Per decision (G), a new test file enforces the docs contract: the README has v2 code blocks, lists all five skills, has no v1 `pre:` / `post:` keywords in `concept` fences; the methodology doc cites the paper and references Counter + Logger; the CHANGELOG has a 0.2.0 entry with a paper reference. Decision (N) pins the fence-context handling.

**Files:**
- Create: `architecture-ide/tests/test_docs.py`

- [ ] **Step 9.1: Create the test file**

Create `architecture-ide/tests/test_docs.py`:

```python
"""
Docs-lint contract tests (concept-lang 0.2.0 — P6).

These tests enforce a contract between the user-facing documentation
(`README.md`, `CHANGELOG.md`, `docs/methodology.md`) and the 0.2.0
paper-alignment release:

  1. README lists all five skills and contains a v2 concept code block.
  2. README does not contain v1 `pre:` / `post:` keywords inside a
     fenced code block tagged `concept`. Lines inside a fenced block
     tagged `legacy` are exempt so a migration guide can show a
     before/after.
  3. methodology.md cites the paper via the arXiv URL and references
     the Counter + Logger example.
  4. CHANGELOG.md has a `## [0.2.0]` header and a paper reference.

The test file is deliberately small. It complements tests/test_skills.py
(skill-lint) but does NOT import from it — the two surfaces have
different failure modes and should fail independently.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
METHODOLOGY = REPO_ROOT / "docs" / "methodology.md"


FIVE_SKILLS = ("build", "build-sync", "review", "scaffold", "explore")

PAPER_URL = "arxiv.org/abs/2508.14511"


def _strip_legacy_fences(text: str) -> str:
    """Remove the contents of any fenced block tagged `legacy`.

    Decision (N): the legacy carve-out lets the CHANGELOG show a v1 → v2
    migration snippet without tripping the forbidden-phrase check. No
    other fence tag is exempt.
    """
    out_lines: list[str] = []
    in_legacy = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```legacy"):
            in_legacy = True
            continue
        if in_legacy and stripped == "```":
            in_legacy = False
            continue
        if not in_legacy:
            out_lines.append(line)
    return "\n".join(out_lines)


def _concept_fence_bodies(text: str) -> list[str]:
    """Return the body text of every fenced block tagged `concept`."""
    pattern = re.compile(r"^```concept\s*\n(.*?)\n```", re.MULTILINE | re.DOTALL)
    return pattern.findall(text)


def test_readme_exists_and_is_non_empty() -> None:
    assert README.exists(), f"README missing: {README}"
    assert README.read_text().strip(), "README is empty"


def test_readme_lists_all_five_skills() -> None:
    text = README.read_text()
    missing = [s for s in FIVE_SKILLS if f"`{s}`" not in text and f"**{s}**" not in text]
    assert not missing, f"README is missing skills: {missing}"


def test_readme_has_v2_concept_code_block() -> None:
    text = README.read_text()
    bodies = _concept_fence_bodies(text)
    assert bodies, "README has no fenced `concept` code block"
    # At least one body must use the v2 structure: `purpose`, `state`,
    # `actions`, `operational principle`.
    for body in bodies:
        if (
            "purpose" in body
            and "state" in body
            and "actions" in body
            and "operational principle" in body
        ):
            return
    pytest.fail(
        "README has concept fences but none use the v2 structure "
        "(purpose / state / actions / operational principle)"
    )


def test_readme_has_no_v1_pre_post_keywords() -> None:
    text = _strip_legacy_fences(README.read_text())
    bodies = _concept_fence_bodies(text)
    for body in bodies:
        assert not re.search(r"(?m)^\s*pre\s*:", body), (
            "README concept fence contains v1 `pre:` keyword"
        )
        assert not re.search(r"(?m)^\s*post\s*:", body), (
            "README concept fence contains v1 `post:` keyword"
        )


def test_readme_cites_paper() -> None:
    text = README.read_text()
    assert PAPER_URL in text, f"README does not cite {PAPER_URL}"


def test_methodology_exists_and_is_non_empty() -> None:
    assert METHODOLOGY.exists(), f"methodology.md missing: {METHODOLOGY}"
    assert METHODOLOGY.read_text().strip(), "methodology.md is empty"


def test_methodology_cites_paper() -> None:
    text = METHODOLOGY.read_text()
    assert PAPER_URL in text, f"methodology.md does not cite {PAPER_URL}"


def test_methodology_walks_counter_and_logger() -> None:
    text = METHODOLOGY.read_text()
    assert "Counter" in text, "methodology.md does not mention Counter"
    assert "Logger" in text, "methodology.md does not mention Logger"
    assert "LogInc" in text or "log" in text.lower(), (
        "methodology.md does not reference the log sync"
    )


def test_changelog_exists_and_is_non_empty() -> None:
    assert CHANGELOG.exists(), f"CHANGELOG.md missing: {CHANGELOG}"
    assert CHANGELOG.read_text().strip(), "CHANGELOG.md is empty"


def test_changelog_has_0_2_0_entry() -> None:
    text = CHANGELOG.read_text()
    assert re.search(r"^## \[0\.2\.0\]", text, re.MULTILINE), (
        "CHANGELOG.md does not have a `## [0.2.0]` section header"
    )


def test_changelog_cites_paper() -> None:
    text = CHANGELOG.read_text()
    assert PAPER_URL in text, f"CHANGELOG.md does not cite {PAPER_URL}"


def test_changelog_has_unreleased_placeholder() -> None:
    text = CHANGELOG.read_text()
    assert re.search(r"^## \[Unreleased\]", text, re.MULTILINE), (
        "CHANGELOG.md does not have a `## [Unreleased]` placeholder section"
    )
```

- [ ] **Step 9.2: Run the new test in isolation**

Run: `cd architecture-ide && uv run pytest tests/test_docs.py -v`

Expected: eleven tests pass — `test_readme_exists_and_is_non_empty`, `test_readme_lists_all_five_skills`, `test_readme_has_v2_concept_code_block`, `test_readme_has_no_v1_pre_post_keywords`, `test_readme_cites_paper`, `test_methodology_exists_and_is_non_empty`, `test_methodology_cites_paper`, `test_methodology_walks_counter_and_logger`, `test_changelog_exists_and_is_non_empty`, `test_changelog_has_0_2_0_entry`, `test_changelog_cites_paper`, `test_changelog_has_unreleased_placeholder`. If the count is off, one of the docs files from Tasks 6–8 drifted from the expectations — re-read the failing test message and fix the doc file, not the test.

- [ ] **Step 9.3: Run the full suite**

Run: `uv run pytest -q`

Expected: **313 passed** (301 from Task 5 baseline + 12 new docs-lint tests). The floor per decision (Q) is 302; the actual count is 313.

- [ ] **Step 9.4: Commit**

```bash
git add architecture-ide/tests/test_docs.py
git commit -m "test(docs): lint README, CHANGELOG, and methodology for v2 contract"
```

---

## Task 10: Final docs-lint cross-check — no lingering v1 surface references in prose

The docs-lint test in Task 9 pins the required markers. This task is a one-shot sweep of the documentation surface for any remaining v1 references that slipped through the rewrites. It is a manual grep pass, not a committed test, and the commit (if any) is "cleanup, zero changes" — the whole point is that the docs should already be clean by this task.

**Files:**
- No file changes expected. If the grep catches something, edit the offending file in place.

- [ ] **Step 10.1: Grep for lingering v1 keywords across all documentation**

Run (from the repo root):

```bash
grep -nE '(^|[^`])get_dependency_graph' README.md CHANGELOG.md docs/methodology.md 2>&1 | grep -v 'legacy' | grep -v 'back-compat alias' | grep -v 'preserved as a back-compat'
```

Expected: no matches. Every legitimate mention of `get_dependency_graph` is either inside a `legacy` fence or explicitly framed as a deprecated alias. If a match fires and it is not excluded by the grep filters, edit the file to either remove the reference or re-frame it.

Run:

```bash
grep -nE '^\s*(pre|post):' README.md CHANGELOG.md docs/methodology.md
```

Expected: no matches. The v1 `pre:` and `post:` keywords should be absent from docs prose (they are already pinned as absent in README v2 concept fences by Task 9, but this check also covers the CHANGELOG and methodology prose).

Run:

```bash
grep -nE 'scaffold_concepts\s+tool.*state\s+machine' README.md CHANGELOG.md docs/methodology.md
```

Expected: no matches. The v1 scaffold state-machine output is explicitly deprecated and should not be mentioned in prose.

- [ ] **Step 10.2: Grep for broken markdown links**

Run (from the repo root):

```bash
grep -oE '\[.+?\]\([^)]+\)' README.md CHANGELOG.md docs/methodology.md | sort -u
```

Expected: all links point at existing files or external URLs. For each relative link, spot-check that the target exists.

Specifically verify:
- `docs/methodology.md` is a valid link from `README.md` → `ls docs/methodology.md`
- `CHANGELOG.md` is a valid link from `README.md` → `ls CHANGELOG.md`
- `docs/methodology.md` is a valid link from `CHANGELOG.md` → already verified above
- `skills/build/SKILL.md`, `skills/build-sync/SKILL.md` are valid links from `CHANGELOG.md` → `ls skills/build/SKILL.md skills/build-sync/SKILL.md`

If any link is broken, fix it in place and add a one-line commit.

- [ ] **Step 10.3: Grep for lingering four-skill references**

Run (from the repo root):

```bash
grep -nE 'four (skills|tools)' README.md CHANGELOG.md docs/methodology.md
```

Expected: no matches. The 0.2.0 release ships five skills; any "four skills" phrasing is stale.

- [ ] **Step 10.4: Verify the skills directory has exactly five skills**

Run: `find skills -name 'SKILL.md' | wc -l`

Expected: `5`. If not, the P5 rewrite is incomplete and P6 cannot close. Escalate by re-running the P5 gate.

- [ ] **Step 10.5: If any fix was committed, run the full suite again**

Run (from `architecture-ide/`): `uv run pytest -q`

Expected: 313 passed. If any test fails after a docs fix, the fix accidentally broke the lint — revisit the fix.

- [ ] **Step 10.6: Commit (only if a fix was made)**

If Steps 10.1–10.3 surfaced any edits, commit them:

```bash
git add README.md CHANGELOG.md docs/methodology.md
git commit -m "docs(cleanup): remove lingering v1 references from prose"
```

If no edits were needed, skip this commit and proceed to Task 11.

---

## Task 11: P6 gate — final suite run and tag

The gate is: runtime workspace migrated to v2, `.app` file relocated, `docs/methodology.md` present and passing lint, `README.md` rewritten and passing lint, `CHANGELOG.md` present with 0.2.0 entry, runtime dogfood test green, docs-lint test green, full suite at 313+ passing.

**Files:**
- No code changes (this task only runs verification and tags the milestone).

- [ ] **Step 11.1: Confirm the runtime workspace inventory**

Run (from the repo root):

```bash
ls architecture-ide/concepts/
ls architecture-ide/syncs/
ls architecture-ide/apps/
```

Expected:

```
# concepts/
Concept.concept  DesignSession.concept  Diagram.concept  Workspace.concept

# syncs/
session_introduces.sync  specify_draws_diagram.sync  workspace_tracks_concept.sync

# apps/
architecture_ide.app
```

Four concepts, three syncs, one app spec. No lowercase v1 files in `concepts/`. No `.app` file in `concepts/`.

- [ ] **Step 11.2: Confirm the documentation inventory**

Run (from the repo root):

```bash
ls README.md CHANGELOG.md docs/methodology.md
```

Expected: all three files exist.

- [ ] **Step 11.3: Full test suite**

Run (from `architecture-ide/`): `uv run pytest -v`

Expected: every test passes. Approximate counts:
- P5 baseline: 297
- Task 5 runtime dogfood: +4
- Task 9 docs-lint: +12
- **Total: roughly 313 passed.** The floor per decision (Q) is 302; actual count drifts slightly with how pytest parametrizations expand. Do not hard-code.

If the count is lower than 302, one of the new test files is collecting fewer tests than expected — check `tests/test_runtime_dogfood.py` and `tests/test_docs.py` for missing test functions.

- [ ] **Step 11.4: Run the docs-specific tests in isolation**

Run (from `architecture-ide/`): `uv run pytest tests/test_runtime_dogfood.py tests/test_docs.py -v`

Expected: 16 tests pass (4 runtime dogfood + 12 docs-lint). This guarantees the P6-specific surface is green even if some unrelated test ever becomes flaky.

- [ ] **Step 11.5: Smoke-load the runtime workspace via the real MCP server**

Run (from the repo root):

```bash
WORKSPACE_DIR=architecture-ide uv run --directory architecture-ide python -c "
from concept_lang.server import create_server
s = create_server('architecture-ide')
tools = sorted(s._tool_manager._tools.keys())
print(f'Tool count: {len(tools)}')
print(f'Has validate_workspace: {\"validate_workspace\" in tools}')
print(f'Has list_syncs: {\"list_syncs\" in tools}')
"
```

Expected:

```
Tool count: 23 (or thereabouts — the exact number depends on P4 registrations)
Has validate_workspace: True
Has list_syncs: True
```

This confirms that when the plugin points at the runtime workspace, every P4 tool is still reachable and the workspace root resolution works. If the Python call raises, the runtime workspace has a parse error that slipped through the dogfood test — investigate.

- [ ] **Step 11.6: Skip the commit step**

The gate itself does not produce file changes, so there is nothing to commit in this task. Jump to tagging.

- [ ] **Step 11.7: Tag the milestone**

```bash
git tag p6-examples-and-docs-complete -m "P6 gate passed: runtime workspace migrated to v2, methodology + README + CHANGELOG shipped, dogfood and docs-lint tests pinned"
```

- [ ] **Step 11.8: Final status check**

Run: `git log --oneline -15`

Expected: roughly 7 small commits in the `docs(runtime) / test(dogfood) / docs(methodology) / docs(readme) / docs(changelog) / test(docs) / docs(cleanup)` namespace, ending with the tag `p6-examples-and-docs-complete`. The cleanup commit is optional (decision (L)); if no cleanup was needed the count is 6.

Run: `git tag | grep -E 'p[1-6]'`

Expected:

```
p1-parser-complete
p2-validator-complete
p3-workspace-loader-complete
p4-tooling-migration-complete
p5-skills-rewrite-complete
p6-examples-and-docs-complete
```

---

## What's next (not in this plan)

After this plan lands and the `p6-examples-and-docs-complete` tag is in place, the follow-up plans are:

- **P7 — Delete v1 code.** Remove `concept_lang.parser`, `concept_lang.models`, `concept_lang.validator`, `concept_lang.diff` v1 backing (if any residue), `concept_lang.explorer` v1 backing (if any residue), `concept_lang.codegen/`, `concept_lang.diagrams/` (if still consuming v1 models), the `get_dependency_graph` back-compat alias, any v1 test files, and any v1 re-exports. After P7 the codebase imports only from the new modules.

- **App format v2.** The v1 app-spec format is still alive in `0.2.0` via the `register_app_tools` bridge. A dedicated plan migrates it to a v2 AST, writes a v2 validator, and rewrites the `architecture_ide.app` fixture.

- **C8 completeness rule.** The unreferenced-state warning rule was deferred from P2 because it is hard to express as a minimal positive fixture. A follow-up plan reintroduces it once the authoring pipeline has enough signal to distinguish "unused state" from "state referenced by a sync-level query".

- **P3 line-number tightening (T20 carry-over).** A subset of the negative fixtures still has `line: null` in their expected diagnostics. A follow-up plan tightens the line numbers in all negative fixtures once the transformer meta-plumbing covers every position-bearing rule.

- **`OPStep.inputs/outputs` tuple-shape cleanup.** The AST still stores operational-principle input / output fields as `list[tuple[str, str]]` rather than `list[TypedName]`. The cleanup is low-risk but not urgent and has been carried across P3, P4, P5, and now P6 without being done.

- **Paper-aligned runtime engine (Layer 2).** The paper's §6 and Appendix A describe a full synchronization runtime with action graphs and flow-ID tracking. This is explicitly out of scope for the language + tooling spec and is slated for its own follow-up spec.

- **README screenshots / asciicast / demo GIF.** Decision (J) ruled these out of scope for P6. A follow-up docs polish plan can add them after 0.2.0 ships.

- **Marketplace publish.** The user handles release distribution manually; no plan needed.

---

## Self-review

- **Spec coverage** —
  Spec §5.4 has four documentation items. Each is addressed by a task in this plan:

  | Spec §5.4 item | Task in P6 |
  |---|---|
  | `README.md` — new concept + sync examples, updated skill table, new directory layout | Task 7 |
  | `skills/*/SKILL.md` — rewritten prompts for each skill | Done in P5, not re-touched |
  | **New**: `docs/methodology.md` — explainer tying the DSL to the paper's terminology, with citation | Task 6 |
  | **New**: `CHANGELOG.md` — 0.2.0 entry linking to the paper and methodology doc | Task 8 |

  Spec §6.4's P6 row adds a fifth item: "`architecture-ide/concepts/` rewritten in-place". Tasks 1, 2, 3, and 4 address this.

  Spec §6.5 adds a sixth item: "`CHANGELOG.md` gets a '0.2.0 — Paper alignment' entry". Task 8 addresses this.

  P6 does not cover spec §5.3 out-of-scope items (runtime engine, action graph, flow-ID tracking, `codegen/` update, LSP, `migrate` tool) — those are out of scope by design.

- **Placeholder scan** — every code block in the plan is a literal drop-in. No task says "similar to above" or leaves a "TBD". The `CHANGELOG.md` task uses a literal date string (`2026-04-10`) because that is today per the environment's `# currentDate`. The "What's next" section intentionally lists high-level items without implementation detail; those are placeholders for future plans, not for this plan.

- **Type consistency** —
  - File paths: `architecture-ide/concepts/`, `architecture-ide/syncs/`, `architecture-ide/apps/`, `architecture-ide/tests/test_runtime_dogfood.py`, `architecture-ide/tests/test_docs.py`, `README.md`, `CHANGELOG.md`, `docs/methodology.md` — consistent across every task body and the file structure section.
  - Test file names: the two new test files are `test_runtime_dogfood.py` and `test_docs.py`. The test function names inside each file are listed explicitly in Tasks 5 and 9 respectively and are cross-referenced from the gate task.
  - Concept names: `Counter`, `Logger`, `Concept`, `DesignSession`, `Diagram`, `Workspace` — consistent. The sync names `LogInc`, `SessionIntroduces`, `SpecifyDrawsDiagram`, `WorkspaceTracksConcept` — consistent. The runtime dogfood test pins `EXPECTED_CONCEPTS = {"Concept", "DesignSession", "Diagram", "Workspace"}` and `EXPECTED_SYNCS = {"SessionIntroduces", "SpecifyDrawsDiagram", "WorkspaceTracksConcept"}` (note PascalCase on sync names per P1).
  - Paper URL: `https://arxiv.org/abs/2508.14511` and `arXiv:2508.14511` — used consistently in README, CHANGELOG, methodology doc, and docs-lint test.
  - Keep a Changelog version: `1.1.0` — pinned in decision (E) and in the CHANGELOG body.
  - Skill names: `build`, `build-sync`, `review`, `scaffold`, `explore` — five entries, consistent across README, methodology, CHANGELOG, and decision (K).
  - Rule codes: `C1`–`C9` (minus `C8`), `S1`–`S5` — unchanged from P2.

- **Scope discipline** —
  - No grammar changes, no AST changes, no new validator rules, no new MCP tools, no new skills — P6 is docs + examples only.
  - No v1 deletion — P7.
  - No app-spec format v2 — post-P7.
  - No publish, no screenshots, no demo GIFs — decision (J).
  - No `OPStep.inputs/outputs` tuple-shape cleanup — still deferred.
  - No T20 line-number tightening — still deferred.
  - No `scaffold_tools._METHODOLOGY` touch — already done in P5.
  - No `prompts.py` touch — already done in P5.
  - No `.claude-plugin/plugin.json` version change — already at 0.2.0 from P5.

- **Commit discipline** —
  - Task 1: no commit (staging only).
  - Task 2: no commit (staging only).
  - Task 3: no commit (staging only).
  - Task 4: one commit (`docs(runtime): migrate architecture-ide workspace to v2 layout`) — absorbs Tasks 1, 2, 3, 4 into one logical change.
  - Task 5: one commit (`test(dogfood): …`).
  - Task 6: one commit (`docs(methodology): …`).
  - Task 7: one commit (`docs(readme): …`).
  - Task 8: one commit (`docs(changelog): …`).
  - Task 9: one commit (`test(docs): …`).
  - Task 10: zero or one commit depending on whether cleanup was needed.
  - Task 11: zero commits, only a tag.
  - **Total: 6 or 7 commits plus one tag.**
  - No task commits into `architecture-ide/src/concept_lang/` — P6 is strictly docs + examples + tests.

- **Test strategy coherence** —
  - Runtime dogfood test (`tests/test_runtime_dogfood.py`) exercises the migrated runtime workspace end to end via `load_workspace` + `validate_workspace`. It pins the concept set and the sync set verbatim so silent drift fires.
  - Docs-lint test (`tests/test_docs.py`) exercises the three documentation files via filesystem reads and regex assertions. It is decoupled from the skill-lint test in P5 (`tests/test_skills.py`) because the two surfaces have different failure modes.
  - Both new tests live under `architecture-ide/tests/` alongside the rest of the test suite so `uv run pytest` from the package root picks them up automatically.
  - No end-to-end docs rendering (Markdown HTML conversion, link resolver) is automated — decision (G) keeps the lint small and targeted; broken links are caught by a one-shot grep in Task 10.

- **Running discipline** — every task has a "create / rewrite / verify" triple followed by a targeted-test step and (for Tasks 5 and 9) a full-suite step before committing. No task skips straight to commit.

- **Ambiguity check** —
  - "Runtime directory" is the `architecture-ide/concepts/` + `architecture-ide/syncs/` + `architecture-ide/apps/` triple after Task 4. Before Task 4 it is "the v1 files still on disk plus the new v2 copies on top". The plan is explicit about this mixed state in Task 2 Step 2.3.
  - "Repo root" vs "`architecture-ide/`" — called out at the top of the File structure section. Every command that touches `README.md`, `CHANGELOG.md`, or `docs/methodology.md` specifies "from the repo root". Every command that touches `architecture-ide/…` paths is either absolute or explicitly rooted.
  - "Fixture vs runtime" — decision (A) is explicit that the fixtures stay at `tests/fixtures/architecture_ide/` and the runtime is a *copy* in `architecture-ide/concepts/` + `architecture-ide/syncs/`. The runtime dogfood test does not share a fixture helper with the P1 parser tests.
  - "App-spec bridge" — the v1 `register_app_tools` from P4 loads `.app` files from the workspace root via filesystem glob. The move to `architecture-ide/apps/architecture_ide.app` is safe because `load_workspace` does not read `.app` files (decision (B) and P3 out-of-scope note) and `register_app_tools` resolves the workspace root via `_resolve_workspace_root`. A test assertion that the bridge still works with the new location would be valuable but is out of scope for P6 — the existing P4 `test_mcp_tools.py::TestAppTools` class covers the contract and does not pin the app-spec location.
  - "Docs-lint forbidden phrase scope" — decision (N) narrows the forbidden-phrase regex to lines inside fenced `concept` blocks (for `pre:` / `post:`) or whole-document matches (for `get_dependency_graph` with exclusion heuristics). The carve-out for `legacy` fences is narrow and explicit.
  - "PascalCase filename convention" — decision (I) is explicit that runtime and fixture filenames are both PascalCase because P1 Task 13 introduced the convention. The v1 lowercase runtime files are deleted, not renamed.

- **Task count** — 11 tasks total:
  1. Copy v2 fixture concepts into runtime
  2. Delete v1 runtime concept files
  3. Move v1 app-spec file to `apps/`
  4. Create `syncs/` directory, copy fixtures, commit migration
  5. Add runtime dogfood test
  6. Write `docs/methodology.md`
  7. Rewrite `README.md`
  8. Create `CHANGELOG.md`
  9. Add docs-lint test
  10. Final docs-lint cross-check
  11. P6 gate + tag

  Tasks 1, 2, 3, 4 together form the runtime migration (decision (L) — `git rm` + `git mv` + commit as one logical change). The brief asked for 8–14 tasks; 11 is in range.

- **Heredoc gotcha reminder** — pinned into the plan's header under the "Heredoc reminder" block. Every file-creation task below uses `cat > path <<'EOF' … EOF` as the authoritative method so the plan is robust against `Edit` / `Write` sandbox blocks.
