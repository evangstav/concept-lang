# concept-lang 0.2.0 — P2: Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the paper-alignment validator on top of the P1 AST. At the end of this plan, `validate_workspace()` runs the full rule set (`C1`-`C9` minus `C8`, `S1`-`S5`) over the positive fixture workspaces with zero error-level diagnostics, and every negative fixture in `tests/fixtures/negative/` fires exactly the diagnostic codes declared in its matching `*.expected.json`.

**Architecture:** A new `concept_lang.validate` package lives *alongside* the v1 `concept_lang.validator` until P7. It operates on `concept_lang.ast.Workspace` values (already built by P1) and emits `Diagnostic` records. Each rule is a small pure function `rule(...) -> list[Diagnostic]`. A top-level `validate_workspace()` aggregates all rules; per-file wrappers `validate_concept_file()` and `validate_sync_file()` support the MCP tool path (single-file edits with minimal cross-ref context).

**Tech Stack:** Python 3.10+, Pydantic 2, pytest, uv. No new dependencies - Lark is only used at parse time; the validator consumes the already-built AST.

**Scope note:** This plan covers **P2 only**.

- In scope: rules `C1`, `C2`, `C3`, `C4`, `C5`, `C6`, `C7`, `C9`, `S1`, `S2`, `S3`, `S4`, `S5`. `C8` is deliberately deferred (the spec marks it "skipped for the first cut" because it is triggered by omission and hard to express as a minimal positive fixture).
- Out of scope: `load_workspace()` (cross-file directory loader - P3), MCP tool changes (P4), skill updates (P5), v1 code deletion (P7), app-spec validator migration (`A1`/`A2` stay in the untouched v1 `app_validator.py` until P4).

**Spec reference:** [`docs/superpowers/specs/2026-04-10-paper-alignment-design.md`](../specs/2026-04-10-paper-alignment-design.md) §4.3 and §6.2.

**Starting state:** Branch `feat/p1-parser`, HEAD at tag `p1-parser-complete` (`59cb510`). `concept_lang.ast`, `concept_lang.parse`, and the positive fixtures all exist and all tests pass. The v1 `concept_lang.validator`, `concept_lang.parser`, `concept_lang.models`, and `concept_lang.app_validator` modules are untouched and continue to pass their own tests.

---

## File structure (what this plan creates)

```
architecture-ide/
  src/concept_lang/
    validate/
      __init__.py                                  # CREATE: package + public API
      diagnostic.py                                # CREATE: Diagnostic Pydantic model
      helpers.py                                   # CREATE: workspace indices (known concepts, actions, etc.)
      concept_rules.py                             # CREATE: rules C1..C9 (skipping C8)
      sync_rules.py                                # CREATE: rules S1..S5
      workspace.py                                 # CREATE: validate_workspace + single-file wrappers
    # v1 files STILL UNTOUCHED:
    #   validator.py, parser.py, models.py, app_validator.py, ...
  tests/
    test_validate.py                               # CREATE: all validator tests
    fixtures/
      negative/                                    # CREATE: negative fixtures + expected
        C1_state_references_other_concept.concept
        C1_state_references_other_concept.expected.json
        C2_effects_references_foreign_state.concept
        C2_effects_references_foreign_state.expected.json
        C3_op_principle_uses_foreign_action.concept
        C3_op_principle_uses_foreign_action.expected.json
        C4_concept_has_sync_section.concept
        C4_concept_has_sync_section.expected.json
        C5_missing_purpose.concept
        C5_missing_purpose.expected.json
        C6_no_actions.concept
        C6_no_actions.expected.json
        C7_only_error_cases.concept
        C7_only_error_cases.expected.json
        C9_missing_op_principle.concept
        C9_missing_op_principle.expected.json
        S1_sync_references_unknown_concept.sync
        S1_sync_references_unknown_concept.expected.json
        S2_pattern_field_not_in_action.sync
        S2_pattern_field_not_in_action.expected.json
        S3_then_var_not_bound.sync
        S3_then_var_not_bound.expected.json
        S4_where_var_not_bound.sync
        S4_where_var_not_bound.expected.json
        S5_sync_references_one_concept.sync
        S5_sync_references_one_concept.expected.json
```

**All commands below assume the working directory is `architecture-ide/`** (the package root with `pyproject.toml`). All paths in Files sections are relative to that directory.

**Diagnostic shape used throughout the plan:**

```python
class Diagnostic(BaseModel):
    severity: Literal["error", "warning", "info"]
    file: Path | None   # None for workspace-scoped diagnostics
    line: int | None    # None if not applicable
    column: int | None  # None if not applicable
    code: str           # e.g. "C1", "S3"
    message: str
```

**Rule function signature convention:**

- Concept rules operate on a single `ConceptAST` plus, when needed, a `WorkspaceIndex` for cross-reference lookups, and return `list[Diagnostic]`.
- Sync rules operate on a single `SyncAST` plus a `WorkspaceIndex`, and return `list[Diagnostic]`.
- Line numbers are best-effort. P1 does not yet attach `line`/`column` to AST nodes, so most diagnostics produced in P2 use `line=None`. The negative fixture `*.expected.json` files therefore use `"line": null` for matching. A follow-up plan (P3 or later) can tighten this once the parser attaches positions.

---

## Task 1: `Diagnostic` type and round-trip tests

**Files:**
- Create: `src/concept_lang/validate/__init__.py`
- Create: `src/concept_lang/validate/diagnostic.py`
- Create: `tests/test_validate.py`

- [ ] **Step 1.1: Write the failing test**

Create `tests/test_validate.py`:

```python
"""Tests for the new validator (concept_lang.validate)."""

from pathlib import Path

from concept_lang.validate.diagnostic import Diagnostic


class TestDiagnostic:
    def test_round_trip(self):
        d = Diagnostic(
            severity="error",
            file=Path("tests/fixtures/negative/C1_state_references_other_concept.concept"),
            line=5,
            column=3,
            code="C1",
            message="state field 'owner' references unknown type 'User'",
        )
        dumped = d.model_dump(mode="json")
        restored = Diagnostic.model_validate(dumped)
        assert restored == d

    def test_workspace_scoped_has_no_file(self):
        d = Diagnostic(
            severity="warning",
            file=None,
            line=None,
            column=None,
            code="S5",
            message="sync references only one concept",
        )
        assert d.file is None
        assert d.line is None

    def test_severity_literal(self):
        import pytest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Diagnostic(
                severity="fatal",  # type: ignore[arg-type]
                file=None,
                line=None,
                column=None,
                code="C1",
                message="...",
            )
```

- [ ] **Step 1.2: Run the test - it should fail**

Run: `uv run pytest tests/test_validate.py -v`
Expected: `ModuleNotFoundError: No module named 'concept_lang.validate'`.

- [ ] **Step 1.3: Create the validate package**

Create `src/concept_lang/validate/__init__.py`:

```python
"""
concept-lang 0.2.0 validator.

Lives alongside the v1 `concept_lang.validator` until P7. Consumes AST
values produced by `concept_lang.parse` and emits `Diagnostic` records.

Public API (grows across the tasks of the P2 plan):
    Diagnostic
    validate_workspace
    validate_concept_file
    validate_sync_file
"""

from concept_lang.validate.diagnostic import Diagnostic

__all__ = ["Diagnostic"]
```

- [ ] **Step 1.4: Create the Diagnostic module**

Create `src/concept_lang/validate/diagnostic.py`:

```python
"""Diagnostic record emitted by every validator rule."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class Diagnostic(BaseModel):
    """
    One diagnostic record produced by the validator.

    A `file=None` diagnostic is workspace-scoped (for example, a cross-file
    rule reporting that a sync references a concept that does not exist
    anywhere in the workspace).

    `line` and `column` are best-effort: the P1 parser does not yet attach
    source positions to AST nodes, so most P2 diagnostics use
    `line=None`/`column=None`. A follow-up plan will wire Lark's position
    metadata through the transformers.
    """

    severity: Literal["error", "warning", "info"]
    file: Path | None = None
    line: int | None = None
    column: int | None = None
    code: str
    message: str
```

- [ ] **Step 1.5: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 3 passed.

- [ ] **Step 1.6: Commit**

```bash
git add src/concept_lang/validate/__init__.py src/concept_lang/validate/diagnostic.py tests/test_validate.py
git commit -m "feat(validate): Diagnostic type for the new validator"
```

---

## Task 2: Workspace index helper (`WorkspaceIndex`)

Before any rule is implemented, we add a small shared helper that precomputes the cross-reference tables every rule needs: the set of known concept names, the map from `(concept_name, action_name)` to the list of `ActionCase`s, and the set of field names per concept. This keeps every rule function a short dispatch over cached data.

**Files:**
- Create: `src/concept_lang/validate/helpers.py`
- Modify: `tests/test_validate.py`

- [ ] **Step 2.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.ast import (
    Action,
    ActionCase,
    ConceptAST,
    OperationalPrinciple,
    StateDecl,
    TypedName,
    Workspace,
)
from concept_lang.validate.helpers import WorkspaceIndex


def _make_tiny_workspace() -> Workspace:
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
                        inputs=[TypedName(name="amount", type_expr="int")],
                        outputs=[TypedName(name="total", type_expr="int")],
                    )
                ],
            ),
            Action(
                name="read",
                cases=[
                    ActionCase(
                        inputs=[],
                        outputs=[TypedName(name="total", type_expr="int")],
                    )
                ],
            ),
        ],
        operational_principle=OperationalPrinciple(steps=[]),
        source="",
    )
    return Workspace(concepts={"Counter": counter}, syncs={})


class TestWorkspaceIndex:
    def test_known_concept_names(self):
        idx = WorkspaceIndex.build(_make_tiny_workspace())
        assert "Counter" in idx.concept_names
        assert "Unknown" not in idx.concept_names

    def test_action_cases_lookup(self):
        idx = WorkspaceIndex.build(_make_tiny_workspace())
        cases = idx.action_cases("Counter", "inc")
        assert cases is not None
        assert len(cases) == 1
        assert cases[0].inputs[0].name == "amount"

    def test_action_cases_missing(self):
        idx = WorkspaceIndex.build(_make_tiny_workspace())
        assert idx.action_cases("Counter", "delete") is None
        assert idx.action_cases("Unknown", "inc") is None

    def test_state_field_names(self):
        idx = WorkspaceIndex.build(_make_tiny_workspace())
        fields = idx.state_field_names("Counter")
        assert fields == {"total"}
        assert idx.state_field_names("Unknown") == set()

    def test_concept_action_field_names(self):
        idx = WorkspaceIndex.build(_make_tiny_workspace())
        # Union of all input + output field names across all cases of the action.
        names = idx.action_field_names("Counter", "inc")
        assert names == {"amount", "total"}
```

- [ ] **Step 2.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestWorkspaceIndex -v`
Expected: `ModuleNotFoundError: No module named 'concept_lang.validate.helpers'`.

- [ ] **Step 2.3: Create the helpers module**

Create `src/concept_lang/validate/helpers.py`:

```python
"""
Shared cross-reference indices used by validator rules.

A `WorkspaceIndex` is built once per `validate_workspace` call and passed
into the individual rule functions. This keeps rules O(1) on their common
lookups (is this concept known? what fields does this action have?).
"""

from dataclasses import dataclass, field

from concept_lang.ast import ActionCase, Workspace


@dataclass
class WorkspaceIndex:
    """Precomputed cross-reference tables for a `Workspace`."""

    concept_names: set[str] = field(default_factory=set)
    # (concept_name, action_name) -> list of action cases
    _action_cases: dict[tuple[str, str], list[ActionCase]] = field(default_factory=dict)
    # concept_name -> set of declared state field names
    _state_fields: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def build(cls, workspace: Workspace) -> "WorkspaceIndex":
        idx = cls()
        for name, concept in workspace.concepts.items():
            idx.concept_names.add(name)
            idx._state_fields[name] = {s.name for s in concept.state}
            for action in concept.actions:
                idx._action_cases[(name, action.name)] = list(action.cases)
        return idx

    def action_cases(self, concept: str, action: str) -> list[ActionCase] | None:
        """Return the list of cases for `concept/action`, or None if unknown."""
        return self._action_cases.get((concept, action))

    def state_field_names(self, concept: str) -> set[str]:
        """Return the set of state field names for `concept` (empty if unknown)."""
        return self._state_fields.get(concept, set())

    def action_field_names(self, concept: str, action: str) -> set[str]:
        """
        Union of input and output field names across all cases of
        `concept/action`. Empty if the action is unknown.
        """
        cases = self.action_cases(concept, action)
        if cases is None:
            return set()
        names: set[str] = set()
        for case in cases:
            for inp in case.inputs:
                names.add(inp.name)
            for out in case.outputs:
                names.add(out.name)
        return names
```

- [ ] **Step 2.4: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 8 passed (3 from Task 1 + 5 new).

- [ ] **Step 2.5: Commit**

```bash
git add src/concept_lang/validate/helpers.py tests/test_validate.py
git commit -m "feat(validate): WorkspaceIndex for cross-reference lookups"
```

---

## Task 3: Rule C1 - state declarations reference only own type params + primitives

**Rule:** A concept's `state` declarations may only reference its own type parameters and primitive types. No other concept names.

**Implementation approach:** A state field's `type_expr` is kept as raw text (e.g. `"set U"`, `"U -> string"`, `"set Item"`). We tokenize it on non-identifier characters and check every identifier against: the concept's own type params, a small set of primitives, and a set of reserved type-expression keywords (`set`, `seq`, `opt`, `map`). Anything else is flagged as a foreign reference.

**Files:**
- Create: `src/concept_lang/validate/concept_rules.py`
- Create: `tests/fixtures/negative/C1_state_references_other_concept.concept`
- Create: `tests/fixtures/negative/C1_state_references_other_concept.expected.json`
- Modify: `src/concept_lang/validate/__init__.py`
- Modify: `tests/test_validate.py`

- [ ] **Step 3.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.parse import parse_concept_source
from concept_lang.validate import rule_c1_state_independence


class TestRuleC1:
    def test_own_type_param_is_allowed(self):
        src = """
concept Box [T]

  purpose
    store things

  state
    items: set T

  actions
    add [ item: T ] => [ box: Box ]

  operational principle
    after add [ item: x ] => [ box: b ]
"""
        ast = parse_concept_source(src)
        diags = rule_c1_state_independence(ast)
        assert diags == []

    def test_primitive_types_are_allowed(self):
        src = """
concept Counter

  purpose
    count things

  state
    total: int
    label: string

  actions
    inc [ ] => [ total: int ]

  operational principle
    after inc [ ] => [ total: 1 ]
"""
        ast = parse_concept_source(src)
        diags = rule_c1_state_independence(ast)
        assert diags == []

    def test_foreign_concept_is_flagged(self):
        src = """
concept Basket

  purpose
    hold user items

  state
    owner: User

  actions
    add [ item: string ] => [ basket: Basket ]

  operational principle
    after add [ item: "apple" ] => [ basket: b ]
"""
        ast = parse_concept_source(src)
        diags = rule_c1_state_independence(ast)
        assert len(diags) == 1
        assert diags[0].code == "C1"
        assert diags[0].severity == "error"
        assert "User" in diags[0].message

    def test_relation_with_foreign_on_either_side(self):
        src = """
concept Assignment

  purpose
    assign tasks to people

  state
    assigned: Task -> Person

  actions
    assign [ task: string ; person: string ] => [ assignment: Assignment ]

  operational principle
    after assign [ task: "t" ; person: "p" ] => [ assignment: a ]
"""
        ast = parse_concept_source(src)
        diags = rule_c1_state_independence(ast)
        codes = [d.code for d in diags]
        # Both Task and Person should be flagged - the rule reports each.
        assert codes.count("C1") == 2
```

- [ ] **Step 3.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestRuleC1 -v`
Expected: `ImportError: cannot import name 'rule_c1_state_independence' from 'concept_lang.validate'`.

- [ ] **Step 3.3: Create the concept_rules module with C1**

Create `src/concept_lang/validate/concept_rules.py`:

```python
"""
Validator rules for a single `ConceptAST` (paper rules C1..C9 except C8).

Each rule is a pure function that takes the concept AST (and, when it
needs cross-file context, a `WorkspaceIndex`) and returns a list of
`Diagnostic` records. Line/column information is best-effort: the P1
parser does not yet attach source positions to AST nodes, so most
diagnostics produced here use `line=None`.
"""

import re
from pathlib import Path

from concept_lang.ast import ActionCase, ConceptAST
from concept_lang.validate.diagnostic import Diagnostic

# Primitive types that a concept's state may reference without declaring
# them as type parameters. Matches the paper's Alloy-style type expressions.
_PRIMITIVE_TYPES: frozenset[str] = frozenset({
    "bool",
    "boolean",
    "int",
    "integer",
    "float",
    "number",
    "string",
    "str",
    "text",
    "date",
    "datetime",
    "time",
    "duration",
})

# Reserved words that may appear inside a type expression but are not
# themselves type references (they are constructors or operators).
_TYPE_EXPR_RESERVED: frozenset[str] = frozenset({
    "set",
    "seq",
    "opt",
    "map",
    "lone",
    "one",
    "some",
})

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _tokens_in(type_expr: str) -> list[str]:
    """Return the identifier tokens that appear in a type expression."""
    return _IDENT_RE.findall(type_expr)


def rule_c1_state_independence(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C1: State declarations may only reference own type params + primitives.

    Any identifier token in `type_expr` that is not the concept's own type
    parameter, a primitive type, or a reserved type-expression keyword is
    flagged as a foreign reference.
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
                    line=None,
                    column=None,
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

- [ ] **Step 3.4: Re-export the rule from the package**

Edit `src/concept_lang/validate/__init__.py` and replace its contents with:

```python
"""
concept-lang 0.2.0 validator.

Lives alongside the v1 `concept_lang.validator` until P7. Consumes AST
values produced by `concept_lang.parse` and emits `Diagnostic` records.

Public API (grows across the tasks of the P2 plan):
    Diagnostic
    rule_c1_state_independence
    validate_workspace
    validate_concept_file
    validate_sync_file
"""

from concept_lang.validate.concept_rules import rule_c1_state_independence
from concept_lang.validate.diagnostic import Diagnostic

__all__ = [
    "Diagnostic",
    "rule_c1_state_independence",
]
```

- [ ] **Step 3.5: Create the C1 negative fixture**

Create `tests/fixtures/negative/C1_state_references_other_concept.concept`:

```
concept Basket

  purpose
    hold user items

  state
    owner: User

  actions
    add [ item: string ] => [ basket: Basket ]

  operational principle
    after add [ item: "apple" ] => [ basket: b ]
```

Create `tests/fixtures/negative/C1_state_references_other_concept.expected.json`:

```json
{
  "diagnostics": [
    {
      "code": "C1",
      "severity": "error",
      "line": null
    }
  ]
}
```

- [ ] **Step 3.6: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py::TestRuleC1 -v`
Expected: 4 passed.

- [ ] **Step 3.7: Commit**

```bash
git add src/concept_lang/validate/concept_rules.py src/concept_lang/validate/__init__.py tests/fixtures/negative/C1_state_references_other_concept.concept tests/fixtures/negative/C1_state_references_other_concept.expected.json tests/test_validate.py
git commit -m "feat(validate): rule C1 - state independence"
```

---

## Task 4: Rule C2 - effects clause references only own state fields

**Rule:** Each action case's `effects:` clause may only reference state fields declared in *this* concept.

**Implementation:** For every `EffectClause` on every `ActionCase`, check that `clause.field` is in the concept's own state field names.

**Files:**
- Modify: `src/concept_lang/validate/concept_rules.py`
- Modify: `src/concept_lang/validate/__init__.py`
- Create: `tests/fixtures/negative/C2_effects_references_foreign_state.concept`
- Create: `tests/fixtures/negative/C2_effects_references_foreign_state.expected.json`
- Modify: `tests/test_validate.py`

- [ ] **Step 4.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.validate import rule_c2_effects_independence


class TestRuleC2:
    def test_effects_on_own_field_is_allowed(self):
        src = """
concept Password [U]

  purpose
    store credentials

  state
    password: U -> string

  actions
    set [ user: U ; password: string ] => [ user: U ]
      store the hash
      effects:
        password[user] := hash

  operational principle
    after set [ user: x ; password: "secret" ] => [ user: x ]
"""
        ast = parse_concept_source(src)
        diags = rule_c2_effects_independence(ast)
        assert diags == []

    def test_effects_on_foreign_field_is_flagged(self):
        src = """
concept Password [U]

  purpose
    store credentials

  state
    password: U -> string

  actions
    set [ user: U ; password: string ] => [ user: U ]
      store the hash
      effects:
        profile[user] := picture

  operational principle
    after set [ user: x ; password: "secret" ] => [ user: x ]
"""
        ast = parse_concept_source(src)
        diags = rule_c2_effects_independence(ast)
        assert len(diags) == 1
        assert diags[0].code == "C2"
        assert "profile" in diags[0].message
        assert "Password" in diags[0].message
```

- [ ] **Step 4.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestRuleC2 -v`
Expected: `ImportError: cannot import name 'rule_c2_effects_independence'`.

- [ ] **Step 4.3: Add C2 to `concept_rules.py`**

Append to `src/concept_lang/validate/concept_rules.py`:

```python
def rule_c2_effects_independence(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C2: Effects clauses may only reference state fields declared on this concept.
    """
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
                        line=None,
                        column=None,
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

- [ ] **Step 4.4: Re-export from the package**

Edit `src/concept_lang/validate/__init__.py` to add `rule_c2_effects_independence`:

```python
from concept_lang.validate.concept_rules import (
    rule_c1_state_independence,
    rule_c2_effects_independence,
)
from concept_lang.validate.diagnostic import Diagnostic

__all__ = [
    "Diagnostic",
    "rule_c1_state_independence",
    "rule_c2_effects_independence",
]
```

- [ ] **Step 4.5: Create the C2 negative fixture**

Create `tests/fixtures/negative/C2_effects_references_foreign_state.concept`:

```
concept Password [U]

  purpose
    store credentials

  state
    password: U -> string

  actions
    set [ user: U ; password: string ] => [ user: U ]
      store the hash
      effects:
        profile[user] := picture

  operational principle
    after set [ user: x ; password: "secret" ] => [ user: x ]
```

Create `tests/fixtures/negative/C2_effects_references_foreign_state.expected.json`:

```json
{
  "diagnostics": [
    {
      "code": "C2",
      "severity": "error",
      "line": null
    }
  ]
}
```

- [ ] **Step 4.6: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 10 passed.

- [ ] **Step 4.7: Commit**

```bash
git add src/concept_lang/validate/concept_rules.py src/concept_lang/validate/__init__.py tests/fixtures/negative/C2_effects_references_foreign_state.concept tests/fixtures/negative/C2_effects_references_foreign_state.expected.json tests/test_validate.py
git commit -m "feat(validate): rule C2 - effects independence"
```

---

## Task 5: Rule C3 - operational principle uses only own actions

**Rule:** A concept's `operational principle` may only invoke actions of *this* concept.

**Implementation:** Every `OPStep.action_name` must appear in the concept's own actions list.

**Files:**
- Modify: `src/concept_lang/validate/concept_rules.py`
- Modify: `src/concept_lang/validate/__init__.py`
- Create: `tests/fixtures/negative/C3_op_principle_uses_foreign_action.concept`
- Create: `tests/fixtures/negative/C3_op_principle_uses_foreign_action.expected.json`
- Modify: `tests/test_validate.py`

- [ ] **Step 5.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.validate import rule_c3_op_principle_independence


class TestRuleC3:
    def test_own_actions_only(self):
        src = """
concept Counter

  purpose
    count things

  state
    total: int

  actions
    inc [ ] => [ total: int ]
    read [ ] => [ total: int ]

  operational principle
    after inc [ ] => [ total: 1 ]
    and read [ ] => [ total: 1 ]
"""
        ast = parse_concept_source(src)
        diags = rule_c3_op_principle_independence(ast)
        assert diags == []

    def test_foreign_action_is_flagged(self):
        src = """
concept Counter

  purpose
    count things

  state
    total: int

  actions
    inc [ ] => [ total: int ]

  operational principle
    after inc [ ] => [ total: 1 ]
    then sendEmail [ body: "hi" ] => [ sent: true ]
"""
        ast = parse_concept_source(src)
        diags = rule_c3_op_principle_independence(ast)
        assert len(diags) == 1
        assert diags[0].code == "C3"
        assert "sendEmail" in diags[0].message
```

- [ ] **Step 5.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestRuleC3 -v`
Expected: `ImportError: cannot import name 'rule_c3_op_principle_independence'`.

- [ ] **Step 5.3: Add C3 to `concept_rules.py`**

Append to `src/concept_lang/validate/concept_rules.py`:

```python
def rule_c3_op_principle_independence(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C3: Operational principle may only invoke actions of this concept.
    """
    diagnostics: list[Diagnostic] = []
    own_actions: set[str] = {a.name for a in concept.actions}
    for step in concept.operational_principle.steps:
        if step.action_name in own_actions:
            continue
        diagnostics.append(
            Diagnostic(
                severity="error",
                file=file,
                line=None,
                column=None,
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

- [ ] **Step 5.4: Re-export from the package**

Edit `src/concept_lang/validate/__init__.py` to add the new rule:

```python
from concept_lang.validate.concept_rules import (
    rule_c1_state_independence,
    rule_c2_effects_independence,
    rule_c3_op_principle_independence,
)
from concept_lang.validate.diagnostic import Diagnostic

__all__ = [
    "Diagnostic",
    "rule_c1_state_independence",
    "rule_c2_effects_independence",
    "rule_c3_op_principle_independence",
]
```

- [ ] **Step 5.5: Create the C3 negative fixture**

Create `tests/fixtures/negative/C3_op_principle_uses_foreign_action.concept`:

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
    then sendEmail [ body: "hi" ] => [ sent: true ]
```

Create `tests/fixtures/negative/C3_op_principle_uses_foreign_action.expected.json`:

```json
{
  "diagnostics": [
    {
      "code": "C3",
      "severity": "error",
      "line": null
    }
  ]
}
```

- [ ] **Step 5.6: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 12 passed.

- [ ] **Step 5.7: Commit**

```bash
git add src/concept_lang/validate/concept_rules.py src/concept_lang/validate/__init__.py tests/fixtures/negative/C3_op_principle_uses_foreign_action.concept tests/fixtures/negative/C3_op_principle_uses_foreign_action.expected.json tests/test_validate.py
git commit -m "feat(validate): rule C3 - operational principle independence"
```

---

## Task 6: Rule C4 - concept has no `sync` section

**Rule:** No concept may have a `sync` section. In the new format, syncs are top-level files.

**Implementation note:** The new `concept.lark` grammar from P1 *does not* include a `sync` section rule - any concept file that contains one already fails at parse time. `C4` catches the migration case: when the validator is asked to validate a raw source that contains the old inline `sync` keyword on an indented line. Because the parser rejects this outright, the rule is implemented as a **source-text scan**: the validator opens the source (available on `ConceptAST.source` or as a file path) and looks for a top-level `sync` keyword line inside the concept body.

This rule is most useful when the user is migrating: they call `validate_concept_file()` on a v1 concept file that still contains inline syncs, and they need a helpful error message instead of an opaque Lark parse error. For that reason, `rule_c4_no_inline_sync` operates on **raw source text** and a path, not on the parsed AST (the parser would have already rejected the file).

**Files:**
- Modify: `src/concept_lang/validate/concept_rules.py`
- Modify: `src/concept_lang/validate/__init__.py`
- Create: `tests/fixtures/negative/C4_concept_has_sync_section.concept`
- Create: `tests/fixtures/negative/C4_concept_has_sync_section.expected.json`
- Modify: `tests/test_validate.py`

- [ ] **Step 6.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.validate import rule_c4_no_inline_sync


class TestRuleC4:
    def test_no_sync_section_is_clean(self):
        src = """
concept Counter

  purpose
    count things

  state
    total: int

  actions
    inc [ ] => [ total: int ]

  operational principle
    after inc [ ] => [ total: 1 ]
"""
        diags = rule_c4_no_inline_sync(src, file=None)
        assert diags == []

    def test_inline_sync_section_is_flagged(self):
        src = """
concept Counter

  purpose
    count things

  state
    total: int

  actions
    inc [ ] => [ total: int ]

  operational principle
    after inc [ ] => [ total: 1 ]

  sync
    when inc then log
"""
        diags = rule_c4_no_inline_sync(src, file=None)
        assert len(diags) == 1
        assert diags[0].code == "C4"
        assert diags[0].severity == "error"
        assert "top-level" in diags[0].message.lower()

    def test_word_sync_inside_identifier_is_ignored(self):
        # An action named "resync" should not trigger C4.
        src = """
concept Counter

  purpose
    count things

  actions
    resync [ ] => [ total: int ]
"""
        diags = rule_c4_no_inline_sync(src, file=None)
        assert diags == []
```

- [ ] **Step 6.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestRuleC4 -v`
Expected: `ImportError: cannot import name 'rule_c4_no_inline_sync'`.

- [ ] **Step 6.3: Add C4 to `concept_rules.py`**

Append to `src/concept_lang/validate/concept_rules.py`:

```python
# An indented `sync` section header line. We require leading whitespace
# (section headers inside a concept are indented) followed by `sync` as a
# whole word. This avoids matching identifiers like `resync`.
_INLINE_SYNC_RE = re.compile(r"^[ \t]+sync\b", re.MULTILINE)


def rule_c4_no_inline_sync(
    source: str,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C4: Concepts may not contain an inline `sync` section.

    In the new format syncs are top-level files. This rule exists to give
    a clear error when migrating v1 concept files that still embed syncs
    inside the concept body.

    Operates on raw source text because a concept file containing an
    inline `sync` section is not parseable by the new grammar - so the AST
    path is unavailable.
    """
    diagnostics: list[Diagnostic] = []
    for match in _INLINE_SYNC_RE.finditer(source):
        line_no = source.count("\n", 0, match.start()) + 1
        diagnostics.append(
            Diagnostic(
                severity="error",
                file=file,
                line=line_no,
                column=None,
                code="C4",
                message=(
                    "inline `sync` section is not allowed in concept files - "
                    "move it to a top-level `.sync` file"
                ),
            )
        )
    return diagnostics
```

- [ ] **Step 6.4: Re-export from the package**

Edit `src/concept_lang/validate/__init__.py` to add the new rule:

```python
from concept_lang.validate.concept_rules import (
    rule_c1_state_independence,
    rule_c2_effects_independence,
    rule_c3_op_principle_independence,
    rule_c4_no_inline_sync,
)
from concept_lang.validate.diagnostic import Diagnostic

__all__ = [
    "Diagnostic",
    "rule_c1_state_independence",
    "rule_c2_effects_independence",
    "rule_c3_op_principle_independence",
    "rule_c4_no_inline_sync",
]
```

- [ ] **Step 6.5: Create the C4 negative fixture**

Create `tests/fixtures/negative/C4_concept_has_sync_section.concept`:

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

  sync
    when inc then log
```

Create `tests/fixtures/negative/C4_concept_has_sync_section.expected.json`:

```json
{
  "diagnostics": [
    {
      "code": "C4",
      "severity": "error",
      "line": null
    }
  ]
}
```

Note: the matching sweep test (Task 19) compares codes and severities but leaves `line` untouched; we mark `line: null` in the expected file to signal "any line is fine."

- [ ] **Step 6.6: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 15 passed.

- [ ] **Step 6.7: Commit**

```bash
git add src/concept_lang/validate/concept_rules.py src/concept_lang/validate/__init__.py tests/fixtures/negative/C4_concept_has_sync_section.concept tests/fixtures/negative/C4_concept_has_sync_section.expected.json tests/test_validate.py
git commit -m "feat(validate): rule C4 - no inline sync sections in concepts"
```

---

## Task 7: Rule C5 - concept has a non-empty purpose

**Rule:** Every concept has a non-empty `purpose`.

**Files:**
- Modify: `src/concept_lang/validate/concept_rules.py`
- Modify: `src/concept_lang/validate/__init__.py`
- Create: `tests/fixtures/negative/C5_missing_purpose.concept`
- Create: `tests/fixtures/negative/C5_missing_purpose.expected.json`
- Modify: `tests/test_validate.py`

- [ ] **Step 7.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.validate import rule_c5_has_purpose


class TestRuleC5:
    def test_non_empty_purpose_is_allowed(self):
        src = """
concept Counter

  purpose
    count things

  actions
    inc [ ] => [ total: int ]

  operational principle
    after inc [ ] => [ total: 1 ]
"""
        ast = parse_concept_source(src)
        diags = rule_c5_has_purpose(ast)
        assert diags == []

    def test_whitespace_only_purpose_is_flagged(self):
        # We cannot easily construct this from the parser (the grammar
        # requires at least one non-whitespace purpose line), so we
        # hand-build the AST.
        ast = ConceptAST(
            name="Empty",
            params=[],
            purpose="   ",
            state=[],
            actions=[],
            operational_principle=OperationalPrinciple(steps=[]),
            source="",
        )
        diags = rule_c5_has_purpose(ast)
        assert len(diags) == 1
        assert diags[0].code == "C5"
        assert diags[0].severity == "error"

    def test_fully_empty_purpose_is_flagged(self):
        ast = ConceptAST(
            name="Empty",
            params=[],
            purpose="",
            state=[],
            actions=[],
            operational_principle=OperationalPrinciple(steps=[]),
            source="",
        )
        diags = rule_c5_has_purpose(ast)
        assert len(diags) == 1
        assert diags[0].code == "C5"
```

- [ ] **Step 7.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestRuleC5 -v`
Expected: `ImportError: cannot import name 'rule_c5_has_purpose'`.

- [ ] **Step 7.3: Add C5 to `concept_rules.py`**

Append to `src/concept_lang/validate/concept_rules.py`:

```python
def rule_c5_has_purpose(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C5: Every concept has a non-empty `purpose`.
    """
    if concept.purpose and concept.purpose.strip():
        return []
    return [
        Diagnostic(
            severity="error",
            file=file,
            line=None,
            column=None,
            code="C5",
            message=f"concept '{concept.name}' has an empty purpose",
        )
    ]
```

- [ ] **Step 7.4: Re-export from the package**

Edit `src/concept_lang/validate/__init__.py` to add the new rule:

```python
from concept_lang.validate.concept_rules import (
    rule_c1_state_independence,
    rule_c2_effects_independence,
    rule_c3_op_principle_independence,
    rule_c4_no_inline_sync,
    rule_c5_has_purpose,
)
from concept_lang.validate.diagnostic import Diagnostic

__all__ = [
    "Diagnostic",
    "rule_c1_state_independence",
    "rule_c2_effects_independence",
    "rule_c3_op_principle_independence",
    "rule_c4_no_inline_sync",
    "rule_c5_has_purpose",
]
```

- [ ] **Step 7.5: Create the C5 negative fixture**

C5 is tricky at the file level: the grammar requires a non-whitespace purpose body, so a genuinely empty-purpose file is not parseable. The rule itself is covered by the hand-built AST tests above. To keep the negative fixture directory structurally complete (and to satisfy the sweep test's "every rule has a fixture" check in Task 19), we ship a **minimal parse-clean** fixture whose `expected.json` declares zero diagnostics. The sweep test (Task 19) has a special case for C5 that asserts it parses without errors.

Create `tests/fixtures/negative/C5_missing_purpose.concept`:

```
concept Empty

  purpose
    placeholder purpose text

  actions
    noop [ ] => [ ok: boolean ]

  operational principle
    after noop [ ] => [ ok: true ]
```

Create `tests/fixtures/negative/C5_missing_purpose.expected.json`:

```json
{
  "diagnostics": []
}
```

The expected `"diagnostics": []` means: "this fixture should produce no error-level diagnostics." Task 19's sweep test has an explicit `test_c5_fixture_parses_clean_even_though_listed` assertion that documents why C5 lives here as a no-error fixture.

- [ ] **Step 7.6: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 18 passed.

- [ ] **Step 7.7: Commit**

```bash
git add src/concept_lang/validate/concept_rules.py src/concept_lang/validate/__init__.py tests/fixtures/negative/C5_missing_purpose.concept tests/fixtures/negative/C5_missing_purpose.expected.json tests/test_validate.py
git commit -m "feat(validate): rule C5 - concept has non-empty purpose"
```

---

## Task 8: Rule C6 - concept has at least one action

**Rule:** Every concept has at least one action.

**Files:**
- Modify: `src/concept_lang/validate/concept_rules.py`
- Modify: `src/concept_lang/validate/__init__.py`
- Create: `tests/fixtures/negative/C6_no_actions.concept`
- Create: `tests/fixtures/negative/C6_no_actions.expected.json`
- Modify: `tests/test_validate.py`

- [ ] **Step 8.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.validate import rule_c6_has_actions


class TestRuleC6:
    def test_one_action_is_allowed(self):
        ast = ConceptAST(
            name="Counter",
            params=[],
            purpose="count things",
            state=[],
            actions=[
                Action(
                    name="inc",
                    cases=[
                        ActionCase(
                            inputs=[],
                            outputs=[TypedName(name="total", type_expr="int")],
                        )
                    ],
                )
            ],
            operational_principle=OperationalPrinciple(steps=[]),
            source="",
        )
        assert rule_c6_has_actions(ast) == []

    def test_zero_actions_is_flagged(self):
        ast = ConceptAST(
            name="Pointless",
            params=[],
            purpose="do nothing",
            state=[],
            actions=[],
            operational_principle=OperationalPrinciple(steps=[]),
            source="",
        )
        diags = rule_c6_has_actions(ast)
        assert len(diags) == 1
        assert diags[0].code == "C6"
        assert diags[0].severity == "error"
```

- [ ] **Step 8.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestRuleC6 -v`
Expected: `ImportError: cannot import name 'rule_c6_has_actions'`.

- [ ] **Step 8.3: Add C6 to `concept_rules.py`**

Append to `src/concept_lang/validate/concept_rules.py`:

```python
def rule_c6_has_actions(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C6: Every concept has at least one action.
    """
    if concept.actions:
        return []
    return [
        Diagnostic(
            severity="error",
            file=file,
            line=None,
            column=None,
            code="C6",
            message=f"concept '{concept.name}' has no actions",
        )
    ]
```

- [ ] **Step 8.4: Re-export from the package**

Edit `src/concept_lang/validate/__init__.py` to add the new rule:

```python
from concept_lang.validate.concept_rules import (
    rule_c1_state_independence,
    rule_c2_effects_independence,
    rule_c3_op_principle_independence,
    rule_c4_no_inline_sync,
    rule_c5_has_purpose,
    rule_c6_has_actions,
)
from concept_lang.validate.diagnostic import Diagnostic

__all__ = [
    "Diagnostic",
    "rule_c1_state_independence",
    "rule_c2_effects_independence",
    "rule_c3_op_principle_independence",
    "rule_c4_no_inline_sync",
    "rule_c5_has_purpose",
    "rule_c6_has_actions",
]
```

- [ ] **Step 8.5: Create the C6 negative fixture**

Create `tests/fixtures/negative/C6_no_actions.concept`:

```
concept Pointless

  purpose
    do nothing

  operational principle
    after inc [ ] => [ total: 1 ]
```

Note: this fixture will also trigger C3 (operational principle references `inc`, which is not a declared action). The expected file lists the codes that must fire; cascading diagnostics are fine because the sweep test (Task 19) uses subset matching.

Create `tests/fixtures/negative/C6_no_actions.expected.json`:

```json
{
  "diagnostics": [
    {
      "code": "C3",
      "severity": "error",
      "line": null
    },
    {
      "code": "C6",
      "severity": "error",
      "line": null
    }
  ]
}
```

- [ ] **Step 8.6: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 20 passed.

- [ ] **Step 8.7: Commit**

```bash
git add src/concept_lang/validate/concept_rules.py src/concept_lang/validate/__init__.py tests/fixtures/negative/C6_no_actions.concept tests/fixtures/negative/C6_no_actions.expected.json tests/test_validate.py
git commit -m "feat(validate): rule C6 - concept has at least one action"
```

---

## Task 9: Rule C7 - every action has at least one non-error case

**Rule:** Every action has at least one case with a non-error output. We define an "error case" as any `ActionCase` whose outputs contain a field named `error` (matching the paper's convention).

**Files:**
- Modify: `src/concept_lang/validate/concept_rules.py`
- Modify: `src/concept_lang/validate/__init__.py`
- Create: `tests/fixtures/negative/C7_only_error_cases.concept`
- Create: `tests/fixtures/negative/C7_only_error_cases.expected.json`
- Modify: `tests/test_validate.py`

- [ ] **Step 9.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.validate import rule_c7_action_has_success_case


class TestRuleC7:
    def test_success_and_error_is_allowed(self):
        src = """
concept Password [U]

  purpose
    store credentials

  state
    password: U -> string

  actions
    set [ user: U ; password: string ] => [ user: U ]
    set [ user: U ; password: string ] => [ error: string ]

  operational principle
    after set [ user: x ; password: "secret" ] => [ user: x ]
"""
        ast = parse_concept_source(src)
        diags = rule_c7_action_has_success_case(ast)
        assert diags == []

    def test_only_error_case_is_flagged(self):
        src = """
concept Password [U]

  purpose
    store credentials

  actions
    set [ user: U ; password: string ] => [ error: string ]

  operational principle
    after set [ user: x ; password: "secret" ] => [ error: "nope" ]
"""
        ast = parse_concept_source(src)
        diags = rule_c7_action_has_success_case(ast)
        assert len(diags) == 1
        assert diags[0].code == "C7"
        assert "set" in diags[0].message
```

- [ ] **Step 9.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestRuleC7 -v`
Expected: `ImportError: cannot import name 'rule_c7_action_has_success_case'`.

- [ ] **Step 9.3: Add C7 to `concept_rules.py`**

Append to `src/concept_lang/validate/concept_rules.py`:

```python
def _is_error_case(case: ActionCase) -> bool:
    """
    An action case is considered an "error case" if any of its output
    fields is literally named `error`. This matches the paper convention
    shown on Password.set and User.register.
    """
    return any(out.name == "error" for out in case.outputs)


def rule_c7_action_has_success_case(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C7: Every action has at least one case with a non-error output.
    """
    diagnostics: list[Diagnostic] = []
    for action in concept.actions:
        if any(not _is_error_case(case) for case in action.cases):
            continue
        diagnostics.append(
            Diagnostic(
                severity="error",
                file=file,
                line=None,
                column=None,
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

- [ ] **Step 9.4: Re-export from the package**

Edit `src/concept_lang/validate/__init__.py` to add the new rule:

```python
from concept_lang.validate.concept_rules import (
    rule_c1_state_independence,
    rule_c2_effects_independence,
    rule_c3_op_principle_independence,
    rule_c4_no_inline_sync,
    rule_c5_has_purpose,
    rule_c6_has_actions,
    rule_c7_action_has_success_case,
)
from concept_lang.validate.diagnostic import Diagnostic

__all__ = [
    "Diagnostic",
    "rule_c1_state_independence",
    "rule_c2_effects_independence",
    "rule_c3_op_principle_independence",
    "rule_c4_no_inline_sync",
    "rule_c5_has_purpose",
    "rule_c6_has_actions",
    "rule_c7_action_has_success_case",
]
```

- [ ] **Step 9.5: Create the C7 negative fixture**

Create `tests/fixtures/negative/C7_only_error_cases.concept`:

```
concept Password [U]

  purpose
    store credentials

  actions
    set [ user: U ; password: string ] => [ error: string ]

  operational principle
    after set [ user: x ; password: "secret" ] => [ error: "nope" ]
```

Create `tests/fixtures/negative/C7_only_error_cases.expected.json`:

```json
{
  "diagnostics": [
    {
      "code": "C7",
      "severity": "error",
      "line": null
    }
  ]
}
```

- [ ] **Step 9.6: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 22 passed.

- [ ] **Step 9.7: Commit**

```bash
git add src/concept_lang/validate/concept_rules.py src/concept_lang/validate/__init__.py tests/fixtures/negative/C7_only_error_cases.concept tests/fixtures/negative/C7_only_error_cases.expected.json tests/test_validate.py
git commit -m "feat(validate): rule C7 - every action has a non-error case"
```

---

## Task 10: Rule C9 - operational principle is present and non-empty

**Rule:** `operational principle` is required and has at least one step.

**Note:** `C8` (every state field referenced by at least one effect) is deferred per the spec. We jump from C7 to C9.

**Files:**
- Modify: `src/concept_lang/validate/concept_rules.py`
- Modify: `src/concept_lang/validate/__init__.py`
- Create: `tests/fixtures/negative/C9_missing_op_principle.concept`
- Create: `tests/fixtures/negative/C9_missing_op_principle.expected.json`
- Modify: `tests/test_validate.py`

- [ ] **Step 10.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.validate import rule_c9_has_op_principle


class TestRuleC9:
    def test_non_empty_op_principle_is_allowed(self):
        src = """
concept Counter

  purpose
    count things

  actions
    inc [ ] => [ total: int ]

  operational principle
    after inc [ ] => [ total: 1 ]
"""
        ast = parse_concept_source(src)
        assert rule_c9_has_op_principle(ast) == []

    def test_empty_op_principle_is_flagged(self):
        ast = ConceptAST(
            name="Counter",
            params=[],
            purpose="count things",
            state=[],
            actions=[],
            operational_principle=OperationalPrinciple(steps=[]),
            source="",
        )
        diags = rule_c9_has_op_principle(ast)
        assert len(diags) == 1
        assert diags[0].code == "C9"
        assert diags[0].severity == "error"
```

- [ ] **Step 10.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestRuleC9 -v`
Expected: `ImportError: cannot import name 'rule_c9_has_op_principle'`.

- [ ] **Step 10.3: Add C9 to `concept_rules.py`**

Append to `src/concept_lang/validate/concept_rules.py`:

```python
def rule_c9_has_op_principle(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C9: Operational principle is required and has at least one step.
    """
    if concept.operational_principle.steps:
        return []
    return [
        Diagnostic(
            severity="error",
            file=file,
            line=None,
            column=None,
            code="C9",
            message=(
                f"concept '{concept.name}' has no operational principle steps "
                f"- describe the archetypal scenario using the concept's own "
                f"actions"
            ),
        )
    ]
```

- [ ] **Step 10.4: Re-export from the package**

Edit `src/concept_lang/validate/__init__.py` to add the new rule:

```python
from concept_lang.validate.concept_rules import (
    rule_c1_state_independence,
    rule_c2_effects_independence,
    rule_c3_op_principle_independence,
    rule_c4_no_inline_sync,
    rule_c5_has_purpose,
    rule_c6_has_actions,
    rule_c7_action_has_success_case,
    rule_c9_has_op_principle,
)
from concept_lang.validate.diagnostic import Diagnostic

__all__ = [
    "Diagnostic",
    "rule_c1_state_independence",
    "rule_c2_effects_independence",
    "rule_c3_op_principle_independence",
    "rule_c4_no_inline_sync",
    "rule_c5_has_purpose",
    "rule_c6_has_actions",
    "rule_c7_action_has_success_case",
    "rule_c9_has_op_principle",
]
```

- [ ] **Step 10.5: Create the C9 negative fixture**

The grammar's `op_section` rule is optional on `concept_def`, so a concept with no operational principle at all parses cleanly (with an empty `OperationalPrinciple(steps=[])`). This is exactly the C9 failure condition.

Create `tests/fixtures/negative/C9_missing_op_principle.concept`:

```
concept Counter

  purpose
    count things

  state
    total: int

  actions
    inc [ ] => [ total: int ]
```

Create `tests/fixtures/negative/C9_missing_op_principle.expected.json`:

```json
{
  "diagnostics": [
    {
      "code": "C9",
      "severity": "error",
      "line": null
    }
  ]
}
```

- [ ] **Step 10.6: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 24 passed.

- [ ] **Step 10.7: Commit**

```bash
git add src/concept_lang/validate/concept_rules.py src/concept_lang/validate/__init__.py tests/fixtures/negative/C9_missing_op_principle.concept tests/fixtures/negative/C9_missing_op_principle.expected.json tests/test_validate.py
git commit -m "feat(validate): rule C9 - operational principle is required"
```

---

## Task 11: Rule S1 - sync action references resolve to known concepts + actions

**Rule:** Every `Concept/action` referenced in a sync's `when`/`then` resolves to an actual concept + action in the workspace.

**Files:**
- Create: `src/concept_lang/validate/sync_rules.py`
- Modify: `src/concept_lang/validate/__init__.py`
- Create: `tests/fixtures/negative/S1_sync_references_unknown_concept.sync`
- Create: `tests/fixtures/negative/S1_sync_references_unknown_concept.expected.json`
- Modify: `tests/test_validate.py`

- [ ] **Step 11.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.ast import SyncAST
from concept_lang.parse import parse_sync_source
from concept_lang.validate import rule_s1_references_resolve
from concept_lang.validate.helpers import WorkspaceIndex


def _workspace_with_counter_and_log() -> Workspace:
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
                        inputs=[TypedName(name="amount", type_expr="int")],
                        outputs=[TypedName(name="total", type_expr="int")],
                    )
                ],
            )
        ],
        operational_principle=OperationalPrinciple(steps=[]),
        source="",
    )
    log = ConceptAST(
        name="Log",
        params=[],
        purpose="record events",
        state=[],
        actions=[
            Action(
                name="append",
                cases=[
                    ActionCase(
                        inputs=[TypedName(name="event", type_expr="string")],
                        outputs=[TypedName(name="entry", type_expr="string")],
                    )
                ],
            )
        ],
        operational_principle=OperationalPrinciple(steps=[]),
        source="",
    )
    return Workspace(concepts={"Counter": counter, "Log": log}, syncs={})


class TestRuleS1:
    def test_known_refs_are_allowed(self):
        ws = _workspace_with_counter_and_log()
        idx = WorkspaceIndex.build(ws)
        sync = parse_sync_source(
            """
sync LogEveryInc

  when
    Counter/inc: [ amount: ?amount ] => [ total: ?total ]
  then
    Log/append: [ event: ?total ]
"""
        )
        diags = rule_s1_references_resolve(sync, idx)
        assert diags == []

    def test_unknown_concept_is_flagged(self):
        ws = _workspace_with_counter_and_log()
        idx = WorkspaceIndex.build(ws)
        sync = parse_sync_source(
            """
sync BadSync

  when
    Counter/inc: [ amount: ?amount ] => [ total: ?total ]
  then
    Mailer/send: [ body: ?total ]
"""
        )
        diags = rule_s1_references_resolve(sync, idx)
        codes = [d.code for d in diags]
        assert codes.count("S1") == 1
        assert "Mailer" in diags[0].message

    def test_unknown_action_on_known_concept_is_flagged(self):
        ws = _workspace_with_counter_and_log()
        idx = WorkspaceIndex.build(ws)
        sync = parse_sync_source(
            """
sync BadSync

  when
    Counter/decrement: [ amount: ?amount ] => [ total: ?total ]
  then
    Log/append: [ event: ?total ]
"""
        )
        diags = rule_s1_references_resolve(sync, idx)
        assert len(diags) == 1
        assert diags[0].code == "S1"
        assert "Counter" in diags[0].message
        assert "decrement" in diags[0].message
```

- [ ] **Step 11.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestRuleS1 -v`
Expected: `ImportError: cannot import name 'rule_s1_references_resolve'`.

- [ ] **Step 11.3: Create the sync_rules module with S1**

Create `src/concept_lang/validate/sync_rules.py`:

```python
"""
Validator rules for a single `SyncAST` (paper rules S1..S5).

Each rule is a pure function that takes the sync AST plus a
`WorkspaceIndex` (for cross-reference lookups) and returns a list of
`Diagnostic` records. Line/column information is best-effort: the P1
parser does not yet attach source positions to AST nodes, so most
diagnostics produced here use `line=None`.
"""

import re
from pathlib import Path

from concept_lang.ast import ActionPattern, SyncAST
from concept_lang.validate.diagnostic import Diagnostic
from concept_lang.validate.helpers import WorkspaceIndex

_VAR_RE = re.compile(r"\?[A-Za-z_][A-Za-z0-9_]*")


def _iter_patterns(sync: SyncAST) -> list[tuple[str, ActionPattern]]:
    """Yield (section_label, pattern) pairs for all action patterns in the sync."""
    out: list[tuple[str, ActionPattern]] = []
    for p in sync.when:
        out.append(("when", p))
    for p in sync.then:
        out.append(("then", p))
    return out


def rule_s1_references_resolve(
    sync: SyncAST,
    index: WorkspaceIndex,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    S1: Every `Concept/action` in `when`/`then` resolves to a known
    concept + action in the workspace.
    """
    diagnostics: list[Diagnostic] = []
    for section, pattern in _iter_patterns(sync):
        if pattern.concept not in index.concept_names:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    file=file,
                    line=None,
                    column=None,
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
                    line=None,
                    column=None,
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

- [ ] **Step 11.4: Re-export from the package**

Edit `src/concept_lang/validate/__init__.py` to add the new rule:

```python
from concept_lang.validate.concept_rules import (
    rule_c1_state_independence,
    rule_c2_effects_independence,
    rule_c3_op_principle_independence,
    rule_c4_no_inline_sync,
    rule_c5_has_purpose,
    rule_c6_has_actions,
    rule_c7_action_has_success_case,
    rule_c9_has_op_principle,
)
from concept_lang.validate.diagnostic import Diagnostic
from concept_lang.validate.sync_rules import rule_s1_references_resolve

__all__ = [
    "Diagnostic",
    "rule_c1_state_independence",
    "rule_c2_effects_independence",
    "rule_c3_op_principle_independence",
    "rule_c4_no_inline_sync",
    "rule_c5_has_purpose",
    "rule_c6_has_actions",
    "rule_c7_action_has_success_case",
    "rule_c9_has_op_principle",
    "rule_s1_references_resolve",
]
```

- [ ] **Step 11.5: Create the S1 negative fixture**

Create `tests/fixtures/negative/S1_sync_references_unknown_concept.sync`:

```
sync BadSync

  when
    Counter/inc: [ amount: ?amount ] => [ total: ?total ]
  then
    Mailer/send: [ body: ?total ]
```

Create `tests/fixtures/negative/S1_sync_references_unknown_concept.expected.json`:

```json
{
  "diagnostics": [
    {
      "code": "S1",
      "severity": "error",
      "line": null
    }
  ]
}
```

- [ ] **Step 11.6: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 27 passed.

- [ ] **Step 11.7: Commit**

```bash
git add src/concept_lang/validate/sync_rules.py src/concept_lang/validate/__init__.py tests/fixtures/negative/S1_sync_references_unknown_concept.sync tests/fixtures/negative/S1_sync_references_unknown_concept.expected.json tests/test_validate.py
git commit -m "feat(validate): rule S1 - sync references resolve"
```

---

## Task 12: Rule S2 - pattern field names exist in action signatures

**Rule:** For every action pattern in a sync's `when`/`then`, every named input or output field must exist in at least one case of that action's declared signature. An empty pattern list `[ ]` is always allowed (it means "match anything").

**Files:**
- Modify: `src/concept_lang/validate/sync_rules.py`
- Modify: `src/concept_lang/validate/__init__.py`
- Create: `tests/fixtures/negative/S2_pattern_field_not_in_action.sync`
- Create: `tests/fixtures/negative/S2_pattern_field_not_in_action.expected.json`
- Modify: `tests/test_validate.py`

- [ ] **Step 12.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.validate import rule_s2_pattern_fields_exist


class TestRuleS2:
    def test_known_fields_are_allowed(self):
        ws = _workspace_with_counter_and_log()
        idx = WorkspaceIndex.build(ws)
        sync = parse_sync_source(
            """
sync LogEveryInc

  when
    Counter/inc: [ amount: ?amount ] => [ total: ?total ]
  then
    Log/append: [ event: ?total ]
"""
        )
        diags = rule_s2_pattern_fields_exist(sync, idx)
        assert diags == []

    def test_unknown_input_field_is_flagged(self):
        ws = _workspace_with_counter_and_log()
        idx = WorkspaceIndex.build(ws)
        sync = parse_sync_source(
            """
sync BadSync

  when
    Counter/inc: [ bogus: ?bogus ] => [ total: ?total ]
  then
    Log/append: [ event: ?total ]
"""
        )
        diags = rule_s2_pattern_fields_exist(sync, idx)
        assert len(diags) == 1
        assert diags[0].code == "S2"
        assert "bogus" in diags[0].message

    def test_empty_pattern_always_allowed(self):
        ws = _workspace_with_counter_and_log()
        idx = WorkspaceIndex.build(ws)
        sync = parse_sync_source(
            """
sync Any

  when
    Counter/inc: [ ] => [ ]
  then
    Log/append: [ event: ?any ]
"""
        )
        diags = rule_s2_pattern_fields_exist(sync, idx)
        assert diags == []

    def test_unknown_action_is_not_reported_by_s2(self):
        # S1 reports unknown actions; S2 stays silent on them to avoid
        # spamming the user with cascading diagnostics.
        ws = _workspace_with_counter_and_log()
        idx = WorkspaceIndex.build(ws)
        sync = parse_sync_source(
            """
sync BadSync

  when
    Counter/unknown: [ bogus: ?x ] => [ ]
  then
    Log/append: [ event: ?x ]
"""
        )
        diags = rule_s2_pattern_fields_exist(sync, idx)
        assert diags == []
```

- [ ] **Step 12.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestRuleS2 -v`
Expected: `ImportError: cannot import name 'rule_s2_pattern_fields_exist'`.

- [ ] **Step 12.3: Add S2 to `sync_rules.py`**

Append to `src/concept_lang/validate/sync_rules.py`:

```python
def rule_s2_pattern_fields_exist(
    sync: SyncAST,
    index: WorkspaceIndex,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    S2: Input/output pattern field names referenced in an action pattern
    must exist in at least one case of that action's signature.

    An unknown action is silently ignored here - S1 handles that.
    An empty pattern list matches anything, so empty patterns never fire.
    """
    diagnostics: list[Diagnostic] = []
    for section, pattern in _iter_patterns(sync):
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
                    line=None,
                    column=None,
                    code="S2",
                    message=(
                        f"sync '{sync.name}' {section} pattern "
                        f"'{pattern.concept}/{pattern.action}' references "
                        f"unknown field '{pf.name}' (declared fields: "
                        f"{sorted(allowed)!r})"
                    ),
                )
            )
    return diagnostics
```

- [ ] **Step 12.4: Re-export from the package**

Edit `src/concept_lang/validate/__init__.py` to add `rule_s2_pattern_fields_exist`:

```python
from concept_lang.validate.sync_rules import (
    rule_s1_references_resolve,
    rule_s2_pattern_fields_exist,
)
```

Add `rule_s2_pattern_fields_exist` to `__all__` as well.

- [ ] **Step 12.5: Create the S2 negative fixture**

Create `tests/fixtures/negative/S2_pattern_field_not_in_action.sync`:

```
sync BadSync

  when
    Counter/inc: [ bogus: ?bogus ] => [ total: ?total ]
  then
    Log/append: [ event: ?total ]
```

Create `tests/fixtures/negative/S2_pattern_field_not_in_action.expected.json`:

```json
{
  "diagnostics": [
    {
      "code": "S2",
      "severity": "error",
      "line": null
    }
  ]
}
```

- [ ] **Step 12.6: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 31 passed.

- [ ] **Step 12.7: Commit**

```bash
git add src/concept_lang/validate/sync_rules.py src/concept_lang/validate/__init__.py tests/fixtures/negative/S2_pattern_field_not_in_action.sync tests/fixtures/negative/S2_pattern_field_not_in_action.expected.json tests/test_validate.py
git commit -m "feat(validate): rule S2 - sync pattern fields match action signatures"
```

---

## Task 13: Rule S3 - every `?var` used in `then` is bound in `when` or `where`

**Rule:** Every `?var` used in a sync's `then` clause must be bound either by a `when` pattern (input or output slot) or by the `where` clause (a `bind` or a state query triple).

**Files:**
- Modify: `src/concept_lang/validate/sync_rules.py`
- Modify: `src/concept_lang/validate/__init__.py`
- Create: `tests/fixtures/negative/S3_then_var_not_bound.sync`
- Create: `tests/fixtures/negative/S3_then_var_not_bound.expected.json`
- Modify: `tests/test_validate.py`

- [ ] **Step 13.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.validate import rule_s3_then_vars_bound


class TestRuleS3:
    def _index(self) -> WorkspaceIndex:
        return WorkspaceIndex.build(_workspace_with_counter_and_log())

    def test_vars_bound_in_when_are_allowed(self):
        idx = self._index()
        sync = parse_sync_source(
            """
sync LogEveryInc

  when
    Counter/inc: [ amount: ?amount ] => [ total: ?total ]
  then
    Log/append: [ event: ?total ]
"""
        )
        assert rule_s3_then_vars_bound(sync, idx) == []

    def test_var_bound_in_where_bind_is_allowed(self):
        idx = self._index()
        sync = parse_sync_source(
            """
sync BindThenUse

  when
    Counter/inc: [ ] => [ ]
  where
    bind (uuid() as ?entry)
  then
    Log/append: [ event: ?entry ]
"""
        )
        assert rule_s3_then_vars_bound(sync, idx) == []

    def test_unbound_var_in_then_is_flagged(self):
        idx = self._index()
        sync = parse_sync_source(
            """
sync Bad

  when
    Counter/inc: [ ] => [ total: ?total ]
  then
    Log/append: [ event: ?mystery ]
"""
        )
        diags = rule_s3_then_vars_bound(sync, idx)
        assert len(diags) == 1
        assert diags[0].code == "S3"
        assert "?mystery" in diags[0].message
```

- [ ] **Step 13.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestRuleS3 -v`
Expected: `ImportError: cannot import name 'rule_s3_then_vars_bound'`.

- [ ] **Step 13.3: Add the shared binding-collector helpers and S3**

Append to `src/concept_lang/validate/sync_rules.py`:

```python
def _vars_in_pattern(pattern: ActionPattern) -> set[str]:
    """Return the set of `?var` tokens that appear in an action pattern."""
    seen: set[str] = set()
    for pf in list(pattern.input_pattern) + list(pattern.output_pattern):
        if pf.kind == "var":
            seen.add(pf.value)
    return seen


def _bindings_from_when(sync: SyncAST) -> set[str]:
    """Variables bound by any `when` pattern (both inputs and outputs)."""
    bound: set[str] = set()
    for pattern in sync.when:
        bound |= _vars_in_pattern(pattern)
    return bound


def _bindings_from_where(sync: SyncAST) -> set[str]:
    """
    Variables introduced by the `where` clause:
      - each `bind (expr as ?var)` introduces `?var`
      - each state query triple binds its subject + object `?var` tokens
    """
    bound: set[str] = set()
    if sync.where is None:
        return bound
    for bind in sync.where.binds:
        bound.add(bind.variable)
    for query in sync.where.queries:
        for triple in query.triples:
            if triple.subject.startswith("?"):
                bound.add(triple.subject)
            if triple.object.startswith("?"):
                bound.add(triple.object)
    return bound


def rule_s3_then_vars_bound(
    sync: SyncAST,
    index: WorkspaceIndex,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    S3: Every `?var` used in `then` is bound in `when` or `where`.

    The `index` argument is unused for this rule - it is kept in the
    signature so every sync rule has a uniform shape that
    `validate_workspace` can dispatch uniformly.
    """
    _ = index  # unused; kept for signature uniformity
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
                    line=None,
                    column=None,
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

- [ ] **Step 13.4: Re-export from the package**

Edit `src/concept_lang/validate/__init__.py` to add `rule_s3_then_vars_bound`:

```python
from concept_lang.validate.sync_rules import (
    rule_s1_references_resolve,
    rule_s2_pattern_fields_exist,
    rule_s3_then_vars_bound,
)
```

Add `rule_s3_then_vars_bound` to `__all__`.

- [ ] **Step 13.5: Create the S3 negative fixture**

Create `tests/fixtures/negative/S3_then_var_not_bound.sync`:

```
sync Bad

  when
    Counter/inc: [ ] => [ total: ?total ]
  then
    Log/append: [ event: ?mystery ]
```

Create `tests/fixtures/negative/S3_then_var_not_bound.expected.json`:

```json
{
  "diagnostics": [
    {
      "code": "S3",
      "severity": "error",
      "line": null
    }
  ]
}
```

- [ ] **Step 13.6: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 34 passed.

- [ ] **Step 13.7: Commit**

```bash
git add src/concept_lang/validate/sync_rules.py src/concept_lang/validate/__init__.py tests/fixtures/negative/S3_then_var_not_bound.sync tests/fixtures/negative/S3_then_var_not_bound.expected.json tests/test_validate.py
git commit -m "feat(validate): rule S3 - then variables must be bound"
```

---

## Task 14: Rule S4 - every `?var` used in `where` state queries is bound

**Rule:** Every `?var` used as the **subject** of a `where` state query triple is bound by `when`, by an earlier `bind` in the same `where`, or by an earlier query in the same `where`. Object variables are not checked here - the paper treats them as introduced by the query itself (SPARQL pattern matching).

**Files:**
- Modify: `src/concept_lang/validate/sync_rules.py`
- Modify: `src/concept_lang/validate/__init__.py`
- Create: `tests/fixtures/negative/S4_where_var_not_bound.sync`
- Create: `tests/fixtures/negative/S4_where_var_not_bound.expected.json`
- Modify: `tests/test_validate.py`

- [ ] **Step 14.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.validate import rule_s4_where_vars_bound


class TestRuleS4:
    def _index(self) -> WorkspaceIndex:
        return WorkspaceIndex.build(_workspace_with_counter_and_log())

    def test_subject_bound_in_when_is_allowed(self):
        idx = self._index()
        sync = parse_sync_source(
            """
sync Ok

  when
    Counter/inc: [ ] => [ total: ?total ]
  where
    Counter: { ?total amount: ?amount }
  then
    Log/append: [ event: ?amount ]
"""
        )
        assert rule_s4_where_vars_bound(sync, idx) == []

    def test_subject_unbound_is_flagged(self):
        idx = self._index()
        sync = parse_sync_source(
            """
sync Bad

  when
    Counter/inc: [ ] => [ ]
  where
    Counter: { ?mystery amount: ?amount }
  then
    Log/append: [ event: ?amount ]
"""
        )
        diags = rule_s4_where_vars_bound(sync, idx)
        assert len(diags) == 1
        assert diags[0].code == "S4"
        assert "?mystery" in diags[0].message

    def test_subject_bound_by_earlier_bind_is_allowed(self):
        idx = self._index()
        sync = parse_sync_source(
            """
sync Ok

  when
    Counter/inc: [ ] => [ ]
  where
    bind (uuid() as ?entry)
    Counter: { ?entry amount: ?amount }
  then
    Log/append: [ event: ?amount ]
"""
        )
        assert rule_s4_where_vars_bound(sync, idx) == []
```

- [ ] **Step 14.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestRuleS4 -v`
Expected: `ImportError: cannot import name 'rule_s4_where_vars_bound'`.

- [ ] **Step 14.3: Add S4 to `sync_rules.py`**

Append to `src/concept_lang/validate/sync_rules.py`:

```python
def rule_s4_where_vars_bound(
    sync: SyncAST,
    index: WorkspaceIndex,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    S4: Every `?var` used as the **subject** of a `where` state query
    triple must be bound by:
      - a `when` pattern,
      - an earlier `bind` in the same `where`,
      - or an earlier query in the same `where`.

    Object variables are not checked here - the paper treats them as
    introduced by the query itself (SPARQL pattern matching).
    """
    _ = index
    if sync.where is None:
        return []
    diagnostics: list[Diagnostic] = []
    bound: set[str] = _bindings_from_when(sync)
    for bind in sync.where.binds:
        bound.add(bind.variable)
    # Walk queries in source order, accumulating bindings as we go.
    for query in sync.where.queries:
        for triple in query.triples:
            if triple.subject.startswith("?") and triple.subject not in bound:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        file=file,
                        line=None,
                        column=None,
                        code="S4",
                        message=(
                            f"sync '{sync.name}' where clause state query on "
                            f"concept '{query.concept}' uses unbound subject "
                            f"'{triple.subject}' (bind it in `when` or in an "
                            f"earlier `where` item)"
                        ),
                    )
                )
            # After inspecting this triple, both its subject and object are
            # considered bound for subsequent triples.
            if triple.subject.startswith("?"):
                bound.add(triple.subject)
            if triple.object.startswith("?"):
                bound.add(triple.object)
    return diagnostics
```

- [ ] **Step 14.4: Re-export from the package**

Edit `src/concept_lang/validate/__init__.py` to add `rule_s4_where_vars_bound`:

```python
from concept_lang.validate.sync_rules import (
    rule_s1_references_resolve,
    rule_s2_pattern_fields_exist,
    rule_s3_then_vars_bound,
    rule_s4_where_vars_bound,
)
```

Add `rule_s4_where_vars_bound` to `__all__`.

- [ ] **Step 14.5: Create the S4 negative fixture**

Create `tests/fixtures/negative/S4_where_var_not_bound.sync`:

```
sync Bad

  when
    Counter/inc: [ ] => [ ]
  where
    Counter: { ?mystery amount: ?amount }
  then
    Log/append: [ event: ?amount ]
```

Create `tests/fixtures/negative/S4_where_var_not_bound.expected.json`:

```json
{
  "diagnostics": [
    {
      "code": "S4",
      "severity": "error",
      "line": null
    }
  ]
}
```

- [ ] **Step 14.6: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 37 passed.

- [ ] **Step 14.7: Commit**

```bash
git add src/concept_lang/validate/sync_rules.py src/concept_lang/validate/__init__.py tests/fixtures/negative/S4_where_var_not_bound.sync tests/fixtures/negative/S4_where_var_not_bound.expected.json tests/test_validate.py
git commit -m "feat(validate): rule S4 - where state query subjects must be bound"
```

---

## Task 15: Rule S5 - warning if a sync references fewer than 2 distinct concepts

**Rule:** A sync should reference at least 2 distinct concepts across its `when`+`then`. If only one concept appears, emit a **warning** (not an error) - a single-concept sync is usually a sign that the rule belongs inside the concept rather than in a cross-cutting sync.

**Files:**
- Modify: `src/concept_lang/validate/sync_rules.py`
- Modify: `src/concept_lang/validate/__init__.py`
- Create: `tests/fixtures/negative/S5_sync_references_one_concept.sync`
- Create: `tests/fixtures/negative/S5_sync_references_one_concept.expected.json`
- Modify: `tests/test_validate.py`

- [ ] **Step 15.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.validate import rule_s5_multiple_concepts


class TestRuleS5:
    def _index(self) -> WorkspaceIndex:
        return WorkspaceIndex.build(_workspace_with_counter_and_log())

    def test_two_concepts_is_clean(self):
        idx = self._index()
        sync = parse_sync_source(
            """
sync LogEveryInc

  when
    Counter/inc: [ ] => [ total: ?total ]
  then
    Log/append: [ event: ?total ]
"""
        )
        assert rule_s5_multiple_concepts(sync, idx) == []

    def test_one_concept_is_warning(self):
        idx = self._index()
        sync = parse_sync_source(
            """
sync InternalOnly

  when
    Counter/inc: [ ] => [ total: ?total ]
  then
    Counter/inc: [ amount: ?total ]
"""
        )
        diags = rule_s5_multiple_concepts(sync, idx)
        assert len(diags) == 1
        assert diags[0].code == "S5"
        assert diags[0].severity == "warning"
```

- [ ] **Step 15.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestRuleS5 -v`
Expected: `ImportError: cannot import name 'rule_s5_multiple_concepts'`.

- [ ] **Step 15.3: Add S5 to `sync_rules.py`**

Append to `src/concept_lang/validate/sync_rules.py`:

```python
def rule_s5_multiple_concepts(
    sync: SyncAST,
    index: WorkspaceIndex,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    S5 (warning): A sync should reference at least 2 distinct concepts
    across its `when` and `then` clauses.
    """
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
            line=None,
            column=None,
            code="S5",
            message=(
                f"sync '{sync.name}' references only {len(concepts)} "
                f"concept(s) ({sorted(concepts)!r}) - single-concept syncs "
                f"are usually better expressed inside the concept itself"
            ),
        )
    ]
```

- [ ] **Step 15.4: Re-export from the package**

Edit `src/concept_lang/validate/__init__.py` to add `rule_s5_multiple_concepts`:

```python
from concept_lang.validate.sync_rules import (
    rule_s1_references_resolve,
    rule_s2_pattern_fields_exist,
    rule_s3_then_vars_bound,
    rule_s4_where_vars_bound,
    rule_s5_multiple_concepts,
)
```

Add `rule_s5_multiple_concepts` to `__all__`.

- [ ] **Step 15.5: Create the S5 negative fixture**

Create `tests/fixtures/negative/S5_sync_references_one_concept.sync`:

```
sync InternalOnly

  when
    Counter/inc: [ ] => [ total: ?total ]
  then
    Counter/inc: [ amount: ?total ]
```

Create `tests/fixtures/negative/S5_sync_references_one_concept.expected.json`:

```json
{
  "diagnostics": [
    {
      "code": "S5",
      "severity": "warning",
      "line": null
    }
  ]
}
```

- [ ] **Step 15.6: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 39 passed.

- [ ] **Step 15.7: Commit**

```bash
git add src/concept_lang/validate/sync_rules.py src/concept_lang/validate/__init__.py tests/fixtures/negative/S5_sync_references_one_concept.sync tests/fixtures/negative/S5_sync_references_one_concept.expected.json tests/test_validate.py
git commit -m "feat(validate): rule S5 - warning for single-concept syncs"
```

---

## Task 16: `validate_workspace` aggregator

**Files:**
- Create: `src/concept_lang/validate/workspace.py`
- Modify: `src/concept_lang/validate/__init__.py`
- Modify: `tests/test_validate.py`

- [ ] **Step 16.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.validate import validate_workspace


class TestValidateWorkspace:
    def test_clean_workspace_has_no_errors(self):
        ws = _workspace_with_counter_and_log()
        diags = validate_workspace(ws)
        errors = [d for d in diags if d.severity == "error"]
        assert errors == []

    def test_dirty_workspace_collects_all_concept_diagnostics(self):
        # A concept whose state references a foreign type and whose
        # operational principle is empty - expect C1 + C9.
        bad = ConceptAST(
            name="Bad",
            params=[],
            purpose="do bad things",
            state=[StateDecl(name="owner", type_expr="User")],
            actions=[
                Action(
                    name="noop",
                    cases=[
                        ActionCase(
                            inputs=[],
                            outputs=[TypedName(name="ok", type_expr="boolean")],
                        )
                    ],
                )
            ],
            operational_principle=OperationalPrinciple(steps=[]),
            source="",
        )
        ws = Workspace(concepts={"Bad": bad}, syncs={})
        diags = validate_workspace(ws)
        codes = {d.code for d in diags if d.severity == "error"}
        assert "C1" in codes
        assert "C9" in codes

    def test_collects_sync_diagnostics(self):
        ws = _workspace_with_counter_and_log()
        ws.syncs["Broken"] = parse_sync_source(
            """
sync Broken

  when
    Counter/inc: [ ] => [ ]
  then
    Nowhere/do: [ ]
"""
        )
        diags = validate_workspace(ws)
        codes = {d.code for d in diags if d.severity == "error"}
        assert "S1" in codes
```

- [ ] **Step 16.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestValidateWorkspace -v`
Expected: `ImportError: cannot import name 'validate_workspace'`.

- [ ] **Step 16.3: Create the workspace aggregator**

Create `src/concept_lang/validate/workspace.py`:

```python
"""
Workspace-level aggregator: runs every rule across every concept and
sync and returns the combined list of diagnostics. Also hosts the
single-file `validate_concept_file` and `validate_sync_file` wrappers
used by the MCP tool path.
"""

from pathlib import Path

from concept_lang.ast import ConceptAST, SyncAST, Workspace
from concept_lang.validate.concept_rules import (
    rule_c1_state_independence,
    rule_c2_effects_independence,
    rule_c3_op_principle_independence,
    rule_c4_no_inline_sync,
    rule_c5_has_purpose,
    rule_c6_has_actions,
    rule_c7_action_has_success_case,
    rule_c9_has_op_principle,
)
from concept_lang.validate.diagnostic import Diagnostic
from concept_lang.validate.helpers import WorkspaceIndex
from concept_lang.validate.sync_rules import (
    rule_s1_references_resolve,
    rule_s2_pattern_fields_exist,
    rule_s3_then_vars_bound,
    rule_s4_where_vars_bound,
    rule_s5_multiple_concepts,
)


def validate_workspace(
    workspace: Workspace,
    *,
    concept_files: dict[str, Path] | None = None,
    sync_files: dict[str, Path] | None = None,
) -> list[Diagnostic]:
    """
    Run every concept and sync rule against the given workspace.

    `concept_files` and `sync_files` optionally map the concept/sync name
    to the source file it came from so that emitted diagnostics carry a
    useful `file` path. They default to `None`, which is appropriate when
    the workspace was built in-memory (e.g. in unit tests).
    """
    concept_files = concept_files or {}
    sync_files = sync_files or {}

    index = WorkspaceIndex.build(workspace)
    diagnostics: list[Diagnostic] = []

    for name, concept in workspace.concepts.items():
        file = concept_files.get(name)
        diagnostics.extend(rule_c1_state_independence(concept, file=file))
        diagnostics.extend(rule_c2_effects_independence(concept, file=file))
        diagnostics.extend(rule_c3_op_principle_independence(concept, file=file))
        # C4 runs on the raw source, not the AST.
        diagnostics.extend(rule_c4_no_inline_sync(concept.source, file=file))
        diagnostics.extend(rule_c5_has_purpose(concept, file=file))
        diagnostics.extend(rule_c6_has_actions(concept, file=file))
        diagnostics.extend(rule_c7_action_has_success_case(concept, file=file))
        diagnostics.extend(rule_c9_has_op_principle(concept, file=file))

    for name, sync in workspace.syncs.items():
        file = sync_files.get(name)
        diagnostics.extend(rule_s1_references_resolve(sync, index, file=file))
        diagnostics.extend(rule_s2_pattern_fields_exist(sync, index, file=file))
        diagnostics.extend(rule_s3_then_vars_bound(sync, index, file=file))
        diagnostics.extend(rule_s4_where_vars_bound(sync, index, file=file))
        diagnostics.extend(rule_s5_multiple_concepts(sync, index, file=file))

    return diagnostics
```

- [ ] **Step 16.4: Re-export from the package**

Edit `src/concept_lang/validate/__init__.py` to add `validate_workspace`:

```python
from concept_lang.validate.concept_rules import (
    rule_c1_state_independence,
    rule_c2_effects_independence,
    rule_c3_op_principle_independence,
    rule_c4_no_inline_sync,
    rule_c5_has_purpose,
    rule_c6_has_actions,
    rule_c7_action_has_success_case,
    rule_c9_has_op_principle,
)
from concept_lang.validate.diagnostic import Diagnostic
from concept_lang.validate.sync_rules import (
    rule_s1_references_resolve,
    rule_s2_pattern_fields_exist,
    rule_s3_then_vars_bound,
    rule_s4_where_vars_bound,
    rule_s5_multiple_concepts,
)
from concept_lang.validate.workspace import validate_workspace

__all__ = [
    "Diagnostic",
    "rule_c1_state_independence",
    "rule_c2_effects_independence",
    "rule_c3_op_principle_independence",
    "rule_c4_no_inline_sync",
    "rule_c5_has_purpose",
    "rule_c6_has_actions",
    "rule_c7_action_has_success_case",
    "rule_c9_has_op_principle",
    "rule_s1_references_resolve",
    "rule_s2_pattern_fields_exist",
    "rule_s3_then_vars_bound",
    "rule_s4_where_vars_bound",
    "rule_s5_multiple_concepts",
    "validate_workspace",
]
```

- [ ] **Step 16.5: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 42 passed.

- [ ] **Step 16.6: Commit**

```bash
git add src/concept_lang/validate/workspace.py src/concept_lang/validate/__init__.py tests/test_validate.py
git commit -m "feat(validate): validate_workspace aggregator"
```

---

## Task 17: Single-file wrappers `validate_concept_file` and `validate_sync_file`

**Files:**
- Modify: `src/concept_lang/validate/workspace.py`
- Modify: `src/concept_lang/validate/__init__.py`
- Modify: `tests/test_validate.py`

The MCP tool path needs two convenience wrappers: given a single `.concept` or `.sync` file, parse it, build a minimal workspace for cross-reference context, run the rules that apply, and return the diagnostics.

For a single `.concept` file, the wrapper runs all concept rules. Cross-concept references (e.g. a concept whose state references another concept) are detected by `C1` regardless of what's in the workspace, so no extra context is needed.

For a single `.sync` file, the wrapper accepts an optional `extra_concepts` mapping so that the caller (typically the MCP server) can supply already-loaded concept ASTs for cross-reference checks. When `extra_concepts` is `None`, the sync is validated in isolation and `S1`/`S2` will flag every reference.

- [ ] **Step 17.1: Write the failing test**

Append to `tests/test_validate.py`:

```python
from concept_lang.validate import validate_concept_file, validate_sync_file


class TestSingleFileValidators:
    def test_validate_concept_file_clean(self, tmp_path):
        p = tmp_path / "Counter.concept"
        p.write_text(
            """
concept Counter

  purpose
    count things

  state
    total: int

  actions
    inc [ ] => [ total: int ]

  operational principle
    after inc [ ] => [ total: 1 ]
""",
            encoding="utf-8",
        )
        diags = validate_concept_file(p)
        errors = [d for d in diags if d.severity == "error"]
        assert errors == []

    def test_validate_concept_file_dirty(self, tmp_path):
        p = tmp_path / "Bad.concept"
        p.write_text(
            """
concept Bad

  purpose
    bad

  state
    owner: User

  actions
    noop [ ] => [ ok: boolean ]

  operational principle
    after noop [ ] => [ ok: true ]
""",
            encoding="utf-8",
        )
        diags = validate_concept_file(p)
        codes = {d.code for d in diags if d.severity == "error"}
        assert "C1" in codes
        # Every emitted diagnostic carries the file path.
        assert all(d.file == p for d in diags)

    def test_validate_sync_file_with_extra_concepts(self, tmp_path):
        p = tmp_path / "log.sync"
        p.write_text(
            """
sync LogEveryInc

  when
    Counter/inc: [ ] => [ total: ?total ]
  then
    Log/append: [ event: ?total ]
""",
            encoding="utf-8",
        )
        ws = _workspace_with_counter_and_log()
        diags = validate_sync_file(p, extra_concepts=ws.concepts)
        errors = [d for d in diags if d.severity == "error"]
        assert errors == []

    def test_validate_sync_file_without_context_flags_unknown(self, tmp_path):
        p = tmp_path / "log.sync"
        p.write_text(
            """
sync LogEveryInc

  when
    Counter/inc: [ ] => [ total: ?total ]
  then
    Log/append: [ event: ?total ]
""",
            encoding="utf-8",
        )
        diags = validate_sync_file(p)
        # Without extra_concepts, every reference is unknown -> S1 fires twice.
        s1s = [d for d in diags if d.code == "S1"]
        assert len(s1s) == 2
```

- [ ] **Step 17.2: Run - fails**

Run: `uv run pytest tests/test_validate.py::TestSingleFileValidators -v`
Expected: `ImportError: cannot import name 'validate_concept_file'`.

- [ ] **Step 17.3: Add the wrappers to `workspace.py`**

Append to `src/concept_lang/validate/workspace.py`:

```python
from concept_lang.parse import parse_concept_file, parse_sync_file


def validate_concept_file(path: Path) -> list[Diagnostic]:
    """
    Validate a single `.concept` file.

    Runs every concept rule (C1..C9 except C8) on the parsed AST plus the
    source-level C4 scan. Returns all diagnostics with `file=path`.
    """
    source = path.read_text(encoding="utf-8")
    diagnostics: list[Diagnostic] = []
    # C4 first - it reports migration errors even if the file would
    # otherwise parse. We then try to parse.
    diagnostics.extend(rule_c4_no_inline_sync(source, file=path))

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
        return diagnostics

    diagnostics.extend(rule_c1_state_independence(concept, file=path))
    diagnostics.extend(rule_c2_effects_independence(concept, file=path))
    diagnostics.extend(rule_c3_op_principle_independence(concept, file=path))
    diagnostics.extend(rule_c5_has_purpose(concept, file=path))
    diagnostics.extend(rule_c6_has_actions(concept, file=path))
    diagnostics.extend(rule_c7_action_has_success_case(concept, file=path))
    diagnostics.extend(rule_c9_has_op_principle(concept, file=path))
    return diagnostics


def validate_sync_file(
    path: Path,
    *,
    extra_concepts: dict[str, ConceptAST] | None = None,
) -> list[Diagnostic]:
    """
    Validate a single `.sync` file.

    When `extra_concepts` is provided, cross-reference rules (S1, S2)
    resolve against that dictionary. Otherwise the sync is validated in
    isolation and every cross-reference is flagged as unknown.
    """
    diagnostics: list[Diagnostic] = []
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
        return diagnostics

    scratch_ws = Workspace(
        concepts=dict(extra_concepts or {}),
        syncs={sync.name: sync},
    )
    index = WorkspaceIndex.build(scratch_ws)
    diagnostics.extend(rule_s1_references_resolve(sync, index, file=path))
    diagnostics.extend(rule_s2_pattern_fields_exist(sync, index, file=path))
    diagnostics.extend(rule_s3_then_vars_bound(sync, index, file=path))
    diagnostics.extend(rule_s4_where_vars_bound(sync, index, file=path))
    diagnostics.extend(rule_s5_multiple_concepts(sync, index, file=path))
    return diagnostics
```

Note: the `parse_concept_file` / `parse_sync_file` import lives inside the file body (or at the top) alongside the Task 16 imports. If you already added it at the top during Task 16, skip this import step.

- [ ] **Step 17.4: Re-export the wrappers from the package**

Edit `src/concept_lang/validate/__init__.py` to import both new names:

```python
from concept_lang.validate.workspace import (
    validate_concept_file,
    validate_sync_file,
    validate_workspace,
)
```

Add `validate_concept_file` and `validate_sync_file` to `__all__`.

- [ ] **Step 17.5: Run tests - should pass**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 46 passed.

- [ ] **Step 17.6: Commit**

```bash
git add src/concept_lang/validate/workspace.py src/concept_lang/validate/__init__.py tests/test_validate.py
git commit -m "feat(validate): single-file validate_concept_file and validate_sync_file"
```

---

## Task 18: Meta-test - positive fixtures have zero error-level diagnostics

**Files:**
- Modify: `tests/test_validate.py`

- [ ] **Step 18.1: Write the meta-test**

Append to `tests/test_validate.py`:

```python
from concept_lang.parse import parse_concept_file, parse_sync_file


FIXTURES_ROOT = Path(__file__).parent / "fixtures"


def _load_fixture_workspace(subdir: str) -> tuple[
    Workspace,
    dict[str, Path],
    dict[str, Path],
]:
    """
    Load a positive-fixtures workspace by reading every concept and sync
    file under `tests/fixtures/<subdir>/`. Returns the Workspace plus the
    concept_files and sync_files mappings for richer diagnostics.
    """
    root = FIXTURES_ROOT / subdir
    concepts: dict[str, ConceptAST] = {}
    syncs: dict[str, SyncAST] = {}
    concept_files: dict[str, Path] = {}
    sync_files: dict[str, Path] = {}
    for f in sorted((root / "concepts").glob("*.concept")):
        ast = parse_concept_file(f)
        concepts[ast.name] = ast
        concept_files[ast.name] = f
    for f in sorted((root / "syncs").glob("*.sync")):
        sync = parse_sync_file(f)
        syncs[sync.name] = sync
        sync_files[sync.name] = f
    return (
        Workspace(concepts=concepts, syncs=syncs),
        concept_files,
        sync_files,
    )


class TestPositiveFixturesHaveNoErrors:
    def test_architecture_ide_workspace_is_clean(self):
        ws, cf, sf = _load_fixture_workspace("architecture_ide")
        diags = validate_workspace(ws, concept_files=cf, sync_files=sf)
        errors = [d for d in diags if d.severity == "error"]
        assert errors == [], (
            "architecture_ide fixtures produced error diagnostics:\n"
            + "\n".join(f"  {d.code} ({d.file}): {d.message}" for d in errors)
        )

    def test_realworld_workspace_is_clean(self):
        ws, cf, sf = _load_fixture_workspace("realworld")
        diags = validate_workspace(ws, concept_files=cf, sync_files=sf)
        errors = [d for d in diags if d.severity == "error"]
        assert errors == [], (
            "realworld fixtures produced error diagnostics:\n"
            + "\n".join(f"  {d.code} ({d.file}): {d.message}" for d in errors)
        )
```

- [ ] **Step 18.2: Run the meta-test**

Run: `uv run pytest tests/test_validate.py::TestPositiveFixturesHaveNoErrors -v`
Expected: 2 passed.

If any fixture reports an error, treat it as a **rule bug**, not a fixture bug. The positive fixtures are paper-faithful and must be accepted by a correct validator. Fix the rule (or, as a last resort, document a deliberate false positive and tighten the rule's scope) before proceeding. Commit the fix separately.

- [ ] **Step 18.3: Commit**

```bash
git add tests/test_validate.py
git commit -m "test(validate): positive fixtures have zero error-level diagnostics"
```

---

## Task 19: Meta-test - negative fixtures fire their expected codes

**Files:**
- Modify: `tests/test_validate.py`

- [ ] **Step 19.1: Write the negative-fixture sweep**

Append to `tests/test_validate.py`:

```python
import json


NEGATIVE_ROOT = FIXTURES_ROOT / "negative"


def _expected_for(fixture_path: Path) -> dict:
    """Load the matching `*.expected.json` file for a negative fixture."""
    expected_path = NEGATIVE_ROOT / f"{fixture_path.stem}.expected.json"
    return json.loads(expected_path.read_text(encoding="utf-8"))


def _shared_concepts_for_sync_negatives() -> dict[str, ConceptAST]:
    """
    A small concept pool that gives the negative sync fixtures something
    to resolve against. We reuse the in-memory Counter + Log concepts
    from the earlier sync tests so that S2 etc. have real signatures.
    """
    ws = _workspace_with_counter_and_log()
    return dict(ws.concepts)


class TestNegativeFixturesFireExpectedCodes:
    def _fire_concept_fixture(self, path: Path) -> list[Diagnostic]:
        return validate_concept_file(path)

    def _fire_sync_fixture(self, path: Path) -> list[Diagnostic]:
        return validate_sync_file(
            path,
            extra_concepts=_shared_concepts_for_sync_negatives(),
        )

    def test_every_negative_fixture_has_an_expected_file(self):
        concept_fixtures = sorted(NEGATIVE_ROOT.glob("*.concept"))
        sync_fixtures = sorted(NEGATIVE_ROOT.glob("*.sync"))
        # Spec §6.2 lists 13 negative fixtures (C1..C9 except C8, S1..S5).
        assert len(concept_fixtures) == 8, [p.name for p in concept_fixtures]
        assert len(sync_fixtures) == 5, [p.name for p in sync_fixtures]
        for p in concept_fixtures + sync_fixtures:
            expected_path = NEGATIVE_ROOT / f"{p.stem}.expected.json"
            assert expected_path.exists(), f"missing expected file for {p.name}"

    def test_concept_negative_fixtures_fire_expected_codes(self):
        for fixture in sorted(NEGATIVE_ROOT.glob("*.concept")):
            expected = _expected_for(fixture)
            diags = self._fire_concept_fixture(fixture)
            emitted_codes = {(d.code, d.severity) for d in diags}
            for want in expected["diagnostics"]:
                key = (want["code"], want["severity"])
                assert key in emitted_codes, (
                    f"{fixture.name}: expected {key} in {sorted(emitted_codes)}"
                )

    def test_sync_negative_fixtures_fire_expected_codes(self):
        for fixture in sorted(NEGATIVE_ROOT.glob("*.sync")):
            expected = _expected_for(fixture)
            diags = self._fire_sync_fixture(fixture)
            emitted_codes = {(d.code, d.severity) for d in diags}
            for want in expected["diagnostics"]:
                key = (want["code"], want["severity"])
                assert key in emitted_codes, (
                    f"{fixture.name}: expected {key} in {sorted(emitted_codes)}"
                )

    def test_c5_fixture_parses_clean_even_though_listed(self):
        """
        C5's negative fixture is a minimal-but-valid concept - we
        deliberately keep C5 AST-level only because the grammar requires a
        non-whitespace purpose body. Assert that the fixture produces
        zero error-level diagnostics (the expected file says
        `"diagnostics": []`).
        """
        fixture = NEGATIVE_ROOT / "C5_missing_purpose.concept"
        diags = validate_concept_file(fixture)
        errors = [d for d in diags if d.severity == "error"]
        assert errors == []
```

- [ ] **Step 19.2: Run the sweep**

Run: `uv run pytest tests/test_validate.py::TestNegativeFixturesFireExpectedCodes -v`
Expected: 4 passed.

If a fixture fires the wrong codes (for example S2 cascades when only S1 was expected), either (a) update the fixture to isolate the target rule, or (b) add the cascading code to the expected file. The expected files use a **subset** check, so emitting additional diagnostics is allowed as long as the declared codes are present. A good negative fixture should still be minimal - prefer fixing the fixture to broadening the expected set.

- [ ] **Step 19.3: Commit**

```bash
git add tests/test_validate.py
git commit -m "test(validate): negative fixtures fire their expected diagnostic codes"
```

---

## Task 20: P2 gate - full validator suite + realworld acceptance + tag

**Files:**
- Modify: `tests/test_validate.py`

- [ ] **Step 20.1: Write the P2 gate**

Append to `tests/test_validate.py`:

```python
class TestP2Gate:
    """
    The P2 gate from the paper-alignment spec:

      1. Every positive fixture (architecture_ide + realworld) produces
         zero error-level diagnostics.
      2. Every negative fixture fires at least the codes declared in its
         matching `*.expected.json`.
      3. The realworld workspace is the paper's canonical case study; if
         it validates clean, the validator is faithful to the paper.
    """

    def test_paper_case_study_is_accepted_by_validator(self):
        ws, cf, sf = _load_fixture_workspace("realworld")
        diags = validate_workspace(ws, concept_files=cf, sync_files=sf)
        errors = [d for d in diags if d.severity == "error"]
        assert errors == [], (
            "paper case study (realworld fixtures) produced errors:\n"
            + "\n".join(f"  {d.code} ({d.file}): {d.message}" for d in errors)
        )

    def test_every_spec_rule_has_a_coverage_class(self):
        """
        Sanity check: every rule declared in spec §4.3 (except C8 and the
        app-spec rules which stay in v1 for P2) has at least one test
        class in this file.
        """
        import tests.test_validate as this_module

        expected_class_names = {
            "TestRuleC1",
            "TestRuleC2",
            "TestRuleC3",
            "TestRuleC4",
            "TestRuleC5",
            "TestRuleC6",
            "TestRuleC7",
            "TestRuleC9",
            "TestRuleS1",
            "TestRuleS2",
            "TestRuleS3",
            "TestRuleS4",
            "TestRuleS5",
        }
        present = {name for name in dir(this_module) if name.startswith("TestRule")}
        missing = expected_class_names - present
        assert not missing, f"missing coverage classes: {sorted(missing)}"
```

- [ ] **Step 20.2: Run the full validator suite**

Run: `uv run pytest tests/test_validate.py -v`
Expected: every test passes.

- [ ] **Step 20.3: Run the whole project test suite to confirm no regressions**

Run: `uv run pytest -v`
Expected: all pre-existing P1 tests (`test_ast.py`, `test_parse.py`) still pass, and the untouched v1 tests (`test_validator.py`, `test_diff.py`) still pass.

- [ ] **Step 20.4: Commit the gate**

```bash
git add tests/test_validate.py
git commit -m "test(gate): P2 gate - full validator suite + paper acceptance"
```

- [ ] **Step 20.5: Tag the milestone**

```bash
git tag p2-validator-complete -m "P2 gate passed: validator implements C1..C9 (minus C8) and S1..S5"
```

- [ ] **Step 20.6: Final status check**

Run: `git log --oneline -25`
Expected: ~20 small commits in the `feat(validate)` / `test(validate)` / `test(gate)` namespace, ending with the tag `p2-validator-complete`.

---

## What's next (not in this plan)

After this plan lands and the `p2-validator-complete` tag is in place, the follow-up plans are:

- **P3 - Workspace loader**: `load_workspace()` that walks a directory, parses every `.concept` and `.sync` file, builds a `Workspace`, and attaches file paths. `validate_workspace` then gains a "load and validate in one call" convenience entry point. Also the place to wire Lark line/column information through the transformers so diagnostics carry real positions.
- **P4 - Tooling migration**: rewire MCP tools (`read_concept`, `write_concept`, new `read_sync`, `write_sync`, `validate_workspace`), `diff.py`, `explorer.py`, and `app_parser.py` / `app_validator.py` to the new AST.
- **P5 - Skills rewrite**: `build`, `build-sync`, `review`, `scaffold`, `explore`.
- **P6 - Examples + docs**: update `architecture-ide/concepts/*` in place, rewrite `README.md`, add `docs/methodology.md`.
- **P7 - Delete v1**: remove `concept_lang.validator`, `concept_lang.parser`, `concept_lang.models`, their tests, and the `concept_lang.app_validator` / `concept_lang.app_parser` modules.

Each deserves its own plan, written after the preceding phase lands so we're planning on verified ground.

---

## Self-review (filled in after drafting, before execution)

- **Spec coverage** - every validator rule in §4.3 except `C8` and the app-spec rules (`A1`, `A2`) has a dedicated task:

  | Rule | Task |
  |---|---|
  | C1 | Task 3 |
  | C2 | Task 4 |
  | C3 | Task 5 |
  | C4 | Task 6 |
  | C5 | Task 7 |
  | C6 | Task 8 |
  | C7 | Task 9 |
  | C8 | **deferred** (per spec §6.2 "skipped for the first cut") |
  | C9 | Task 10 |
  | S1 | Task 11 |
  | S2 | Task 12 |
  | S3 | Task 13 |
  | S4 | Task 14 |
  | S5 | Task 15 |
  | A1, A2 | out of scope for P2 (stay in the v1 `app_validator.py` until P4) |

- **Placeholder scan** - no "TBD", no "similar to above", no "etc." in place of code. Every code block is literal. `C8` is explicitly called out as deferred, not omitted silently.

- **Type consistency** - `Diagnostic` fields are the same in Task 1's model definition, every rule implementation, and the `*.expected.json` schema. Concept-rule signatures are uniform `rule(concept, *, file=None) -> list[Diagnostic]`; the `rule_c4_no_inline_sync` exception (takes `source: str` instead of `concept: ConceptAST`) is documented in Task 6 and exercised by the `validate_workspace` aggregator in Task 16 via `concept.source`. Sync-rule signatures are uniform `rule(sync, index, *, file=None) -> list[Diagnostic]`; rules that do not use the index (`S3`, `S4`, `S5`) keep the argument and assign it to `_` for documentation.

- **Ambiguity check** - the "what is an error case" definition (Task 9: "any case whose outputs contain a field named `error`") is not redefined anywhere else. The "what is bound" definition lives in the shared helpers `_bindings_from_when` / `_bindings_from_where` (Task 13) and is used identically by S3 and S4.

- **Fixture rule coverage** - every negative fixture in spec §6.2 has a matching task. `C5_missing_purpose.concept` is an intentional no-error fixture because the grammar prevents the failure case from being expressed at the file level; the rule is covered by hand-built AST tests in Task 7 and by the explicit `test_c5_fixture_parses_clean_even_though_listed` assertion in Task 19. This decision is called out in both Task 7 and Task 19.

- **Commit discipline** - every task ends with a single `git add` + `git commit` covering exactly the files listed in its Files section. No task commits v1 files; the v1 modules (`concept_lang.validator`, `concept_lang.parser`, `concept_lang.models`, `concept_lang.app_validator`) are untouched throughout P2.

- **Consistent cross-fixture dependency** - sync tests use a single shared `_workspace_with_counter_and_log()` builder defined once in Task 11 and reused by Tasks 12..16 and the negative sync-fixture sweep in Task 19. The earlier Task 2 helper builder `_make_tiny_workspace()` is independent and used only by the `TestWorkspaceIndex` tests.

- **Running test counts are approximate** - each task step documents its expected `pytest` count, but the exact numbers depend on how pytest counts parameterized tests. The authoritative gate is Task 20's `uv run pytest` sweep, which does not hard-code a number. If an intermediate task's count is off by a small number, treat the test-step execution as truth and update the plan inline.
