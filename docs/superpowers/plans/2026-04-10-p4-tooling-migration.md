# concept-lang 0.2.0 — P4: Tooling Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the user-facing tooling — `concept_lang.diff`, `concept_lang.explorer`, and the MCP tool layer (`concept_lang.server`, `concept_lang.tools/`, `concept_lang.resources`, `concept_lang.prompts`) — to consume the new AST (`concept_lang.ast`) and new validator (`concept_lang.validate`) via `concept_lang.loader.load_workspace`. Rename `get_dependency_graph` to `get_workspace_graph` with edges as syncs (not inferred from trigger references), and add five new MCP tools: `read_sync`, `write_sync`, `list_syncs`, `validate_sync`, `validate_workspace`. At the end of this plan, every MCP tool in spec §5.1 exists in its v2 form, `diff` and `explorer` consume the new AST end-to-end, and the v1 modules (`parser.py`, `models.py`, `validator.py`, `app_parser.py`, `app_validator.py`) are still in the tree but no longer reachable from any MCP tool or user-facing entry point — they stay solely to back the still-v1 app-spec handling, which P4 wires behind the new MCP tool layer.

**Architecture:** The MCP tools now call `load_workspace(root)` to get a `Workspace` value plus parse diagnostics, then run validator rules against that workspace. The tool layer decides what to return to the MCP client based on the combined diagnostic list — never the raw AST unless the caller explicitly asked for it. `diff.py` and `explorer.py` are rewritten in-place against `concept_lang.ast.ConceptAST` and `concept_lang.ast.SyncAST`, because their consumers (the MCP tool layer) are being rewired in the same plan. App-spec handling stays on v1 (`concept_lang.app_parser`, `concept_lang.app_validator`) but is reached only via the `register_app_tools` entry points, which keep working unchanged. `codegen/` is explicitly out of scope and its tool registration is removed from the MCP server for P4 (the backends still import v1 internally, so re-enabling them is a single line once P5/P6 decides what to do).

**Tech Stack:** Python 3.10+, Lark (already in deps), Pydantic 2, pytest, uv. No new runtime dependencies.

**Scope note:** This plan covers **P4 only**.

- In scope: `diff.py` rewrite (new AST), `explorer.py` rewrite (new AST + syncs-as-edges graph), MCP tool layer rewiring for every tool in spec §5.1 (`read_concept`, `write_concept`, `list_concepts`, `validate_concept`, `get_workspace_graph` rename, new `read_sync` / `write_sync` / `list_syncs` / `validate_sync` / `validate_workspace`), `resources.py` re-export, `prompts.py` text updates that reference renamed tools, `concept_lang.__init__` public surface cleanup, integration smoke tests, and the P4 gate + tag.
- Out of scope: `codegen/` migration (spec §5.3 defers it — P4 removes its MCP registration but leaves the module intact), `scaffold_concepts` tool methodology rewrite (stays on the v1 docstring for now — the tool is a payload builder that does not parse concepts, so it keeps working as-is; P5 rewrites the embedded methodology block when the `scaffold` skill lands), `diagram_tools` per-concept Mermaid generators (`get_state_machine`, `get_entity_diagram`) — these continue to call v1 through a thin adapter that `parse_file` → convert to v1 `ConceptAST` → run v1 diagram generator; removing them entirely is P5/P6's call because they are still useful to the `explore` skill, app-spec format migration (the new AST has no `AppSpec` types; P4 keeps the v1 `app_parser` / `app_validator` pair behind the `register_app_tools` entry points and treats them as a black box — a dedicated plan will replace them later), skill markdown updates (P5), README / docs updates (P6), v1 module deletion (P7), new validator rules (including the still-deferred C8), grammar changes, AST type changes.

**Spec reference:** [`docs/superpowers/specs/2026-04-10-paper-alignment-design.md`](../specs/2026-04-10-paper-alignment-design.md) §5.1 (MCP tools table), §5.3 (explicitly out of scope), §4.4 (data flow: `load_workspace` → `validate_workspace`).

**Starting state:** Branch `feat/p1-parser`, HEAD at tag `p3-workspace-loader-complete` (`afc9326`). `concept_lang.ast`, `concept_lang.parse`, `concept_lang.validate`, `concept_lang.loader`, and both positive-fixture workspaces exist. `uv run pytest` reports **206 passing**. The v1 modules (`concept_lang.parser`, `concept_lang.models`, `concept_lang.validator`, `concept_lang.diff`, `concept_lang.explorer`, `concept_lang.app_parser`, `concept_lang.app_validator`) are still untouched and still pass their own tests. The MCP tool layer (`concept_lang.server`, `concept_lang.tools/`, `concept_lang.resources`, `concept_lang.prompts`) still imports from v1 exclusively.

---

## File structure (what this plan creates or modifies)

```
architecture-ide/
  src/concept_lang/
    __init__.py                                    # MODIFY: drop v1 re-exports, keep v2 surface
    diff.py                                        # REWRITE: consume concept_lang.ast
    explorer.py                                    # REWRITE: consume concept_lang.ast, syncs-as-edges
    resources.py                                   # MODIFY: use load_workspace, new AST shape
    prompts.py                                     # MODIFY: update tool-name references
    server.py                                      # MODIFY: workspace_root, drop codegen_tools
    tools/
      __init__.py                                  # MODIFY: drop codegen, add sync_tools, workspace_tools
      _io.py                                       # REWRITE: workspace-root-aware helpers on new AST
      concept_tools.py                             # REWRITE: new AST + new validator
      sync_tools.py                                # CREATE: read_sync / write_sync / list_syncs / validate_sync
      workspace_tools.py                           # CREATE: validate_workspace + get_workspace_graph
      diff_tools.py                                # REWRITE: new AST
      explorer_tools.py                            # REWRITE: new AST
      diagram_tools.py                             # MODIFY: drop get_dependency_graph (moved), keep per-concept diagrams via v1 adapter
      scaffold_tools.py                            # UNCHANGED: payload builder, no parsing
      codegen_tools.py                             # UNCHANGED: removed from server registration, file stays
      app_tools.py                                 # MODIFY: workspace_root parameter, v1 internals preserved
    # v1 files STILL UNTOUCHED (but increasingly isolated):
    #   parser.py, models.py, validator.py, app_parser.py, app_validator.py
    #   diagrams/ (still consumes models.py; wrapped by a v1 adapter in diagram_tools)
    #   codegen/ (still consumes models.py; no longer exposed via MCP)
  tests/
    test_diff.py                                   # REWRITE: new AST types, same algorithm
    test_explorer.py                               # CREATE: new explorer tests (graph shape, syncs-as-edges)
    test_mcp_tools.py                              # CREATE: integration tests for the MCP tool layer
    fixtures/
      mcp/                                         # CREATE: tiny curated workspace for MCP tool tests
        clean/
          concepts/
            Counter.concept
          syncs/
            log.sync
        with_error/
          concepts/
            Counter.concept                        # has C5 (missing purpose)
          syncs/
            log.sync
        empty/
          concepts/
            .gitkeep
          syncs/
            .gitkeep
    # v1 tests STILL UNTOUCHED:
    #   test_validator.py (v1 validator)
```

**All commands below assume the working directory is `architecture-ide/`** (the package root with `pyproject.toml`). All paths in Files sections are relative to that directory.

---

**Design decisions (made and justified up front; later tasks reference them by letter):**

- **(A) In-place rewrites for `diff.py` and `explorer.py`.** Both modules are rewritten in the same file, with their test files rewritten in the same commit. The alternative — writing `diff_v2.py` / `explorer_v2.py` alongside v1 and swapping at the end of P4 — would double the review surface and leave dead code around until P7. Because these modules each have a single caller (`diff_tools.py` / `explorer_tools.py`) and both callers are rewired inside P4, a sandwich commit structure works: first rewrite the module, then rewrite its test file against the new AST, then rewire its MCP caller. Each commit leaves the test suite green. The v1 `diff` / `explorer` code is simply gone after the rewrite tasks — there is no `_v1` suffix fallback.

- **(B) Workspace root vs. concepts dir.** The current MCP server takes a `concepts_dir` string and passes it to every tool. `load_workspace(root)` expects a root with `concepts/` and `syncs/` subdirectories. P4 introduces `workspace_root: str` as the new canonical parameter and keeps backward compatibility for the existing `CONCEPTS_DIR` environment variable: when `CONCEPTS_DIR` points to a directory that contains `.concept` files directly (no `concepts/` subdir), the tool layer treats the **parent** of that directory as the workspace root. A helper `_resolve_workspace_root(raw: str) -> Path` encapsulates the heuristic. Rationale: users already have MCP server installations set to `CONCEPTS_DIR=./concepts`; silently accepting that layout avoids breaking them. New installs should set `WORKSPACE_DIR` (also honored) pointing at the project root. Both env vars map to the same `workspace_root` internally. Document both in `server.py` and the docstring of `_resolve_workspace_root`.

- **(C) Single shared loader cache per tool-layer call.** Every tool that needs the workspace calls `_load_workspace(workspace_root)` (a module-level helper in `tools/_io.py`). The helper simply delegates to `concept_lang.loader.load_workspace` and returns `(Workspace, list[Diagnostic])`. There is no persistent cache across tool calls — each MCP tool invocation reloads from disk. Rationale: MCP tool calls are already rare (seconds apart at best); a persistent cache would introduce staleness bugs for the `write_*` tools and is not worth the complexity. If a future profile shows this is a bottleneck, a mtime-based cache can drop in later.

- **(D) Tool file layout.** The existing `tools/` directory contains one file per category: `concept_tools.py`, `diff_tools.py`, `explorer_tools.py`, `diagram_tools.py`, `scaffold_tools.py`, `codegen_tools.py`, `app_tools.py`. P4 adds `sync_tools.py` and `workspace_tools.py` as sibling files — one per category, **not** one per tool. `workspace_tools.py` hosts both `validate_workspace` and `get_workspace_graph` because both operate on the whole `Workspace` value. `sync_tools.py` hosts `read_sync` / `write_sync` / `list_syncs` / `validate_sync`. Rationale: 10+ separate files (one per tool) would fragment shared helpers; the category grouping keeps related concerns co-located and mirrors the existing layout.

- **(E) `get_workspace_graph` edge semantics.** The old `get_dependency_graph` (in `diagram_tools.py`) built a Mermaid `graph TD` where edges were inferred from each concept's embedded `sync` clauses (v1 `SyncClause.trigger_concept`). In v2, syncs are standalone `.sync` files and the `trigger_concept` information is on `SyncAST.when[*].concept`. The new `get_workspace_graph` builds a Mermaid graph where **each sync contributes one labeled edge** from the first `when` concept to each `then` concept. Self-loops (when == then on the same concept) are rendered as `A ->|sync SyncName| A`. Multiple `when` concepts in a single sync are handled by emitting one edge per `(when_concept, then_concept)` pair. Rationale: this matches spec §5.1's description "nodes are concepts, edges are syncs" literally and gives the `explore` skill a well-defined hook for clicking an edge to open the sync file.

- **(F) `get_dependency_graph` backward-compat alias.** The old tool name is kept as an alias that calls the new `get_workspace_graph` implementation with a deprecation comment in its docstring: `"Deprecated: use get_workspace_graph. Removed in P7."`. The alias lives in `workspace_tools.py` next to its replacement and gets a single test pinning that the alias returns the same string as `get_workspace_graph()`. Rationale: minimizes the risk that an external skill or manual MCP client silently breaks; the alias is cheap and clearly marked for P7 removal.

- **(G) `validate_concept` tool signature.** The old tool took `source: str` and parsed + validated it in memory. The new tool keeps the same signature (`source: str`) but internally: (1) writes the source to a temp `.concept` file, (2) calls `validate_concept_file(path)` which parses and runs C1–C9 (minus C8), (3) if the source parsed, loads the surrounding workspace via `load_workspace(workspace_root)`, substitutes the current concept's AST into the workspace (by `ast.name`), and runs `validate_workspace` to catch cross-reference diagnostics (S1/S2), (4) returns the combined diagnostic list. The temp file is deleted in a `finally`. Rationale: `validate_concept_file` is already the single source of truth for C-rules on a file; piggybacking on it avoids a second code path. The "substitute then re-validate" step gives users the same cross-ref feedback they get today from the v1 tool.

- **(H) `validate_sync` tool signature.** Same pattern as (G), but calls `validate_sync_file(path, extra_concepts=ws.concepts)` so that S1 / S2 resolve against the existing concepts in the workspace. Rationale: parallel structure to `validate_concept`.

- **(I) `read_concept` / `read_sync` return shape.** Both return `json.dumps({"source": <raw>, "ast": <ast.model_dump(exclude={"source"})>})`. The `source` field mirrors the v1 tool contract. The `ast` field uses the new `concept_lang.ast` shape. Rationale: minimal surface change for callers — the existing MCP client code that reads `result["source"]` keeps working; the `result["ast"]` payload is now the new AST shape and P5's skill update absorbs the shape change.

- **(J) `list_concepts` vs. `list_syncs` scope.** Both read from the workspace on disk via the canonical subdirectories (`<root>/concepts/*.concept`, `<root>/syncs/*.sync`). They **do not** call `load_workspace` — they just glob, because parsing is wasted work for a name listing. The sorted list of bare names (without extension) is returned as a JSON array. Rationale: cheap, fast, and matches the existing `list_concepts` contract.

- **(K) `write_concept` / `write_sync` validation.** Both run their single-file validator (`validate_concept_file` / `validate_sync_file` on the temp file approach from (G)) before writing to disk. If any `error`-severity diagnostic fires, the write is refused and the diagnostics are returned in the response body with `"written": false`. Otherwise the file is written and `"written": true` plus the final path is returned. Rationale: matches v1 behavior (validate-before-write) and makes cross-ref errors (S1/S2) visible at write time.

- **(L) `explorer.py` graph shape contract.** The D3 graph data has `nodes: [{id, purpose, stateCount, actionCount, external?}]` and `edges: [{source, target, type: "sync", syncName, internal}]` where `syncName` is the sync file's declared `SyncAST.name`. Param edges (v1's `{type: "param"}`) are deprecated — the new AST models params as bare type variable strings on the concept, and the spec wants concept-to-concept edges to be syncs only. A future enhancement can add a `{type: "param"}` layer if the methodology calls for it; P4 drops param edges from the graph because it would conflict with the "edges are syncs" semantics in spec §5.1. Rationale: one kind of edge per plane makes the graph unambiguous.

- **(M) App-spec tools stay on v1 unchanged.** `register_app_tools(mcp, workspace_root)` keeps calling `app_parser.parse_app_file` / `app_validator.validate_app` and loading concepts via the v1 `parser.parse_file` helper. The new `tools/_io.py` does not provide any v1 loading helpers, so `app_tools.py` keeps its own tiny `_load_declared_concepts_v1` helper that imports from `concept_lang.parser` and `concept_lang.models` directly. Rationale: the v1 app format is untouched until a dedicated plan migrates it; keeping the app tool path self-contained makes the eventual removal a single-file change.

- **(N) `concept_lang.__init__` surface cleanup.** P4 drops the v1 re-exports from `concept_lang.__init__` (`ConceptAST`, `StateDecl`, `Action`, `PrePost`, `SyncClause`, `SyncInvocation`, `ParseError`, `parse_concept`, `parse_file`, `ValidationIssue`, `ValidationResult`, `Severity`, `validate_concept_ast`, `validate_workspace`) and replaces them with v2 re-exports: `ConceptAST`, `SyncAST`, `Workspace` from `concept_lang.ast`, `Diagnostic` from `concept_lang.validate`, `load_workspace` from `concept_lang.loader`, `parse_concept_source`, `parse_concept_file`, `parse_sync_source`, `parse_sync_file` from `concept_lang.parse`, `validate_workspace`, `validate_concept_file`, `validate_sync_file` from `concept_lang.validate`, and `create_server` from `concept_lang.server`. The v1 names are gone from the package-level namespace but still reachable via their fully-qualified module paths (`concept_lang.models.ConceptAST`, etc.), which is enough for the v1 tests and the app-spec path to keep working. Rationale: the package top-level is the public API; migrating it now (P4) rather than at deletion time (P7) gives downstream consumers one coherent import story for the whole v2 phase.

- **(O) Test strategy for the MCP tool layer.** Each MCP tool function is tested by calling the inner Python function directly (not through the MCP protocol). The current `register_*_tools` shape uses closures and a decorator (`@mcp.tool(...)`) which does not return the inner function. Rather than refactor, tests use a fake `FastMCP`-like object (`_FakeMCP`) that records every `@mcp.tool(...)` decoration and exposes the decorated functions in a `.tools` dict. This fake lives in `tests/test_mcp_tools.py` as a private helper. Rationale: the fake is 20 lines, it preserves the existing `register_*_tools` signature, and the tests exercise the exact function the real MCP server registers.

- **(P) No validator rule changes, no AST changes, no grammar changes.** P4 is a wiring phase. If a task finds that the rule set or the AST is missing something, flag it in the "What's next" section at the bottom of this plan instead of patching in place. Rationale: P4 has enough surface area already; keeping the contract surface stable across phases keeps each phase small enough to review.

**Diagnostic handling contract (used throughout the later tasks):**

> Every MCP tool that returns validation feedback serializes diagnostics via `Diagnostic.model_dump(mode="json")`. The response JSON for a tool call that includes validation always has a top-level `diagnostics` key (a list, possibly empty) in addition to whatever tool-specific fields the tool wants to return. Error-level diagnostics set `"valid": false` in the response; otherwise `"valid": true`. `write_*` tools additionally set `"written": true|false` based on whether the write actually happened.

---

## Task 1: Rewrite `diff.py` against the new AST

The v1 `diff.py` consumes `concept_lang.models.ConceptAST`, `StateDecl`, `Action`, `SyncClause`. The new AST drops `ConceptAST.sync` entirely (syncs are separate files now), and `ActionCase` replaces `PrePost`. The diff engine needs to compute `state`, `action`, and `sync` changes against new AST values. For sync diffs, P4's diff operates on two `SyncAST` values (not on concepts' embedded sync clauses). For concept diffs, the sync section is simply gone.

**Files:**
- Modify: `src/concept_lang/diff.py`

- [ ] **Step 1.1: Replace the file with the v2 diff engine**

Replace the entire contents of `src/concept_lang/diff.py` with the following.

```python
"""
Concept diff and evolution tracking (v2 — consumes concept_lang.ast).

Structural diff of concept versions: detect state added/removed/renamed,
actions changed (by case shape), effects changed, operational principle
changed. The sync section moved out of concepts in 0.2.0 — use
`diff_syncs(old_sync, new_sync)` on two `SyncAST` values for sync-level
changes.

Answers: what changed, what downstream syncs are broken, what concepts
are affected. Foundation for safe evolution of concept-based systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from concept_lang.ast import (
    Action,
    ActionCase,
    ConceptAST,
    OperationalPrinciple,
    OPStep,
    StateDecl,
    SyncAST,
    Workspace,
)


class ChangeKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    RENAMED = "renamed"


@dataclass
class StateChange:
    kind: ChangeKind
    name: str
    old_name: str | None = None
    old_type_expr: str | None = None
    new_type_expr: str | None = None

    def to_dict(self) -> dict:
        d: dict = {"kind": self.kind.value, "name": self.name}
        if self.old_name:
            d["old_name"] = self.old_name
        if self.old_type_expr is not None:
            d["old_type_expr"] = self.old_type_expr
        if self.new_type_expr is not None:
            d["new_type_expr"] = self.new_type_expr
        return d


@dataclass
class ActionChange:
    kind: ChangeKind
    name: str
    details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict = {"kind": self.kind.value, "name": self.name}
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class OPChange:
    """A single edit in the operational principle step list."""
    kind: ChangeKind
    step_index: int
    description: str

    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "step_index": self.step_index,
            "description": self.description,
        }


@dataclass
class BrokenSync:
    """A sync in the workspace that is invalidated by a concept diff."""
    sync_name: str
    reason: str

    def to_dict(self) -> dict:
        return {"sync": self.sync_name, "reason": self.reason}


@dataclass
class ConceptDiff:
    """Full structural diff between two versions of a concept."""
    concept_name: str
    params_changed: bool = False
    old_params: list[str] = field(default_factory=list)
    new_params: list[str] = field(default_factory=list)
    purpose_changed: bool = False
    state_changes: list[StateChange] = field(default_factory=list)
    action_changes: list[ActionChange] = field(default_factory=list)
    op_changes: list[OPChange] = field(default_factory=list)
    broken_syncs: list[BrokenSync] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return (
            self.params_changed
            or self.purpose_changed
            or bool(self.state_changes)
            or bool(self.action_changes)
            or bool(self.op_changes)
        )

    def to_dict(self) -> dict:
        d: dict = {"concept": self.concept_name, "has_changes": self.has_changes}
        if self.params_changed:
            d["params"] = {"old": self.old_params, "new": self.new_params}
        if self.purpose_changed:
            d["purpose_changed"] = True
        if self.state_changes:
            d["state_changes"] = [c.to_dict() for c in self.state_changes]
        if self.action_changes:
            d["action_changes"] = [c.to_dict() for c in self.action_changes]
        if self.op_changes:
            d["op_changes"] = [c.to_dict() for c in self.op_changes]
        if self.broken_syncs:
            d["broken_syncs"] = [b.to_dict() for b in self.broken_syncs]
        return d


@dataclass
class SyncDiff:
    """Structural diff between two versions of a single `.sync` file."""
    sync_name: str
    when_changed: bool = False
    where_changed: bool = False
    then_changed: bool = False

    @property
    def has_changes(self) -> bool:
        return self.when_changed or self.where_changed or self.then_changed

    def to_dict(self) -> dict:
        return {
            "sync": self.sync_name,
            "has_changes": self.has_changes,
            "when_changed": self.when_changed,
            "where_changed": self.where_changed,
            "then_changed": self.then_changed,
        }


# ---------------------------------------------------------------------------
# Concept diff
# ---------------------------------------------------------------------------


def diff_concepts(old: ConceptAST, new: ConceptAST) -> ConceptDiff:
    """Compute a structural diff between two versions of a concept."""
    result = ConceptDiff(concept_name=new.name)

    if old.params != new.params:
        result.params_changed = True
        result.old_params = old.params
        result.new_params = new.params

    if old.purpose.strip() != new.purpose.strip():
        result.purpose_changed = True

    result.state_changes = _diff_state(old.state, new.state)
    result.action_changes = _diff_actions(old.actions, new.actions)
    result.op_changes = _diff_op_principle(
        old.operational_principle, new.operational_principle
    )

    return result


def _diff_state(old: list[StateDecl], new: list[StateDecl]) -> list[StateChange]:
    changes: list[StateChange] = []
    old_by_name = {s.name: s for s in old}
    new_by_name = {s.name: s for s in new}

    old_names = set(old_by_name)
    new_names = set(new_by_name)

    # Detect renames: same type_expr, one removed + one added
    removed = old_names - new_names
    added = new_names - old_names
    renamed: set[tuple[str, str]] = set()

    for r in list(removed):
        for a in list(added):
            if old_by_name[r].type_expr == new_by_name[a].type_expr:
                renamed.add((r, a))
                removed.discard(r)
                added.discard(a)
                break

    for old_name, new_name in renamed:
        changes.append(StateChange(
            kind=ChangeKind.RENAMED,
            name=new_name,
            old_name=old_name,
            old_type_expr=old_by_name[old_name].type_expr,
            new_type_expr=new_by_name[new_name].type_expr,
        ))

    for name in sorted(removed):
        changes.append(StateChange(
            kind=ChangeKind.REMOVED,
            name=name,
            old_type_expr=old_by_name[name].type_expr,
        ))

    for name in sorted(added):
        changes.append(StateChange(
            kind=ChangeKind.ADDED,
            name=name,
            new_type_expr=new_by_name[name].type_expr,
        ))

    for name in sorted(old_names & new_names):
        if old_by_name[name].type_expr != new_by_name[name].type_expr:
            changes.append(StateChange(
                kind=ChangeKind.MODIFIED,
                name=name,
                old_type_expr=old_by_name[name].type_expr,
                new_type_expr=new_by_name[name].type_expr,
            ))

    return changes


def _diff_actions(old: list[Action], new: list[Action]) -> list[ActionChange]:
    changes: list[ActionChange] = []
    old_by_name = {a.name: a for a in old}
    new_by_name = {a.name: a for a in new}

    old_names = set(old_by_name)
    new_names = set(new_by_name)

    for name in sorted(old_names - new_names):
        changes.append(ActionChange(kind=ChangeKind.REMOVED, name=name))

    for name in sorted(new_names - old_names):
        changes.append(ActionChange(kind=ChangeKind.ADDED, name=name))

    for name in sorted(old_names & new_names):
        details = _compare_action(old_by_name[name], new_by_name[name])
        if details:
            changes.append(ActionChange(
                kind=ChangeKind.MODIFIED, name=name, details=details
            ))

    return changes


def _case_signature(case: ActionCase) -> tuple[str, str]:
    """Canonical shape of a case's inputs/outputs, ignoring body/effects."""
    ins = ", ".join(f"{tn.name}: {tn.type_expr}" for tn in case.inputs)
    outs = ", ".join(f"{tn.name}: {tn.type_expr}" for tn in case.outputs)
    return (ins, outs)


def _compare_action(old: Action, new: Action) -> list[str]:
    details: list[str] = []

    if len(old.cases) != len(new.cases):
        details.append(f"case count: {len(old.cases)} -> {len(new.cases)}")
        return details

    for idx, (oc, nc) in enumerate(zip(old.cases, new.cases)):
        old_sig = _case_signature(oc)
        new_sig = _case_signature(nc)
        if old_sig != new_sig:
            details.append(
                f"case {idx} signature: ({old_sig[0]}) => ({old_sig[1]}) "
                f"-> ({new_sig[0]}) => ({new_sig[1]})"
            )
            continue

        old_effects = [e.raw for e in oc.effects]
        new_effects = [e.raw for e in nc.effects]
        if old_effects != new_effects:
            details.append(f"case {idx} effects changed")

        if oc.body != nc.body:
            details.append(f"case {idx} body changed")

    return details


def _diff_op_principle(
    old: OperationalPrinciple, new: OperationalPrinciple
) -> list[OPChange]:
    """Coarse diff: per-step index, report added / removed / modified."""
    changes: list[OPChange] = []
    n_old = len(old.steps)
    n_new = len(new.steps)
    common = min(n_old, n_new)

    for idx in range(common):
        if _op_step_differs(old.steps[idx], new.steps[idx]):
            changes.append(OPChange(
                kind=ChangeKind.MODIFIED,
                step_index=idx,
                description=(
                    f"step {idx}: {old.steps[idx].keyword} "
                    f"{old.steps[idx].action_name} changed"
                ),
            ))

    for idx in range(common, n_old):
        changes.append(OPChange(
            kind=ChangeKind.REMOVED,
            step_index=idx,
            description=f"step {idx}: {old.steps[idx].action_name} removed",
        ))

    for idx in range(common, n_new):
        changes.append(OPChange(
            kind=ChangeKind.ADDED,
            step_index=idx,
            description=f"step {idx}: {new.steps[idx].action_name} added",
        ))

    return changes


def _op_step_differs(a: OPStep, b: OPStep) -> bool:
    return (
        a.keyword != b.keyword
        or a.action_name != b.action_name
        or a.inputs != b.inputs
        or a.outputs != b.outputs
    )


# ---------------------------------------------------------------------------
# Sync diff
# ---------------------------------------------------------------------------


def diff_syncs(old: SyncAST, new: SyncAST) -> SyncDiff:
    """Compute a structural diff between two versions of a sync."""
    result = SyncDiff(sync_name=new.name)

    if [p.model_dump() for p in old.when] != [p.model_dump() for p in new.when]:
        result.when_changed = True
    if [p.model_dump() for p in old.then] != [p.model_dump() for p in new.then]:
        result.then_changed = True

    old_where = old.where.model_dump() if old.where else None
    new_where = new.where.model_dump() if new.where else None
    if old_where != new_where:
        result.where_changed = True

    return result


# ---------------------------------------------------------------------------
# Impact analysis: find broken syncs in the workspace
# ---------------------------------------------------------------------------


def find_broken_syncs(
    diff: ConceptDiff,
    workspace: Workspace,
) -> list[BrokenSync]:
    """
    Given a diff of one concept, find syncs in the workspace that are
    now broken by the changes.
    """
    broken: list[BrokenSync] = []
    concept_name = diff.concept_name

    removed_actions: set[str] = set()
    modified_action_cases: set[str] = set()

    for ac in diff.action_changes:
        if ac.kind == ChangeKind.REMOVED:
            removed_actions.add(ac.name)
        elif ac.kind == ChangeKind.MODIFIED:
            if any("signature" in d for d in ac.details):
                modified_action_cases.add(ac.name)

    for sync_name, sync in workspace.syncs.items():
        # Check every action pattern in when/then for references to
        # Concept/action where Concept == concept_name.
        all_patterns = list(sync.when) + list(sync.then)
        for pat in all_patterns:
            if pat.concept != concept_name:
                continue
            if pat.action in removed_actions:
                broken.append(BrokenSync(
                    sync_name=sync_name,
                    reason=(
                        f"Action '{pat.action}' was removed from "
                        f"'{concept_name}'"
                    ),
                ))
                break
            if pat.action in modified_action_cases:
                broken.append(BrokenSync(
                    sync_name=sync_name,
                    reason=(
                        f"Action '{pat.action}' in '{concept_name}' "
                        f"had its case signature changed"
                    ),
                ))
                break

    return broken


def diff_concepts_with_impact(
    old: ConceptAST,
    new: ConceptAST,
    workspace: Workspace | None = None,
) -> ConceptDiff:
    """Diff two concept versions and optionally find broken downstream syncs."""
    result = diff_concepts(old, new)
    if workspace is not None:
        result.broken_syncs = find_broken_syncs(result, workspace)
    return result
```

- [ ] **Step 1.2: Run the existing diff test file — it will fail**

Run: `uv run pytest tests/test_diff.py -v`
Expected: every test fails with `ImportError` because `concept_lang.models` no longer re-exports the fields the tests build against. This is expected — Task 2 rewrites the test file against the new AST.

Do **not** try to fix `test_diff.py` here. Leave the red state for the commit.

- [ ] **Step 1.3: Run the other test files to confirm the diff rewrite did not break them**

Run: `uv run pytest --ignore=tests/test_diff.py -q`
Expected: 206-N passing, where N is the test count in `test_diff.py`. No new failures in any other file.

- [ ] **Step 1.4: Commit**

```bash
git add src/concept_lang/diff.py
git commit -m "refactor(diff): rewrite against new AST (test_diff red until task 2)"
```

---

## Task 2: Rewrite `tests/test_diff.py` against the new AST

**Files:**
- Modify: `tests/test_diff.py`

- [ ] **Step 2.1: Replace the test file**

Replace `tests/test_diff.py` with the following. The tests cover the same algorithmic cases as v1 (no-change, params, purpose, state, actions) plus new coverage for operational-principle diffs and the new `diff_syncs` / workspace-aware impact analysis.

```python
"""Tests for concept diff and evolution tracking (v2 — consumes concept_lang.ast)."""

from concept_lang.ast import (
    Action,
    ActionCase,
    ConceptAST,
    OperationalPrinciple,
    OPStep,
    StateDecl,
    SyncAST,
    ActionPattern,
    TypedName,
    Workspace,
)
from concept_lang.diff import (
    ChangeKind,
    ConceptDiff,
    SyncDiff,
    diff_concepts,
    diff_concepts_with_impact,
    diff_syncs,
    find_broken_syncs,
)


def _empty_op() -> OperationalPrinciple:
    return OperationalPrinciple(steps=[])


def _make_concept(
    name: str = "Test",
    params: list[str] | None = None,
    state: list[StateDecl] | None = None,
    actions: list[Action] | None = None,
    op: OperationalPrinciple | None = None,
    purpose: str = "test concept",
) -> ConceptAST:
    return ConceptAST(
        name=name,
        params=params or [],
        purpose=purpose,
        state=state or [],
        actions=actions or [],
        operational_principle=op or _empty_op(),
        source="",
    )


def _single_case_action(name: str, ins: list[tuple[str, str]], outs: list[tuple[str, str]]) -> Action:
    case = ActionCase(
        inputs=[TypedName(name=n, type_expr=t) for n, t in ins],
        outputs=[TypedName(name=n, type_expr=t) for n, t in outs],
        body=[],
    )
    return Action(name=name, cases=[case])


# ---------------------------------------------------------------------------
# No changes
# ---------------------------------------------------------------------------


class TestNoChanges:
    def test_identical_concepts(self):
        c = _make_concept(
            state=[StateDecl(name="items", type_expr="set Item")],
            actions=[_single_case_action("add", [("x", "Item")], [("x", "Item")])],
        )
        diff = diff_concepts(c, c)
        assert not diff.has_changes

    def test_to_dict_minimal(self):
        c = _make_concept()
        diff = diff_concepts(c, c)
        d = diff.to_dict()
        assert d["has_changes"] is False
        assert "state_changes" not in d


# ---------------------------------------------------------------------------
# Param changes
# ---------------------------------------------------------------------------


class TestParamChanges:
    def test_params_added(self):
        old = _make_concept(params=["U"])
        new = _make_concept(params=["U", "R"])
        diff = diff_concepts(old, new)
        assert diff.params_changed
        assert diff.old_params == ["U"]
        assert diff.new_params == ["U", "R"]

    def test_params_removed(self):
        old = _make_concept(params=["U", "R"])
        new = _make_concept(params=["U"])
        diff = diff_concepts(old, new)
        assert diff.params_changed

    def test_params_unchanged(self):
        old = _make_concept(params=["U"])
        new = _make_concept(params=["U"])
        diff = diff_concepts(old, new)
        assert not diff.params_changed


# ---------------------------------------------------------------------------
# Purpose changes
# ---------------------------------------------------------------------------


class TestPurposeChanges:
    def test_purpose_edit(self):
        old = _make_concept(purpose="old")
        new = _make_concept(purpose="new")
        diff = diff_concepts(old, new)
        assert diff.purpose_changed

    def test_purpose_whitespace_only_ignored(self):
        old = _make_concept(purpose="hello")
        new = _make_concept(purpose="  hello  ")
        diff = diff_concepts(old, new)
        assert not diff.purpose_changed


# ---------------------------------------------------------------------------
# State changes
# ---------------------------------------------------------------------------


class TestStateChanges:
    def test_state_added(self):
        old = _make_concept()
        new = _make_concept(state=[StateDecl(name="items", type_expr="set Item")])
        diff = diff_concepts(old, new)
        assert len(diff.state_changes) == 1
        assert diff.state_changes[0].kind == ChangeKind.ADDED
        assert diff.state_changes[0].name == "items"

    def test_state_removed(self):
        old = _make_concept(state=[StateDecl(name="items", type_expr="set Item")])
        new = _make_concept()
        diff = diff_concepts(old, new)
        assert diff.state_changes[0].kind == ChangeKind.REMOVED

    def test_state_type_modified(self):
        old = _make_concept(state=[StateDecl(name="items", type_expr="set Item")])
        new = _make_concept(state=[StateDecl(name="items", type_expr="set OtherItem")])
        diff = diff_concepts(old, new)
        assert diff.state_changes[0].kind == ChangeKind.MODIFIED
        assert diff.state_changes[0].old_type_expr == "set Item"
        assert diff.state_changes[0].new_type_expr == "set OtherItem"

    def test_state_renamed(self):
        """Same type_expr but different name → detected as rename."""
        old = _make_concept(state=[StateDecl(name="items", type_expr="set Item")])
        new = _make_concept(state=[StateDecl(name="records", type_expr="set Item")])
        diff = diff_concepts(old, new)
        assert len(diff.state_changes) == 1
        assert diff.state_changes[0].kind == ChangeKind.RENAMED
        assert diff.state_changes[0].old_name == "items"
        assert diff.state_changes[0].name == "records"


# ---------------------------------------------------------------------------
# Action changes
# ---------------------------------------------------------------------------


class TestActionChanges:
    def test_action_added(self):
        old = _make_concept()
        new = _make_concept(actions=[_single_case_action("add", [], [])])
        diff = diff_concepts(old, new)
        assert diff.action_changes[0].kind == ChangeKind.ADDED
        assert diff.action_changes[0].name == "add"

    def test_action_removed(self):
        old = _make_concept(actions=[_single_case_action("add", [], [])])
        new = _make_concept()
        diff = diff_concepts(old, new)
        assert diff.action_changes[0].kind == ChangeKind.REMOVED

    def test_action_signature_modified(self):
        old = _make_concept(actions=[_single_case_action("add", [("x", "Item")], [])])
        new = _make_concept(actions=[_single_case_action("add", [("x", "Widget")], [])])
        diff = diff_concepts(old, new)
        assert diff.action_changes[0].kind == ChangeKind.MODIFIED
        assert any("signature" in d for d in diff.action_changes[0].details)

    def test_action_case_count_changed(self):
        old_action = _single_case_action("add", [], [])
        extra = ActionCase(
            inputs=[],
            outputs=[TypedName(name="error", type_expr="string")],
            body=["error case"],
        )
        new_action = Action(name="add", cases=[old_action.cases[0], extra])
        old = _make_concept(actions=[old_action])
        new = _make_concept(actions=[new_action])
        diff = diff_concepts(old, new)
        assert diff.action_changes[0].kind == ChangeKind.MODIFIED
        assert any("case count" in d for d in diff.action_changes[0].details)


# ---------------------------------------------------------------------------
# Operational principle changes
# ---------------------------------------------------------------------------


class TestOPChanges:
    def test_op_step_added(self):
        old = _make_concept()
        new_op = OperationalPrinciple(steps=[
            OPStep(
                keyword="after",
                action_name="add",
                inputs=[("x", "x1")],
                outputs=[],
            ),
        ])
        new = _make_concept(op=new_op)
        diff = diff_concepts(old, new)
        assert len(diff.op_changes) == 1
        assert diff.op_changes[0].kind == ChangeKind.ADDED
        assert diff.op_changes[0].step_index == 0

    def test_op_step_modified(self):
        old_op = OperationalPrinciple(steps=[
            OPStep(keyword="after", action_name="add", inputs=[("x", "x1")], outputs=[]),
        ])
        new_op = OperationalPrinciple(steps=[
            OPStep(keyword="after", action_name="add", inputs=[("x", "x2")], outputs=[]),
        ])
        diff = diff_concepts(_make_concept(op=old_op), _make_concept(op=new_op))
        assert len(diff.op_changes) == 1
        assert diff.op_changes[0].kind == ChangeKind.MODIFIED

    def test_op_step_removed(self):
        old_op = OperationalPrinciple(steps=[
            OPStep(keyword="after", action_name="add", inputs=[], outputs=[]),
        ])
        diff = diff_concepts(_make_concept(op=old_op), _make_concept())
        assert diff.op_changes[0].kind == ChangeKind.REMOVED


# ---------------------------------------------------------------------------
# Sync diff
# ---------------------------------------------------------------------------


def _pat(concept: str, action: str) -> ActionPattern:
    return ActionPattern(
        concept=concept,
        action=action,
        input_pattern=[],
        output_pattern=[],
    )


class TestSyncDiff:
    def test_identical_syncs_no_changes(self):
        s = SyncAST(
            name="Hello",
            when=[_pat("A", "do")],
            where=None,
            then=[_pat("B", "do")],
            source="",
        )
        d = diff_syncs(s, s)
        assert not d.has_changes

    def test_when_changed(self):
        old = SyncAST(name="Hello", when=[_pat("A", "do")], then=[_pat("B", "do")], source="")
        new = SyncAST(name="Hello", when=[_pat("A", "other")], then=[_pat("B", "do")], source="")
        d = diff_syncs(old, new)
        assert d.when_changed
        assert not d.then_changed

    def test_then_changed(self):
        old = SyncAST(name="Hello", when=[_pat("A", "do")], then=[_pat("B", "do")], source="")
        new = SyncAST(name="Hello", when=[_pat("A", "do")], then=[_pat("C", "do")], source="")
        d = diff_syncs(old, new)
        assert d.then_changed


# ---------------------------------------------------------------------------
# Impact analysis
# ---------------------------------------------------------------------------


class TestImpactAnalysis:
    def test_action_removal_breaks_downstream_sync(self):
        old_concept = _make_concept(
            name="Auth",
            actions=[
                _single_case_action("login", [("u", "User")], [("u", "User")]),
                _single_case_action("logout", [("u", "User")], []),
            ],
        )
        new_concept = _make_concept(
            name="Auth",
            actions=[_single_case_action("login", [("u", "User")], [("u", "User")])],
        )
        sync = SyncAST(
            name="OnLogout",
            when=[_pat("Auth", "logout")],
            where=None,
            then=[_pat("Session", "close")],
            source="",
        )
        ws = Workspace(concepts={"Auth": new_concept}, syncs={"OnLogout": sync})

        diff = diff_concepts_with_impact(old_concept, new_concept, ws)
        assert len(diff.broken_syncs) == 1
        assert diff.broken_syncs[0].sync_name == "OnLogout"
        assert "logout" in diff.broken_syncs[0].reason

    def test_unrelated_sync_not_broken(self):
        old = _make_concept(name="Auth", actions=[_single_case_action("login", [], [])])
        new = _make_concept(name="Auth")
        sync = SyncAST(
            name="Unrelated",
            when=[_pat("Other", "foo")],
            then=[_pat("Other", "bar")],
            source="",
        )
        ws = Workspace(concepts={"Auth": new}, syncs={"Unrelated": sync})
        diff = diff_concepts_with_impact(old, new, ws)
        assert diff.broken_syncs == []

    def test_signature_change_breaks_downstream(self):
        old = _make_concept(
            name="Auth",
            actions=[_single_case_action("login", [("u", "User")], [])],
        )
        new = _make_concept(
            name="Auth",
            actions=[_single_case_action("login", [("u", "Admin")], [])],
        )
        sync = SyncAST(
            name="OnLogin",
            when=[_pat("Auth", "login")],
            then=[_pat("Session", "open")],
            source="",
        )
        ws = Workspace(concepts={"Auth": new}, syncs={"OnLogin": sync})
        diff = diff_concepts_with_impact(old, new, ws)
        assert len(diff.broken_syncs) == 1
        assert "signature" in diff.broken_syncs[0].reason or "case" in diff.broken_syncs[0].reason
```

- [ ] **Step 2.2: Run the rewritten test file**

Run: `uv run pytest tests/test_diff.py -v`
Expected: every test passes.

- [ ] **Step 2.3: Run the full project test suite**

Run: `uv run pytest -q`
Expected: 206 - (old test_diff.py count) + (new test_diff.py count) passing. No failures in any other file.

- [ ] **Step 2.4: Commit**

```bash
git add tests/test_diff.py
git commit -m "test(diff): rewrite tests against new AST"
```

---

## Task 3: Rewrite `explorer.py` against the new AST

Per decision (L): the D3 graph is now syncs-as-edges. Per-concept Mermaid diagrams (`state_machine`, `entity_diagram`) still live in `concept_lang.diagrams` and still consume v1 `models.ConceptAST`. The explorer bridges this by converting each new `ConceptAST` to a v1 `models.ConceptAST` via a small adapter defined inline in `explorer.py`. This adapter is marked as temporary and will be removed when the `diagrams/` module is migrated or deleted in P5/P6.

**Files:**
- Modify: `src/concept_lang/explorer.py`

- [ ] **Step 3.1: Replace the top of `explorer.py` with the v2 explorer core**

Open `src/concept_lang/explorer.py`. Replace the imports and every function above `_HTML_TEMPLATE` with the following. The `_HTML_TEMPLATE` string literal itself stays untouched — only the Python logic above it changes.

```python
"""
Generate a self-contained interactive HTML concept explorer (v2 — new AST).

Produces a single HTML file with embedded CSS and JavaScript that renders:
- A clickable concept graph: nodes are concepts, edges are syncs
- State machine diagram for selected concept (via v1 diagrams, temporarily)
- Entity/state detail panel
- Action browser (multi-case)
- Per-sync flow diagram (when → where → then)

Uses D3.js for force-directed graph layout and Mermaid for diagram rendering.
All workspace data is embedded as JSON so the page works offline.
"""

from __future__ import annotations

import json

from concept_lang.ast import (
    ActionPattern,
    ConceptAST,
    PatternField,
    SyncAST,
    Workspace,
)


# --- v1 adapter (temporary; removed when diagrams/ migrates) ----------------


def _to_v1_concept(c: ConceptAST):
    """
    Build a v1 `concept_lang.models.ConceptAST` from a v2 concept so the
    existing Mermaid diagram generators keep working until the diagrams/
    module migrates (P5 or later).

    The conversion is lossy: v2 multi-case actions collapse to a single v1
    action whose pre/post clauses come from the first case's effects.
    Operational principle is not represented in v1. Syncs are always empty
    because v2 holds them in separate files.
    """
    from concept_lang.models import (
        Action as V1Action,
        ConceptAST as V1ConceptAST,
        PrePost as V1PrePost,
        StateDecl as V1StateDecl,
    )

    v1_state = [V1StateDecl(name=s.name, type_expr=s.type_expr) for s in c.state]

    v1_actions: list = []
    for action in c.actions:
        first_case = action.cases[0]
        params = [f"{tn.name}: {tn.type_expr}" for tn in first_case.inputs]
        post_clauses = [e.raw for e in first_case.effects]
        v1_actions.append(V1Action(
            name=action.name,
            params=params,
            pre=None,
            post=V1PrePost(clauses=post_clauses) if post_clauses else None,
        ))

    return V1ConceptAST(
        name=c.name,
        params=c.params,
        purpose=c.purpose,
        state=v1_state,
        actions=v1_actions,
        sync=[],
        source=c.source,
    )


# --- concept JSON payload for the HTML ---------------------------------------


def _concept_to_dict(c: ConceptAST) -> dict:
    return {
        "name": c.name,
        "params": c.params,
        "purpose": c.purpose,
        "state": [{"name": s.name, "type_expr": s.type_expr} for s in c.state],
        "actions": [
            {
                "name": a.name,
                "cases": [
                    {
                        "inputs": [
                            {"name": tn.name, "type_expr": tn.type_expr}
                            for tn in case.inputs
                        ],
                        "outputs": [
                            {"name": tn.name, "type_expr": tn.type_expr}
                            for tn in case.outputs
                        ],
                        "body": case.body,
                        "effects": [e.raw for e in case.effects],
                    }
                    for case in a.cases
                ],
            }
            for a in c.actions
        ],
        "operational_principle": [
            {
                "keyword": step.keyword,
                "action_name": step.action_name,
                "inputs": step.inputs,
                "outputs": step.outputs,
            }
            for step in c.operational_principle.steps
        ],
    }


def _sync_to_dict(s: SyncAST) -> dict:
    return {
        "name": s.name,
        "when": [_pattern_to_dict(p) for p in s.when],
        "where": _where_to_dict(s),
        "then": [_pattern_to_dict(p) for p in s.then],
    }


def _pattern_to_dict(p: ActionPattern) -> dict:
    return {
        "concept": p.concept,
        "action": p.action,
        "input_pattern": [_field_to_dict(f) for f in p.input_pattern],
        "output_pattern": [_field_to_dict(f) for f in p.output_pattern],
    }


def _field_to_dict(f: PatternField) -> dict:
    return {"name": f.name, "kind": f.kind, "value": f.value}


def _where_to_dict(s: SyncAST) -> dict | None:
    if s.where is None:
        return None
    return {
        "queries": [
            {
                "concept": q.concept,
                "is_optional": q.is_optional,
                "triples": [
                    {"subject": t.subject, "predicate": t.predicate, "object": t.object}
                    for t in q.triples
                ],
            }
            for q in s.where.queries
        ],
        "binds": [
            {"expression": b.expression, "variable": b.variable}
            for b in s.where.binds
        ],
    }


# --- graph data: syncs as edges ---------------------------------------------


def _build_graph_data(workspace: Workspace) -> dict:
    """
    Build nodes and edges for the dependency graph.

    Nodes: one per concept. External references (a sync mentioning a
    concept that is not in the workspace) become `{external: True}` nodes
    so dangling references stay visible.

    Edges: one per (sync, when_concept, then_concept) triple. Each edge
    carries the sync name so the UI can link the edge back to its source
    file. Self-loops are allowed.
    """
    concept_names = set(workspace.concepts)
    nodes: list[dict] = []
    seen: set[str] = set()

    def add_node(name: str, *, external: bool = False) -> None:
        if name in seen:
            return
        seen.add(name)
        if external:
            nodes.append({"id": name, "external": True})
            return
        c = workspace.concepts[name]
        nodes.append({
            "id": name,
            "purpose": c.purpose,
            "stateCount": len(c.state),
            "actionCount": len(c.actions),
        })

    for name in sorted(concept_names):
        add_node(name)

    edges: list[dict] = []

    for sync_name in sorted(workspace.syncs):
        sync = workspace.syncs[sync_name]
        if not sync.when:
            continue
        when_concepts = sorted({p.concept for p in sync.when})
        then_concepts = sorted({p.concept for p in sync.then})

        for src in when_concepts:
            if src not in concept_names:
                add_node(src, external=True)
            for dst in then_concepts:
                if dst not in concept_names:
                    add_node(dst, external=True)
                edges.append({
                    "source": src,
                    "target": dst,
                    "type": "sync",
                    "syncName": sync_name,
                    "internal": src in concept_names and dst in concept_names,
                })

    return {"nodes": nodes, "edges": edges}


def _build_sync_index(workspace: Workspace) -> dict:
    """
    Build an index keyed by `concept.action` string, mapping to the syncs
    that mention that action in either `when` or `then`.
    """
    index: dict[str, list[dict]] = {}
    for sync_name, sync in workspace.syncs.items():
        for role, patterns in (("when", sync.when), ("then", sync.then)):
            for pat in patterns:
                key = f"{pat.concept}.{pat.action}"
                index.setdefault(key, []).append({
                    "sync": sync_name,
                    "role": role,
                })
    return index


# --- graph mermaid for the top-level view ------------------------------------


def _workspace_graph_mermaid(workspace: Workspace) -> str:
    """Mermaid `graph TD` for the workspace: concepts + syncs-as-edges."""
    lines = ["graph TD"]

    concept_names = set(workspace.concepts)
    external_refs: set[str] = set()

    for name in sorted(concept_names):
        lines.append(f'    {name}["{name}"]')

    for sync_name in sorted(workspace.syncs):
        sync = workspace.syncs[sync_name]
        when_concepts = sorted({p.concept for p in sync.when})
        then_concepts = sorted({p.concept for p in sync.then})
        for src in when_concepts:
            if src not in concept_names:
                external_refs.add(src)
            for dst in then_concepts:
                if dst not in concept_names:
                    external_refs.add(dst)
                lines.append(f"    {src} -->|sync {sync_name}| {dst}")

    for ext in sorted(external_refs):
        lines.append(f'    {ext}["{ext} ?"]:::external')

    if external_refs:
        lines.append(
            "    classDef external fill:#21262d,stroke:#484f58,stroke-dasharray:5"
        )

    return "\n".join(lines)


# --- top-level entry point ---------------------------------------------------


def generate_explorer(workspace: Workspace) -> str:
    """
    Generate a self-contained interactive HTML explorer for the given
    workspace (concepts + syncs).
    """
    concept_data = {
        name: _concept_to_dict(c) for name, c in workspace.concepts.items()
    }
    sync_data = {
        name: _sync_to_dict(s) for name, s in workspace.syncs.items()
    }
    graph_data = _build_graph_data(workspace)
    sync_index = _build_sync_index(workspace)

    # Per-concept Mermaid diagrams, still generated through the v1 adapter.
    from concept_lang.diagrams import entity_diagram, state_machine
    mermaid_diagrams: dict[str, dict[str, str]] = {}
    for name, c in workspace.concepts.items():
        v1 = _to_v1_concept(c)
        mermaid_diagrams[name] = {
            "state_machine": state_machine(v1),
            "entity_diagram": entity_diagram(v1),
        }

    dep_graph_mermaid = (
        _workspace_graph_mermaid(workspace)
        if workspace.concepts or workspace.syncs
        else "graph TD\n    empty[No concepts]"
    )

    return _HTML_TEMPLATE.replace(
        "/*__CONCEPT_DATA__*/{}", json.dumps(concept_data, indent=2)
    ).replace(
        '/*__SYNC_DATA__*/{}', json.dumps(sync_data, indent=2)
    ).replace(
        '/*__GRAPH_DATA__*/{"nodes":[],"edges":[]}', json.dumps(graph_data, indent=2)
    ).replace(
        "/*__SYNC_INDEX__*/{}", json.dumps(sync_index, indent=2)
    ).replace(
        "/*__MERMAID_DIAGRAMS__*/{}", json.dumps(mermaid_diagrams, indent=2)
    ).replace(
        '/*__DEP_GRAPH_MERMAID__*/"graph TD"', json.dumps(dep_graph_mermaid)
    )
```

- [ ] **Step 3.2: Add a `/*__SYNC_DATA__*/{}` placeholder to the HTML template**

The v2 explorer adds a new JSON payload for sync data. In `_HTML_TEMPLATE`, locate the existing `<script>` block that declares `const CONCEPT_DATA = /*__CONCEPT_DATA__*/{};` and add an adjacent line:

```javascript
const SYNC_DATA = /*__SYNC_DATA__*/{};
```

This is a cosmetic edit — the HTML template is a single large string literal. Find the `const CONCEPT_DATA = /*__CONCEPT_DATA__*/{};` line inside the `_HTML_TEMPLATE` variable and add the `SYNC_DATA` declaration on the next line.

- [ ] **Step 3.3: Run a smoke import**

Run: `uv run python -c "from concept_lang.explorer import generate_explorer; print('ok')"`
Expected: prints `ok`. No import errors.

- [ ] **Step 3.4: Commit**

```bash
git add src/concept_lang/explorer.py
git commit -m "refactor(explorer): rewrite against new AST with syncs-as-edges graph"
```

---

## Task 4: Add tests for the new explorer

There was no dedicated test file for the v1 explorer. P4 adds one to pin the new contract: graph shape, node count, edge payload with `syncName`, and external-reference handling.

**Files:**
- Create: `tests/test_explorer.py`

- [ ] **Step 4.1: Write the test file**

Create `tests/test_explorer.py` with the following contents:

```python
"""Tests for the interactive HTML explorer (v2 — consumes concept_lang.ast)."""

import json
import re

from concept_lang.ast import (
    Action,
    ActionCase,
    ActionPattern,
    ConceptAST,
    OperationalPrinciple,
    OPStep,
    StateDecl,
    SyncAST,
    TypedName,
    Workspace,
)
from concept_lang.explorer import (
    _build_graph_data,
    _build_sync_index,
    _workspace_graph_mermaid,
    generate_explorer,
)


def _tiny_workspace() -> Workspace:
    counter = ConceptAST(
        name="Counter",
        params=[],
        purpose="count things",
        state=[StateDecl(name="total", type_expr="int")],
        actions=[
            Action(
                name="inc",
                cases=[
                    ActionCase(
                        inputs=[],
                        outputs=[TypedName(name="total", type_expr="int")],
                        body=["increment"],
                    )
                ],
            )
        ],
        operational_principle=OperationalPrinciple(steps=[
            OPStep(keyword="after", action_name="inc", inputs=[], outputs=[("total", "1")]),
        ]),
        source="",
    )
    logger = ConceptAST(
        name="Logger",
        params=[],
        purpose="log events",
        state=[],
        actions=[
            Action(
                name="write",
                cases=[
                    ActionCase(
                        inputs=[TypedName(name="msg", type_expr="string")],
                        outputs=[],
                        body=["write to log"],
                    )
                ],
            )
        ],
        operational_principle=OperationalPrinciple(steps=[
            OPStep(
                keyword="after",
                action_name="write",
                inputs=[("msg", '"hi"')],
                outputs=[],
            ),
        ]),
        source="",
    )
    log_inc = SyncAST(
        name="LogInc",
        when=[ActionPattern(concept="Counter", action="inc", input_pattern=[], output_pattern=[])],
        where=None,
        then=[ActionPattern(concept="Logger", action="write", input_pattern=[], output_pattern=[])],
        source="",
    )
    return Workspace(
        concepts={"Counter": counter, "Logger": logger},
        syncs={"LogInc": log_inc},
    )


class TestGraphData:
    def test_one_node_per_concept(self):
        ws = _tiny_workspace()
        data = _build_graph_data(ws)
        names = {n["id"] for n in data["nodes"]}
        assert names == {"Counter", "Logger"}

    def test_one_edge_per_sync_triple(self):
        ws = _tiny_workspace()
        data = _build_graph_data(ws)
        assert len(data["edges"]) == 1
        edge = data["edges"][0]
        assert edge["source"] == "Counter"
        assert edge["target"] == "Logger"
        assert edge["syncName"] == "LogInc"
        assert edge["type"] == "sync"
        assert edge["internal"] is True

    def test_external_concept_reference_is_surfaced(self):
        ws = _tiny_workspace()
        # Add a sync that mentions a concept that doesn't exist.
        ws.syncs["Orphan"] = SyncAST(
            name="Orphan",
            when=[ActionPattern(concept="Counter", action="inc", input_pattern=[], output_pattern=[])],
            then=[ActionPattern(concept="Ghost", action="haunt", input_pattern=[], output_pattern=[])],
            source="",
        )
        data = _build_graph_data(ws)
        ghost = next((n for n in data["nodes"] if n["id"] == "Ghost"), None)
        assert ghost is not None
        assert ghost.get("external") is True

    def test_empty_workspace(self):
        data = _build_graph_data(Workspace())
        assert data == {"nodes": [], "edges": []}


class TestSyncIndex:
    def test_sync_index_captures_when_and_then(self):
        ws = _tiny_workspace()
        index = _build_sync_index(ws)
        assert "Counter.inc" in index
        assert any(e["sync"] == "LogInc" and e["role"] == "when" for e in index["Counter.inc"])
        assert "Logger.write" in index
        assert any(e["sync"] == "LogInc" and e["role"] == "then" for e in index["Logger.write"])


class TestWorkspaceGraphMermaid:
    def test_mermaid_contains_sync_edge(self):
        ws = _tiny_workspace()
        s = _workspace_graph_mermaid(ws)
        assert s.startswith("graph TD")
        assert re.search(r"Counter\s*-->\|sync LogInc\|\s*Logger", s)


class TestGenerateExplorer:
    def test_generate_returns_html_with_embedded_json(self):
        ws = _tiny_workspace()
        html = generate_explorer(ws)
        assert "<html" in html
        # The concept data payload got injected.
        assert '"Counter"' in html
        # The sync edge made it into the injected graph data.
        assert '"syncName": "LogInc"' in html

    def test_generate_empty_workspace(self):
        html = generate_explorer(Workspace())
        assert "<html" in html
        assert "No concepts" in html
```

- [ ] **Step 4.2: Run the test file**

Run: `uv run pytest tests/test_explorer.py -v`
Expected: every test passes.

- [ ] **Step 4.3: Commit**

```bash
git add tests/test_explorer.py
git commit -m "test(explorer): pin v2 graph shape and HTML output"
```

---

## Task 5: Rewrite `tools/_io.py` with workspace-root helpers

Per decision (B): `_io.py` now provides two helpers: `resolve_workspace_root(raw: str) -> Path` and `load_workspace_from_root(workspace_root: str) -> tuple[Workspace, list[Diagnostic]]`. The old `load_all_concepts` helper is deleted — every tool that needs parsing goes through `load_workspace_from_root`. The `list_concept_names` helper is deleted — tools that need bare name listings inline their own glob call (cheap enough).

**Files:**
- Modify: `src/concept_lang/tools/_io.py`

- [ ] **Step 5.1: Replace the file**

Replace the contents of `src/concept_lang/tools/_io.py` with:

```python
"""Shared helpers for the MCP tool layer (v2 — workspace-root aware)."""

from __future__ import annotations

from pathlib import Path

from concept_lang.ast import Workspace
from concept_lang.loader import load_workspace
from concept_lang.validate.diagnostic import Diagnostic


def resolve_workspace_root(raw: str) -> Path:
    """
    Turn a raw string (from an env var or MCP server arg) into a
    canonical workspace root path.

    Heuristic:
    * If ``raw`` points at a directory whose basename is ``concepts`` or
      ``syncs``, treat its **parent** as the workspace root. This keeps
      existing installations that set ``CONCEPTS_DIR=./concepts`` working
      without changes.
    * Otherwise treat ``raw`` itself as the workspace root.
    """
    p = Path(raw).expanduser()
    if p.name in ("concepts", "syncs"):
        return p.parent
    return p


def load_workspace_from_root(
    workspace_root: str,
) -> tuple[Workspace, list[Diagnostic]]:
    """
    Call ``concept_lang.loader.load_workspace`` with a resolved root.

    Returns a ``(Workspace, diagnostics)`` tuple identical to the loader's.
    This helper exists so that every MCP tool uses the same resolution
    heuristic without repeating the Path massaging.
    """
    root = resolve_workspace_root(workspace_root)
    return load_workspace(root)


def concepts_dir_for(workspace_root: str) -> Path:
    """Return the canonical ``<root>/concepts`` directory."""
    return resolve_workspace_root(workspace_root) / "concepts"


def syncs_dir_for(workspace_root: str) -> Path:
    """Return the canonical ``<root>/syncs`` directory."""
    return resolve_workspace_root(workspace_root) / "syncs"
```

- [ ] **Step 5.2: Run the tests that do not depend on MCP tool imports**

Run: `uv run pytest tests/test_ast.py tests/test_parse.py tests/test_validate.py tests/test_loader.py tests/test_diff.py tests/test_explorer.py -q`
Expected: all pass.

- [ ] **Step 5.3: Smoke-import the new module**

Run: `uv run python -c "from concept_lang.tools._io import resolve_workspace_root; print(resolve_workspace_root('./concepts'))"`
Expected: prints a path ending in `.` (because `./concepts` resolves to a path whose parent is `.`).

- [ ] **Step 5.4: Commit**

```bash
git add src/concept_lang/tools/_io.py
git commit -m "refactor(tools/_io): workspace-root aware helpers on new AST"
```

---

## Task 6: Rewrite `tools/concept_tools.py`

Per decisions (G), (I), (J), (K): the tool file exposes `list_concepts`, `read_concept`, `write_concept`, and `validate_concept`. Each goes through `load_workspace_from_root` for cross-reference context (except `list_concepts`, which only globs). Diagnostics are serialized via `Diagnostic.model_dump(mode="json")`.

**Files:**
- Modify: `src/concept_lang/tools/concept_tools.py`

- [ ] **Step 6.1: Replace the file**

Replace the contents of `src/concept_lang/tools/concept_tools.py` with:

```python
"""MCP tools for .concept files (v2 — consumes concept_lang.ast)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from concept_lang.parse import parse_concept_source
from concept_lang.validate import validate_concept_file, validate_workspace

from ._io import concepts_dir_for, load_workspace_from_root


def _diag_list(diags) -> list[dict]:
    return [d.model_dump(mode="json") for d in diags]


def register_concept_tools(mcp: FastMCP, workspace_root: str) -> None:

    @mcp.tool(description="List all .concept files in the workspace")
    def list_concepts() -> str:
        directory = concepts_dir_for(workspace_root)
        if not directory.is_dir():
            return json.dumps([])
        names = sorted(p.stem for p in directory.glob("*.concept"))
        return json.dumps(names)

    @mcp.tool(
        description=(
            "Read and parse a .concept file. Returns the raw source and the "
            "parsed AST as JSON. Pass the concept name without the .concept "
            "extension."
        )
    )
    def read_concept(name: str) -> str:
        path = concepts_dir_for(workspace_root) / f"{name}.concept"
        if not path.exists():
            return json.dumps({"error": f"Concept '{name}' not found"})
        source = path.read_text(encoding="utf-8")
        try:
            ast = parse_concept_source(source)
        except Exception as exc:
            return json.dumps({"error": f"Parse error: {exc}"})
        return json.dumps({
            "source": source,
            "ast": ast.model_dump(exclude={"source"}),
        })

    @mcp.tool(
        description=(
            "Write or overwrite a .concept file. Validates the source "
            "(parser + rules C1..C9 minus C8 + cross-reference rules) before "
            "writing. Refuses the write if any error-level diagnostic fires."
        )
    )
    def write_concept(name: str, source: str) -> str:
        diagnostics = _validate_concept_source(
            source=source, name=name, workspace_root=workspace_root
        )
        if any(d.severity == "error" for d in diagnostics):
            return json.dumps({
                "written": False,
                "valid": False,
                "diagnostics": _diag_list(diagnostics),
            })

        target_dir = concepts_dir_for(workspace_root)
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{name}.concept"
        path.write_text(source, encoding="utf-8")
        return json.dumps({
            "written": True,
            "valid": True,
            "path": str(path),
            "diagnostics": _diag_list(diagnostics),
        })

    @mcp.tool(
        description=(
            "Validate .concept source text without writing to disk. Runs "
            "C1..C9 (minus C8) and cross-reference rules (S1, S2) against "
            "the surrounding workspace. Returns the diagnostic list."
        )
    )
    def validate_concept(source: str) -> str:
        diagnostics = _validate_concept_source(
            source=source, name=None, workspace_root=workspace_root
        )
        return json.dumps({
            "valid": not any(d.severity == "error" for d in diagnostics),
            "diagnostics": _diag_list(diagnostics),
        })


def _validate_concept_source(
    *,
    source: str,
    name: str | None,
    workspace_root: str,
) -> list:
    """
    Shared validation path for both `validate_concept` and `write_concept`.

    1. Write ``source`` to a temp file so ``validate_concept_file`` can run
       C4 against the raw source and parse the rest through Lark.
    2. Load the surrounding workspace via ``load_workspace``.
    3. If the temp file parsed, substitute the resulting concept into the
       workspace (keyed by its declared name) and run ``validate_workspace``
       to pick up cross-reference rules (S1, S2).
    4. Combine the single-file diagnostics and the workspace diagnostics,
       de-duplicating by ``(code, file, line, message)``.

    Returns the combined diagnostic list. The temp file is always cleaned
    up in a ``finally``.
    """
    temp_path: Path | None = None
    try:
        # Use the workspace's concepts/ subdir as the tempfile parent so
        # C4's source-level scan sees the file at a realistic location.
        parent = concepts_dir_for(workspace_root)
        parent.mkdir(parents=True, exist_ok=True)
        suffix = f"_{name}.concept" if name else ".concept"
        fd, raw = tempfile.mkstemp(
            prefix="_validate_", suffix=suffix, dir=parent
        )
        temp_path = Path(raw)
        with open(fd, "w", encoding="utf-8") as f:
            f.write(source)

        file_diags = validate_concept_file(temp_path)

        # Cross-ref pass: only if the temp file parsed cleanly (no P0).
        parse_errors = [d for d in file_diags if d.code == "P0"]
        if parse_errors:
            return file_diags

        workspace, load_diags = load_workspace_from_root(workspace_root)
        # Substitute the current concept by re-parsing the source into an
        # AST (the concept's declared name, not the file stem, is the key).
        try:
            fresh_ast = parse_concept_source(source)
        except Exception:
            return file_diags
        workspace.concepts[fresh_ast.name] = fresh_ast

        ws_diags = validate_workspace(workspace)

        # De-duplicate: file_diags already contains C1..C9; ws_diags has
        # S1..S5 plus re-runs of the C rules on every concept in the
        # workspace. Filter ws_diags down to "things that mention the
        # current concept or its name" — for P4 we just take the full
        # ws_diags list and let the caller filter; test coverage will
        # catch any double-reporting.
        combined = list(file_diags) + [
            d for d in ws_diags if d not in file_diags
        ]
        return combined
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
```

- [ ] **Step 6.2: Smoke-import the new module**

Run: `uv run python -c "from concept_lang.tools.concept_tools import register_concept_tools; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 6.3: Commit**

```bash
git add src/concept_lang/tools/concept_tools.py
git commit -m "refactor(tools/concept): new AST + validator + workspace cross-refs"
```

---

## Task 7: Create `tools/sync_tools.py`

Per decision (H), (I), (J), (K): the sync tool file exposes `list_syncs`, `read_sync`, `write_sync`, `validate_sync`. Same shape as `concept_tools.py` but against `.sync` files.

**Files:**
- Create: `src/concept_lang/tools/sync_tools.py`

- [ ] **Step 7.1: Write the file**

Create `src/concept_lang/tools/sync_tools.py` with:

```python
"""MCP tools for .sync files (v2 — new)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from concept_lang.parse import parse_sync_source
from concept_lang.validate import validate_sync_file

from ._io import load_workspace_from_root, syncs_dir_for


def _diag_list(diags) -> list[dict]:
    return [d.model_dump(mode="json") for d in diags]


def register_sync_tools(mcp: FastMCP, workspace_root: str) -> None:

    @mcp.tool(description="List all .sync files in the workspace")
    def list_syncs() -> str:
        directory = syncs_dir_for(workspace_root)
        if not directory.is_dir():
            return json.dumps([])
        names = sorted(p.stem for p in directory.glob("*.sync"))
        return json.dumps(names)

    @mcp.tool(
        description=(
            "Read and parse a .sync file. Returns the raw source and the "
            "parsed AST as JSON. Pass the sync name without the .sync "
            "extension."
        )
    )
    def read_sync(name: str) -> str:
        path = syncs_dir_for(workspace_root) / f"{name}.sync"
        if not path.exists():
            return json.dumps({"error": f"Sync '{name}' not found"})
        source = path.read_text(encoding="utf-8")
        try:
            ast = parse_sync_source(source)
        except Exception as exc:
            return json.dumps({"error": f"Parse error: {exc}"})
        return json.dumps({
            "source": source,
            "ast": ast.model_dump(exclude={"source"}),
        })

    @mcp.tool(
        description=(
            "Write or overwrite a .sync file. Validates the source (parser "
            "+ rules S1..S5 against the workspace concepts) before writing. "
            "Refuses the write if any error-level diagnostic fires."
        )
    )
    def write_sync(name: str, source: str) -> str:
        diagnostics = _validate_sync_source(
            source=source, name=name, workspace_root=workspace_root
        )
        if any(d.severity == "error" for d in diagnostics):
            return json.dumps({
                "written": False,
                "valid": False,
                "diagnostics": _diag_list(diagnostics),
            })

        target_dir = syncs_dir_for(workspace_root)
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{name}.sync"
        path.write_text(source, encoding="utf-8")
        return json.dumps({
            "written": True,
            "valid": True,
            "path": str(path),
            "diagnostics": _diag_list(diagnostics),
        })

    @mcp.tool(
        description=(
            "Validate .sync source text without writing to disk. Runs "
            "S1..S5 against the surrounding workspace concepts. Returns "
            "the diagnostic list."
        )
    )
    def validate_sync(source: str) -> str:
        diagnostics = _validate_sync_source(
            source=source, name=None, workspace_root=workspace_root
        )
        return json.dumps({
            "valid": not any(d.severity == "error" for d in diagnostics),
            "diagnostics": _diag_list(diagnostics),
        })


def _validate_sync_source(
    *,
    source: str,
    name: str | None,
    workspace_root: str,
) -> list:
    """
    Shared validation path for ``validate_sync`` and ``write_sync``.

    1. Write ``source`` to a temp ``.sync`` file under the workspace's
       ``syncs/`` directory.
    2. Load the surrounding workspace so its concepts are available for
       cross-reference rules (S1, S2).
    3. Call ``validate_sync_file(temp_path, extra_concepts=workspace.concepts)``.
    4. Clean up the temp file.
    """
    temp_path: Path | None = None
    try:
        parent = syncs_dir_for(workspace_root)
        parent.mkdir(parents=True, exist_ok=True)
        suffix = f"_{name}.sync" if name else ".sync"
        fd, raw = tempfile.mkstemp(
            prefix="_validate_", suffix=suffix, dir=parent
        )
        temp_path = Path(raw)
        with open(fd, "w", encoding="utf-8") as f:
            f.write(source)

        workspace, _load_diags = load_workspace_from_root(workspace_root)
        diagnostics = validate_sync_file(
            temp_path, extra_concepts=workspace.concepts
        )

        # The temp file name leaks into diagnostic messages via the
        # `file=` field. Callers that want a real name should look at
        # the sync's declared name (S1/S2 diagnostics include it in the
        # message string).
        return diagnostics
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
```

- [ ] **Step 7.2: Smoke-import**

Run: `uv run python -c "from concept_lang.tools.sync_tools import register_sync_tools; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 7.3: Commit**

```bash
git add src/concept_lang/tools/sync_tools.py
git commit -m "feat(tools/sync): list_syncs read_sync write_sync validate_sync"
```

---

## Task 8: Create `tools/workspace_tools.py` with `validate_workspace` and `get_workspace_graph`

Per decisions (D), (E), (F): this file hosts the two tools that operate on the whole `Workspace` value. `get_workspace_graph` emits a Mermaid `graph TD` where edges are syncs; `validate_workspace` runs all rules across all files. The file also registers a backward-compat `get_dependency_graph` alias.

**Files:**
- Create: `src/concept_lang/tools/workspace_tools.py`

- [ ] **Step 8.1: Write the file**

Create `src/concept_lang/tools/workspace_tools.py` with:

```python
"""MCP tools for whole-workspace operations (v2 — new)."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from concept_lang.ast import Workspace
from concept_lang.validate import validate_workspace as _validate_workspace

from ._io import load_workspace_from_root


def _diag_list(diags) -> list[dict]:
    return [d.model_dump(mode="json") for d in diags]


def _workspace_graph_mermaid(workspace: Workspace) -> str:
    """
    Build a Mermaid `graph TD` where nodes are concepts and edges are
    syncs. Each sync contributes one `(when_concept, then_concept)` edge
    labeled with the sync's declared name.
    """
    lines = ["graph TD"]

    concept_names = set(workspace.concepts)
    external_refs: set[str] = set()

    for name in sorted(concept_names):
        lines.append(f'    {name}["{name}"]')

    for sync_name in sorted(workspace.syncs):
        sync = workspace.syncs[sync_name]
        when_concepts = sorted({p.concept for p in sync.when})
        then_concepts = sorted({p.concept for p in sync.then})
        for src in when_concepts:
            if src not in concept_names:
                external_refs.add(src)
            for dst in then_concepts:
                if dst not in concept_names:
                    external_refs.add(dst)
                lines.append(f"    {src} -->|sync {sync_name}| {dst}")

    for ext in sorted(external_refs):
        lines.append(f'    {ext}["{ext} ?"]:::external')

    if external_refs:
        lines.append(
            "    classDef external fill:#21262d,stroke:#484f58,stroke-dasharray:5"
        )

    return "\n".join(lines)


def register_workspace_tools(mcp: FastMCP, workspace_root: str) -> None:

    @mcp.tool(
        description=(
            "Validate every .concept and .sync file in the workspace. "
            "Runs C1..C9 (minus C8) plus S1..S5, plus per-file parse "
            "diagnostics. Returns the combined diagnostic list and a "
            "top-level `valid` boolean."
        )
    )
    def validate_workspace() -> str:
        ws, load_diags = load_workspace_from_root(workspace_root)
        rule_diags = _validate_workspace(ws)
        diagnostics = list(load_diags) + list(rule_diags)
        return json.dumps({
            "valid": not any(d.severity == "error" for d in diagnostics),
            "diagnostics": _diag_list(diagnostics),
            "concept_count": len(ws.concepts),
            "sync_count": len(ws.syncs),
        })

    @mcp.tool(
        description=(
            "Generate a Mermaid graph TD for the whole workspace. "
            "Nodes are concepts; edges are syncs labeled with their "
            "declared name. Pass to "
            "mcp__claude_ai_Mermaid_Chart__validate_and_render_mermaid_diagram "
            "to render. Replaces the old `get_dependency_graph`."
        )
    )
    def get_workspace_graph() -> str:
        ws, _diags = load_workspace_from_root(workspace_root)
        if not ws.concepts and not ws.syncs:
            return "// No concepts or syncs found"
        return _workspace_graph_mermaid(ws)

    @mcp.tool(
        description=(
            "Deprecated: use get_workspace_graph. Returns the same Mermaid "
            "string. Removed in P7."
        )
    )
    def get_dependency_graph() -> str:
        return get_workspace_graph()
```

- [ ] **Step 8.2: Smoke-import**

Run: `uv run python -c "from concept_lang.tools.workspace_tools import register_workspace_tools; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 8.3: Commit**

```bash
git add src/concept_lang/tools/workspace_tools.py
git commit -m "feat(tools/workspace): validate_workspace + get_workspace_graph"
```

---

## Task 9: Rewrite `tools/diff_tools.py`

`diff_concept` / `diff_concept_against_disk` now operate on the new AST. The workspace parameter of `diff_concepts_with_impact` is now a `Workspace` value rather than a list.

**Files:**
- Modify: `src/concept_lang/tools/diff_tools.py`

- [ ] **Step 9.1: Replace the file**

Replace the contents of `src/concept_lang/tools/diff_tools.py` with:

```python
"""MCP tools for concept diff (v2 — consumes concept_lang.ast)."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from concept_lang.diff import diff_concepts_with_impact
from concept_lang.parse import parse_concept_source

from ._io import concepts_dir_for, load_workspace_from_root


def register_diff_tools(mcp: FastMCP, workspace_root: str) -> None:

    @mcp.tool(
        description=(
            "Compute a structural diff between two versions of a concept. "
            "Pass two concept source texts (old and new). Returns semantic "
            "changes (state, actions, operational principle) plus any "
            "downstream syncs in the workspace that the new version breaks."
        )
    )
    def diff_concept(old_source: str, new_source: str) -> str:
        try:
            old_ast = parse_concept_source(old_source)
        except Exception as exc:
            return json.dumps({"error": f"Failed to parse old source: {exc}"})
        try:
            new_ast = parse_concept_source(new_source)
        except Exception as exc:
            return json.dumps({"error": f"Failed to parse new source: {exc}"})

        workspace, _diags = load_workspace_from_root(workspace_root)
        result = diff_concepts_with_impact(old_ast, new_ast, workspace)
        return json.dumps(result.to_dict())

    @mcp.tool(
        description=(
            "Diff a concept's current on-disk version against a proposed "
            "new version. Pass the concept name and the new source text. "
            "Returns structural changes and any broken downstream syncs."
        )
    )
    def diff_concept_against_disk(name: str, new_source: str) -> str:
        path = concepts_dir_for(workspace_root) / f"{name}.concept"
        if not path.exists():
            return json.dumps({"error": f"Concept '{name}' not found on disk"})
        try:
            old_ast = parse_concept_source(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return json.dumps({"error": f"Failed to parse on-disk version: {exc}"})

        try:
            new_ast = parse_concept_source(new_source)
        except Exception as exc:
            return json.dumps({"error": f"Failed to parse new source: {exc}"})

        workspace, _diags = load_workspace_from_root(workspace_root)
        result = diff_concepts_with_impact(old_ast, new_ast, workspace)
        return json.dumps(result.to_dict())
```

- [ ] **Step 9.2: Smoke-import**

Run: `uv run python -c "from concept_lang.tools.diff_tools import register_diff_tools; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 9.3: Commit**

```bash
git add src/concept_lang/tools/diff_tools.py
git commit -m "refactor(tools/diff): new AST + workspace-root loader"
```

---

## Task 10: Rewrite `tools/explorer_tools.py`

**Files:**
- Modify: `src/concept_lang/tools/explorer_tools.py`

- [ ] **Step 10.1: Replace the file**

Replace the contents of `src/concept_lang/tools/explorer_tools.py` with:

```python
"""MCP tools for the interactive HTML concept explorer (v2)."""

from __future__ import annotations

import webbrowser
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from concept_lang.explorer import generate_explorer

from ._io import load_workspace_from_root, resolve_workspace_root


def register_explorer_tools(mcp: FastMCP, workspace_root: str) -> None:

    @mcp.tool(
        description=(
            "Generate an interactive HTML concept explorer for the current "
            "workspace. Returns a self-contained HTML page with a clickable "
            "concept graph (syncs as edges), per-concept state and entity "
            "diagrams, and per-sync flow diagrams. Open the returned file "
            "path in a browser to explore."
        )
    )
    def get_interactive_explorer(open_browser: bool = True) -> str:
        workspace, _diags = load_workspace_from_root(workspace_root)
        if not workspace.concepts and not workspace.syncs:
            return f"No concepts or syncs found in {workspace_root}"

        html = generate_explorer(workspace)

        root = resolve_workspace_root(workspace_root)
        out_path = root / "concept-explorer.html"
        out_path.write_text(html, encoding="utf-8")

        if open_browser:
            webbrowser.open(f"file://{out_path}")

        return f"Explorer generated: {out_path}"

    @mcp.tool(
        description=(
            "Get the interactive explorer as raw HTML string. Use this "
            "when you want to embed the explorer or serve it differently "
            "rather than writing it to a file."
        )
    )
    def get_explorer_html() -> str:
        workspace, _diags = load_workspace_from_root(workspace_root)
        if not workspace.concepts and not workspace.syncs:
            return "<!-- No concepts or syncs found -->"
        return generate_explorer(workspace)
```

- [ ] **Step 10.2: Smoke-import**

Run: `uv run python -c "from concept_lang.tools.explorer_tools import register_explorer_tools; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 10.3: Commit**

```bash
git add src/concept_lang/tools/explorer_tools.py
git commit -m "refactor(tools/explorer): new AST + workspace loader"
```

---

## Task 11: Update `tools/diagram_tools.py` to drop `get_dependency_graph`

Per decision (E) / (F): the whole-workspace Mermaid graph moved to `workspace_tools.get_workspace_graph` (with a backward-compat alias). `diagram_tools` keeps its per-concept generators (`get_state_machine`, `get_entity_diagram`) but drops `get_dependency_graph`. The per-concept generators still use the v1 `diagrams/` module; the adapter pattern from Task 3 is imported directly so the v1 `parser.parse_file` import goes away.

**Files:**
- Modify: `src/concept_lang/tools/diagram_tools.py`

- [ ] **Step 11.1: Replace the file**

Replace the contents of `src/concept_lang/tools/diagram_tools.py` with:

```python
"""MCP tools for per-concept Mermaid diagrams (v2)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from concept_lang.ast import ConceptAST
from concept_lang.diagrams import entity_diagram, state_machine
from concept_lang.explorer import _to_v1_concept
from concept_lang.parse import parse_concept_file

from ._io import concepts_dir_for


def register_diagram_tools(mcp: FastMCP, workspace_root: str) -> None:

    def _load(name: str) -> ConceptAST:
        path = concepts_dir_for(workspace_root) / f"{name}.concept"
        if not path.exists():
            raise FileNotFoundError(f"Concept '{name}' not found")
        return parse_concept_file(path)

    @mcp.tool(
        description=(
            "Generate a Mermaid stateDiagram-v2 for a concept. "
            "Shows how actions transition entities through the concept's "
            "principal set. Pass to "
            "mcp__claude_ai_Mermaid_Chart__validate_and_render_mermaid_diagram "
            "to render."
        )
    )
    def get_state_machine(name: str) -> str:
        try:
            return state_machine(_to_v1_concept(_load(name)))
        except FileNotFoundError as e:
            return f"// Error: {e}"
        except Exception as e:
            return f"// Error: {e}"

    @mcp.tool(
        description=(
            "Generate a Mermaid classDiagram for a concept. "
            "Shows the concept's state model: sets as classes, relations "
            "as associations. Pass to "
            "mcp__claude_ai_Mermaid_Chart__validate_and_render_mermaid_diagram "
            "to render."
        )
    )
    def get_entity_diagram(name: str) -> str:
        try:
            return entity_diagram(_to_v1_concept(_load(name)))
        except FileNotFoundError as e:
            return f"// Error: {e}"
        except Exception as e:
            return f"// Error: {e}"
```

Note: the whole-workspace `get_dependency_graph` tool is deliberately absent — it lives in `workspace_tools.py` now (with a backward-compat alias under the old name).

- [ ] **Step 11.2: Smoke-import**

Run: `uv run python -c "from concept_lang.tools.diagram_tools import register_diagram_tools; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 11.3: Commit**

```bash
git add src/concept_lang/tools/diagram_tools.py
git commit -m "refactor(tools/diagram): drop dependency_graph, keep per-concept via v1 adapter"
```

---

## Task 12: Update `tools/__init__.py` to register the new tool modules

**Files:**
- Modify: `src/concept_lang/tools/__init__.py`

- [ ] **Step 12.1: Replace the file**

Replace the contents of `src/concept_lang/tools/__init__.py` with:

```python
"""
MCP tool registrations for concept-lang 0.2.0.

The code-generation tools (`codegen_tools`) are intentionally NOT
re-exported: per the paper-alignment spec §5.3 they stay on v1 until a
dedicated migration and are not exposed via the MCP server in P4. The
source file is preserved so a future phase can rewire it quickly.
"""

from .app_tools import register_app_tools
from .concept_tools import register_concept_tools
from .diagram_tools import register_diagram_tools
from .diff_tools import register_diff_tools
from .explorer_tools import register_explorer_tools
from .scaffold_tools import register_scaffold_tools
from .sync_tools import register_sync_tools
from .workspace_tools import register_workspace_tools

__all__ = [
    "register_app_tools",
    "register_concept_tools",
    "register_diagram_tools",
    "register_diff_tools",
    "register_explorer_tools",
    "register_scaffold_tools",
    "register_sync_tools",
    "register_workspace_tools",
]
```

- [ ] **Step 12.2: Smoke-import**

Run: `uv run python -c "from concept_lang.tools import register_concept_tools, register_sync_tools, register_workspace_tools; print('ok')"`
Expected: prints `ok`. The absence of `register_codegen_tools` is intentional and matches the spec.

- [ ] **Step 12.3: Commit**

```bash
git add src/concept_lang/tools/__init__.py
git commit -m "refactor(tools): register sync_tools and workspace_tools, drop codegen"
```

---

## Task 13: Update `server.py` to wire the new tool layer

Per decision (B): the server takes a `workspace_root` string, honors both `WORKSPACE_DIR` and `CONCEPTS_DIR` env vars, and drops the codegen registration. `app_tools` continues to be registered unchanged.

**Files:**
- Modify: `src/concept_lang/server.py`

- [ ] **Step 13.1: Replace the file**

Replace the contents of `src/concept_lang/server.py` with:

```python
"""MCP server entry point for concept-lang 0.2.0."""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from .prompts import register_prompts
from .resources import register_resources
from .tools import (
    register_app_tools,
    register_concept_tools,
    register_diagram_tools,
    register_diff_tools,
    register_explorer_tools,
    register_scaffold_tools,
    register_sync_tools,
    register_workspace_tools,
)


def _resolve_workspace_root_arg(workspace_root: str | None) -> str:
    """
    Resolve the workspace root from the ctor arg, then env vars.

    Checks (in order):
      1. the `workspace_root` argument
      2. the `WORKSPACE_DIR` environment variable
      3. the legacy `CONCEPTS_DIR` environment variable (for back-compat
         with existing installations; the tool layer's
         `resolve_workspace_root` helper will walk up one level if the
         value ends in `/concepts`)
      4. the literal string `./concepts` (legacy default)
    """
    if workspace_root is not None:
        return workspace_root
    env = os.environ.get("WORKSPACE_DIR")
    if env:
        return env
    env = os.environ.get("CONCEPTS_DIR")
    if env:
        return env
    return "./concepts"


def create_server(workspace_root: str | None = None) -> FastMCP:
    root = _resolve_workspace_root_arg(workspace_root)

    mcp = FastMCP("concept-lang")

    register_concept_tools(mcp, root)
    register_sync_tools(mcp, root)
    register_workspace_tools(mcp, root)
    register_diff_tools(mcp, root)
    register_diagram_tools(mcp, root)
    register_explorer_tools(mcp, root)
    register_scaffold_tools(mcp, root)
    register_app_tools(mcp, root)
    register_resources(mcp, root)
    register_prompts(mcp)

    return mcp


def main() -> None:
    mcp = create_server()
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 13.2: Smoke-import**

Run: `uv run python -c "from concept_lang.server import create_server; s = create_server('/tmp/nonexistent-workspace-root'); print('ok')"`
Expected: prints `ok`. The server constructs successfully even when the root does not exist — individual tools will emit L0 at call time.

- [ ] **Step 13.3: Commit**

```bash
git add src/concept_lang/server.py
git commit -m "refactor(server): workspace_root, drop codegen, register sync/workspace tools"
```

---

## Task 14: Update `resources.py` to use `load_workspace`

**Files:**
- Modify: `src/concept_lang/resources.py`

- [ ] **Step 14.1: Replace the file**

Replace the contents of `src/concept_lang/resources.py` with:

```python
"""MCP resources for concept-lang 0.2.0."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from .tools._io import concepts_dir_for, load_workspace_from_root, syncs_dir_for


def register_resources(mcp: FastMCP, workspace_root: str) -> None:

    @mcp.resource("concept://all")
    def all_concepts() -> str:
        """All parsed concepts as a JSON list."""
        workspace, _diags = load_workspace_from_root(workspace_root)
        result = [
            ast.model_dump(exclude={"source"})
            for ast in workspace.concepts.values()
        ]
        return json.dumps(result, indent=2)

    @mcp.resource("sync://all")
    def all_syncs() -> str:
        """All parsed syncs as a JSON list."""
        workspace, _diags = load_workspace_from_root(workspace_root)
        result = [
            ast.model_dump(exclude={"source"})
            for ast in workspace.syncs.values()
        ]
        return json.dumps(result, indent=2)

    @mcp.resource("concept://{name}")
    def get_concept(name: str) -> str:
        """Raw source of a single concept file."""
        path = concepts_dir_for(workspace_root) / f"{name}.concept"
        if not path.exists():
            return f"// Concept '{name}' not found"
        return path.read_text(encoding="utf-8")

    @mcp.resource("sync://{name}")
    def get_sync(name: str) -> str:
        """Raw source of a single sync file."""
        path = syncs_dir_for(workspace_root) / f"{name}.sync"
        if not path.exists():
            return f"// Sync '{name}' not found"
        return path.read_text(encoding="utf-8")
```

- [ ] **Step 14.2: Smoke-import**

Run: `uv run python -c "from concept_lang.resources import register_resources; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 14.3: Commit**

```bash
git add src/concept_lang/resources.py
git commit -m "refactor(resources): use load_workspace, add sync resources"
```

---

## Task 15: Update `prompts.py` to reference `get_workspace_graph`

The `review_concepts` prompt currently ends with "Also use `get_dependency_graph` to render the overall concept map...". P4 updates that to the new tool name. The `build_concept` prompt text stays as-is — it describes a natural-language workflow and does not name any MCP tools. The wholesale prompt rewrite is P5's job.

**Files:**
- Modify: `src/concept_lang/prompts.py`

- [ ] **Step 15.1: Patch the one tool reference**

In `src/concept_lang/prompts.py`, find the line:

```python
Also use `get_dependency_graph` to render the overall concept map and check for unexpected coupling.""",
```

and replace it with:

```python
Also use `get_workspace_graph` to render the overall concept map (nodes are concepts, edges are syncs) and check for unexpected coupling.""",
```

Leave the rest of the file untouched. The system-prompt text for `build_concept` still describes the v1 sync-inside-concept syntax; P5's skill rewrite replaces that.

- [ ] **Step 15.2: Smoke-import**

Run: `uv run python -c "from concept_lang.prompts import register_prompts; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 15.3: Commit**

```bash
git add src/concept_lang/prompts.py
git commit -m "refactor(prompts): rename get_dependency_graph → get_workspace_graph"
```

---

## Task 16: Clean up `concept_lang/__init__.py`

Per decision (N): drop every v1 re-export and expose a coherent v2 surface.

**Files:**
- Modify: `src/concept_lang/__init__.py`

- [ ] **Step 16.1: Replace the file**

Replace the contents of `src/concept_lang/__init__.py` with:

```python
"""
concept-lang 0.2.0 public API.

The v1 modules (`concept_lang.parser`, `concept_lang.models`,
`concept_lang.validator`, `concept_lang.app_parser`,
`concept_lang.app_validator`) are still importable via their fully
qualified paths for the sake of the app-spec tool path and legacy tests,
but the package-level namespace only exposes the v2 surface.
"""

from concept_lang.ast import (
    Action,
    ActionCase,
    ActionPattern,
    BindClause,
    ConceptAST,
    EffectClause,
    OPStep,
    OperationalPrinciple,
    PatternField,
    StateDecl,
    StateQuery,
    SyncAST,
    Triple,
    TypedName,
    WhereClause,
    Workspace,
)
from concept_lang.loader import load_workspace
from concept_lang.parse import (
    parse_concept_file,
    parse_concept_source,
    parse_sync_file,
    parse_sync_source,
)
from concept_lang.server import create_server
from concept_lang.validate import (
    Diagnostic,
    validate_concept_file,
    validate_sync_file,
    validate_workspace,
)

__all__ = [
    # AST
    "Action",
    "ActionCase",
    "ActionPattern",
    "BindClause",
    "ConceptAST",
    "EffectClause",
    "OPStep",
    "OperationalPrinciple",
    "PatternField",
    "StateDecl",
    "StateQuery",
    "SyncAST",
    "Triple",
    "TypedName",
    "WhereClause",
    "Workspace",
    # Parser
    "parse_concept_file",
    "parse_concept_source",
    "parse_sync_file",
    "parse_sync_source",
    # Loader
    "load_workspace",
    # Validator
    "Diagnostic",
    "validate_concept_file",
    "validate_sync_file",
    "validate_workspace",
    # MCP server
    "create_server",
]
```

- [ ] **Step 16.2: Run the full test suite**

Run: `uv run pytest -q`
Expected: every test passes. The v1 test files (`test_validator.py`) import from `concept_lang.parser` / `concept_lang.models` / `concept_lang.validator` directly — those fully qualified imports still resolve because the v1 modules are still in the tree.

If `test_validator.py` fails with `ImportError`, investigate: it should be importing from the fully-qualified paths (`from concept_lang.validator import ...`, `from concept_lang.models import ...`) which are unaffected. If it was importing from `concept_lang` (top-level) then it must be updated to fully-qualified imports — that is the only legal back-compat shim in P4.

- [ ] **Step 16.3: Commit**

```bash
git add src/concept_lang/__init__.py
git commit -m "refactor(__init__): expose v2 API, drop v1 re-exports"
```

---

## Task 17: App-tools adjustment for new `workspace_root` parameter

`app_tools.py` currently takes `concepts_dir: str` and reads `.app` files from that directory. Now that the server passes `workspace_root`, the app tools need to learn the new layout. Per decision (M): the app path stays entirely on v1 internally, but the entry signature and the file-lookup path must use the new workspace layout. The app files themselves live in the root's `apps/` subdirectory (or, for back-compat, directly in the root's `concepts/` directory if no `apps/` dir exists).

**Files:**
- Modify: `src/concept_lang/tools/app_tools.py`

- [ ] **Step 17.1: Update the entry-point signature and file lookup**

Replace the contents of `src/concept_lang/tools/app_tools.py` with:

```python
"""MCP tools for app specs (concept composition layer).

App specs still use the v1 `.app` format; `concept_lang.app_parser` and
`concept_lang.app_validator` are unchanged and will stay on v1 until a
dedicated follow-up plan migrates them. P4 only adjusts this file to
honor the new `workspace_root` parameter and the new workspace layout.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from concept_lang.app_parser import AppParseError, parse_app, parse_app_file
from concept_lang.app_validator import validate_app
from concept_lang.models import ConceptAST as V1ConceptAST
from concept_lang.parser import ParseError as V1ParseError, parse_file as v1_parse_file

from ._io import concepts_dir_for, resolve_workspace_root


def _apps_dir(workspace_root: str) -> Path:
    """
    Return the directory where `.app` files live.

    Convention: ``<root>/apps/``. For legacy installations where `.app`
    files live alongside `.concept` files in the root's ``concepts/``
    directory, fall back to that location if no ``apps/`` dir exists.
    """
    root = resolve_workspace_root(workspace_root)
    apps = root / "apps"
    if apps.is_dir():
        return apps
    legacy = root / "concepts"
    if legacy.is_dir():
        return legacy
    return apps  # non-existent path; callers handle FileNotFoundError


def _load_declared_concepts_v1(
    workspace_root: str, concept_names: list[str]
) -> dict[str, V1ConceptAST]:
    """Load v1 concept ASTs for the given names using the v1 parser."""
    directory = concepts_dir_for(workspace_root)
    loaded: dict[str, V1ConceptAST] = {}
    for name in concept_names:
        path = directory / f"{name}.concept"
        if not path.exists():
            continue
        try:
            loaded[name] = v1_parse_file(str(path))
        except V1ParseError:
            continue
    return loaded


def register_app_tools(mcp: FastMCP, workspace_root: str) -> None:

    @mcp.tool(description="List all .app files in the workspace")
    def list_apps() -> str:
        directory = _apps_dir(workspace_root)
        if not directory.is_dir():
            return json.dumps([])
        names = sorted(p.stem for p in directory.glob("*.app"))
        return json.dumps(names)

    @mcp.tool(
        description=(
            "Read and parse an .app file. Returns the parsed app spec as "
            "JSON. Pass the app name without the .app extension."
        )
    )
    def read_app(name: str) -> str:
        path = _apps_dir(workspace_root) / f"{name}.app"
        if not path.exists():
            return json.dumps({"error": f"App '{name}' not found"})
        try:
            app = parse_app_file(str(path))
            return json.dumps({
                "name": app.name,
                "purpose": app.purpose,
                "concepts": [
                    {"name": c.name, "bindings": c.bindings}
                    for c in app.concepts
                ],
                "source": app.source,
            })
        except AppParseError as e:
            return json.dumps({"error": str(e)})

    @mcp.tool(
        description=(
            "Write or overwrite an .app file. Validates the source before "
            "writing. Pass app name (without extension) and the full source "
            "text."
        )
    )
    def write_app(name: str, source: str) -> str:
        try:
            parse_app(source)
        except AppParseError as e:
            return json.dumps({
                "error": f"Validation failed: {e}", "written": False
            })

        target_dir = _apps_dir(workspace_root)
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{name}.app"
        path.write_text(source, encoding="utf-8")
        return json.dumps({"written": True, "path": str(path)})

    @mcp.tool(
        description=(
            "Validate an .app file against its concept definitions. "
            "Checks that all concepts exist, type bindings are correct, "
            "and sync dependencies are satisfied. Uses the v1 concept "
            "parser because the .app format is still on v1."
        )
    )
    def validate_app_spec(name: str) -> str:
        path = _apps_dir(workspace_root) / f"{name}.app"
        if not path.exists():
            return json.dumps({"error": f"App '{name}' not found"})
        try:
            app = parse_app_file(str(path))
        except AppParseError as e:
            return json.dumps({"valid": False, "error": str(e)})

        concept_names = [c.name for c in app.concepts]
        loaded = _load_declared_concepts_v1(workspace_root, concept_names)
        errors = validate_app(app, loaded)

        return json.dumps({
            "valid": len([e for e in errors if e.level == "error"]) == 0,
            "errors": [e.to_dict() for e in errors if e.level == "error"],
            "warnings": [e.to_dict() for e in errors if e.level == "warning"],
            "concepts_declared": len(app.concepts),
            "concepts_loaded": len(loaded),
        })

    @mcp.tool(
        description=(
            "Generate a Mermaid dependency graph for an app spec, showing "
            "only the concepts declared in the app and their sync/param "
            "relationships. Pass the app name without the .app extension. "
            "(v1-format app spec; uses the v1 concept parser internally.)"
        )
    )
    def get_app_dependency_graph(name: str) -> str:
        path = _apps_dir(workspace_root) / f"{name}.app"
        if not path.exists():
            return f"// Error: App '{name}' not found"
        try:
            app = parse_app_file(str(path))
        except AppParseError as e:
            return f"// Error: {e}"

        concept_names = [c.name for c in app.concepts]
        loaded = _load_declared_concepts_v1(workspace_root, concept_names)

        if not loaded:
            return "// No concept files found for this app"

        concepts_list = list(loaded.values())
        declared_set = {c.name for c in app.concepts}

        lines = [f"graph TD"]
        lines.append(f'    subgraph {app.name}["{app.name}"]')

        for binding in app.concepts:
            label = binding.name
            if binding.bindings:
                label += f"[{', '.join(binding.bindings)}]"
            lines.append(f'        {binding.name}["{label}"]')

        for ast in concepts_list:
            binding = next(b for b in app.concepts if b.name == ast.name)
            for bound_to in binding.bindings:
                if bound_to in declared_set:
                    lines.append(f"        {ast.name} -->|param| {bound_to}")

            seen_sync: set[str] = set()
            for clause in ast.sync:
                dep = clause.trigger_concept
                if dep not in seen_sync and dep in declared_set:
                    seen_sync.add(dep)
                    lines.append(f"        {ast.name} -.->|sync| {dep}")

        lines.append("    end")

        for ast in concepts_list:
            for clause in ast.sync:
                if clause.trigger_concept not in declared_set:
                    lines.append(
                        f'    {clause.trigger_concept}["{clause.trigger_concept} ?"]:::external'
                    )
                    lines.append(
                        f"    {ast.name} -.->|sync| {clause.trigger_concept}"
                    )

        lines.append(
            "    classDef external fill:#21262d,stroke:#484f58,stroke-dasharray:5"
        )

        return "\n".join(lines)
```

- [ ] **Step 17.2: Smoke-import**

Run: `uv run python -c "from concept_lang.tools.app_tools import register_app_tools; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 17.3: Commit**

```bash
git add src/concept_lang/tools/app_tools.py
git commit -m "refactor(tools/app): workspace_root parameter, v1 internals preserved"
```

---

## Task 18: Fixture workspace for MCP tool tests

**Files:**
- Create: `tests/fixtures/mcp/clean/concepts/Counter.concept`
- Create: `tests/fixtures/mcp/clean/concepts/Logger.concept`
- Create: `tests/fixtures/mcp/clean/syncs/log.sync`
- Create: `tests/fixtures/mcp/with_error/concepts/Counter.concept`
- Create: `tests/fixtures/mcp/with_error/concepts/Logger.concept`
- Create: `tests/fixtures/mcp/with_error/syncs/log.sync`
- Create: `tests/fixtures/mcp/empty/concepts/.gitkeep`
- Create: `tests/fixtures/mcp/empty/syncs/.gitkeep`

Note: the `clean` and `with_error` workspaces both declare a `Logger` concept in addition to `Counter` so that the `log.sync` fixture does not fire S1 (sync references unknown concept). This is important because the tests in Task 19 assert that the `clean` workspace produces **no** error-level diagnostics; if `Logger` were missing, the sync rule S1 would always fire.

- [ ] **Step 18.1: Create the clean fixture**

Create `tests/fixtures/mcp/clean/concepts/Counter.concept` with:

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

Create `tests/fixtures/mcp/clean/concepts/Logger.concept` with:

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

Create `tests/fixtures/mcp/clean/syncs/log.sync` with:

```
sync LogInc

  when
    Counter/inc: [ ] => [ total: ?total ]
  then
    Logger/write: [ msg: ?total ] => [ ]
```

- [ ] **Step 18.2: Create the with_error fixture**

Create `tests/fixtures/mcp/with_error/concepts/Counter.concept` — identical to the clean `Counter.concept` but with the `purpose` section's body line removed, so it fires C5:

```
concept Counter

  purpose

  state
    total: int

  actions
    inc [ ] => [ total: int ]

  operational principle
    after inc [ ] => [ total: 1 ]
```

Create `tests/fixtures/mcp/with_error/concepts/Logger.concept` — copy from the clean `Logger.concept` verbatim.

Create `tests/fixtures/mcp/with_error/syncs/log.sync` — copy from the clean `log.sync` verbatim.

- [ ] **Step 18.3: Create the empty fixture**

Create `tests/fixtures/mcp/empty/concepts/.gitkeep` (empty file).
Create `tests/fixtures/mcp/empty/syncs/.gitkeep` (empty file).

- [ ] **Step 18.4: Verify the clean fixture parses and validates cleanly**

Run:

```bash
uv run python -c "
from pathlib import Path
from concept_lang.loader import load_workspace
from concept_lang.validate import validate_workspace
ws, d = load_workspace(Path('tests/fixtures/mcp/clean'))
print('concepts:', sorted(ws.concepts))
print('syncs:', sorted(ws.syncs))
print('load diags:', d)
print('rule diags:', [(x.code, x.severity, x.message) for x in validate_workspace(ws)])
"
```

Expected: concepts == `['Counter', 'Logger']`, syncs == `['LogInc']`, load diagnostics empty, rule diagnostics empty (or all non-error). If the fixture's `purpose` or operational-principle shape does not match the P1 grammar, tweak the fixture — the spec accepts minor variations. If you hit a parse error, read `tests/fixtures/realworld/concepts/Article.concept` for a known-good template.

- [ ] **Step 18.5: Verify the with_error fixture fires C5**

Run: `uv run python -c "from concept_lang.validate import validate_concept_file; from pathlib import Path; print([d.code for d in validate_concept_file(Path('tests/fixtures/mcp/with_error/concepts/Counter.concept'))])"`
Expected: the output contains `'C5'`. If it does not, the fixture's purpose section isn't actually empty from the rule's perspective — adjust until C5 fires.

- [ ] **Step 18.6: Commit**

```bash
git add tests/fixtures/mcp/
git commit -m "test(fixtures): mcp tool workspaces (clean, with_error, empty)"
```

---

## Task 19: MCP tool integration tests

Per decision (O): tests use a fake `FastMCP` that records decorated functions. Each test exercises the tool function directly and asserts on the returned JSON body.

**Files:**
- Create: `tests/test_mcp_tools.py`

- [ ] **Step 19.1: Write the test file**

Create `tests/test_mcp_tools.py` with:

```python
"""Integration tests for the MCP tool layer (v2).

These tests call the tool functions directly via a fake FastMCP. They do
not exercise the MCP protocol itself — that's reserved for the P5 skills
pipeline.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable

import pytest

from concept_lang.tools.concept_tools import register_concept_tools
from concept_lang.tools.diff_tools import register_diff_tools
from concept_lang.tools.explorer_tools import register_explorer_tools
from concept_lang.tools.sync_tools import register_sync_tools
from concept_lang.tools.workspace_tools import register_workspace_tools


FIXTURES = Path(__file__).parent / "fixtures" / "mcp"


class _FakeMCP:
    """Minimal stand-in for FastMCP that captures @mcp.tool() decorations."""

    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Any]] = {}
        self.resources: dict[str, Callable[..., Any]] = {}

    def tool(self, *args, **kwargs):  # matches FastMCP.tool decorator
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.tools[fn.__name__] = fn
            return fn
        return decorator

    def resource(self, pattern: str):
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.resources[pattern] = fn
            return fn
        return decorator


def _make_mcp(workspace_root: Path) -> _FakeMCP:
    mcp = _FakeMCP()
    register_concept_tools(mcp, str(workspace_root))
    register_sync_tools(mcp, str(workspace_root))
    register_workspace_tools(mcp, str(workspace_root))
    register_diff_tools(mcp, str(workspace_root))
    register_explorer_tools(mcp, str(workspace_root))
    return mcp


def _call(mcp: _FakeMCP, name: str, **kwargs) -> Any:
    raw = mcp.tools[name](**kwargs)
    if isinstance(raw, str) and raw.startswith(("{", "[")):
        return json.loads(raw)
    return raw


def _copy_workspace(src: Path, dst: Path) -> None:
    """Copy a fixture workspace tree into a writable temp directory."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


# ---------------------------------------------------------------------------
# Concept tools
# ---------------------------------------------------------------------------


class TestListConcepts:
    def test_clean_workspace_lists_counter_and_logger(self):
        mcp = _make_mcp(FIXTURES / "clean")
        body = _call(mcp, "list_concepts")
        assert body == ["Counter", "Logger"]

    def test_empty_workspace_lists_nothing(self):
        mcp = _make_mcp(FIXTURES / "empty")
        body = _call(mcp, "list_concepts")
        assert body == []


class TestReadConcept:
    def test_reads_existing_concept(self):
        mcp = _make_mcp(FIXTURES / "clean")
        body = _call(mcp, "read_concept", name="Counter")
        assert "source" in body
        assert "concept Counter" in body["source"]
        assert body["ast"]["name"] == "Counter"

    def test_missing_concept_returns_error(self):
        mcp = _make_mcp(FIXTURES / "clean")
        body = _call(mcp, "read_concept", name="Nope")
        assert "error" in body


class TestValidateConcept:
    def test_clean_source_has_no_errors(self):
        mcp = _make_mcp(FIXTURES / "clean")
        source = (FIXTURES / "clean" / "concepts" / "Counter.concept").read_text()
        body = _call(mcp, "validate_concept", source=source)
        assert body["valid"] is True
        assert all(d["severity"] != "error" for d in body["diagnostics"])

    def test_purpose_missing_source_fires_c5(self):
        mcp = _make_mcp(FIXTURES / "clean")
        source = (FIXTURES / "with_error" / "concepts" / "Counter.concept").read_text()
        body = _call(mcp, "validate_concept", source=source)
        assert body["valid"] is False
        codes = {d["code"] for d in body["diagnostics"]}
        assert "C5" in codes


class TestWriteConcept:
    def test_refuses_invalid_write(self, tmp_path):
        # Copy the clean fixture into a writable temp workspace.
        workspace = tmp_path / "ws"
        _copy_workspace(FIXTURES / "clean", workspace)
        mcp = _make_mcp(workspace)

        bad_source = (FIXTURES / "with_error" / "concepts" / "Counter.concept").read_text()
        body = _call(mcp, "write_concept", name="Broken", source=bad_source)
        assert body["written"] is False
        assert body["valid"] is False
        assert not (workspace / "concepts" / "Broken.concept").exists()

    def test_accepts_valid_write(self, tmp_path):
        workspace = tmp_path / "ws"
        _copy_workspace(FIXTURES / "clean", workspace)
        mcp = _make_mcp(workspace)

        good = (FIXTURES / "clean" / "concepts" / "Counter.concept").read_text()
        body = _call(mcp, "write_concept", name="Counter2", source=good)
        assert body["written"] is True
        assert (workspace / "concepts" / "Counter2.concept").exists()


# ---------------------------------------------------------------------------
# Sync tools
# ---------------------------------------------------------------------------


class TestListSyncs:
    def test_clean_workspace_lists_log(self):
        mcp = _make_mcp(FIXTURES / "clean")
        body = _call(mcp, "list_syncs")
        assert body == ["log"]  # filename stem is `log`

    def test_empty_workspace_lists_nothing(self):
        mcp = _make_mcp(FIXTURES / "empty")
        body = _call(mcp, "list_syncs")
        assert body == []


class TestReadSync:
    def test_reads_existing_sync(self):
        mcp = _make_mcp(FIXTURES / "clean")
        body = _call(mcp, "read_sync", name="log")
        assert "sync LogInc" in body["source"]
        assert body["ast"]["name"] == "LogInc"

    def test_missing_sync_returns_error(self):
        mcp = _make_mcp(FIXTURES / "clean")
        body = _call(mcp, "read_sync", name="nope")
        assert "error" in body


class TestValidateSync:
    def test_clean_sync_has_no_errors(self):
        mcp = _make_mcp(FIXTURES / "clean")
        source = (FIXTURES / "clean" / "syncs" / "log.sync").read_text()
        body = _call(mcp, "validate_sync", source=source)
        # The clean fixture has both Counter and Logger concepts, so S1
        # should not fire.
        errors = [d for d in body["diagnostics"] if d["severity"] == "error"]
        assert errors == []


# ---------------------------------------------------------------------------
# Workspace tools
# ---------------------------------------------------------------------------


class TestValidateWorkspace:
    def test_clean_workspace_reports_no_errors(self):
        mcp = _make_mcp(FIXTURES / "clean")
        body = _call(mcp, "validate_workspace")
        errors = [d for d in body["diagnostics"] if d["severity"] == "error"]
        assert errors == []
        assert body["concept_count"] == 2
        assert body["sync_count"] == 1

    def test_with_error_workspace_reports_c5(self):
        mcp = _make_mcp(FIXTURES / "with_error")
        body = _call(mcp, "validate_workspace")
        codes = {d["code"] for d in body["diagnostics"]}
        assert "C5" in codes
        assert body["valid"] is False


class TestGetWorkspaceGraph:
    def test_clean_workspace_has_counter_and_sync_edge(self):
        mcp = _make_mcp(FIXTURES / "clean")
        s = mcp.tools["get_workspace_graph"]()
        assert s.startswith("graph TD")
        assert "Counter" in s
        assert "Logger" in s
        assert "LogInc" in s

    def test_empty_workspace_returns_placeholder(self):
        mcp = _make_mcp(FIXTURES / "empty")
        s = mcp.tools["get_workspace_graph"]()
        assert "No concepts" in s or "No syncs" in s

    def test_dependency_graph_alias_matches_workspace_graph(self):
        mcp = _make_mcp(FIXTURES / "clean")
        new = mcp.tools["get_workspace_graph"]()
        old = mcp.tools["get_dependency_graph"]()
        assert new == old


# ---------------------------------------------------------------------------
# Diff tools (smoke tests)
# ---------------------------------------------------------------------------


class TestDiffTools:
    def test_diff_concept_identical(self):
        mcp = _make_mcp(FIXTURES / "clean")
        source = (FIXTURES / "clean" / "concepts" / "Counter.concept").read_text()
        body = _call(mcp, "diff_concept", old_source=source, new_source=source)
        assert body["has_changes"] is False


# ---------------------------------------------------------------------------
# Explorer tools (smoke)
# ---------------------------------------------------------------------------


class TestExplorerTools:
    def test_get_explorer_html_returns_html(self):
        mcp = _make_mcp(FIXTURES / "clean")
        html = mcp.tools["get_explorer_html"]()
        assert "<html" in html
        assert "Counter" in html
```

- [ ] **Step 19.2: Run the tests**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: every test passes. If a test fails because the `log.sync` fixture fires an unexpected sync rule, check Task 18's fixtures — the `clean` workspace is supposed to declare both `Counter` and `Logger` so that S1 / S2 do not fire.

If the `Counter.concept` fixture does not parse cleanly (Task 18.4 was supposed to verify this), go back and fix it before proceeding.

- [ ] **Step 19.3: Commit**

```bash
git add tests/test_mcp_tools.py
git commit -m "test(mcp): integration tests for v2 tool layer"
```

---

## Task 20: Line-number tightening for the remaining negative fixtures (optional)

This is a small follow-up carried over from P3 — the spec's position-threading contract says every diagnostic should carry a real line number, and P3 only tightened 4 of the 13 fixtures (C1, C2, C3, S1). The other 9 fixtures still use `"line": null` in their `.expected.json`. P3's §7 step `_assert_expected_in_diagnostics` accepts both `null` (match anything) and an integer (exact match), so tightening is purely additive.

This task tightens C4 (if not already done in commit `35cd3f7` per the brief — confirm and skip if so), C5, C6, C7, C9, S2, S3, S4, S5.

**Files:**
- Modify: `tests/fixtures/negative/C5_missing_purpose.expected.json`
- Modify: `tests/fixtures/negative/C6_no_actions.expected.json`
- Modify: `tests/fixtures/negative/C7_only_error_cases.expected.json`
- Modify: `tests/fixtures/negative/C9_missing_op_principle.expected.json`
- Modify: `tests/fixtures/negative/S2_pattern_field_not_in_action.expected.json`
- Modify: `tests/fixtures/negative/S3_then_var_not_bound.expected.json`
- Modify: `tests/fixtures/negative/S4_where_var_not_bound.expected.json`
- Modify: `tests/fixtures/negative/S5_sync_references_one_concept.expected.json`

- [ ] **Step 20.1: Determine the real line number for each fixture**

For each fixture, run the validator and record the line reported by each diagnostic:

```bash
uv run python -c "
from pathlib import Path
from concept_lang.validate import validate_concept_file, validate_sync_file

for stem in ['C5_missing_purpose', 'C6_no_actions', 'C7_only_error_cases', 'C9_missing_op_principle']:
    path = Path(f'tests/fixtures/negative/{stem}.concept')
    for d in validate_concept_file(path):
        if d.code[0] == stem[0]:
            print(stem, d.code, d.line)

for stem in ['S2_pattern_field_not_in_action', 'S3_then_var_not_bound', 'S4_where_var_not_bound', 'S5_sync_references_one_concept']:
    path = Path(f'tests/fixtures/negative/{stem}.sync')
    for d in validate_sync_file(path):
        if d.code[0] == stem[0]:
            print(stem, d.code, d.line)
"
```

Expected: one (fixture, code, line) triple per fixture. Write each result down. If any fixture prints `None` for the line, that diagnostic was never position-threaded in P3 — note it as a follow-up (do not tighten that entry; leave `"line": null`).

- [ ] **Step 20.2: Update each `.expected.json` in turn**

For each fixture whose line was a concrete integer, open the matching `tests/fixtures/negative/<stem>.expected.json` and replace the `"line": null` entry with `"line": <the integer from step 20.1>`. Leave every other field (severity, code, message) unchanged.

- [ ] **Step 20.3: Run the negative-fixture sweep**

Run: `uv run pytest tests/test_validate.py -k "negative" -v`
Expected: every tightened fixture still passes. If a tightened fixture fails, check whether the diagnostic was reporting against the wrong node — that is a real P2 bug and should be filed as a P4 follow-up rather than masked by reverting to `null`.

- [ ] **Step 20.4: Commit**

```bash
git add tests/fixtures/negative/
git commit -m "test(fixtures): tighten line numbers for remaining negative fixtures"
```

**Optional task:** if any tightening exposes a latent position bug, skip the fix in P4 (P4 is a wiring phase; position regressions belong in a P3 follow-up). Revert the offending `.expected.json` to `"line": null` and flag the fixture in the "What's next" section at the bottom of this plan.

---

## Task 21: P4 gate — integration smoke test and tag

The gate test exercises the full P4 pipeline: load → validate → explorer → graph → diff → tool layer. It runs against both positive fixtures (architecture_ide and realworld) plus the new MCP fixture.

**Files:**
- Modify: `tests/test_mcp_tools.py`

- [ ] **Step 21.1: Append the gate class**

Append to `tests/test_mcp_tools.py`:

```python
class TestP4Gate:
    """
    End-to-end: every P4 MCP tool runs against a positive fixture workspace
    and produces a well-formed response.
    """

    REALWORLD = Path(__file__).parent / "fixtures" / "realworld"
    ARCHITECTURE_IDE = Path(__file__).parent / "fixtures" / "architecture_ide"

    @pytest.mark.parametrize("root", [REALWORLD, ARCHITECTURE_IDE])
    def test_whole_pipeline_on_positive_fixture(self, root: Path):
        mcp = _make_mcp(root)

        # list
        concepts = _call(mcp, "list_concepts")
        syncs = _call(mcp, "list_syncs")
        assert isinstance(concepts, list)
        assert isinstance(syncs, list)
        assert len(concepts) > 0

        # read one concept and one sync (if present)
        first_concept = concepts[0]
        read = _call(mcp, "read_concept", name=first_concept)
        assert "source" in read
        assert read["ast"]["name"]

        if syncs:
            first_sync = syncs[0]
            read_s = _call(mcp, "read_sync", name=first_sync)
            assert "source" in read_s

        # validate whole workspace
        vw = _call(mcp, "validate_workspace")
        errors = [d for d in vw["diagnostics"] if d["severity"] == "error"]
        assert errors == [], (
            f"positive fixture {root.name} should validate cleanly, got: "
            + json.dumps(errors, indent=2)
        )

        # workspace graph
        g = mcp.tools["get_workspace_graph"]()
        assert g.startswith("graph TD")
        for name in concepts:
            assert name in g

        # explorer HTML
        html = mcp.tools["get_explorer_html"]()
        assert "<html" in html
        for name in concepts:
            assert name in html
```

- [ ] **Step 21.2: Run the gate test**

Run: `uv run pytest tests/test_mcp_tools.py::TestP4Gate -v`
Expected: 2 passed (one per positive fixture).

If the realworld fixture fails with a validator error, re-read the diagnostic: it is almost certainly a real regression in Task 6 / 7 / 8's `_validate_*_source` helpers (double-counting a C-rule, etc.). Fix there, not in the fixture.

- [ ] **Step 21.3: Run the full project test suite**

Run: `uv run pytest -v`
Expected: every test in the project passes. Roughly:

- `tests/test_ast.py` (P1 AST + P3 positions)
- `tests/test_parse.py` (P1 parse + P3 position integration)
- `tests/test_validate.py` (P2 validator + P3 position assertions + P4 tightened fixtures)
- `tests/test_loader.py` (P3 loader)
- `tests/test_diff.py` (P4 rewritten against new AST)
- `tests/test_explorer.py` (P4 new test file)
- `tests/test_mcp_tools.py` (P4 new test file, including gate)
- `tests/test_validator.py` (untouched v1 validator)

Count should land somewhere around **240+**: 206 baseline from P3, minus the old diff tests (~40), plus the new diff tests (~20), plus `test_explorer.py` (~10), plus `test_mcp_tools.py` (~25), plus the gate (~2). Exact numbers will drift; do not hard-code a target count in the test suite.

- [ ] **Step 21.4: Commit the gate**

```bash
git add tests/test_mcp_tools.py
git commit -m "test(gate): P4 gate — load → validate → explorer → graph end-to-end"
```

- [ ] **Step 21.5: Tag the milestone**

```bash
git tag p4-tooling-migration-complete -m "P4 gate passed: MCP tool layer wired to new AST + validator + loader"
```

- [ ] **Step 21.6: Final status check**

Run: `git log --oneline -30`
Expected: ~21 small commits in the `refactor(diff|explorer|tools|server|resources|prompts|__init__)` / `feat(tools/sync|tools/workspace)` / `test(diff|explorer|mcp|fixtures|gate)` namespace, ending with `test(gate)` and the tag `p4-tooling-migration-complete`.

---

## What's next (not in this plan)

After this plan lands and the `p4-tooling-migration-complete` tag is in place, the follow-up plans are:

- **P5 — Skills rewrite**: `build`, `build-sync` (new), `review`, `scaffold`, `explore`. Each skill's markdown prompts get updated to call the new MCP tool names (`get_workspace_graph`, `read_sync`, `validate_workspace`) and to speak the new concept + sync format. The `scaffold_concepts` tool's embedded methodology block gets replaced here too.
- **P6 — Examples + docs**: update `architecture-ide/concepts/*` in place (they are still in v1 format on disk), split into `architecture-ide/concepts/` and `architecture-ide/syncs/`, rewrite `README.md`, add `docs/methodology.md`. At this point the default `CONCEPTS_DIR=./concepts` back-compat shim can be dropped because every shipped example uses the new layout.
- **P7 — Delete v1**: remove `concept_lang.parser`, `concept_lang.models`, `concept_lang.validator`, `concept_lang.app_parser`, `concept_lang.app_validator`, `concept_lang.diagrams` (if not migrated by then), and their tests. Drop the `_to_v1_concept` adapter from `explorer.py`. Drop the `concept_lang.codegen` module (or promote it to a separate package). Remove the `get_dependency_graph` backward-compat alias. This plan assumes P5 and P6 have been merged and no MCP consumer still imports the old names.

Two small design questions still live in the P4 region and should be addressed in one of the above phases:

- **App-spec format migration**. The `.app` format is still v1 and `concept_lang.app_parser` / `concept_lang.app_validator` are still untouched. A dedicated plan (post-P7) should introduce an `AppSpec` AST in `concept_lang.ast`, write a Lark grammar, and port the app-spec tools onto it. Until then the v1 path stays fenced off behind `register_app_tools` and is the only reason `concept_lang.models` / `concept_lang.parser` still need to exist.
- **`OPStep.inputs/outputs` tuple shape**. P3 flagged this as a P5/P6 decision and P4 did not touch it. The explorer currently surfaces OP-step args as `list[tuple[str, str]]` in the embedded JSON payload. If a future rule or skill needs to distinguish literal arguments from variable references, this becomes a real problem. P6 (docs + examples) is the natural place to resolve it because the distinction between "OP step args" and "sync pattern fields" becomes user-visible there.

Additional follow-up noted during P4 execution (to be filled in by the executor as they go):

- **(fill in)** — fixtures where position tightening exposed a latent P3 bug, if any.
- **(fill in)** — any tool whose MCP integration test revealed a false-positive diagnostic.
- **(fill in)** — any v1 adapter (`_to_v1_concept`) corner case that the explorer round-trip loses.

Each follow-up deserves its own ticket or its own plan, written after P4 lands so we're planning on verified ground.

---

## Self-review (filled in after drafting, before execution)

- **Spec coverage** — every MCP tool from spec §5.1 has a task:

  | Spec tool | Task | Status in P4 |
  |---|---|---|
  | `read_concept` | Task 6 | updated — new AST shape |
  | `write_concept` | Task 6 | updated — validates on write |
  | `list_concepts` | Task 6 | updated — concepts only |
  | `validate_concept` | Task 6 | updated — C1..C9 + cross-refs |
  | `get_workspace_graph` (rename) | Task 8 | new name, edges are syncs |
  | `get_dependency_graph` (alias) | Task 8 | back-compat alias |
  | `read_sync` | Task 7 | new |
  | `write_sync` | Task 7 | new — validates on write |
  | `list_syncs` | Task 7 | new |
  | `validate_sync` | Task 7 | new — S1..S5 |
  | `validate_workspace` | Task 8 | new — all rules, all files |

  Supporting infrastructure tasks:

  | Scope item | Task(s) |
  |---|---|
  | `diff.py` new AST | Task 1 |
  | `diff.py` tests rewritten | Task 2 |
  | `explorer.py` new AST + syncs-as-edges | Task 3 |
  | `explorer.py` tests | Task 4 |
  | `tools/_io.py` workspace-root helpers | Task 5 |
  | `tools/__init__.py` registrations | Task 12 |
  | `server.py` rewire + env-var back-compat | Task 13 |
  | `resources.py` updated | Task 14 |
  | `prompts.py` tool-name update | Task 15 |
  | `concept_lang.__init__` surface cleanup | Task 16 |
  | `app_tools.py` workspace_root param (v1 internals) | Task 17 |
  | `diagram_tools.py` drop dependency_graph | Task 11 |
  | MCP fixture workspace | Task 18 |
  | MCP integration tests | Task 19 |
  | Fixture line-number tightening (P3 follow-up) | Task 20 |
  | P4 gate + tag | Task 21 |

- **Placeholder scan** — every code block is a literal drop-in. The only "fill this in" points are:
  - Task 18's fixture bodies, which are known-good but may need minor tweaks if the P1 grammar is stricter than anticipated; the task includes a verification step that catches this.
  - Task 20's line numbers, which are explicitly computed in-task by running the validator.
  - "What's next" has three `(fill in)` bullet points that are placeholders for the executor to record any follow-ups they discover. These are deliberate — they are not code placeholders, they are notes for the retrospective.

- **Type consistency** — across every task:
  - Tool entry points consistently take `workspace_root: str` (not `Path`). Internal helpers in `_io.py` convert to `Path` once via `resolve_workspace_root`.
  - Diagnostic list shape is always `list[Diagnostic]` inside Python, serialized as `list[dict]` via `d.model_dump(mode="json")` at MCP boundaries.
  - Tool response envelope: `{"valid": bool, "diagnostics": [...], ...tool-specific fields}`. `write_*` tools add `{"written": bool, "path": str | not present}`.
  - `diff_concepts_with_impact` takes a `Workspace | None`, not a `list[ConceptAST]`. Tasks 1, 2, 9 are consistent.
  - Every MCP tool that parses concept or sync source uses `parse_concept_source` / `parse_sync_source` from `concept_lang.parse`; no task calls into `concept_lang.parser` (v1) except `app_tools.py` which is explicitly on v1.

- **Ambiguity check** —
  - "Workspace root" is defined once in decision (B) and never ambiguous again. The helper `_resolve_workspace_root` is the single point of resolution.
  - "Cross-reference rules" (S1/S2) are only run in Tasks 6 and 7 via `validate_workspace` / `validate_sync_file(extra_concepts=...)`. No task invents a third path.
  - "Syncs as edges" graph semantics are pinned in decision (E), documented in Task 8's implementation, and tested in Task 4 and Task 19.
  - The temp-file validation pattern (Tasks 6, 7) is defined once via `_validate_concept_source` / `_validate_sync_source` helpers. Both helpers use the same cleanup-in-finally structure; neither task duplicates the other's pattern.
  - The `_FakeMCP` test helper (Task 19) is defined once at the top of `test_mcp_tools.py` and reused by every test class. No task proposes a parallel testing fixture.

- **Scope discipline** — no new validator rules (C8 stays deferred), no grammar edits, no AST type changes, no `codegen/` touches (the file stays but is unregistered in `tools/__init__.py`), no changes to `concept_lang.diagrams` beyond the v1-adapter bridge in `explorer.py` and `diagram_tools.py`, no skill markdown changes, no README touches, no v1 module deletions, no app-format migration.

- **Commit discipline** — every task ends with exactly one `git add` + `git commit` covering the files listed in its Files section. Tasks that create fixture trees commit fixtures with the test file that pins them (Task 18 is the one exception: its fixtures are committed on their own because they feed the Task 19 tests). No task commits v1 files (the only modifications to v1 files are Task 17's tightened imports in `app_tools.py`, which stays on v1 but gets a new signature).

- **Test strategy coherence** — the test pyramid is: (1) unit tests for the diff engine and explorer internals (Tasks 2, 4), (2) integration tests for the MCP tool layer via `_FakeMCP` (Task 19), (3) an end-to-end gate that runs against both positive-fixture workspaces (Task 21). No protocol-level MCP test exists; the plan explicitly defers that to P5 when the skill pipeline lands and real end-to-end verification becomes possible.

- **Back-compat guarantees pinned** — (i) `CONCEPTS_DIR=./concepts` keeps working (Task 5's `resolve_workspace_root` + Task 13's env-var fallback), (ii) `get_dependency_graph` is still a callable tool name (Task 8's alias + Task 19's test), (iii) `read_concept` / `write_concept` response shape still has `source` and returns a JSON string (Task 6's `_diag_list` adds `diagnostics`, does not remove anything), (iv) the v1 app-spec path keeps working end-to-end (Task 17 preserves the internals).

- **Running discipline** — every task has a "replace / create the file" step, a "smoke-import or run the targeted test" step, and (for the ones that modify shared modules) a "run the broader suite" step before committing. No task skips straight to commit.
