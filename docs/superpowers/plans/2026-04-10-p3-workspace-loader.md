# concept-lang 0.2.0 — P3: Workspace Loader + Source Positions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship two capabilities on top of the P2 validator: (1) a directory-walking `load_workspace(root)` that reads every `.concept` and `.sync` file under a root and returns a populated `Workspace` plus per-file parse-error diagnostics, and (2) real Lark source positions threaded through the concept and sync transformers so every user-visible AST node carries `line`/`column`, and every existing validator diagnostic (C1–C9 minus C8, S1–S5) reports a real line number instead of `None`.

**Architecture:** One new module, `concept_lang.loader`. Position threading is a local modification to `concept_lang.ast` (optional `line`/`column` fields with `None` defaults), `concept_lang.parse` (enable `propagate_positions=True` on the Lark constructor), and the two existing transformers (switch selected rule methods to `@v_args(meta=True, inline=True)` so they receive a `Meta` object). The v1 code is still untouched — P4 migrates tooling, P7 deletes v1.

**Tech Stack:** Python 3.10+, Lark (already in deps), Pydantic 2, pytest, uv. No new runtime dependencies.

**Scope note:** This plan covers **P3 only**.

- In scope: source-position fields on user-visible AST nodes, Lark `propagate_positions=True`, transformer meta-plumbing, `load_workspace()` directory walker with partial-load semantics, validator rule sweeps to thread positions into every existing diagnostic, tightened `*.expected.json` line numbers for a representative subset of negative fixtures, and the P3 gate + tag.
- Out of scope: app-spec loading (the v1 `concept_lang.app_parser` / `concept_lang.app_validator` pair stays until P4 migrates it; `load_workspace` deliberately does **not** read `apps/*.app`), MCP tool changes (P4), skills rewrites (P5), v1 code deletion (P7), and any new validator rules (including the still-deferred C8).

**Spec reference:** [`docs/superpowers/specs/2026-04-10-paper-alignment-design.md`](../specs/2026-04-10-paper-alignment-design.md) §4.4 (data flow) and §5.1 (`load_workspace()` backbone for MCP tools). `Diagnostic.line`/`column` are defined in §4.5.

**Starting state:** Branch `feat/p1-parser`, HEAD at tag `p2-validator-complete` (`31b4dd0`). `concept_lang.ast`, `concept_lang.parse`, `concept_lang.validate`, and both fixture workspaces exist. `uv run pytest` reports **148 passing**. The v1 modules (`concept_lang.parser`, `concept_lang.models`, `concept_lang.validator`, `concept_lang.app_parser`, `concept_lang.app_validator`) are untouched and continue to pass their own tests.

---

## File structure (what this plan creates or modifies)

```
architecture-ide/
  src/concept_lang/
    __init__.py                                    # MODIFY: re-export load_workspace
    ast.py                                         # MODIFY: add line/column to positioned nodes
    parse.py                                       # MODIFY: propagate_positions=True on Lark(...)
    loader.py                                      # CREATE: load_workspace directory walker
    transformers/
      concept_transformer.py                       # MODIFY: thread meta through rule methods
      sync_transformer.py                          # MODIFY: thread meta through rule methods
    validate/
      concept_rules.py                             # MODIFY: use node.line instead of line=None
      sync_rules.py                                # MODIFY: use node.line instead of line=None
    # v1 files STILL UNTOUCHED:
    #   parser.py, models.py, validator.py, app_parser.py, app_validator.py, ...
  tests/
    __init__.py                                    # CREATE: empty package marker (see Task 1)
    test_ast.py                                    # MODIFY: new position round-trip tests
    test_parse.py                                  # MODIFY: position-threading integration tests
    test_validate.py                               # MODIFY: position assertions + tightened matcher
    test_loader.py                                 # CREATE: load_workspace unit + integration tests
    fixtures/
      loader/                                      # CREATE: tiny curated trees for loader tests
        clean/
          concepts/
            Counter.concept
          syncs/
            log.sync
        bad_concept/
          concepts/
            Broken.concept
            Counter.concept
          syncs/
            log.sync
        empty/
          concepts/
            .gitkeep
          syncs/
            .gitkeep
        concepts_only/
          concepts/
            Counter.concept
        syncs_only/
          syncs/
            standalone.sync
      negative/                                    # MODIFY: tighten line numbers in 4 fixtures
        C1_state_references_other_concept.expected.json
        C2_effects_references_foreign_state.expected.json
        C3_op_principle_uses_foreign_action.expected.json
        S1_sync_references_unknown_concept.expected.json
```

**All commands below assume the working directory is `architecture-ide/`** (the package root with `pyproject.toml`). All paths in Files sections are relative to that directory.

**Design decisions (made and justified up front; later tasks reference them by letter):**

- **(A) Position representation.** Every positioned AST node gains two optional fields, `line: int | None = None` and `column: int | None = None`, directly on the node. **We do NOT introduce a `SourceSpan` type.** Rationale: the validator's `Diagnostic` model already flattens positions to `line`/`column`, so a wrapper class would only add an indirection at every access site. End-line / end-column are not needed for P3's diagnostics (the paper's rule set all points at a single location). If a later phase needs span highlighting, it can add `SourceSpan` on top without touching P3's field names — the current `line`/`column` stay as the single-point shorthand.
- **(B) Which nodes get positions.** The **user-visible, top-level-ish** nodes do: `ConceptAST`, `StateDecl`, `Action`, `ActionCase`, `EffectClause`, `OperationalPrinciple`, `OPStep`, `SyncAST`, `ActionPattern`, `StateQuery`, `BindClause`, `WhereClause`. The **purely structural helpers** do **not** get positions: `TypedName`, `PatternField`, `Triple`. Rationale: every validator diagnostic in P2 points at a node from the first group, so threading positions into helpers would be plumbing with no payoff. A `TypedName` position can always be recovered from its enclosing `ActionCase` / `OPStep` / `StateDecl` if a future rule needs it.
- **(C) Transformer meta plumbing.** We enable `propagate_positions=True` on both `Lark(...)` constructors in `parse.py`, and switch only the rule methods that produce positioned AST nodes to `@v_args(meta=True, inline=True)`. That decorator override on a single method works even when the class is already decorated with `@v_args(inline=True)` (verified against the live grammar). Leaf token methods (`NAME`, `TYPE_EXPR`, etc.) stay as-is — they see a `Token` and do not need `meta`. Rationale: this is the smallest diff that produces correct positions; we don't rewrite either transformer's shape.
- **(D) `load_workspace` return signature.** `load_workspace(root: Path) -> tuple[Workspace, list[Diagnostic]]`. A partial workspace plus a list of `P0` parse-error diagnostics (one per file that failed to parse). Callers that want "all or nothing" semantics can check `any(d.severity == "error" for d in diags)`. Rationale: the paper-aligned flow is "best effort, show me everything" — a broken `Web.concept` should not hide a clean `Password.concept` from the tool. This also keeps `load_workspace` composable with `validate_workspace`: concat the two diagnostic lists.
- **(E) Negative-fixture line tightening.** We tighten **four** fixtures to exact line numbers (C1, C2, C3, S1) as a visible demonstration that positions flow all the way from source to `*.expected.json`. The other nine stay as `"line": null`. The negative-fixture sweep in `test_validate.py` is updated to allow both `null` (match anything) and an integer (exact match) per expected entry. Rationale: tightening every fixture is busywork once a handful have demonstrated the contract; `null` remains a valid matcher so the other fixtures don't need rewrites.
- **(F) Follow-ups from P2 that P3 does / does not address.**
  - `tests/__init__.py` is **added** in Task 1 (tiny fix before any other test import). Rationale: Task 20 of P2 used `sys.modules[__name__]` as a workaround; this plan exercises enough new test modules that a real package marker is cheaper than repeating the workaround.
  - `C8` (state field referenced in effects, warning) stays **deferred**. Rationale: P3's mandate is "thread positions through what exists". Adding a rule during a wiring phase is scope creep.
  - `OPStep.inputs/outputs as tuple[str, str]` stays **as-is**. Rationale: this is a semantic question about whether OP-step arguments should ever be unified with sync `PatternField`s. It deserves a dedicated discussion, not a drive-by change in a plumbing phase. Flag it in the closing "What's next" section.

**Validator positioning contract (used throughout the later tasks):**

> When a rule flags an AST node, the diagnostic's `line` and `column` come directly from that node's `line`/`column` fields. If the node has `line=None` (should not happen for parser output after P3, but may happen in hand-built test ASTs), the diagnostic also carries `line=None`. Rules never fabricate positions.

---

## Task 1: Promote `tests/` to a real package

A P2 follow-up. P2's Task 20 gate used `sys.modules[__name__]` to introspect the current test module because `tests/` was not yet a Python package. P3 uses enough new test modules (`test_loader.py`, additions to `test_parse.py` and `test_validate.py`) that a proper package marker is the cleanest path.

**Files:**
- Create: `tests/__init__.py`

- [ ] **Step 1.1: Create the empty marker**

Create `tests/__init__.py`:

```python
"""Test package for concept-lang 0.2.0 (P1+P2+P3)."""
```

- [ ] **Step 1.2: Confirm the test suite still runs**

Run: `uv run pytest -q`
Expected: 148 passed (same count as the P2 gate).

- [ ] **Step 1.3: Commit**

```bash
git add tests/__init__.py
git commit -m "test: promote tests/ to a package for cross-module imports"
```

---

## Task 2: Add `line`/`column` fields to concept AST nodes

Per decision (B), the user-visible concept nodes are: `ConceptAST`, `StateDecl`, `Action`, `ActionCase`, `EffectClause`, `OperationalPrinciple`, `OPStep`. `TypedName` deliberately does not get positions — its enclosing node always carries one.

**Files:**
- Modify: `src/concept_lang/ast.py`
- Modify: `tests/test_ast.py`

- [ ] **Step 2.1: Write the failing test**

Append to `tests/test_ast.py`:

```python
class TestConceptASTPositions:
    def test_concept_ast_line_defaults_to_none(self):
        ast = TestConceptAST()._make_password_concept()
        assert ast.line is None
        assert ast.column is None

    def test_state_decl_line_defaults_to_none(self):
        decl = StateDecl(name="total", type_expr="int")
        assert decl.line is None
        assert decl.column is None

    def test_action_line_roundtrip(self):
        action = Action(
            name="inc",
            cases=[ActionCase(inputs=[], outputs=[])],
            line=12,
            column=5,
        )
        dumped = action.model_dump()
        assert dumped["line"] == 12
        assert dumped["column"] == 5
        assert Action.model_validate(dumped) == action

    def test_action_case_line_roundtrip(self):
        case = ActionCase(inputs=[], outputs=[], line=15, column=7)
        assert ActionCase.model_validate(case.model_dump()) == case

    def test_effect_clause_line_roundtrip(self):
        ec = EffectClause(
            raw="total := total + 1",
            field="total",
            op=":=",
            rhs="total + 1",
            line=20,
            column=9,
        )
        assert EffectClause.model_validate(ec.model_dump()) == ec

    def test_operational_principle_line_roundtrip(self):
        op = OperationalPrinciple(steps=[], line=30, column=3)
        assert OperationalPrinciple.model_validate(op.model_dump()) == op

    def test_op_step_line_roundtrip(self):
        step = OPStep(
            keyword="after",
            action_name="inc",
            inputs=[],
            outputs=[],
            line=33,
            column=5,
        )
        assert OPStep.model_validate(step.model_dump()) == step
```

- [ ] **Step 2.2: Run the test — it should fail**

Run: `uv run pytest tests/test_ast.py::TestConceptASTPositions -v`
Expected: `AttributeError` on the first assertion (`ast.line` does not exist yet), or `ValidationError: line: Extra inputs are not permitted` when constructing `Action(..., line=12)`.

- [ ] **Step 2.3: Add the fields**

Edit `src/concept_lang/ast.py`. Add two optional fields to each of the concept-side positioned nodes. The fields go at the bottom of the class body so they stay out of the way of the semantic fields. Apply the change to:

- `ConceptAST`
- `StateDecl`
- `Action`
- `ActionCase`
- `EffectClause`
- `OperationalPrinciple`
- `OPStep`

Each class gains exactly these two lines:

```python
    line: int | None = None
    column: int | None = None
```

For example, `ActionCase` becomes:

```python
class ActionCase(BaseModel):
    """
    One case of a multi-case action. A concept's action may have several
    cases sharing a name (e.g. one success case, one error case).
    """
    inputs: list[TypedName]
    outputs: list[TypedName]
    body: list[str] = []              # natural-language description lines
    effects: list[EffectClause] = []  # optional formal state deltas
    line: int | None = None
    column: int | None = None
```

Do **not** add `line`/`column` to `TypedName` (decision B).

- [ ] **Step 2.4: Run the test — should pass**

Run: `uv run pytest tests/test_ast.py::TestConceptASTPositions -v`
Expected: 7 passed.

- [ ] **Step 2.5: Sanity-check the existing AST tests**

Run: `uv run pytest tests/test_ast.py -v`
Expected: every existing test (`TestTypedName`, `TestEffectClause`, `TestConceptAST`, etc.) still passes. Defaults are `None`, so hand-constructed ASTs keep working; round-trips via `model_dump()` / `model_validate()` include the new fields but equality still holds.

- [ ] **Step 2.6: Commit**

```bash
git add src/concept_lang/ast.py tests/test_ast.py
git commit -m "feat(ast): optional line/column fields on concept nodes"
```

---

## Task 3: Add `line`/`column` fields to sync AST nodes

Per decision (B), the user-visible sync nodes are: `SyncAST`, `ActionPattern`, `StateQuery`, `BindClause`, `WhereClause`. `PatternField` and `Triple` stay unpositioned — they're structural helpers.

**Files:**
- Modify: `src/concept_lang/ast.py`
- Modify: `tests/test_ast.py`

- [ ] **Step 3.1: Write the failing test**

Append to `tests/test_ast.py`:

```python
class TestSyncASTPositions:
    def test_sync_ast_line_defaults_to_none(self):
        sync = TestSyncAST()._make_register_sync()
        assert sync.line is None
        assert sync.column is None

    def test_action_pattern_line_roundtrip(self):
        ap = ActionPattern(
            concept="Counter",
            action="inc",
            input_pattern=[],
            output_pattern=[],
            line=4,
            column=5,
        )
        assert ActionPattern.model_validate(ap.model_dump()) == ap

    def test_state_query_line_roundtrip(self):
        q = StateQuery(
            concept="Article",
            triples=[Triple(subject="?a", predicate="title", object="?t")],
            line=9,
            column=5,
        )
        assert StateQuery.model_validate(q.model_dump()) == q

    def test_bind_clause_line_roundtrip(self):
        b = BindClause(expression="uuid()", variable="?u", line=11, column=7)
        assert BindClause.model_validate(b.model_dump()) == b

    def test_where_clause_line_roundtrip(self):
        wc = WhereClause(queries=[], binds=[], line=8, column=3)
        assert WhereClause.model_validate(wc.model_dump()) == wc
```

- [ ] **Step 3.2: Run the test — should fail**

Run: `uv run pytest tests/test_ast.py::TestSyncASTPositions -v`
Expected: the first assertion fails (no `line` attribute on `SyncAST`) or a `ValidationError` for `ActionPattern(..., line=4)`.

- [ ] **Step 3.3: Add the fields**

Edit `src/concept_lang/ast.py`. Add `line`/`column` (same two lines as Task 2) to:

- `ActionPattern`
- `StateQuery`
- `BindClause`
- `WhereClause`
- `SyncAST`

Do **not** add them to `PatternField` or `Triple` (decision B).

- [ ] **Step 3.4: Run the test — should pass**

Run: `uv run pytest tests/test_ast.py::TestSyncASTPositions -v`
Expected: 5 passed.

- [ ] **Step 3.5: Full AST sanity check**

Run: `uv run pytest tests/test_ast.py -v`
Expected: every test in the file passes.

- [ ] **Step 3.6: Commit**

```bash
git add src/concept_lang/ast.py tests/test_ast.py
git commit -m "feat(ast): optional line/column fields on sync nodes"
```

---

## Task 4: Enable `propagate_positions=True` on both Lark parsers

Before we touch the transformers, we turn on Lark's position propagation. This alone doesn't change any test outcome (the transformers still ignore meta), but it makes `tree.meta.line` / `.column` populated on every parse tree node, which is the prerequisite for Task 5 and Task 6.

**Files:**
- Modify: `src/concept_lang/parse.py`
- Modify: `tests/test_parse.py`

- [ ] **Step 4.1: Write the failing test**

Append to `tests/test_parse.py`:

```python
class TestLarkPropagatePositions:
    """
    Pre-transformer sanity check: with propagate_positions=True, the raw
    Lark parse tree must carry .meta.line / .meta.column on interior nodes.
    This is the foundation for threading positions into the AST (Task 5/6).
    """

    def test_concept_parse_tree_has_meta_lines(self):
        from concept_lang.grammars import read_grammar
        from lark import Lark

        src = (
            "concept Counter\n"
            "\n"
            "  purpose\n"
            "    count things\n"
            "\n"
            "  state\n"
            "    total: int\n"
            "\n"
            "  actions\n"
            "    inc [ ] => [ total: int ]\n"
            "\n"
            "  operational principle\n"
            "    after inc [ ] => [ total: 1 ]\n"
        )
        parser = Lark(
            read_grammar("concept.lark"),
            parser="earley",
            maybe_placeholders=False,
            propagate_positions=True,
        )
        tree = parser.parse(src)
        # `state_decl` starts at line 7 in the source above (1-indexed).
        state_decl = next(
            t for t in tree.iter_subtrees() if t.data == "state_decl"
        )
        assert state_decl.meta.line == 7
        assert state_decl.meta.column >= 1

    def test_sync_parse_tree_has_meta_lines(self):
        from concept_lang.grammars import read_grammar
        from lark import Lark

        src = (
            "sync LogInc\n"
            "\n"
            "  when\n"
            "    Counter/inc: [ ] => [ total: ?total ]\n"
            "  then\n"
            "    Log/append: [ event: ?total ]\n"
        )
        parser = Lark(
            read_grammar("sync.lark"),
            parser="earley",
            maybe_placeholders=False,
            propagate_positions=True,
        )
        tree = parser.parse(src)
        action_patterns = [
            t for t in tree.iter_subtrees() if t.data == "action_pattern"
        ]
        assert action_patterns
        # First `action_pattern` is under `when` on line 4.
        assert action_patterns[0].meta.line == 4
```

- [ ] **Step 4.2: Run the test — may or may not fail**

Run: `uv run pytest tests/test_parse.py::TestLarkPropagatePositions -v`

Note: these tests build their own `Lark(...)` instances with `propagate_positions=True`, so they may actually pass before Step 4.3. That is acceptable — the tests exist to **pin** Lark's meta behavior so Task 5 and Task 6 can rely on it. The production parsers in `parse.py` still need the flag flipped in Step 4.3, because otherwise the transformers see empty metas.

- [ ] **Step 4.3: Enable the flag in `parse.py`**

Edit `src/concept_lang/parse.py`. In `_get_concept_parser`, add `propagate_positions=True` to the `Lark(...)` call:

```python
def _get_concept_parser() -> Lark:
    global _concept_parser
    if _concept_parser is None:
        _concept_parser = Lark(
            read_grammar("concept.lark"),
            parser="earley",
            maybe_placeholders=False,
            propagate_positions=True,
        )
    return _concept_parser
```

Do the same for `_get_sync_parser`:

```python
def _get_sync_parser() -> Lark:
    global _sync_parser
    if _sync_parser is None:
        _sync_parser = Lark(
            read_grammar("sync.lark"),
            parser="earley",
            maybe_placeholders=False,
            propagate_positions=True,
        )
    return _sync_parser
```

- [ ] **Step 4.4: Run the whole parse test suite**

Run: `uv run pytest tests/test_parse.py -v`
Expected: every existing `test_parse.py` test still passes (the transformers still ignore `meta`), and the new `TestLarkPropagatePositions` tests pass.

- [ ] **Step 4.5: Commit**

```bash
git add src/concept_lang/parse.py tests/test_parse.py
git commit -m "feat(parse): enable propagate_positions on both Lark parsers"
```

---

## Task 5: Thread positions through `ConceptTransformer`

Now the concept transformer picks up Lark's `Meta` objects and writes `line`/`column` onto the nodes it produces. Per decision (C), we override `@v_args` only on the methods that build a positioned AST node.

Lark's `Meta` object may be empty on rules that match zero tokens (e.g. an optional absent section). We check `meta.empty` and fall back to `None` in that case — our AST fields are optional specifically so this path is expressible.

**Files:**
- Modify: `src/concept_lang/transformers/concept_transformer.py`
- Modify: `tests/test_parse.py`

- [ ] **Step 5.1: Write the failing integration test**

Append to `tests/test_parse.py`:

```python
class TestConceptTransformerPositions:
    """
    Position threading from Lark's meta into the ConceptAST. Every assertion
    here pins one user-visible node to the specific source line it came from.
    """

    _SRC = (
        "concept Counter\n"                        # line 1
        "\n"                                         # line 2
        "  purpose\n"                                # line 3
        "    count things\n"                         # line 4
        "\n"                                         # line 5
        "  state\n"                                  # line 6
        "    total: int\n"                           # line 7
        "\n"                                         # line 8
        "  actions\n"                                # line 9
        "    inc [ n: int ] => [ total: int ]\n"    # line 10
        "      add n to total\n"                     # line 11
        "      effects:\n"                           # line 12
        "        total := total + n\n"               # line 13
        "\n"                                         # line 14
        "  operational principle\n"                  # line 15
        "    after inc [ n: 1 ] => [ total: 1 ]\n"  # line 16
    )

    def _parse(self):
        return parse_concept_source(self._SRC)

    def test_concept_ast_line_is_1(self):
        ast = self._parse()
        assert ast.line == 1
        assert ast.column == 1

    def test_state_decl_line_is_7(self):
        ast = self._parse()
        assert len(ast.state) == 1
        assert ast.state[0].line == 7

    def test_action_case_line_is_10(self):
        ast = self._parse()
        assert len(ast.actions) == 1
        case = ast.actions[0].cases[0]
        assert case.line == 10

    def test_action_line_is_10(self):
        ast = self._parse()
        assert ast.actions[0].line == 10

    def test_effect_clause_line_is_13(self):
        ast = self._parse()
        effects = ast.actions[0].cases[0].effects
        assert len(effects) == 1
        assert effects[0].line == 13

    def test_op_step_line_is_16(self):
        ast = self._parse()
        assert ast.operational_principle.steps[0].line == 16

    def test_operational_principle_line_is_15(self):
        ast = self._parse()
        # `operational principle` keyword starts on line 15.
        assert ast.operational_principle.line == 15
```

- [ ] **Step 5.2: Run the test — will fail**

Run: `uv run pytest tests/test_parse.py::TestConceptTransformerPositions -v`
Expected: every assertion fails because the transformer still writes `line=None`.

- [ ] **Step 5.3: Thread meta through the concept transformer**

Edit `src/concept_lang/transformers/concept_transformer.py`. The class stays decorated with `@v_args(inline=True)` at the top. Add an import for `Meta` and a small helper at module scope that converts a Lark `Meta` to an `(int | None, int | None)` tuple:

```python
from lark.tree import Meta


def _pos(meta: Meta) -> tuple[int | None, int | None]:
    """Extract (line, column) from a Lark Meta, tolerating empty metas."""
    if meta is None or meta.empty:
        return (None, None)
    return (meta.line, meta.column)
```

Then convert the rule methods that produce positioned nodes to `@v_args(meta=True, inline=True)`. The per-method override takes precedence over the class-level decorator. Only these methods need changing:

1. `state_decl`
2. `effect_line`
3. `action_case`
4. `op_step`
5. `op_section` (produces `OperationalPrinciple`)
6. `concept_def` (produces `ConceptAST`)

Here is each edit, verbatim. Leave every other method untouched.

**`state_decl`:**

```python
    @v_args(meta=True, inline=True)
    def state_decl(self, meta: Meta, name: str, type_expr: str) -> StateDecl:
        line, col = _pos(meta)
        return StateDecl(name=name, type_expr=type_expr, line=line, column=col)
```

**`effect_line`:**

```python
    @v_args(meta=True, inline=True)
    def effect_line(
        self, meta: Meta, field_ref: str, op: str, rhs: str
    ) -> EffectClause:
        # field_ref might be "password[user]" — strip subscript for .field
        field_name = field_ref.split("[", 1)[0]
        line, col = _pos(meta)
        return EffectClause(
            raw=f"{field_ref} {op} {rhs}",
            field=field_name,
            op=op,  # type: ignore[arg-type]
            rhs=rhs,
            line=line,
            column=col,
        )
```

**`action_case`:**

```python
    @v_args(meta=True, inline=True)
    def action_case(self, meta: Meta, name: str, *rest) -> tuple[str, ActionCase]:
        inputs: list[TypedName] = []
        outputs: list[TypedName] = []
        body_lines: list[str] = []
        effects: list[EffectClause] = []

        list_args = [r for r in rest if isinstance(r, list)]
        tuple_args = [r for r in rest if isinstance(r, tuple)]

        if len(list_args) == 2:
            inputs, outputs = list_args
        elif len(list_args) == 1:
            idx_first_list = next(i for i, r in enumerate(rest) if isinstance(r, list))
            if idx_first_list == 0:
                inputs = list_args[0]
            else:
                outputs = list_args[0]

        if tuple_args:
            body_lines, effects = tuple_args[0]

        line, col = _pos(meta)
        return name, ActionCase(
            inputs=inputs,
            outputs=outputs,
            body=body_lines,
            effects=effects,
            line=line,
            column=col,
        )
```

**`op_step`:**

```python
    @v_args(meta=True, inline=True)
    def op_step(self, meta: Meta, keyword: str, action_name: str, *rest) -> OPStep:
        inputs: list[tuple[str, str]] = []
        outputs: list[tuple[str, str]] = []
        list_args = [r for r in rest if isinstance(r, list)]
        if len(list_args) == 2:
            inputs, outputs = list_args
        elif len(list_args) == 1:
            idx_first = next(i for i, r in enumerate(rest) if isinstance(r, list))
            if idx_first == 0:
                inputs = list_args[0]
            else:
                outputs = list_args[0]
        line, col = _pos(meta)
        return OPStep(
            keyword=keyword,  # type: ignore[arg-type]
            action_name=action_name,
            inputs=inputs,
            outputs=outputs,
            line=line,
            column=col,
        )
```

**`op_section`:**

```python
    @v_args(meta=True, inline=True)
    def op_section(self, meta: Meta, *steps: OPStep) -> OperationalPrinciple:
        line, col = _pos(meta)
        return OperationalPrinciple(steps=list(steps), line=line, column=col)
```

**`concept_def`** — the tricky one. It collects positioned subnodes from `*rest` and has to propagate its own meta onto the top-level `ConceptAST`:

```python
    @v_args(meta=True, inline=True)
    def concept_def(self, meta: Meta, name: str, *rest) -> ConceptAST:
        params: list[str] = []
        purpose: str = ""
        state: list[StateDecl] = []
        actions: list[Action] = []
        op_principle = OperationalPrinciple(steps=[])
        for item in rest:
            if isinstance(item, OperationalPrinciple):
                op_principle = item
            elif isinstance(item, list) and item:
                head = item[0]
                if isinstance(head, str):
                    params = item
                elif isinstance(head, StateDecl):
                    state = item
                elif isinstance(head, Action):
                    actions = item
            elif isinstance(item, str):
                purpose = item
        line, col = _pos(meta)
        return ConceptAST(
            name=name,
            params=params,
            purpose=purpose,
            state=state,
            actions=actions,
            operational_principle=op_principle,
            source="",
            line=line,
            column=col,
        )
```

**`actions_section` must also stamp line/column on the `Action` groups.** The grammar wraps multiple cases under a single `Action` per name, so the natural position for each `Action` is its first case's line. Update `actions_section` in place (no `@v_args(meta=True)` needed; it reads the positions from the cases it received):

```python
    def actions_section(self, *cases: tuple[str, ActionCase]) -> list[Action]:
        grouped: dict[str, list[ActionCase]] = {}
        order: list[str] = []
        first_pos: dict[str, tuple[int | None, int | None]] = {}
        for name, case in cases:
            if name not in grouped:
                grouped[name] = []
                order.append(name)
                first_pos[name] = (case.line, case.column)
            grouped[name].append(case)
        return [
            Action(
                name=n,
                cases=grouped[n],
                line=first_pos[n][0],
                column=first_pos[n][1],
            )
            for n in order
        ]
```

- [ ] **Step 5.4: Run the new position tests**

Run: `uv run pytest tests/test_parse.py::TestConceptTransformerPositions -v`
Expected: 7 passed.

If a specific line is off by one (Lark counts tokens, not keywords), open the grammar and check which rule starts the node in question. Adjust the **expected** line in the test to match reality — these integers are pinned to the grammar's structure, not to an arbitrary counting convention.

- [ ] **Step 5.5: Run the full parse test suite**

Run: `uv run pytest tests/test_parse.py -v`
Expected: every existing parse test still passes. Round-trip tests in `test_ast.py` still pass (defaults are `None`, new fields just round-trip as integers when the parser set them).

- [ ] **Step 5.6: Commit**

```bash
git add src/concept_lang/transformers/concept_transformer.py tests/test_parse.py
git commit -m "feat(parse): thread source positions through concept transformer"
```

---

## Task 6: Thread positions through `SyncTransformer`

Same treatment for the sync transformer. The positioned nodes are `ActionPattern`, `StateQuery`, `BindClause`, `WhereClause`, `SyncAST`.

**Files:**
- Modify: `src/concept_lang/transformers/sync_transformer.py`
- Modify: `tests/test_parse.py`

- [ ] **Step 6.1: Write the failing integration test**

Append to `tests/test_parse.py`:

```python
class TestSyncTransformerPositions:
    _SRC = (
        "sync LogInc\n"                                      # line 1
        "\n"                                                  # line 2
        "  when\n"                                            # line 3
        "    Counter/inc: [ n: ?n ] => [ total: ?t ]\n"      # line 4
        "  where\n"                                           # line 5
        "    bind ( ?n + 1 as ?m )\n"                         # line 6
        "    Log: { ?log event: ?e }\n"                       # line 7
        "  then\n"                                            # line 8
        "    Log/append: [ event: ?m ]\n"                     # line 9
    )

    def _parse(self):
        return parse_sync_source(self._SRC)

    def test_sync_ast_line_is_1(self):
        sync = self._parse()
        assert sync.line == 1

    def test_when_action_pattern_line_is_4(self):
        sync = self._parse()
        assert sync.when[0].line == 4

    def test_where_bind_line_is_6(self):
        sync = self._parse()
        assert sync.where is not None
        assert sync.where.binds[0].line == 6

    def test_where_state_query_line_is_7(self):
        sync = self._parse()
        assert sync.where is not None
        assert sync.where.queries[0].line == 7

    def test_where_clause_line_is_5(self):
        sync = self._parse()
        assert sync.where is not None
        assert sync.where.line == 5

    def test_then_action_pattern_line_is_9(self):
        sync = self._parse()
        assert sync.then[0].line == 9
```

- [ ] **Step 6.2: Run the test — will fail**

Run: `uv run pytest tests/test_parse.py::TestSyncTransformerPositions -v`
Expected: every assertion fails.

- [ ] **Step 6.3: Thread meta through the sync transformer**

Edit `src/concept_lang/transformers/sync_transformer.py`. Add the same `_pos` helper at module scope (a copy is fine — it's three lines — or move it to a shared module if preferred):

```python
from lark.tree import Meta


def _pos(meta: Meta) -> tuple[int | None, int | None]:
    """Extract (line, column) from a Lark Meta, tolerating empty metas."""
    if meta is None or meta.empty:
        return (None, None)
    return (meta.line, meta.column)
```

Override these methods with `@v_args(meta=True, inline=True)`:

**`action_pattern`:**

```python
    @v_args(meta=True, inline=True)
    def action_pattern(
        self,
        meta: Meta,
        concept: str,
        action: str,
        input_pattern: list[PatternField],
        output_pattern: list[PatternField] | None = None,
    ) -> ActionPattern:
        line, col = _pos(meta)
        return ActionPattern(
            concept=concept,
            action=action,
            input_pattern=input_pattern,
            output_pattern=output_pattern if output_pattern is not None else [],
            line=line,
            column=col,
        )
```

**`state_query`:**

```python
    @v_args(meta=True, inline=True)
    def state_query(
        self, meta: Meta, concept: str, triples: list[Triple]
    ) -> StateQuery:
        line, col = _pos(meta)
        return StateQuery(
            concept=concept, triples=triples, is_optional=False,
            line=line, column=col,
        )
```

**`optional_query`:**

```python
    @v_args(meta=True, inline=True)
    def optional_query(
        self, meta: Meta, concept: str, triples: list[Triple]
    ) -> StateQuery:
        line, col = _pos(meta)
        return StateQuery(
            concept=concept, triples=triples, is_optional=True,
            line=line, column=col,
        )
```

**`bind_clause`:**

```python
    @v_args(meta=True, inline=True)
    def bind_clause(
        self, meta: Meta, expression: str, variable: str
    ) -> BindClause:
        line, col = _pos(meta)
        return BindClause(
            expression=expression.strip(),
            variable=variable,
            line=line,
            column=col,
        )
```

**`where_clause`:**

```python
    @v_args(meta=True, inline=True)
    def where_clause(self, meta: Meta, *items) -> WhereClause:
        queries: list[StateQuery] = []
        binds: list[BindClause] = []
        for item in items:
            if isinstance(item, StateQuery):
                queries.append(item)
            elif isinstance(item, BindClause):
                binds.append(item)
        line, col = _pos(meta)
        return WhereClause(
            queries=queries, binds=binds, line=line, column=col,
        )
```

**`sync_def`:**

```python
    @v_args(meta=True, inline=True)
    def sync_def(self, meta: Meta, name: str, *rest) -> SyncAST:
        when: list[ActionPattern] = []
        then: list[ActionPattern] = []
        where: WhereClause | None = None
        if len(rest) == 2:
            when, then = rest
        elif len(rest) == 3:
            when, where, then = rest
        line, col = _pos(meta)
        return SyncAST(
            name=name,
            when=when,
            where=where,
            then=then,
            source="",
            line=line,
            column=col,
        )
```

Leave `when_clause`, `then_clause`, `triple`, `pattern_field`, `pattern_list`, `pattern_value`, leaf tokens, and `start` untouched.

- [ ] **Step 6.4: Run the new position tests**

Run: `uv run pytest tests/test_parse.py::TestSyncTransformerPositions -v`
Expected: 6 passed.

Again, if a specific line is off by one, adjust the expected line number in the test to match the grammar's reality.

- [ ] **Step 6.5: Run the full parse test suite**

Run: `uv run pytest tests/test_parse.py -v`
Expected: every parse test passes, including the pre-existing positive-fixture sweep from P1.

- [ ] **Step 6.6: Commit**

```bash
git add src/concept_lang/transformers/sync_transformer.py tests/test_parse.py
git commit -m "feat(parse): thread source positions through sync transformer"
```

---

## Task 7: Update concept validator rules to thread node positions

Now that the AST carries positions, every concept rule stops writing `line=None` and starts pulling from the node it's flagging. The message strings do **not** change — only `line=`/`column=` arguments do. This keeps the existing negative-fixture sweep happy (the sweep matches on `code`/`severity`; message text is not tested).

**Scope per rule:**

- **C1** — flag at the position of the offending `StateDecl`.
- **C2** — flag at the position of the offending `EffectClause`.
- **C3** — flag at the position of the offending `OPStep`.
- **C4** — already uses a real line (computed from `match.start()` on the raw source); leave it alone.
- **C5** — concept has an empty purpose. Flag at the position of the `ConceptAST` node itself.
- **C6** — concept has no actions. Flag at the `ConceptAST` position.
- **C7** — flag at the position of the offending `Action` (its first case, set by `actions_section` in Task 5).
- **C9** — concept has no operational-principle steps. Flag at the `ConceptAST` position (the `OperationalPrinciple` node's own line may be `None` when the section is entirely absent — use the concept's position as a stable fallback).

**Files:**
- Modify: `src/concept_lang/validate/concept_rules.py`
- Modify: `tests/test_validate.py`

- [ ] **Step 7.1: Write the failing tests**

Append to `tests/test_validate.py`:

```python
class TestConceptRulesCarryPositions:
    """
    After P3, every concept rule that fires on a positioned AST node must
    emit a diagnostic whose `line` matches the node's source line.
    """

    def test_c1_reports_state_decl_line(self):
        src = (
            "concept Basket\n"
            "\n"
            "  purpose\n"
            "    hold items\n"
            "\n"
            "  state\n"
            "    owner: User\n"          # line 7 — offending
            "\n"
            "  actions\n"
            "    add [ item: string ] => [ basket: Basket ]\n"
            "\n"
            "  operational principle\n"
            "    after add [ item: \"a\" ] => [ basket: b ]\n"
        )
        ast = parse_concept_source(src)
        diags = rule_c1_state_independence(ast)
        assert len(diags) == 1
        assert diags[0].line == 7

    def test_c2_reports_effect_clause_line(self):
        src = (
            "concept Counter\n"
            "\n"
            "  purpose\n"
            "    count things\n"
            "\n"
            "  state\n"
            "    total: int\n"
            "\n"
            "  actions\n"
            "    inc [ n: int ] => [ total: int ]\n"
            "      increment\n"
            "      effects:\n"
            "        missing_field := n\n"   # line 13 — offending
            "\n"
            "  operational principle\n"
            "    after inc [ n: 1 ] => [ total: 1 ]\n"
        )
        ast = parse_concept_source(src)
        diags = rule_c2_effects_independence(ast)
        assert len(diags) == 1
        assert diags[0].line == 13

    def test_c3_reports_op_step_line(self):
        src = (
            "concept Counter\n"
            "\n"
            "  purpose\n"
            "    count things\n"
            "\n"
            "  state\n"
            "    total: int\n"
            "\n"
            "  actions\n"
            "    inc [ ] => [ total: int ]\n"
            "\n"
            "  operational principle\n"
            "    after teleport [ ] => [ total: 1 ]\n"   # line 13 — offending
        )
        ast = parse_concept_source(src)
        diags = rule_c3_op_principle_independence(ast)
        assert len(diags) == 1
        assert diags[0].line == 13

    def test_c7_reports_action_line(self):
        # Action has only error cases — flagged at the action's first case line.
        src = (
            "concept Counter\n"
            "\n"
            "  purpose\n"
            "    count things\n"
            "\n"
            "  state\n"
            "    total: int\n"
            "\n"
            "  actions\n"
            "    inc [ n: int ] => [ error: string ]\n"  # line 10
            "      always fails\n"
            "\n"
            "  operational principle\n"
            "    after inc [ n: 1 ] => [ error: \"x\" ]\n"
        )
        ast = parse_concept_source(src)
        diags = rule_c7_action_has_success_case(ast)
        assert len(diags) == 1
        assert diags[0].line == 10

    def test_c5_reports_concept_line(self):
        # Hand-built because the grammar requires a non-empty purpose body.
        from concept_lang.ast import (
            Action, ActionCase, ConceptAST, OperationalPrinciple,
            OPStep, TypedName,
        )
        ast = ConceptAST(
            name="Empty",
            params=[],
            purpose="",   # empty
            state=[],
            actions=[
                Action(
                    name="noop",
                    cases=[ActionCase(inputs=[], outputs=[TypedName(name="ok", type_expr="boolean")])],
                    line=5,
                )
            ],
            operational_principle=OperationalPrinciple(
                steps=[OPStep(keyword="after", action_name="noop", inputs=[], outputs=[])],
            ),
            source="",
            line=1,
            column=1,
        )
        diags = rule_c5_has_purpose(ast)
        assert len(diags) == 1
        assert diags[0].line == 1
```

These tests import `rule_c5_has_purpose` and `rule_c7_action_has_success_case` — ensure the imports at the top of `test_validate.py` already include them (the P2 plan's earlier tasks did add them; no change needed here). If an `ImportError` fires, add the missing names to the existing `from concept_lang.validate import ...` line.

- [ ] **Step 7.2: Run the tests — should fail**

Run: `uv run pytest tests/test_validate.py::TestConceptRulesCarryPositions -v`
Expected: 5 failures — every assertion currently sees `line=None`.

- [ ] **Step 7.3: Update every rule in `concept_rules.py`**

Edit `src/concept_lang/validate/concept_rules.py`. For every rule, replace the hard-coded `line=None`/`column=None` with values pulled from the AST node. No other logic changes.

**`rule_c1_state_independence`:**

```python
def rule_c1_state_independence(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C1: State declarations may only reference own type params + primitives.
    ...
    """
    diagnostics: list[Diagnostic] = []
    allowed: set[str] = set(concept.params) | _PRIMITIVE_TYPES | _TYPE_EXPR_RESERVED
    for decl in concept.state:
        for tok in _tokens_in(decl.type_expr):
            if tok in allowed:
                continue
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    file=file,
                    line=decl.line,
                    column=decl.column,
                    code="C1",
                    message=(
                        f"state field '{decl.name}' references unknown type "
                        f"'{tok}' (a concept may only reference its own type "
                        f"parameters {sorted(concept.params)!r} and primitive "
                        f"types)"
                    ),
                )
            )
    return diagnostics
```

**`rule_c2_effects_independence`:**

```python
def rule_c2_effects_independence(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    own_fields: set[str] = {decl.name for decl in concept.state}
    for action in concept.actions:
        for case in action.cases:
            for effect in case.effects:
                if effect.field in own_fields:
                    continue
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        file=file,
                        line=effect.line,
                        column=effect.column,
                        code="C2",
                        message=(
                            f"action '{action.name}' has an effect on field "
                            f"'{effect.field}', which is not declared in "
                            f"concept '{concept.name}' (declared fields: "
                            f"{sorted(own_fields)!r})"
                        ),
                    )
                )
    return diagnostics
```

**`rule_c3_op_principle_independence`:**

```python
def rule_c3_op_principle_independence(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    own_actions: set[str] = {a.name for a in concept.actions}
    for step in concept.operational_principle.steps:
        if step.action_name in own_actions:
            continue
        diagnostics.append(
            Diagnostic(
                severity="error",
                file=file,
                line=step.line,
                column=step.column,
                code="C3",
                message=(
                    f"operational principle step '{step.keyword} "
                    f"{step.action_name}' references action '{step.action_name}' "
                    f"which is not declared in concept '{concept.name}' "
                    f"(declared actions: {sorted(own_actions)!r})"
                ),
            )
        )
    return diagnostics
```

**`rule_c4_no_inline_sync`:** leave unchanged. It computes `line_no` from `source.count("\n", 0, match.start()) + 1` and already carries a real line number.

**`rule_c5_has_purpose`:**

```python
def rule_c5_has_purpose(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    if concept.purpose and concept.purpose.strip():
        return []
    return [
        Diagnostic(
            severity="error",
            file=file,
            line=concept.line,
            column=concept.column,
            code="C5",
            message=f"concept '{concept.name}' has an empty purpose",
        )
    ]
```

**`rule_c6_has_actions`:**

```python
def rule_c6_has_actions(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    if concept.actions:
        return []
    return [
        Diagnostic(
            severity="error",
            file=file,
            line=concept.line,
            column=concept.column,
            code="C6",
            message=f"concept '{concept.name}' has no actions",
        )
    ]
```

**`rule_c7_action_has_success_case`:**

```python
def rule_c7_action_has_success_case(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for action in concept.actions:
        if any(not _is_error_case(case) for case in action.cases):
            continue
        diagnostics.append(
            Diagnostic(
                severity="error",
                file=file,
                line=action.line,
                column=action.column,
                code="C7",
                message=(
                    f"action '{action.name}' on concept '{concept.name}' has "
                    f"only error cases (every case's outputs include "
                    f"'error') - add a non-error success case"
                ),
            )
        )
    return diagnostics
```

**`rule_c9_has_op_principle`:**

```python
def rule_c9_has_op_principle(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    if concept.operational_principle.steps:
        return []
    return [
        Diagnostic(
            severity="error",
            file=file,
            line=concept.line,
            column=concept.column,
            code="C9",
            message=(
                f"concept '{concept.name}' has no operational principle steps "
                f"- describe the archetypal scenario using the concept's own "
                f"actions"
            ),
        )
    ]
```

- [ ] **Step 7.4: Run the position tests**

Run: `uv run pytest tests/test_validate.py::TestConceptRulesCarryPositions -v`
Expected: 5 passed.

- [ ] **Step 7.5: Full validator sanity check**

Run: `uv run pytest tests/test_validate.py -v`
Expected: every existing validator test still passes. If any P2 test asserts `line is None` on a diagnostic, retire that assertion now — grep to find them:

```bash
grep -n "line is None" tests/test_validate.py
```

For each match, either replace with `line is not None` (the right assertion after P3) or drop the line-level assertion entirely from that test.

- [ ] **Step 7.6: Commit**

```bash
git add src/concept_lang/validate/concept_rules.py tests/test_validate.py
git commit -m "feat(validate): thread AST positions into concept rule diagnostics"
```

---

## Task 8: Update sync validator rules to thread node positions

**Scope per rule:**

- **S1** — flag at the position of the offending `ActionPattern`.
- **S2** — flag at the position of the offending `ActionPattern` (field-level positions are not in the AST; the pattern-level position is the right granularity for P3).
- **S3** — flag at the position of the offending `then` `ActionPattern`.
- **S4** — flag at the position of the offending `StateQuery` (the query that contains the unbound subject).
- **S5** — sync-scoped warning. Flag at the `SyncAST` position.

**Files:**
- Modify: `src/concept_lang/validate/sync_rules.py`
- Modify: `tests/test_validate.py`

- [ ] **Step 8.1: Write the failing tests**

Append to `tests/test_validate.py`:

```python
class TestSyncRulesCarryPositions:
    def _ws(self):
        return _workspace_with_counter_and_log()  # reused from P2 Task 11

    def test_s1_reports_pattern_line(self):
        src = (
            "sync BadWhen\n"                              # line 1
            "\n"                                           # line 2
            "  when\n"                                     # line 3
            "    Nope/do: [ ] => [ ]\n"                   # line 4 — offending
            "  then\n"                                     # line 5
            "    Log/append: [ event: \"e\" ]\n"          # line 6
        )
        sync = parse_sync_source(src)
        index = WorkspaceIndex.build(self._ws())
        diags = rule_s1_references_resolve(sync, index)
        assert len(diags) == 1
        assert diags[0].line == 4

    def test_s2_reports_pattern_line(self):
        src = (
            "sync BadField\n"                              # line 1
            "\n"                                           # line 2
            "  when\n"                                     # line 3
            "    Counter/inc: [ n: ?n ] => [ total: ?t ]\n"  # line 4
            "  then\n"                                     # line 5
            "    Log/append: [ bogus: ?t ]\n"              # line 6 — offending
        )
        sync = parse_sync_source(src)
        index = WorkspaceIndex.build(self._ws())
        diags = rule_s2_pattern_fields_exist(sync, index)
        assert len(diags) == 1
        assert diags[0].line == 6

    def test_s3_reports_then_pattern_line(self):
        src = (
            "sync Unbound\n"                               # line 1
            "\n"                                           # line 2
            "  when\n"                                     # line 3
            "    Counter/inc: [ ] => [ ]\n"                # line 4
            "  then\n"                                     # line 5
            "    Log/append: [ event: ?ghost ]\n"          # line 6 — offending
        )
        sync = parse_sync_source(src)
        index = WorkspaceIndex.build(self._ws())
        diags = rule_s3_then_vars_bound(sync, index)
        assert len(diags) == 1
        assert diags[0].line == 6

    def test_s4_reports_state_query_line(self):
        src = (
            "sync BadWhere\n"                              # line 1
            "\n"                                           # line 2
            "  when\n"                                     # line 3
            "    Counter/inc: [ ] => [ ]\n"                # line 4
            "  where\n"                                    # line 5
            "    Log: { ?ghost event: ?e }\n"             # line 6 — offending
            "  then\n"                                     # line 7
            "    Log/append: [ event: ?e ]\n"              # line 8
        )
        sync = parse_sync_source(src)
        index = WorkspaceIndex.build(self._ws())
        diags = rule_s4_where_vars_bound(sync, index)
        assert len(diags) == 1
        assert diags[0].line == 6

    def test_s5_reports_sync_line(self):
        src = (
            "sync OneConcept\n"                            # line 1
            "\n"                                           # line 2
            "  when\n"                                     # line 3
            "    Counter/inc: [ ] => [ ]\n"                # line 4
            "  then\n"                                     # line 5
            "    Counter/read: [ ] => [ total: ?t ]\n"    # line 6
        )
        sync = parse_sync_source(src)
        index = WorkspaceIndex.build(self._ws())
        diags = rule_s5_multiple_concepts(sync, index)
        assert len(diags) == 1
        assert diags[0].line == 1
```

These tests import `WorkspaceIndex`, `_workspace_with_counter_and_log`, `rule_s1_references_resolve`, etc. They're all already imported at the top of `test_validate.py` from the P2 tasks — no new imports needed.

- [ ] **Step 8.2: Run the tests — should fail**

Run: `uv run pytest tests/test_validate.py::TestSyncRulesCarryPositions -v`
Expected: 5 failures.

- [ ] **Step 8.3: Update every rule in `sync_rules.py`**

Edit `src/concept_lang/validate/sync_rules.py`.

**`rule_s1_references_resolve`:**

```python
def rule_s1_references_resolve(
    sync: SyncAST,
    index: WorkspaceIndex,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for section, pattern in _iter_patterns(sync):
        if pattern.concept not in index.concept_names:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    file=file,
                    line=pattern.line,
                    column=pattern.column,
                    code="S1",
                    message=(
                        f"sync '{sync.name}' {section} references unknown "
                        f"concept '{pattern.concept}' "
                        f"(in '{pattern.concept}/{pattern.action}')"
                    ),
                )
            )
            continue
        if index.action_cases(pattern.concept, pattern.action) is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    file=file,
                    line=pattern.line,
                    column=pattern.column,
                    code="S1",
                    message=(
                        f"sync '{sync.name}' {section} references action "
                        f"'{pattern.concept}/{pattern.action}' which is not "
                        f"declared on concept '{pattern.concept}'"
                    ),
                )
            )
    return diagnostics
```

**`rule_s2_pattern_fields_exist`:**

```python
def rule_s2_pattern_fields_exist(
    sync: SyncAST,
    index: WorkspaceIndex,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for pattern in sync.then:
        cases = index.action_cases(pattern.concept, pattern.action)
        if cases is None:
            continue  # handled by S1
        allowed = index.action_field_names(pattern.concept, pattern.action)
        for pf in list(pattern.input_pattern) + list(pattern.output_pattern):
            if pf.name in allowed:
                continue
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    file=file,
                    line=pattern.line,
                    column=pattern.column,
                    code="S2",
                    message=(
                        f"sync '{sync.name}' then pattern "
                        f"'{pattern.concept}/{pattern.action}' references "
                        f"unknown field '{pf.name}' (declared fields: "
                        f"{sorted(allowed)!r})"
                    ),
                )
            )
    return diagnostics
```

**`rule_s3_then_vars_bound`:**

```python
def rule_s3_then_vars_bound(
    sync: SyncAST,
    index: WorkspaceIndex,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    _ = index
    bound: set[str] = _bindings_from_when(sync) | _bindings_from_where(sync)
    diagnostics: list[Diagnostic] = []
    for pattern in sync.then:
        for var in _vars_in_pattern(pattern):
            if var in bound:
                continue
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    file=file,
                    line=pattern.line,
                    column=pattern.column,
                    code="S3",
                    message=(
                        f"sync '{sync.name}' then clause references "
                        f"unbound variable '{var}' (bind it in `when` or "
                        f"in a `where` bind/state query)"
                    ),
                )
            )
    return diagnostics
```

**`rule_s4_where_vars_bound`:**

```python
def rule_s4_where_vars_bound(
    sync: SyncAST,
    index: WorkspaceIndex,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    _ = index
    if sync.where is None:
        return []
    diagnostics: list[Diagnostic] = []
    bound: set[str] = _bindings_from_when(sync)
    for bind in sync.where.binds:
        bound.add(bind.variable)
    for query in sync.where.queries:
        for triple in query.triples:
            if triple.subject.startswith("?") and triple.subject not in bound:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        file=file,
                        line=query.line,
                        column=query.column,
                        code="S4",
                        message=(
                            f"sync '{sync.name}' where clause state query on "
                            f"concept '{query.concept}' uses unbound subject "
                            f"'{triple.subject}' (bind it in `when` or in an "
                            f"earlier `where` item)"
                        ),
                    )
                )
            if triple.subject.startswith("?"):
                bound.add(triple.subject)
            if triple.object.startswith("?"):
                bound.add(triple.object)
    return diagnostics
```

**`rule_s5_multiple_concepts`:**

```python
def rule_s5_multiple_concepts(
    sync: SyncAST,
    index: WorkspaceIndex,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    _ = index
    concepts: set[str] = set()
    for pattern in list(sync.when) + list(sync.then):
        concepts.add(pattern.concept)
    if len(concepts) >= 2:
        return []
    return [
        Diagnostic(
            severity="warning",
            file=file,
            line=sync.line,
            column=sync.column,
            code="S5",
            message=(
                f"sync '{sync.name}' references only {len(concepts)} "
                f"concept(s) ({sorted(concepts)!r}) - single-concept syncs "
                f"are usually better expressed inside the concept itself"
            ),
        )
    ]
```

- [ ] **Step 8.4: Run the position tests**

Run: `uv run pytest tests/test_validate.py::TestSyncRulesCarryPositions -v`
Expected: 5 passed.

- [ ] **Step 8.5: Full validator sanity check**

Run: `uv run pytest tests/test_validate.py -v`
Expected: every pre-existing validator test still passes.

- [ ] **Step 8.6: Commit**

```bash
git add src/concept_lang/validate/sync_rules.py tests/test_validate.py
git commit -m "feat(validate): thread AST positions into sync rule diagnostics"
```

---

## Task 9: Tighten a representative subset of negative fixture expected lines

Per decision (E), we update **four** `*.expected.json` files to assert exact line numbers: C1, C2, C3, S1. The remaining nine stay with `"line": null`. The negative-fixture sweep learns to treat `null` as "match anything" and an integer as "exact match".

**Files:**
- Modify: `tests/fixtures/negative/C1_state_references_other_concept.expected.json`
- Modify: `tests/fixtures/negative/C2_effects_references_foreign_state.expected.json`
- Modify: `tests/fixtures/negative/C3_op_principle_uses_foreign_action.expected.json`
- Modify: `tests/fixtures/negative/S1_sync_references_unknown_concept.expected.json`
- Modify: `tests/test_validate.py`

- [ ] **Step 9.1: Read the existing fixtures to know what line to assert**

Run:

```bash
cat tests/fixtures/negative/C1_state_references_other_concept.concept
cat tests/fixtures/negative/C2_effects_references_foreign_state.concept
cat tests/fixtures/negative/C3_op_principle_uses_foreign_action.concept
cat tests/fixtures/negative/S1_sync_references_unknown_concept.sync
```

Note the 1-indexed line number of:

- **C1**: the offending `state` declaration line (the line containing the foreign type reference — for the existing fixture, this is the `owner: User` line).
- **C2**: the offending `effects:` clause line (the effect line that references a foreign state field).
- **C3**: the offending `operational principle` step line.
- **S1**: the offending `when` or `then` action-pattern line.

- [ ] **Step 9.2: Update `C1_state_references_other_concept.expected.json`**

Replace the file contents with (substituting `<LINE>` with the value found in Step 9.1):

```json
{
  "diagnostics": [
    {
      "code": "C1",
      "severity": "error",
      "line": <LINE>
    }
  ]
}
```

- [ ] **Step 9.3: Update `C2_effects_references_foreign_state.expected.json`** the same way, using the C2 line number from Step 9.1.

- [ ] **Step 9.4: Update `C3_op_principle_uses_foreign_action.expected.json`** the same way, using the C3 line number from Step 9.1.

- [ ] **Step 9.5: Update `S1_sync_references_unknown_concept.expected.json`** the same way, using the S1 line number from Step 9.1.

- [ ] **Step 9.6: Update the negative-fixture sweep to honor integer line matchers**

Edit `tests/test_validate.py`. Locate the `TestNegativeFixturesFireExpectedCodes` class (from P2 Task 19). Update `test_concept_negative_fixtures_fire_expected_codes` and `test_sync_negative_fixtures_fire_expected_codes` so the match key includes an optional line number. Replace the method bodies with:

```python
    def test_concept_negative_fixtures_fire_expected_codes(self):
        for fixture in sorted(NEGATIVE_ROOT.glob("*.concept")):
            expected = _expected_for(fixture)
            diags = self._fire_concept_fixture(fixture)
            self._assert_expected_in_diagnostics(fixture, expected, diags)

    def test_sync_negative_fixtures_fire_expected_codes(self):
        for fixture in sorted(NEGATIVE_ROOT.glob("*.sync")):
            expected = _expected_for(fixture)
            diags = self._fire_sync_fixture(fixture)
            self._assert_expected_in_diagnostics(fixture, expected, diags)

    def _assert_expected_in_diagnostics(
        self,
        fixture: Path,
        expected: dict,
        diags: list[Diagnostic],
    ) -> None:
        """
        For each entry in `expected['diagnostics']`, assert that at least
        one emitted diagnostic matches its `code` + `severity`, and — if
        `line` is an integer — also matches that exact line. A `line: null`
        entry accepts any emitted line.
        """
        for want in expected["diagnostics"]:
            code = want["code"]
            severity = want["severity"]
            want_line = want.get("line")
            candidates = [
                d for d in diags
                if d.code == code and d.severity == severity
            ]
            assert candidates, (
                f"{fixture.name}: expected ({code}, {severity}) "
                f"in {[(d.code, d.severity) for d in diags]}"
            )
            if want_line is not None:
                line_matched = [d for d in candidates if d.line == want_line]
                assert line_matched, (
                    f"{fixture.name}: expected ({code}, {severity}) "
                    f"at line {want_line}, got lines "
                    f"{sorted(d.line for d in candidates if d.line is not None)}"
                )
```

- [ ] **Step 9.7: Run the negative-fixture sweep**

Run: `uv run pytest tests/test_validate.py::TestNegativeFixturesFireExpectedCodes -v`
Expected: all tests pass. The four tightened fixtures now require their exact line; the other nine still fire by code only.

If a tightened fixture fails with "expected line X, got line Y", re-read the fixture file and update the `<LINE>` value to reflect reality — P3's job is to make diagnostics carry real positions, not to invent line numbers the parser doesn't produce.

- [ ] **Step 9.8: Commit**

```bash
git add \
  tests/fixtures/negative/C1_state_references_other_concept.expected.json \
  tests/fixtures/negative/C2_effects_references_foreign_state.expected.json \
  tests/fixtures/negative/C3_op_principle_uses_foreign_action.expected.json \
  tests/fixtures/negative/S1_sync_references_unknown_concept.expected.json \
  tests/test_validate.py
git commit -m "test(validate): tighten C1/C2/C3/S1 expected lines to real values"
```

---

## Task 10: Create the `concept_lang.loader` module with `load_workspace` (happy path)

Per decision (D), `load_workspace(root: Path) -> tuple[Workspace, list[Diagnostic]]`. This task covers the happy path: clean trees with well-formed concepts and syncs. Task 11 covers error handling.

**Files:**
- Create: `src/concept_lang/loader.py`
- Create: `tests/test_loader.py`
- Create: `tests/fixtures/loader/clean/concepts/Counter.concept`
- Create: `tests/fixtures/loader/clean/syncs/log.sync`
- Create: `tests/fixtures/loader/concepts_only/concepts/Counter.concept`
- Create: `tests/fixtures/loader/syncs_only/syncs/standalone.sync`

- [ ] **Step 10.1: Create the loader fixture files**

Create `tests/fixtures/loader/clean/concepts/Counter.concept`:

```
concept Counter

  purpose
    count things

  state
    total: int

  actions
    inc [ n: int ] => [ total: int ]
      add n to total

  operational principle
    after inc [ n: 1 ] => [ total: 1 ]
```

Create `tests/fixtures/loader/clean/syncs/log.sync`:

```
sync LogInc

  when
    Counter/inc: [ n: ?n ] => [ total: ?t ]
  then
    Log/append: [ event: ?n ]
```

Create `tests/fixtures/loader/concepts_only/concepts/Counter.concept` (same content as the clean Counter above).

Create `tests/fixtures/loader/syncs_only/syncs/standalone.sync`:

```
sync StandaloneSync

  when
    A/do: [ ] => [ ]
  then
    B/do: [ ] => [ ]
```

Note: `standalone.sync` deliberately references concepts that do not exist in the loader fixture tree. The loader tests assert **loader** behavior only — whether the sync parses and gets stored in the Workspace — not validator behavior. A later test in Task 12 exercises load+validate on the real positive fixtures.

- [ ] **Step 10.2: Write the failing happy-path tests**

Create `tests/test_loader.py`:

```python
"""Tests for concept_lang.loader (P3 workspace loader)."""

from pathlib import Path

import pytest

from concept_lang.ast import Workspace
from concept_lang.loader import load_workspace
from concept_lang.validate.diagnostic import Diagnostic


FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "loader"


class TestLoadWorkspaceHappyPath:
    def test_clean_workspace_loads_all_files(self):
        ws, diags = load_workspace(FIXTURES_ROOT / "clean")
        assert isinstance(ws, Workspace)
        assert diags == []
        assert set(ws.concepts.keys()) == {"Counter"}
        assert set(ws.syncs.keys()) == {"LogInc"}

    def test_clean_workspace_concept_has_positions(self):
        ws, _ = load_workspace(FIXTURES_ROOT / "clean")
        counter = ws.concepts["Counter"]
        # Positions threaded via Task 5 must survive the loader path.
        assert counter.line == 1
        assert counter.state[0].line == 7

    def test_clean_workspace_sync_has_positions(self):
        ws, _ = load_workspace(FIXTURES_ROOT / "clean")
        log = ws.syncs["LogInc"]
        assert log.line == 1
        assert log.when[0].line == 4

    def test_concepts_only_workspace(self):
        ws, diags = load_workspace(FIXTURES_ROOT / "concepts_only")
        assert diags == []
        assert set(ws.concepts.keys()) == {"Counter"}
        assert ws.syncs == {}

    def test_syncs_only_workspace(self):
        ws, diags = load_workspace(FIXTURES_ROOT / "syncs_only")
        assert diags == []
        assert ws.concepts == {}
        assert set(ws.syncs.keys()) == {"StandaloneSync"}
```

- [ ] **Step 10.3: Run the tests — fail with ModuleNotFoundError**

Run: `uv run pytest tests/test_loader.py -v`
Expected: `ModuleNotFoundError: No module named 'concept_lang.loader'`.

- [ ] **Step 10.4: Create `concept_lang/loader.py`**

Create `src/concept_lang/loader.py`:

```python
"""
Directory-walking workspace loader for concept-lang 0.2.0.

`load_workspace(root)` reads every `.concept` file under `root/concepts/`
and every `.sync` file under `root/syncs/`, parses each into an AST,
and returns a populated `Workspace` plus a list of parse-error
`Diagnostic` records for any file that failed to parse. This is the
single entry point the MCP tool layer (P4) will use to read a workspace
from disk.

Partial loads are the happy path: a broken `Web.concept` produces a P0
diagnostic and is skipped, while the other concepts and every sync still
load normally. This mirrors the paper's "best effort, show everything"
philosophy — diagnostics are additive, never gating.

Note: `.app` files are *not* loaded. The app-spec parser lives in the
untouched v1 module `concept_lang.app_parser` and will be migrated in
P4. Including it here would couple P3 to the v1 data model.
"""

from pathlib import Path

from concept_lang.ast import Workspace
from concept_lang.parse import parse_concept_file, parse_sync_file
from concept_lang.validate.diagnostic import Diagnostic


def load_workspace(root: Path) -> tuple[Workspace, list[Diagnostic]]:
    """
    Walk a workspace directory and parse every concept and sync file.

    Directory convention (enforced by the paper-alignment spec but
    discovered here by simple glob):

        <root>/concepts/*.concept
        <root>/syncs/*.sync

    Files under other subdirectories are ignored. Subdirectories below
    `concepts/` and `syncs/` are searched recursively so nested
    organisations (e.g. `concepts/auth/Password.concept`) are supported.

    Returns a `(Workspace, diagnostics)` tuple. `Workspace` contains every
    file that parsed successfully, keyed by the concept's / sync's own
    name (not the file name). `diagnostics` contains one `P0` error
    per file that failed to parse, plus one `L0` error if `root` does
    not exist.
    """
    diagnostics: list[Diagnostic] = []
    concepts: dict = {}
    syncs: dict = {}

    if not root.exists():
        diagnostics.append(
            Diagnostic(
                severity="error",
                file=root,
                line=None,
                column=None,
                code="L0",
                message=f"workspace root does not exist: {root}",
            )
        )
        return Workspace(concepts=concepts, syncs=syncs), diagnostics

    concepts_dir = root / "concepts"
    syncs_dir = root / "syncs"

    if concepts_dir.is_dir():
        for path in sorted(concepts_dir.rglob("*.concept")):
            try:
                concept = parse_concept_file(path)
            except Exception as exc:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        file=path,
                        line=None,
                        column=None,
                        code="P0",
                        message=f"parse error: {exc}",
                    )
                )
                continue
            concepts[concept.name] = concept

    if syncs_dir.is_dir():
        for path in sorted(syncs_dir.rglob("*.sync")):
            try:
                sync = parse_sync_file(path)
            except Exception as exc:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        file=path,
                        line=None,
                        column=None,
                        code="P0",
                        message=f"parse error: {exc}",
                    )
                )
                continue
            syncs[sync.name] = sync

    return Workspace(concepts=concepts, syncs=syncs), diagnostics
```

- [ ] **Step 10.5: Run the tests — should pass**

Run: `uv run pytest tests/test_loader.py -v`
Expected: 5 passed.

- [ ] **Step 10.6: Commit**

```bash
git add \
  src/concept_lang/loader.py \
  tests/test_loader.py \
  tests/fixtures/loader/clean/concepts/Counter.concept \
  tests/fixtures/loader/clean/syncs/log.sync \
  tests/fixtures/loader/concepts_only/concepts/Counter.concept \
  tests/fixtures/loader/syncs_only/syncs/standalone.sync
git commit -m "feat(loader): load_workspace happy path (concepts + syncs directories)"
```

---

## Task 11: `load_workspace` error handling — bad file, empty tree, missing directory

Covers the non-happy-path cases: one file in a directory fails to parse (partial load), empty directories (returns empty workspace, no diagnostics), and a missing root (returns empty workspace + one `L0` diagnostic).

**Files:**
- Create: `tests/fixtures/loader/bad_concept/concepts/Broken.concept`
- Create: `tests/fixtures/loader/bad_concept/concepts/Counter.concept`
- Create: `tests/fixtures/loader/bad_concept/syncs/log.sync`
- Create: `tests/fixtures/loader/empty/concepts/.gitkeep`
- Create: `tests/fixtures/loader/empty/syncs/.gitkeep`
- Modify: `tests/test_loader.py`

- [ ] **Step 11.1: Create the `bad_concept` fixture tree**

Create `tests/fixtures/loader/bad_concept/concepts/Broken.concept`:

```
concept Broken

  purpose
    a broken concept that cannot parse

  state
    this is not a valid state line

  actions

  operational principle
```

(The file is intentionally malformed: the `state` line has no `name: type_expr` shape, and `actions` / `operational principle` have no bodies. The new grammar rejects it.)

Create `tests/fixtures/loader/bad_concept/concepts/Counter.concept` — copy the clean Counter contents from Task 10.1.

Create `tests/fixtures/loader/bad_concept/syncs/log.sync` — copy the clean `log.sync` contents from Task 10.1.

- [ ] **Step 11.2: Create the empty fixture tree**

Create `tests/fixtures/loader/empty/concepts/.gitkeep` (empty file).
Create `tests/fixtures/loader/empty/syncs/.gitkeep` (empty file).

- [ ] **Step 11.3: Write the failing error-handling tests**

Append to `tests/test_loader.py`:

```python
class TestLoadWorkspaceErrors:
    def test_bad_concept_still_loads_the_good_ones(self):
        ws, diags = load_workspace(FIXTURES_ROOT / "bad_concept")
        # Counter parses fine, Broken does not.
        assert "Counter" in ws.concepts
        assert "Broken" not in ws.concepts
        # The sync still loads because the broken concept did not short-circuit us.
        assert "LogInc" in ws.syncs
        # One P0 diagnostic for Broken.concept.
        p0s = [d for d in diags if d.code == "P0"]
        assert len(p0s) == 1
        assert p0s[0].severity == "error"
        assert p0s[0].file is not None
        assert p0s[0].file.name == "Broken.concept"

    def test_empty_workspace_has_no_diagnostics(self):
        ws, diags = load_workspace(FIXTURES_ROOT / "empty")
        assert ws.concepts == {}
        assert ws.syncs == {}
        assert diags == []

    def test_missing_root_returns_l0_diagnostic(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        ws, diags = load_workspace(missing)
        assert ws.concepts == {}
        assert ws.syncs == {}
        assert len(diags) == 1
        assert diags[0].code == "L0"
        assert diags[0].severity == "error"
        assert diags[0].file == missing

    def test_missing_concepts_dir_is_ok(self, tmp_path):
        # Root exists, syncs/ exists, concepts/ does not — that's a valid
        # "syncs only" workspace and should not produce a diagnostic.
        (tmp_path / "syncs").mkdir()
        (tmp_path / "syncs" / "x.sync").write_text(
            "sync X\n\n  when\n    A/do: [ ] => [ ]\n  then\n    B/do: [ ] => [ ]\n",
            encoding="utf-8",
        )
        ws, diags = load_workspace(tmp_path)
        assert ws.concepts == {}
        assert "X" in ws.syncs
        assert diags == []

    def test_missing_syncs_dir_is_ok(self, tmp_path):
        (tmp_path / "concepts").mkdir()
        (tmp_path / "concepts" / "Tiny.concept").write_text(
            (
                "concept Tiny\n"
                "\n"
                "  purpose\n"
                "    tiny thing\n"
                "\n"
                "  actions\n"
                "    noop [ ] => [ ok: boolean ]\n"
                "\n"
                "  operational principle\n"
                "    after noop [ ] => [ ok: true ]\n"
            ),
            encoding="utf-8",
        )
        ws, diags = load_workspace(tmp_path)
        assert "Tiny" in ws.concepts
        assert ws.syncs == {}
        assert diags == []

    def test_broken_sync_produces_p0_and_does_not_hide_concept(self, tmp_path):
        (tmp_path / "concepts").mkdir()
        (tmp_path / "concepts" / "Counter.concept").write_text(
            (
                "concept Counter\n"
                "\n"
                "  purpose\n"
                "    count things\n"
                "\n"
                "  state\n"
                "    total: int\n"
                "\n"
                "  actions\n"
                "    inc [ ] => [ total: int ]\n"
                "\n"
                "  operational principle\n"
                "    after inc [ ] => [ total: 1 ]\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "syncs").mkdir()
        (tmp_path / "syncs" / "broken.sync").write_text(
            "sync Broken\n  this is nonsense\n",
            encoding="utf-8",
        )
        ws, diags = load_workspace(tmp_path)
        assert "Counter" in ws.concepts
        assert ws.syncs == {}
        assert len(diags) == 1
        assert diags[0].code == "P0"
        assert diags[0].file is not None
        assert diags[0].file.name == "broken.sync"
```

- [ ] **Step 11.4: Run the tests**

Run: `uv run pytest tests/test_loader.py -v`
Expected: the happy-path tests from Task 10 still pass, and the new error-handling tests also pass. The loader implementation from Task 10 already handles every case (missing root via `root.exists()` check, missing subdir via `is_dir()` guard, parse failures via per-file `try/except`) — no code changes should be needed.

If any test fails, fix the loader — the tests pin the semantics, not the implementation.

- [ ] **Step 11.5: Commit**

```bash
git add \
  tests/fixtures/loader/bad_concept/ \
  tests/fixtures/loader/empty/ \
  tests/test_loader.py
git commit -m "test(loader): error handling (bad file, empty tree, missing root)"
```

---

## Task 12: Integration — `load_workspace` + `validate_workspace`

The paper-alignment spec §5.1 expects MCP tools (P4) to call `load_workspace` followed by `validate_workspace` to produce a single combined diagnostic list. This task pins that interaction with a test that loads the `realworld` positive-fixture tree, validates it, and asserts zero error-level diagnostics. This exercises the full P1+P2+P3 pipeline end-to-end.

**Files:**
- Modify: `tests/test_loader.py`

- [ ] **Step 12.1: Write the integration test**

Append to `tests/test_loader.py`:

```python
class TestLoadAndValidateIntegration:
    """
    End-to-end pin: loading a positive-fixture workspace and validating
    the result must produce zero error-level diagnostics.
    """

    def test_load_and_validate_realworld_is_clean(self):
        from concept_lang.parse import parse_sync_file
        from concept_lang.validate import validate_workspace

        realworld = Path(__file__).parent / "fixtures" / "realworld"
        ws, load_diags = load_workspace(realworld)
        assert load_diags == [], (
            "loading realworld produced parse diagnostics:\n"
            + "\n".join(f"  {d.code} ({d.file}): {d.message}" for d in load_diags)
        )
        assert ws.concepts
        assert ws.syncs

        # Build the concept_files / sync_files map so that validator
        # diagnostics carry real paths.
        concept_files = {
            name: (realworld / "concepts" / f"{name}.concept")
            for name in ws.concepts
        }
        sync_files: dict = {}
        for p in sorted((realworld / "syncs").glob("*.sync")):
            sync_files[parse_sync_file(p).name] = p

        validate_diags = validate_workspace(
            ws, concept_files=concept_files, sync_files=sync_files
        )
        errors = [d for d in validate_diags if d.severity == "error"]
        assert errors == [], (
            "realworld validator errors after load_workspace:\n"
            + "\n".join(f"  {d.code} ({d.file}): {d.message}" for d in errors)
        )

    def test_load_and_validate_architecture_ide_is_clean(self):
        from concept_lang.parse import parse_sync_file
        from concept_lang.validate import validate_workspace

        root = Path(__file__).parent / "fixtures" / "architecture_ide"
        ws, load_diags = load_workspace(root)
        assert load_diags == []

        concept_files = {
            name: (root / "concepts" / f"{name}.concept")
            for name in ws.concepts
        }
        sync_files: dict = {}
        for p in sorted((root / "syncs").glob("*.sync")):
            sync_files[parse_sync_file(p).name] = p

        validate_diags = validate_workspace(
            ws, concept_files=concept_files, sync_files=sync_files
        )
        errors = [d for d in validate_diags if d.severity == "error"]
        assert errors == []
```

**Note on the `concept_files` map:** we reconstruct it from `ws.concepts` keys by assuming `concepts/<Name>.concept` — this is a test-only convenience and works because our positive fixtures follow that convention. A future P4 task may add a richer loader that records file paths directly in `Workspace` or as a parallel map returned from `load_workspace`; for P3 that is out of scope.

- [ ] **Step 12.2: Run the integration test**

Run: `uv run pytest tests/test_loader.py::TestLoadAndValidateIntegration -v`
Expected: 2 passed.

- [ ] **Step 12.3: Commit**

```bash
git add tests/test_loader.py
git commit -m "test(loader): load_workspace + validate_workspace end-to-end on positive fixtures"
```

---

## Task 13: Re-export `load_workspace` from the package root

For ergonomics (the P4 MCP tools will `from concept_lang import load_workspace`), re-export the loader from the top-level package.

**Files:**
- Modify: `src/concept_lang/__init__.py`
- Modify: `tests/test_loader.py`

- [ ] **Step 13.1: Read the current package `__init__.py`**

Run: `cat src/concept_lang/__init__.py`

Record what is currently exported — we append to it, we don't overwrite.

- [ ] **Step 13.2: Write the failing import test**

Append to `tests/test_loader.py`:

```python
class TestLoaderReexport:
    def test_load_workspace_importable_from_package_root(self):
        # Public API: MCP tools in P4 import from the package root.
        from concept_lang import load_workspace as top_level
        from concept_lang.loader import load_workspace as module_level
        assert top_level is module_level
```

- [ ] **Step 13.3: Run the test — fails**

Run: `uv run pytest tests/test_loader.py::TestLoaderReexport -v`
Expected: `ImportError: cannot import name 'load_workspace' from 'concept_lang'`.

- [ ] **Step 13.4: Add the re-export**

Edit `src/concept_lang/__init__.py`. Append (do not overwrite existing contents):

```python
from concept_lang.loader import load_workspace
```

If the existing `__init__.py` already defines an `__all__` list, add `"load_workspace"` to it. Otherwise leave `__all__` alone — the re-export is addressable as `concept_lang.load_workspace` regardless.

- [ ] **Step 13.5: Run the test — passes**

Run: `uv run pytest tests/test_loader.py::TestLoaderReexport -v`
Expected: 1 passed.

- [ ] **Step 13.6: Commit**

```bash
git add src/concept_lang/__init__.py tests/test_loader.py
git commit -m "feat(loader): re-export load_workspace from package root"
```

---

## Task 14: P3 gate — full test suite + tag `p3-workspace-loader-complete`

**Files:**
- Modify: `tests/test_loader.py`

- [ ] **Step 14.1: Write the P3 gate test**

Append to `tests/test_loader.py`:

```python
class TestP3Gate:
    """
    The P3 gate: the full P1+P2+P3 pipeline must accept both positive
    fixture workspaces, produce no parse errors, and carry real source
    positions through every positioned AST node.
    """

    def test_positive_fixtures_round_trip_through_loader_with_positions(self):
        for subdir in ("architecture_ide", "realworld"):
            root = Path(__file__).parent / "fixtures" / subdir
            ws, diags = load_workspace(root)
            assert diags == [], (
                f"{subdir}: parse diagnostics: "
                + "; ".join(f"{d.code} {d.file}: {d.message}" for d in diags)
            )
            assert ws.concepts, f"{subdir}: no concepts loaded"
            # Every loaded concept must carry real line numbers on the
            # nodes the transformer sets (ConceptAST.line is the most
            # reliable — it's always the first token of the file).
            for name, concept in ws.concepts.items():
                assert concept.line is not None, f"{subdir}/{name}: no ConceptAST.line"
                assert concept.line >= 1
                # State declarations, when present, also carry lines.
                for decl in concept.state:
                    assert decl.line is not None, (
                        f"{subdir}/{name}: state '{decl.name}' has no line"
                    )
            for name, sync in ws.syncs.items():
                assert sync.line is not None, f"{subdir}/{name}: no SyncAST.line"
                for ap in sync.when:
                    assert ap.line is not None, (
                        f"{subdir}/{name}: when pattern has no line"
                    )
                for ap in sync.then:
                    assert ap.line is not None, (
                        f"{subdir}/{name}: then pattern has no line"
                    )
```

- [ ] **Step 14.2: Run the gate test**

Run: `uv run pytest tests/test_loader.py::TestP3Gate -v`
Expected: 1 passed.

If a node is unexpectedly `None`, that points at a transformer method that Task 5 or Task 6 missed. Go back and add `@v_args(meta=True, inline=True)` to the method that builds that node.

- [ ] **Step 14.3: Run the full project test suite**

Run: `uv run pytest -v`
Expected: every test in the project passes:

- `tests/test_ast.py` (P1 AST + new position tests)
- `tests/test_parse.py` (P1 parse + new position tests)
- `tests/test_validate.py` (P2 validator + new position assertions)
- `tests/test_loader.py` (new P3 loader tests)
- `tests/test_validator.py` (untouched v1 validator)
- `tests/test_diff.py` (untouched v1 diff)

Count should be roughly **180+** (148 from the P2 baseline plus the new AST / parse / validate / loader tests added across Tasks 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14).

- [ ] **Step 14.4: Commit the gate**

```bash
git add tests/test_loader.py
git commit -m "test(gate): P3 gate — load_workspace + positions end-to-end"
```

- [ ] **Step 14.5: Tag the milestone**

```bash
git tag p3-workspace-loader-complete -m "P3 gate passed: load_workspace and source positions threaded end-to-end"
```

- [ ] **Step 14.6: Final status check**

Run: `git log --oneline -20`
Expected: ~14 small commits in the `feat(ast)` / `feat(parse)` / `feat(validate)` / `feat(loader)` / `test` namespace, ending with `test(gate)` and the tag `p3-workspace-loader-complete`.

---

## What's next (not in this plan)

After this plan lands and the `p3-workspace-loader-complete` tag is in place, the follow-up plans are:

- **P4 — Tooling migration**: rewire MCP tools (`read_concept`, `write_concept`, a new `read_sync` / `write_sync`, `validate_workspace`, `load_workspace`), `diff.py`, `explorer.py`, and the app-spec path (`app_parser.py` / `app_validator.py`) to the new AST. This is where `load_workspace` starts to earn its keep.
- **P5 — Skills rewrite**: `build`, `build-sync`, `review`, `scaffold`, `explore`.
- **P6 — Examples + docs**: update `architecture-ide/concepts/*` in place, rewrite `README.md`, add `docs/methodology.md`.
- **P7 — Delete v1**: remove `concept_lang.parser`, `concept_lang.models`, `concept_lang.validator`, `concept_lang.app_parser`, `concept_lang.app_validator`, and their tests.

Two small design questions still live in the P3 region and should be addressed in one of the above phases:

- **`C8` (state field referenced in effects, warning)** remains deferred. Spec §6.2 still lists it as "skipped for the first cut". P4 or P5 can bundle it when the rule set is revisited.
- **`OPStep.inputs/outputs` as `tuple[str, str]` vs `PatternField`.** This is a live architectural smell flagged in design decision (F) of this plan. Resolving it — either by keeping the tuple shape with a documented contract or by migrating to a new `OPStepArg` Pydantic type — deserves a dedicated discussion, probably during P6 (docs + examples, when the distinction between "OP step args" and "sync pattern fields" becomes user-facing).

Each deserves its own plan, written after the preceding phase lands so we're planning on verified ground.

---

## Self-review (filled in after drafting, before execution)

- **Spec coverage** — every P3 scope item from the brief has a corresponding task:

  | Scope item | Task(s) |
  |---|---|
  | Decision A — `SourceSpan` vs inline fields | Design decisions section (chose inline) |
  | Decision B — which AST nodes get positions | Design decisions section |
  | Decision C — transformer meta propagation | Task 4 (Lark flag) + Task 5 + Task 6 |
  | Decision D — `load_workspace` return type | Design decisions section + Task 10 |
  | Decision E — negative fixture tightening | Task 9 |
  | `tests/__init__.py` (P2 follow-up) | Task 1 |
  | Position fields on concept nodes | Task 2 |
  | Position fields on sync nodes | Task 3 |
  | `propagate_positions=True` on Lark | Task 4 |
  | Concept transformer threading | Task 5 |
  | Sync transformer threading | Task 6 |
  | Concept validator rules use positions | Task 7 |
  | Sync validator rules use positions | Task 8 |
  | Negative fixture line tightening | Task 9 |
  | `load_workspace` happy path | Task 10 |
  | `load_workspace` error handling | Task 11 |
  | `load_workspace` + `validate_workspace` integration | Task 12 |
  | `load_workspace` re-export | Task 13 |
  | P3 gate + tag | Task 14 |

- **Placeholder scan** — no "TBD", no "similar to above", no "etc." in place of code. Every code block is literal. The one intentional placeholder is the `<LINE>` token in Tasks 9.2..9.5 — it is explicitly a number the executor must fill in from the fixture they just read in Step 9.1, and the instruction to do so is spelled out. `C8` is named and explicitly marked deferred in both the scope note and the closing "What's next" section.

- **Type consistency** — across every task:
  - AST field names are always `line: int | None = None` and `column: int | None = None`. No `lineno`, no `col`, no `span`, no `SourceSpan`.
  - Diagnostic construction always uses `line=node.line, column=node.column` (for positioned rules). C4 stays on its existing string-offset computation because the rule runs on raw source and the concept's AST is unavailable there.
  - `load_workspace` signature is exactly `load_workspace(root: Path) -> tuple[Workspace, list[Diagnostic]]` in Task 10, the re-export in Task 13, and the integration tests in Tasks 11 and 12.
  - The P0 (per-file parse error) and L0 (loader-level missing root) diagnostic codes are defined in Task 10 and used consistently thereafter; no task invents a new code.

- **Ambiguity check** —
  - "Positioned node" is defined once in decision (B) with an explicit list; Tasks 2, 3, 5, 6, 14 all dispatch on the same list.
  - "Meta is empty" is handled identically (via the `_pos(meta)` helper) in both transformers (Tasks 5 and 6). The helper's fall-through to `(None, None)` is the one place empty-meta semantics is decided.
  - The negative-fixture matcher contract — "integer means exact, `null` means any" — is defined once in Task 9.6 and the new helper method name `_assert_expected_in_diagnostics` is referenced from both the concept sweep and the sync sweep in the same task.
  - The integration test in Task 12 reconstructs `concept_files` by convention (`concepts/<Name>.concept`) and documents this as a test-only shortcut. No other task assumes the `Workspace` value carries file paths.

- **Scope discipline** — no new validator rules (C8 stays deferred, in line with P2's scope note); no grammar edits (only the `propagate_positions=True` flag on the `Lark(...)` constructor); no v1 files touched; apps deliberately out of scope and called out in both the scope note and the loader module docstring.

- **Commit discipline** — every task ends with exactly one `git add` + `git commit` covering the files listed in its Files section. Tasks that create fixture trees commit the fixture files together with the test file that pins them. No task commits v1 files.

- **Test count tracking** — the plan does not hard-code intermediate `X passed` counts beyond "148" at the start (P2 baseline) and "roughly 180+" at the P3 gate. This avoids off-by-N maintenance churn if intermediate counts drift.

- **Running discipline** — every task has a "run the failing test first" step, a "run the passing test after the implementation" step, and a final full-file or full-project run before committing. No task skips straight to commit.
