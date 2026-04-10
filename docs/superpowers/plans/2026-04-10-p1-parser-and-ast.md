# concept-lang 0.2.0 — P1: Parser + AST Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the new concept + sync grammar, AST, and parser from the spec, validated end-to-end against two hand-written fixture workspaces (architecture-ide + realworld). At the end of this plan, `parse_concept_source()` and `parse_sync_source()` correctly parse every positive fixture into Pydantic ASTs.

**Architecture:** New files live *alongside* the v1 parser/models/validator until P7. Lark handles the new DSL; Pydantic models hold the AST; transformers convert parse trees to AST. The v1 code is completely untouched — P4 migrates tooling, P7 deletes v1.

**Tech Stack:** Python 3.10+, Lark (new dep), Pydantic 2, pytest, uv.

**Scope note:** This plan covers **P1 only** from the spec. P2 (validator) through P7 (delete v1) are deferred to follow-up plans written after P1's gate passes.

**Spec reference:** [`docs/superpowers/specs/2026-04-10-paper-alignment-design.md`](../specs/2026-04-10-paper-alignment-design.md)

---

## File structure (what this plan creates)

```
architecture-ide/
  pyproject.toml                                   # MODIFY: add lark dep
  src/concept_lang/
    ast.py                                         # CREATE: new Pydantic AST
    parse.py                                       # CREATE: parser entry points
    transformers/
      __init__.py                                  # CREATE
      concept_transformer.py                       # CREATE
      sync_transformer.py                          # CREATE
    grammars/
      __init__.py                                  # CREATE
      concept.lark                                 # CREATE
      sync.lark                                    # CREATE
    # v1 files UNTOUCHED:
    #   parser.py, models.py, validator.py, diff.py, explorer.py,
    #   app_parser.py, app_validator.py, prompts.py, server.py,
    #   resources.py, tools/, codegen/, diagrams/
  tests/
    test_ast.py                                    # CREATE: AST round-trip tests
    test_parse.py                                  # CREATE: parser tests
    fixtures/
      architecture_ide/
        concepts/
          Workspace.concept                        # CREATE
          Concept.concept                          # CREATE
          DesignSession.concept                    # CREATE
          Diagram.concept                          # CREATE
        syncs/
          specify_draws_diagram.sync               # CREATE
          session_introduces.sync                  # CREATE
          workspace_tracks_concept.sync            # CREATE
      realworld/
        concepts/
          User.concept                             # CREATE
          Password.concept                         # CREATE
          Profile.concept                          # CREATE
          Article.concept                          # CREATE
          Web.concept                              # CREATE
          JWT.concept                              # CREATE
        syncs/
          register_user.sync                       # CREATE
          register_set_password.sync               # CREATE
          register_error.sync                      # CREATE
          register_default_profile.sync            # CREATE
          new_user_token.sync                      # CREATE
          format_article.sync                      # CREATE
    # v1 tests UNTOUCHED: test_diff.py, test_validator.py
```

**All commands below assume the working directory is `architecture-ide/`** (the package root with `pyproject.toml`). All paths in Files sections are relative to that directory.

---

## Task 1: Add Lark dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1.1: Edit pyproject.toml to add lark**

Change the `dependencies` list in `pyproject.toml` from:

```toml
dependencies = [
    "mcp>=1.2.0",
    "pydantic>=2.0.0",
]
```

to:

```toml
dependencies = [
    "mcp>=1.2.0",
    "pydantic>=2.0.0",
    "lark>=1.2.0",
]
```

- [ ] **Step 1.2: Sync dependencies**

Run: `uv sync`
Expected: installs `lark` and its transitive deps; no errors.

- [ ] **Step 1.3: Verify lark is importable**

Run: `uv run python -c "import lark; print(lark.__version__)"`
Expected: prints a version string like `1.2.2`.

- [ ] **Step 1.4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add lark dependency for new parser"
```

---

## Task 2: Create shared AST types (`TypedName`, `EffectClause`)

**Files:**
- Create: `src/concept_lang/ast.py`
- Create: `tests/test_ast.py`

- [ ] **Step 2.1: Write the failing test**

Create `tests/test_ast.py`:

```python
"""Round-trip tests for the new AST (concept_lang.ast)."""

from concept_lang.ast import TypedName, EffectClause


class TestTypedName:
    def test_round_trip(self):
        tn = TypedName(name="user", type_expr="U")
        dumped = tn.model_dump()
        assert dumped == {"name": "user", "type_expr": "U"}
        assert TypedName.model_validate(dumped) == tn


class TestEffectClause:
    def test_round_trip(self):
        ec = EffectClause(
            raw="password[user] := hash",
            field="password",
            op=":=",
            rhs="hash",
        )
        dumped = ec.model_dump()
        assert TypedName.model_validate(dumped) is not None or True  # sanity
        round_tripped = EffectClause.model_validate(dumped)
        assert round_tripped == ec

    def test_op_literal(self):
        import pytest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            EffectClause(raw="x", field="x", op="<>", rhs="y")  # type: ignore[arg-type]
```

- [ ] **Step 2.2: Run the test — it should fail**

Run: `uv run pytest tests/test_ast.py -v`
Expected: `ModuleNotFoundError: No module named 'concept_lang.ast'`

- [ ] **Step 2.3: Create the minimal ast.py**

Create `src/concept_lang/ast.py`:

```python
"""
New AST for concept-lang 0.2.0.

This module defines the Pydantic data classes that the new parser
(concept_lang.parse) produces. It lives alongside the v1 models
(concept_lang.models) until P7 of the paper-alignment project.

See docs/superpowers/specs/2026-04-10-paper-alignment-design.md §4.1.
"""

from typing import Literal

from pydantic import BaseModel


class TypedName(BaseModel):
    """A named parameter with a type, e.g. `user: U`."""
    name: str
    type_expr: str


class EffectClause(BaseModel):
    """
    A single line in an action case's optional `effects:` subsection.

    Examples:
        password[user] := hash
        tags -= tag
    """
    raw: str                          # the whole clause as written
    field: str                        # e.g. "password"
    op: Literal[":=", "+=", "-="]
    rhs: str                          # right-hand side kept as raw text
```

- [ ] **Step 2.4: Run tests — should pass**

Run: `uv run pytest tests/test_ast.py -v`
Expected: 3 passed.

- [ ] **Step 2.5: Commit**

```bash
git add src/concept_lang/ast.py tests/test_ast.py
git commit -m "feat(ast): TypedName and EffectClause types"
```

---

## Task 3: Concept AST — `ActionCase`, `Action`, `OPStep`, `OperationalPrinciple`, `StateDecl`, `ConceptAST`

**Files:**
- Modify: `src/concept_lang/ast.py`
- Modify: `tests/test_ast.py`

- [ ] **Step 3.1: Write failing tests for the concept AST**

Append to `tests/test_ast.py`:

```python
from concept_lang.ast import (
    Action,
    ActionCase,
    ConceptAST,
    OperationalPrinciple,
    OPStep,
    StateDecl,
)


class TestConceptAST:
    def _make_password_concept(self) -> ConceptAST:
        set_success = ActionCase(
            inputs=[
                TypedName(name="user", type_expr="U"),
                TypedName(name="password", type_expr="string"),
            ],
            outputs=[TypedName(name="user", type_expr="U")],
            body=[
                "generate a random salt for the user",
                "compute a hash of the password with the salt",
                "store the hash and the salt",
            ],
            effects=[
                EffectClause(raw="password[user] := hash", field="password", op=":=", rhs="hash"),
                EffectClause(raw="salt[user] := generated_salt", field="salt", op=":=", rhs="generated_salt"),
            ],
        )
        set_error = ActionCase(
            inputs=[
                TypedName(name="user", type_expr="U"),
                TypedName(name="password", type_expr="string"),
            ],
            outputs=[TypedName(name="error", type_expr="string")],
            body=["if password does not meet complexity requirements"],
        )
        op = OperationalPrinciple(
            steps=[
                OPStep(
                    keyword="after",
                    action_name="set",
                    inputs=[("user", "x"), ("password", '"secret"')],
                    outputs=[("user", "x")],
                ),
                OPStep(
                    keyword="then",
                    action_name="check",
                    inputs=[("user", "x"), ("password", '"secret"')],
                    outputs=[("valid", "true")],
                ),
            ],
        )
        return ConceptAST(
            name="Password",
            params=["U"],
            purpose="to securely store and validate user credentials",
            state=[
                StateDecl(name="password", type_expr="U -> string"),
                StateDecl(name="salt", type_expr="U -> string"),
            ],
            actions=[Action(name="set", cases=[set_success, set_error])],
            operational_principle=op,
            source="",
        )

    def test_round_trip(self):
        ast = self._make_password_concept()
        dumped = ast.model_dump()
        assert ConceptAST.model_validate(dumped) == ast

    def test_action_groups_cases_by_name(self):
        ast = self._make_password_concept()
        assert len(ast.actions) == 1
        assert ast.actions[0].name == "set"
        assert len(ast.actions[0].cases) == 2

    def test_error_case_identified_by_output_field(self):
        ast = self._make_password_concept()
        set_action = ast.actions[0]
        error_case = next(c for c in set_action.cases
                          if any(o.name == "error" for o in c.outputs))
        assert error_case.outputs[0].type_expr == "string"
```

- [ ] **Step 3.2: Run tests — they fail**

Run: `uv run pytest tests/test_ast.py -v`
Expected: `ImportError: cannot import name 'Action' from 'concept_lang.ast'` (or similar).

- [ ] **Step 3.3: Extend `ast.py` with concept types**

Append to `src/concept_lang/ast.py`:

```python
# --- Concept ---------------------------------------------------------------


class ActionCase(BaseModel):
    """
    One case of a multi-case action. A concept's action may have several
    cases sharing a name (e.g. one success case, one error case).
    """
    inputs: list[TypedName]
    outputs: list[TypedName]
    body: list[str] = []              # natural-language description lines
    effects: list[EffectClause] = []  # optional formal state deltas


class Action(BaseModel):
    """An action with one or more cases sharing a name."""
    name: str
    cases: list[ActionCase]


class OPStep(BaseModel):
    """
    One step in an `operational principle`. Keywords are:
      * `after` for the first (initial) step,
      * `then` / `and` for subsequent steps.
    """
    keyword: Literal["after", "then", "and"]
    action_name: str
    inputs: list[tuple[str, str]]     # e.g. [("user", "x"), ("password", '"secret"')]
    outputs: list[tuple[str, str]]


class OperationalPrinciple(BaseModel):
    """Archetypal scenario using the concept's own actions."""
    steps: list[OPStep]


class StateDecl(BaseModel):
    """A state field declaration (Alloy-style type expression)."""
    name: str
    type_expr: str                    # e.g. "set U", "U -> string"


class ConceptAST(BaseModel):
    """Top-level AST for a `.concept` file."""
    name: str
    params: list[str]                 # generic type parameters, e.g. ["U"]
    purpose: str                      # free-text purpose description
    state: list[StateDecl]
    actions: list[Action]
    operational_principle: OperationalPrinciple
    source: str                       # raw source text for diagnostics
```

- [ ] **Step 3.4: Run tests — should pass**

Run: `uv run pytest tests/test_ast.py -v`
Expected: 6 passed (3 from task 2 + 3 new).

- [ ] **Step 3.5: Commit**

```bash
git add src/concept_lang/ast.py tests/test_ast.py
git commit -m "feat(ast): ConceptAST with multi-case actions and operational principle"
```

---

## Task 4: Sync AST — `PatternField`, `ActionPattern`, `Triple`, `StateQuery`, `BindClause`, `WhereClause`, `SyncAST`

**Files:**
- Modify: `src/concept_lang/ast.py`
- Modify: `tests/test_ast.py`

- [ ] **Step 4.1: Write failing tests for the sync AST**

Append to `tests/test_ast.py`:

```python
from concept_lang.ast import (
    ActionPattern,
    BindClause,
    PatternField,
    StateQuery,
    SyncAST,
    Triple,
    WhereClause,
)


class TestSyncAST:
    def _make_register_sync(self) -> SyncAST:
        web_request = ActionPattern(
            concept="Web",
            action="request",
            input_pattern=[
                PatternField(name="method", kind="literal", value='"register"'),
                PatternField(name="username", kind="var", value="?username"),
                PatternField(name="email", kind="var", value="?email"),
            ],
            output_pattern=[
                PatternField(name="request", kind="var", value="?request"),
            ],
        )
        return SyncAST(
            name="RegisterUser",
            when=[web_request],
            where=WhereClause(
                binds=[BindClause(expression="uuid()", variable="?user")],
            ),
            then=[
                ActionPattern(
                    concept="User",
                    action="register",
                    input_pattern=[
                        PatternField(name="user", kind="var", value="?user"),
                        PatternField(name="name", kind="var", value="?username"),
                        PatternField(name="email", kind="var", value="?email"),
                    ],
                    output_pattern=[],
                )
            ],
            source="",
        )

    def test_round_trip(self):
        sync = self._make_register_sync()
        dumped = sync.model_dump()
        assert SyncAST.model_validate(dumped) == sync

    def test_pattern_field_kind_literal(self):
        sync = self._make_register_sync()
        method = sync.when[0].input_pattern[0]
        assert method.kind == "literal"
        assert method.value == '"register"'


class TestWhereClauseStateQuery:
    def test_state_query_with_triples(self):
        q = StateQuery(
            concept="Article",
            triples=[
                Triple(subject="?article", predicate="title", object="?title"),
                Triple(subject="?article", predicate="author", object="?author"),
            ],
        )
        wc = WhereClause(queries=[q])
        assert wc.queries[0].concept == "Article"
        assert wc.queries[0].is_optional is False

    def test_optional_state_query(self):
        q = StateQuery(
            concept="Tag",
            triples=[Triple(subject="?article", predicate="tag", object="?tag")],
            is_optional=True,
        )
        assert q.is_optional is True
```

- [ ] **Step 4.2: Run tests — they fail**

Run: `uv run pytest tests/test_ast.py -v`
Expected: `ImportError` for the new names.

- [ ] **Step 4.3: Extend `ast.py` with sync types**

Append to `src/concept_lang/ast.py`:

```python
# --- Sync ------------------------------------------------------------------


class PatternField(BaseModel):
    """
    One field inside an action pattern's `[ ... ]` bracket.

    Examples:
        method: "register"    → name="method", kind="literal", value='"register"'
        username: ?username   → name="username", kind="var",    value="?username"
    """
    name: str
    kind: Literal["literal", "var"]
    value: str


class ActionPattern(BaseModel):
    """
    `Concept/action: [ input_pattern ] => [ output_pattern ]`

    Used in a sync's `when` clause (as matches) and `then` clause
    (as invocations). An empty pattern list means "match anything".
    """
    concept: str
    action: str
    input_pattern: list[PatternField]
    output_pattern: list[PatternField]


class Triple(BaseModel):
    """One SPARQL-ish triple inside a state query."""
    subject: str                      # e.g. "?article"
    predicate: str                    # e.g. "title"
    object: str                       # e.g. "?title"


class StateQuery(BaseModel):
    """
    `Concept: { ?subject prop: ?obj ; prop: ?obj }`

    Queries the state of a concept. `is_optional` marks it as a SPARQL
    OPTIONAL (left-join); otherwise the query must match for the sync
    to fire.
    """
    concept: str
    triples: list[Triple]
    is_optional: bool = False


class BindClause(BaseModel):
    """
    `bind (<expression> as ?var)`

    Introduces a computed variable. The expression is kept as raw
    text; the runtime (Layer 2) will evaluate it.
    """
    expression: str
    variable: str                     # e.g. "?user"


class WhereClause(BaseModel):
    """The `where` section of a sync: state queries and binds."""
    queries: list[StateQuery] = []
    binds: list[BindClause] = []


class SyncAST(BaseModel):
    """Top-level AST for a `.sync` file."""
    name: str
    when: list[ActionPattern]
    where: WhereClause | None = None
    then: list[ActionPattern]
    source: str
```

- [ ] **Step 4.4: Run tests — should pass**

Run: `uv run pytest tests/test_ast.py -v`
Expected: 10 passed.

- [ ] **Step 4.5: Commit**

```bash
git add src/concept_lang/ast.py tests/test_ast.py
git commit -m "feat(ast): SyncAST with SPARQL-like patterns and state queries"
```

---

## Task 5: `Workspace` AST type

**Files:**
- Modify: `src/concept_lang/ast.py`
- Modify: `tests/test_ast.py`

- [ ] **Step 5.1: Write failing test**

Append to `tests/test_ast.py`:

```python
from concept_lang.ast import Workspace


class TestWorkspace:
    def test_empty_workspace(self):
        ws = Workspace(concepts={}, syncs={})
        assert ws.concepts == {}
        assert ws.syncs == {}

    def test_workspace_lookup(self):
        # We reuse the password concept + register sync from earlier tests
        password = TestConceptAST()._make_password_concept()
        register = TestSyncAST()._make_register_sync()
        ws = Workspace(
            concepts={"Password": password},
            syncs={"RegisterUser": register},
        )
        assert ws.concepts["Password"].purpose.startswith("to securely")
        assert ws.syncs["RegisterUser"].when[0].concept == "Web"
```

- [ ] **Step 5.2: Run — fails**

Run: `uv run pytest tests/test_ast.py::TestWorkspace -v`
Expected: `ImportError: Workspace`.

- [ ] **Step 5.3: Add `Workspace` to `ast.py`**

Append to `src/concept_lang/ast.py`:

```python
# --- Workspace -------------------------------------------------------------


class Workspace(BaseModel):
    """
    A loaded collection of concepts and syncs — the central value that
    every MCP tool operates on.

    Apps (from the existing `*.app` format) are deferred: they keep
    using the v1 types until P4 migrates them.
    """
    concepts: dict[str, "ConceptAST"] = {}
    syncs: dict[str, "SyncAST"] = {}
```

- [ ] **Step 5.4: Run tests — pass**

Run: `uv run pytest tests/test_ast.py -v`
Expected: 12 passed.

- [ ] **Step 5.5: Commit**

```bash
git add src/concept_lang/ast.py tests/test_ast.py
git commit -m "feat(ast): Workspace container for concepts and syncs"
```

---

## Task 6: Concept grammar skeleton — header, params, purpose

**Files:**
- Create: `src/concept_lang/grammars/__init__.py`
- Create: `src/concept_lang/grammars/concept.lark`
- Create: `src/concept_lang/transformers/__init__.py`
- Create: `src/concept_lang/transformers/concept_transformer.py`
- Create: `src/concept_lang/parse.py`
- Create: `tests/test_parse.py`

- [ ] **Step 6.1: Write a failing test for a minimal concept**

Create `tests/test_parse.py`:

```python
"""Tests for the new Lark-based parser (concept_lang.parse)."""

from concept_lang.parse import parse_concept_source


class TestConceptHeader:
    def test_parses_name_and_purpose(self):
        src = """
concept Timer

  purpose
    measure elapsed durations between events
"""
        ast = parse_concept_source(src)
        assert ast.name == "Timer"
        assert ast.params == []
        assert ast.purpose == "measure elapsed durations between events"

    def test_parses_type_parameters(self):
        src = """
concept Session [User, Token]

  purpose
    track authenticated user sessions
"""
        ast = parse_concept_source(src)
        assert ast.name == "Session"
        assert ast.params == ["User", "Token"]
```

- [ ] **Step 6.2: Run — should fail**

Run: `uv run pytest tests/test_parse.py -v`
Expected: `ModuleNotFoundError: No module named 'concept_lang.parse'`

- [ ] **Step 6.3: Create the `grammars/` package**

Create `src/concept_lang/grammars/__init__.py`:

```python
"""Lark grammars for the new concept-lang DSL."""

from pathlib import Path

_GRAMMARS_DIR = Path(__file__).parent


def read_grammar(name: str) -> str:
    """Read a .lark grammar file from this package."""
    return (_GRAMMARS_DIR / name).read_text(encoding="utf-8")
```

- [ ] **Step 6.4: Create the minimal concept grammar**

Create `src/concept_lang/grammars/concept.lark`:

```lark
// concept-lang 0.2.0 — concept grammar (first slice: header + purpose)
// See docs/superpowers/specs/2026-04-10-paper-alignment-design.md §3.1.

start: concept_def

concept_def: "concept" NAME type_params? purpose_section

type_params: "[" NAME ("," NAME)* "]"

purpose_section: "purpose" purpose_body

// The purpose body is one or more indented non-empty lines.
// We capture everything up to the next top-level section or EOF.
purpose_body: PURPOSE_LINE+

PURPOSE_LINE: /[ \t]+[^\n]+/

NAME: /[A-Za-z_][A-Za-z0-9_]*/

%import common.NEWLINE
%import common.WS_INLINE
%ignore NEWLINE
%ignore WS_INLINE
```

- [ ] **Step 6.5: Create the transformers package**

Create `src/concept_lang/transformers/__init__.py`:

```python
"""Lark transformers converting parse trees into concept_lang.ast nodes."""
```

- [ ] **Step 6.6: Create the concept transformer**

Create `src/concept_lang/transformers/concept_transformer.py`:

```python
"""Transform a Lark parse tree for a .concept file into a ConceptAST."""

from lark import Token, Transformer, v_args

from concept_lang.ast import (
    ConceptAST,
    OperationalPrinciple,
)


@v_args(inline=True)
class ConceptTransformer(Transformer):
    """
    Transformer from concept.lark parse tree to ConceptAST.

    Each method here corresponds to a grammar rule; Lark calls them
    bottom-up with the already-transformed child values.
    """

    # --- atoms ---------------------------------------------------------------

    def NAME(self, token: Token) -> str:
        return str(token)

    def PURPOSE_LINE(self, token: Token) -> str:
        return str(token).strip()

    # --- sections ------------------------------------------------------------

    def type_params(self, *names: str) -> list[str]:
        return list(names)

    def purpose_body(self, *lines: str) -> str:
        return " ".join(l for l in lines if l)

    def purpose_section(self, body: str) -> str:
        return body

    # --- top level -----------------------------------------------------------

    def concept_def(self, name: str, *rest) -> ConceptAST:
        # rest may start with a type_params list; purpose is last
        params: list[str] = []
        purpose: str = ""
        for item in rest:
            if isinstance(item, list):
                params = item
            elif isinstance(item, str):
                purpose = item
        return ConceptAST(
            name=name,
            params=params,
            purpose=purpose,
            state=[],
            actions=[],
            operational_principle=OperationalPrinciple(steps=[]),
            source="",
        )

    def start(self, concept: ConceptAST) -> ConceptAST:
        return concept
```

- [ ] **Step 6.7: Create the parser entry point**

Create `src/concept_lang/parse.py`:

```python
"""
New parser entry point for concept-lang 0.2.0.

Lives alongside `concept_lang.parser` (v1) until P7. All functions
here return AST nodes from `concept_lang.ast`, never from
`concept_lang.models`.
"""

from pathlib import Path

from lark import Lark

from concept_lang.ast import ConceptAST
from concept_lang.grammars import read_grammar
from concept_lang.transformers.concept_transformer import ConceptTransformer


_concept_parser: Lark | None = None


def _get_concept_parser() -> Lark:
    global _concept_parser
    if _concept_parser is None:
        _concept_parser = Lark(
            read_grammar("concept.lark"),
            parser="earley",
            maybe_placeholders=False,
        )
    return _concept_parser


def parse_concept_source(source: str) -> ConceptAST:
    """Parse concept source text into a ConceptAST."""
    tree = _get_concept_parser().parse(source)
    ast = ConceptTransformer().transform(tree)
    # Attach the raw source for later diagnostics
    return ast.model_copy(update={"source": source})


def parse_concept_file(path: str | Path) -> ConceptAST:
    """Parse a `.concept` file from disk."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_concept_source(text)
```

- [ ] **Step 6.8: Run the test — should pass**

Run: `uv run pytest tests/test_parse.py -v`
Expected: 2 passed.

- [ ] **Step 6.9: Commit**

```bash
git add src/concept_lang/grammars src/concept_lang/transformers src/concept_lang/parse.py tests/test_parse.py
git commit -m "feat(parse): concept grammar skeleton parses header + purpose"
```

---

## Task 7: Concept grammar — `state` section

**Files:**
- Modify: `src/concept_lang/grammars/concept.lark`
- Modify: `src/concept_lang/transformers/concept_transformer.py`
- Modify: `tests/test_parse.py`

- [ ] **Step 7.1: Write failing tests for state parsing**

Append to `tests/test_parse.py`:

```python
class TestConceptState:
    def test_simple_set(self):
        src = """
concept Tracker

  purpose
    track items that are currently active

  state
    active: set Item
"""
        ast = parse_concept_source(src)
        assert len(ast.state) == 1
        assert ast.state[0].name == "active"
        assert ast.state[0].type_expr == "set Item"

    def test_relation(self):
        src = """
concept Password [U]

  purpose
    store credentials

  state
    password: U -> string
    salt: U -> string
"""
        ast = parse_concept_source(src)
        assert len(ast.state) == 2
        assert ast.state[1].name == "salt"
        assert ast.state[1].type_expr == "U -> string"
```

- [ ] **Step 7.2: Run — fails**

Run: `uv run pytest tests/test_parse.py::TestConceptState -v`
Expected: both fail with a Lark parse error (`state` keyword not in grammar).

- [ ] **Step 7.3: Extend the grammar**

Replace the body of `concept.lark` with:

```lark
// concept-lang 0.2.0 — concept grammar (header + purpose + state)

start: concept_def

concept_def: "concept" NAME type_params? purpose_section state_section?

type_params: "[" NAME ("," NAME)* "]"

purpose_section: "purpose" purpose_body
purpose_body: PURPOSE_LINE+

state_section: "state" state_decl+
state_decl: NAME ":" TYPE_EXPR

// A type expression is a sequence of non-newline chars after the colon,
// stopping at the next newline. We rely on the lexer greediness; the
// rule for `state_decl` uses NAME (before ":") so there's no ambiguity.
TYPE_EXPR: /[^\n]+/

PURPOSE_LINE: /[ \t]+[^\n]+/

NAME: /[A-Za-z_][A-Za-z0-9_]*/

%import common.NEWLINE
%import common.WS_INLINE
%ignore NEWLINE
%ignore WS_INLINE
```

- [ ] **Step 7.4: Extend the transformer**

Add these methods to `ConceptTransformer` in `concept_transformer.py` (keep existing methods):

```python
    from concept_lang.ast import StateDecl  # add this import at the top of the file
```

At the top of the file, change the import to:

```python
from concept_lang.ast import (
    ConceptAST,
    OperationalPrinciple,
    StateDecl,
)
```

Then add these methods inside the class (before `concept_def`):

```python
    def TYPE_EXPR(self, token: Token) -> str:
        return str(token).strip()

    def state_decl(self, name: str, type_expr: str) -> StateDecl:
        return StateDecl(name=name, type_expr=type_expr)

    def state_section(self, *decls: StateDecl) -> list[StateDecl]:
        return list(decls)
```

Update `concept_def` to consume an optional state section:

```python
    def concept_def(self, name: str, *rest) -> ConceptAST:
        params: list[str] = []
        purpose: str = ""
        state: list[StateDecl] = []
        for item in rest:
            if isinstance(item, list) and item and isinstance(item[0], str):
                params = item
            elif isinstance(item, list) and item and isinstance(item[0], StateDecl):
                state = item
            elif isinstance(item, str):
                purpose = item
        return ConceptAST(
            name=name,
            params=params,
            purpose=purpose,
            state=state,
            actions=[],
            operational_principle=OperationalPrinciple(steps=[]),
            source="",
        )
```

- [ ] **Step 7.5: Run tests — should pass**

Run: `uv run pytest tests/test_parse.py -v`
Expected: 4 passed.

- [ ] **Step 7.6: Commit**

```bash
git add src/concept_lang/grammars/concept.lark src/concept_lang/transformers/concept_transformer.py tests/test_parse.py
git commit -m "feat(parse): concept state section with set and relation types"
```

---

## Task 8: Concept grammar — action signature (`name [ inputs ] => [ outputs ]`)

**Files:**
- Modify: `src/concept_lang/grammars/concept.lark`
- Modify: `src/concept_lang/transformers/concept_transformer.py`
- Modify: `tests/test_parse.py`

- [ ] **Step 8.1: Write failing tests for action headers**

Append to `tests/test_parse.py`:

```python
class TestConceptActionHeaders:
    def test_single_action_no_body(self):
        src = """
concept Counter

  purpose
    increment a value

  actions
    increment [ amount: int ] => [ total: int ]
"""
        ast = parse_concept_source(src)
        assert len(ast.actions) == 1
        action = ast.actions[0]
        assert action.name == "increment"
        assert len(action.cases) == 1
        case = action.cases[0]
        assert [(i.name, i.type_expr) for i in case.inputs] == [("amount", "int")]
        assert [(o.name, o.type_expr) for o in case.outputs] == [("total", "int")]

    def test_empty_output(self):
        src = """
concept Logger

  purpose
    record events

  actions
    log [ message: string ] => [ ]
"""
        ast = parse_concept_source(src)
        action = ast.actions[0]
        assert action.cases[0].outputs == []

    def test_multiple_cases_grouped_by_name(self):
        src = """
concept Password [U]

  purpose
    store credentials

  actions
    set [ user: U ; password: string ] => [ user: U ]
    set [ user: U ; password: string ] => [ error: string ]
"""
        ast = parse_concept_source(src)
        assert len(ast.actions) == 1
        set_action = ast.actions[0]
        assert set_action.name == "set"
        assert len(set_action.cases) == 2
        assert set_action.cases[0].outputs[0].name == "user"
        assert set_action.cases[1].outputs[0].name == "error"
```

- [ ] **Step 8.2: Run — fails**

Run: `uv run pytest tests/test_parse.py::TestConceptActionHeaders -v`
Expected: parse errors on `actions` keyword.

- [ ] **Step 8.3: Extend `concept.lark` with an actions section and multi-case grouping**

Replace the full contents of `src/concept_lang/grammars/concept.lark` with:

```lark
// concept-lang 0.2.0 — concept grammar (header + purpose + state + actions headers)

start: concept_def

concept_def: "concept" NAME type_params? purpose_section state_section? actions_section?

type_params: "[" NAME ("," NAME)* "]"

purpose_section: "purpose" purpose_body
purpose_body: PURPOSE_LINE+

state_section: "state" state_decl+
state_decl: NAME ":" TYPE_EXPR

actions_section: "actions" action_case+

action_case: NAME "[" typed_name_list? "]" "=>" "[" typed_name_list? "]"

typed_name_list: typed_name (";" typed_name)*
typed_name: NAME ":" TYPE_REF

TYPE_EXPR: /[^\n]+/
TYPE_REF:  /[A-Za-z_][A-Za-z0-9_ \->]*/

PURPOSE_LINE: /[ \t]+[^\n]+/

NAME: /[A-Za-z_][A-Za-z0-9_]*/

%import common.NEWLINE
%import common.WS_INLINE
%ignore NEWLINE
%ignore WS_INLINE
```

(`TYPE_REF` is the more restricted type expression that appears inside
`[ name: TYPE ]` — it stops at `;` and `]`. `TYPE_EXPR` is the full-line
type used inside `state`.)

- [ ] **Step 8.4: Extend the transformer**

Update imports in `concept_transformer.py`:

```python
from concept_lang.ast import (
    Action,
    ActionCase,
    ConceptAST,
    OperationalPrinciple,
    StateDecl,
    TypedName,
)
```

Add methods inside `ConceptTransformer`:

```python
    def TYPE_REF(self, token: Token) -> str:
        return str(token).strip()

    def typed_name(self, name: str, type_ref: str) -> TypedName:
        return TypedName(name=name, type_expr=type_ref)

    def typed_name_list(self, *names: TypedName) -> list[TypedName]:
        return list(names)

    def action_case(self, name: str, *rest) -> tuple[str, ActionCase]:
        # rest contains up to two typed_name_list results (inputs, outputs),
        # each may be absent if the bracket was empty.
        inputs: list[TypedName] = []
        outputs: list[TypedName] = []
        list_args = [r for r in rest if isinstance(r, list)]
        if len(list_args) == 2:
            inputs, outputs = list_args
        elif len(list_args) == 1:
            # Disambiguate: the first `[...]` is inputs unless it's the second one.
            # Both sides are optional, so check position via rest order:
            if rest[0] is list_args[0]:
                inputs = list_args[0]
            else:
                outputs = list_args[0]
        return name, ActionCase(inputs=inputs, outputs=outputs, body=[], effects=[])

    def actions_section(self, *cases: tuple[str, ActionCase]) -> list[Action]:
        grouped: dict[str, list[ActionCase]] = {}
        order: list[str] = []
        for name, case in cases:
            if name not in grouped:
                grouped[name] = []
                order.append(name)
            grouped[name].append(case)
        return [Action(name=n, cases=grouped[n]) for n in order]
```

Update `concept_def` to accept the actions section:

```python
    def concept_def(self, name: str, *rest) -> ConceptAST:
        params: list[str] = []
        purpose: str = ""
        state: list[StateDecl] = []
        actions: list[Action] = []
        for item in rest:
            if isinstance(item, list) and item:
                head = item[0]
                if isinstance(head, str):
                    params = item
                elif isinstance(head, StateDecl):
                    state = item
                elif isinstance(head, Action):
                    actions = item
            elif isinstance(item, str):
                purpose = item
        return ConceptAST(
            name=name,
            params=params,
            purpose=purpose,
            state=state,
            actions=actions,
            operational_principle=OperationalPrinciple(steps=[]),
            source="",
        )
```

- [ ] **Step 8.5: Run tests — should pass**

Run: `uv run pytest tests/test_parse.py -v`
Expected: 7 passed.

- [ ] **Step 8.6: Commit**

```bash
git add src/concept_lang/grammars/concept.lark src/concept_lang/transformers/concept_transformer.py tests/test_parse.py
git commit -m "feat(parse): action case headers and multi-case grouping"
```

---

## Task 9: Concept grammar — action case body (natural-language lines + `effects:`)

**Files:**
- Modify: `src/concept_lang/grammars/concept.lark`
- Modify: `src/concept_lang/transformers/concept_transformer.py`
- Modify: `tests/test_parse.py`

- [ ] **Step 9.1: Write failing tests**

Append to `tests/test_parse.py`:

```python
class TestConceptActionBody:
    def test_natural_language_body(self):
        src = """
concept Password [U]

  purpose
    credentials

  state
    password: U -> string

  actions
    set [ user: U ; password: string ] => [ user: U ]
      generate a random salt
      compute the hash
      return the user
"""
        ast = parse_concept_source(src)
        case = ast.actions[0].cases[0]
        assert case.body == [
            "generate a random salt",
            "compute the hash",
            "return the user",
        ]
        assert case.effects == []

    def test_effects_clause(self):
        src = """
concept Password [U]

  purpose
    credentials

  state
    password: U -> string
    salt: U -> string

  actions
    set [ user: U ; password: string ] => [ user: U ]
      generate a random salt
      effects:
        password[user] := hash
        salt[user] := generated_salt
"""
        ast = parse_concept_source(src)
        case = ast.actions[0].cases[0]
        assert case.body == ["generate a random salt"]
        assert len(case.effects) == 2
        assert case.effects[0].field == "password"
        assert case.effects[0].op == ":="
        assert case.effects[0].rhs == "hash"
        assert case.effects[1].field == "salt"
```

- [ ] **Step 9.2: Run — fails**

Run: `uv run pytest tests/test_parse.py::TestConceptActionBody -v`
Expected: parse errors.

- [ ] **Step 9.3: Extend the grammar**

Replace `src/concept_lang/grammars/concept.lark` with:

```lark
// concept-lang 0.2.0 — concept grammar (through action bodies with effects:)

start: concept_def

concept_def: "concept" NAME type_params? purpose_section state_section? actions_section?

type_params: "[" NAME ("," NAME)* "]"

purpose_section: "purpose" purpose_body
purpose_body: PURPOSE_LINE+

state_section: "state" state_decl+
state_decl: NAME ":" TYPE_EXPR

actions_section: "actions" action_case+

action_case: NAME "[" typed_name_list? "]" "=>" "[" typed_name_list? "]" case_body?
case_body: (BODY_LINE)* effects_clause?

effects_clause: "effects" ":" effect_line+
effect_line: FIELD_REF EFFECT_OP EFFECT_RHS
FIELD_REF: /[A-Za-z_][A-Za-z0-9_]*(\[[A-Za-z_][A-Za-z0-9_]*\])?/
EFFECT_OP: ":=" | "+=" | "-="
EFFECT_RHS: /[^\n]+/

typed_name_list: typed_name (";" typed_name)*
typed_name: NAME ":" TYPE_REF

TYPE_EXPR: /[^\n]+/
TYPE_REF:  /[A-Za-z_][A-Za-z0-9_ \->]*/

// A body line is any indented line that is NOT a reserved keyword.
BODY_LINE: /[ \t]+(?!purpose|state|actions|operational|effects:|[A-Za-z_][A-Za-z0-9_]*\s*\[)[^\n]+/

PURPOSE_LINE: /[ \t]+[^\n]+/

NAME: /[A-Za-z_][A-Za-z0-9_]*/

%import common.NEWLINE
%import common.WS_INLINE
%ignore NEWLINE
%ignore WS_INLINE
```

The `BODY_LINE` regex uses a negative lookahead to avoid greedily consuming the next action header or section keyword.

- [ ] **Step 9.4: Extend the transformer**

Update `concept_transformer.py` imports:

```python
from concept_lang.ast import (
    Action,
    ActionCase,
    ConceptAST,
    EffectClause,
    OperationalPrinciple,
    StateDecl,
    TypedName,
)
```

Add methods:

```python
    def BODY_LINE(self, token: Token) -> str:
        return str(token).strip()

    def FIELD_REF(self, token: Token) -> str:
        return str(token).strip()

    def EFFECT_OP(self, token: Token) -> str:
        return str(token).strip()

    def EFFECT_RHS(self, token: Token) -> str:
        return str(token).strip()

    def effect_line(self, field_ref: str, op: str, rhs: str) -> EffectClause:
        # field_ref might be "password[user]" — strip the subscript to get the field name
        field_name = field_ref.split("[", 1)[0]
        return EffectClause(
            raw=f"{field_ref} {op} {rhs}",
            field=field_name,
            op=op,   # type: ignore[arg-type]
            rhs=rhs,
        )

    def effects_clause(self, *effects: EffectClause) -> list[EffectClause]:
        return list(effects)

    def case_body(self, *items) -> tuple[list[str], list[EffectClause]]:
        body_lines: list[str] = []
        effects: list[EffectClause] = []
        for item in items:
            if isinstance(item, str):
                body_lines.append(item)
            elif isinstance(item, list):
                effects = item  # the single effects_clause result
        return body_lines, effects
```

Update `action_case` to consume the optional body:

```python
    def action_case(self, name: str, *rest) -> tuple[str, ActionCase]:
        inputs: list[TypedName] = []
        outputs: list[TypedName] = []
        body_lines: list[str] = []
        effects: list[EffectClause] = []

        list_args = [r for r in rest if isinstance(r, list)]
        tuple_args = [r for r in rest if isinstance(r, tuple)]

        # Two `[...]` lists are inputs and outputs (in order).
        if len(list_args) == 2:
            inputs, outputs = list_args
        elif len(list_args) == 1:
            # Can only happen if one side is empty — disambiguate by position.
            idx_first_list = next(i for i, r in enumerate(rest) if isinstance(r, list))
            if idx_first_list == 0:
                # first thing after name is a list → inputs given, outputs empty
                inputs = list_args[0]
            else:
                outputs = list_args[0]

        if tuple_args:
            body_lines, effects = tuple_args[0]

        return name, ActionCase(
            inputs=inputs,
            outputs=outputs,
            body=body_lines,
            effects=effects,
        )
```

- [ ] **Step 9.5: Run tests — should pass**

Run: `uv run pytest tests/test_parse.py -v`
Expected: 9 passed.

- [ ] **Step 9.6: Commit**

```bash
git add src/concept_lang/grammars/concept.lark src/concept_lang/transformers/concept_transformer.py tests/test_parse.py
git commit -m "feat(parse): action case body with natural-language and effects:"
```

---

## Task 10: Concept grammar — `operational principle` section

**Files:**
- Modify: `src/concept_lang/grammars/concept.lark`
- Modify: `src/concept_lang/transformers/concept_transformer.py`
- Modify: `tests/test_parse.py`

- [ ] **Step 10.1: Write failing tests**

Append to `tests/test_parse.py`:

```python
class TestConceptOperationalPrinciple:
    def test_two_step_principle(self):
        src = """
concept Password [U]

  purpose
    credentials

  state
    password: U -> string

  actions
    set [ user: U ; password: string ] => [ user: U ]
    check [ user: U ; password: string ] => [ valid: boolean ]

  operational principle
    after set [ user: x ; password: "secret" ] => [ user: x ]
    then check [ user: x ; password: "secret" ] => [ valid: true ]
"""
        ast = parse_concept_source(src)
        op = ast.operational_principle
        assert len(op.steps) == 2
        assert op.steps[0].keyword == "after"
        assert op.steps[0].action_name == "set"
        assert op.steps[0].inputs == [("user", "x"), ("password", '"secret"')]
        assert op.steps[0].outputs == [("user", "x")]
        assert op.steps[1].keyword == "then"
        assert op.steps[1].action_name == "check"

    def test_and_step(self):
        src = """
concept Counter

  purpose
    count things

  actions
    inc [ ] => [ n: int ]
    read [ ] => [ n: int ]

  operational principle
    after inc [ ] => [ n: 1 ]
    and read [ ] => [ n: 1 ]
"""
        ast = parse_concept_source(src)
        assert ast.operational_principle.steps[1].keyword == "and"
```

- [ ] **Step 10.2: Run — fails**

Run: `uv run pytest tests/test_parse.py::TestConceptOperationalPrinciple -v`
Expected: parse error at `operational` keyword.

- [ ] **Step 10.3: Extend the grammar**

Append to `src/concept_lang/grammars/concept.lark` (and add `op_section?` to `concept_def`):

Replace the `concept_def` line with:

```lark
concept_def: "concept" NAME type_params? purpose_section state_section? actions_section? op_section?
```

Add these rules near the action rules:

```lark
op_section: "operational" "principle" op_step+
op_step: OP_KEYWORD NAME "[" op_arg_list? "]" "=>" "[" op_arg_list? "]"
OP_KEYWORD: "after" | "then" | "and"
op_arg_list: op_arg (";" op_arg)*
op_arg: NAME ":" OP_VALUE
OP_VALUE: /"[^"]*"|[A-Za-z0-9_]+/
```

- [ ] **Step 10.4: Extend the transformer**

Add these methods to `ConceptTransformer`:

```python
    def OP_KEYWORD(self, token: Token) -> str:
        return str(token)

    def OP_VALUE(self, token: Token) -> str:
        return str(token).strip()

    def op_arg(self, name: str, value: str) -> tuple[str, str]:
        return (name, value)

    def op_arg_list(self, *args: tuple[str, str]) -> list[tuple[str, str]]:
        return list(args)

    def op_step(self, keyword: str, action_name: str, *rest) -> "OPStep":
        from concept_lang.ast import OPStep
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
        return OPStep(
            keyword=keyword,  # type: ignore[arg-type]
            action_name=action_name,
            inputs=inputs,
            outputs=outputs,
        )

    def op_section(self, *steps) -> OperationalPrinciple:
        return OperationalPrinciple(steps=list(steps))
```

Update `concept_def` to collect the op section:

```python
    def concept_def(self, name: str, *rest) -> ConceptAST:
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
        return ConceptAST(
            name=name,
            params=params,
            purpose=purpose,
            state=state,
            actions=actions,
            operational_principle=op_principle,
            source="",
        )
```

- [ ] **Step 10.5: Run tests — should pass**

Run: `uv run pytest tests/test_parse.py -v`
Expected: 11 passed.

- [ ] **Step 10.6: Commit**

```bash
git add src/concept_lang/grammars/concept.lark src/concept_lang/transformers/concept_transformer.py tests/test_parse.py
git commit -m "feat(parse): operational principle section"
```

---

## Task 11: Sync grammar skeleton — header + basic `when` + simple `then`

**Files:**
- Create: `src/concept_lang/grammars/sync.lark`
- Create: `src/concept_lang/transformers/sync_transformer.py`
- Modify: `src/concept_lang/parse.py`
- Modify: `tests/test_parse.py`

- [ ] **Step 11.1: Write failing tests for sync parsing**

Append to `tests/test_parse.py`:

```python
from concept_lang.parse import parse_sync_source


class TestSyncBasic:
    def test_simple_when_then(self):
        src = """
sync LogEveryRequest

  when
    Web/request: [ ] => [ request: ?request ]
  then
    Log/append: [ event: ?request ]
"""
        sync = parse_sync_source(src)
        assert sync.name == "LogEveryRequest"
        assert len(sync.when) == 1
        assert sync.when[0].concept == "Web"
        assert sync.when[0].action == "request"
        assert sync.when[0].input_pattern == []
        assert len(sync.when[0].output_pattern) == 1
        assert sync.when[0].output_pattern[0].name == "request"
        assert sync.when[0].output_pattern[0].kind == "var"
        assert sync.when[0].output_pattern[0].value == "?request"
        assert len(sync.then) == 1
        assert sync.then[0].concept == "Log"
        assert sync.then[0].action == "append"

    def test_literal_in_when(self):
        src = """
sync OnRegister

  when
    Web/request: [ method: "register" ] => [ ]
  then
    Audit/log: [ kind: "register" ]
"""
        sync = parse_sync_source(src)
        assert sync.when[0].input_pattern[0].kind == "literal"
        assert sync.when[0].input_pattern[0].value == '"register"'
        assert sync.then[0].input_pattern[0].value == '"register"'
```

- [ ] **Step 11.2: Run — fails**

Run: `uv run pytest tests/test_parse.py::TestSyncBasic -v`
Expected: `ImportError: cannot import name 'parse_sync_source'`.

- [ ] **Step 11.3: Create the sync grammar**

Create `src/concept_lang/grammars/sync.lark`:

```lark
// concept-lang 0.2.0 — sync grammar (first slice: when + then)

start: sync_def

sync_def: "sync" NAME when_clause then_clause

when_clause: "when" action_pattern+
then_clause: "then" action_pattern+

action_pattern: NAME "/" NAME ":" pattern_list ("=>" pattern_list)?

pattern_list: "[" (pattern_field (";" pattern_field)*)? "]"

pattern_field: NAME ":" pattern_value
pattern_value: VAR | LITERAL

VAR: /\?[A-Za-z_][A-Za-z0-9_]*/
LITERAL: /"[^"]*"|[0-9]+|true|false/

NAME: /[A-Za-z_][A-Za-z0-9_]*/

%import common.NEWLINE
%import common.WS_INLINE
%ignore NEWLINE
%ignore WS_INLINE
```

- [ ] **Step 11.4: Create the sync transformer**

Create `src/concept_lang/transformers/sync_transformer.py`:

```python
"""Transform a Lark parse tree for a .sync file into a SyncAST."""

from lark import Token, Transformer, v_args

from concept_lang.ast import (
    ActionPattern,
    PatternField,
    SyncAST,
    WhereClause,
)


@v_args(inline=True)
class SyncTransformer(Transformer):

    # --- atoms ---------------------------------------------------------------

    def NAME(self, token: Token) -> str:
        return str(token)

    def VAR(self, token: Token) -> str:
        return str(token)

    def LITERAL(self, token: Token) -> str:
        return str(token)

    # --- pattern pieces ------------------------------------------------------

    def pattern_value(self, tok: str) -> tuple[str, str]:
        # tok is either a VAR or a LITERAL string (already transformed to str)
        kind = "var" if tok.startswith("?") else "literal"
        return kind, tok

    def pattern_field(self, name: str, value: tuple[str, str]) -> PatternField:
        kind, raw = value
        return PatternField(name=name, kind=kind, value=raw)  # type: ignore[arg-type]

    def pattern_list(self, *fields: PatternField) -> list[PatternField]:
        return list(fields)

    def action_pattern(
        self,
        concept: str,
        action: str,
        input_pattern: list[PatternField],
        output_pattern: list[PatternField] | None = None,
    ) -> ActionPattern:
        return ActionPattern(
            concept=concept,
            action=action,
            input_pattern=input_pattern,
            output_pattern=output_pattern if output_pattern is not None else [],
        )

    # --- sections ------------------------------------------------------------

    def when_clause(self, *patterns: ActionPattern) -> list[ActionPattern]:
        return list(patterns)

    def then_clause(self, *patterns: ActionPattern) -> list[ActionPattern]:
        return list(patterns)

    def sync_def(
        self,
        name: str,
        when: list[ActionPattern],
        then: list[ActionPattern],
    ) -> SyncAST:
        return SyncAST(
            name=name,
            when=when,
            where=None,
            then=then,
            source="",
        )

    def start(self, sync: SyncAST) -> SyncAST:
        return sync
```

- [ ] **Step 11.5: Add the sync parser to `parse.py`**

Append to `src/concept_lang/parse.py`:

```python
from concept_lang.ast import SyncAST
from concept_lang.transformers.sync_transformer import SyncTransformer


_sync_parser: Lark | None = None


def _get_sync_parser() -> Lark:
    global _sync_parser
    if _sync_parser is None:
        _sync_parser = Lark(
            read_grammar("sync.lark"),
            parser="earley",
            maybe_placeholders=False,
        )
    return _sync_parser


def parse_sync_source(source: str) -> SyncAST:
    """Parse sync source text into a SyncAST."""
    tree = _get_sync_parser().parse(source)
    ast = SyncTransformer().transform(tree)
    return ast.model_copy(update={"source": source})


def parse_sync_file(path: str | Path) -> SyncAST:
    """Parse a `.sync` file from disk."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_sync_source(text)
```

- [ ] **Step 11.6: Run tests — should pass**

Run: `uv run pytest tests/test_parse.py -v`
Expected: 13 passed.

- [ ] **Step 11.7: Commit**

```bash
git add src/concept_lang/grammars/sync.lark src/concept_lang/transformers/sync_transformer.py src/concept_lang/parse.py tests/test_parse.py
git commit -m "feat(parse): sync grammar with when/then clauses and pattern matching"
```

---

## Task 12: Sync grammar — `where` clause (state queries, binds, `optional`)

**Files:**
- Modify: `src/concept_lang/grammars/sync.lark`
- Modify: `src/concept_lang/transformers/sync_transformer.py`
- Modify: `tests/test_parse.py`

- [ ] **Step 12.1: Write failing tests**

Append to `tests/test_parse.py`:

```python
class TestSyncWhere:
    def test_bind_only(self):
        src = """
sync Register

  when
    Web/request: [ method: "register" ] => [ ]
  where
    bind (uuid() as ?user)
  then
    User/register: [ user: ?user ]
"""
        sync = parse_sync_source(src)
        assert sync.where is not None
        assert len(sync.where.binds) == 1
        assert sync.where.binds[0].variable == "?user"
        assert "uuid" in sync.where.binds[0].expression

    def test_state_query(self):
        src = """
sync FormatArticle

  when
    Web/format: [ article: ?article ] => [ ]
  where
    Article: {
      ?article title: ?title ;
               body: ?body
    }
  then
    Web/respond: [ title: ?title ]
"""
        sync = parse_sync_source(src)
        assert sync.where is not None
        assert len(sync.where.queries) == 1
        q = sync.where.queries[0]
        assert q.concept == "Article"
        assert q.is_optional is False
        assert len(q.triples) == 2
        assert q.triples[0].subject == "?article"
        assert q.triples[0].predicate == "title"
        assert q.triples[0].object == "?title"

    def test_optional_state_query(self):
        src = """
sync FormatWithTags

  when
    Web/format: [ article: ?article ] => [ ]
  where
    optional Tag: { ?article tag: ?tag }
  then
    Web/respond: [ tag: ?tag ]
"""
        sync = parse_sync_source(src)
        assert sync.where.queries[0].is_optional is True
```

- [ ] **Step 12.2: Run — fails**

Run: `uv run pytest tests/test_parse.py::TestSyncWhere -v`
Expected: parse errors on `where`.

- [ ] **Step 12.3: Extend the sync grammar**

Replace `src/concept_lang/grammars/sync.lark` with:

```lark
// concept-lang 0.2.0 — sync grammar (when + where + then)

start: sync_def

sync_def: "sync" NAME when_clause where_clause? then_clause

when_clause: "when" action_pattern+
then_clause: "then" action_pattern+
where_clause: "where" where_item+

where_item: state_query | optional_query | bind_clause

state_query: NAME ":" "{" triple_list "}"
optional_query: "optional" NAME ":" "{" triple_list "}"

triple_list: triple (";" triple)*
triple: VAR NAME ":" (VAR | LITERAL)

bind_clause: "bind" "(" BIND_EXPR "as" VAR ")"
BIND_EXPR: /[^)]+?(?= as )/

action_pattern: NAME "/" NAME ":" pattern_list ("=>" pattern_list)?
pattern_list: "[" (pattern_field (";" pattern_field)*)? "]"
pattern_field: NAME ":" pattern_value
pattern_value: VAR | LITERAL

VAR: /\?[A-Za-z_][A-Za-z0-9_]*/
LITERAL: /"[^"]*"|[0-9]+|true|false/
NAME: /[A-Za-z_][A-Za-z0-9_]*/

%import common.NEWLINE
%import common.WS_INLINE
%ignore NEWLINE
%ignore WS_INLINE
```

Note: the `triple` rule simplification here expects a *single* predicate per triple. The paper's richer "multiple predicates on one subject" (`?article title: ?t ; body: ?b`) is handled by the `triple_list` separator `;` — each `;` repeats the subject implicitly. We emit one `Triple` per predicate in the transformer.

**Important:** the simplified triple rule above does NOT carry the "shared subject" feature — if you write `?a title: ?t ; body: ?b`, the grammar parses this as two triples both starting with `?a`. To implement this, change `triple_list` to:

```lark
triple_list: triple (";" predicate_only)*
predicate_only: NAME ":" (VAR | LITERAL)
```

and have the transformer propagate the first triple's subject to the subsequent `predicate_only` entries.

- [ ] **Step 12.4: Extend the sync transformer**

Add to `sync_transformer.py`:

```python
from concept_lang.ast import (
    ActionPattern,
    BindClause,
    PatternField,
    StateQuery,
    SyncAST,
    Triple,
    WhereClause,
)
```

Add these methods:

```python
    def BIND_EXPR(self, token: Token) -> str:
        return str(token).strip()

    def triple(self, subject: str, predicate: str, obj: str) -> Triple:
        return Triple(subject=subject, predicate=predicate, object=obj)

    def predicate_only(self, predicate: str, obj: str) -> tuple[str, str]:
        return (predicate, obj)

    def triple_list(self, first: Triple, *rest) -> list[Triple]:
        triples = [first]
        shared_subject = first.subject
        for item in rest:
            # item is a tuple (predicate, object) from predicate_only
            predicate, obj = item
            triples.append(Triple(subject=shared_subject, predicate=predicate, object=obj))
        return triples

    def state_query(self, concept: str, triples: list[Triple]) -> StateQuery:
        return StateQuery(concept=concept, triples=triples, is_optional=False)

    def optional_query(self, concept: str, triples: list[Triple]) -> StateQuery:
        return StateQuery(concept=concept, triples=triples, is_optional=True)

    def bind_clause(self, expression: str, variable: str) -> BindClause:
        return BindClause(expression=expression.strip(), variable=variable)

    def where_clause(self, *items) -> WhereClause:
        queries: list[StateQuery] = []
        binds: list[BindClause] = []
        for item in items:
            if isinstance(item, StateQuery):
                queries.append(item)
            elif isinstance(item, BindClause):
                binds.append(item)
        return WhereClause(queries=queries, binds=binds)
```

Update `sync_def` to accept the optional where clause:

```python
    def sync_def(self, name: str, *rest) -> SyncAST:
        when: list[ActionPattern] = []
        then: list[ActionPattern] = []
        where: WhereClause | None = None
        # `when` always first, `then` always last; `where` is optional between them.
        if len(rest) == 2:
            when, then = rest
        elif len(rest) == 3:
            when, where, then = rest
        return SyncAST(name=name, when=when, where=where, then=then, source="")
```

- [ ] **Step 12.5: Run tests — should pass**

Run: `uv run pytest tests/test_parse.py -v`
Expected: 16 passed.

- [ ] **Step 12.6: Commit**

```bash
git add src/concept_lang/grammars/sync.lark src/concept_lang/transformers/sync_transformer.py tests/test_parse.py
git commit -m "feat(parse): sync where clause with state queries, optional, and binds"
```

---

## Task 13: Architecture-ide concept fixtures (LEARNING MODE CONTRIBUTION)

**Files:**
- Create: `tests/fixtures/architecture_ide/concepts/Workspace.concept`
- Create: `tests/fixtures/architecture_ide/concepts/Concept.concept`
- Create: `tests/fixtures/architecture_ide/concepts/DesignSession.concept`
- Create: `tests/fixtures/architecture_ide/concepts/Diagram.concept`

> **🎓 Learning mode opportunity**: The existing `architecture-ide/concepts/*.concept` files describe concept-lang itself — they're the self-hosting core. The agent can translate these to the new format mechanically, but **the *purpose*, operational principle, and choice of state fields for each are domain judgment calls**. The user should be invited to author these (or at minimum, the `operational principle` section of each) because they shape how concept-lang models itself going forward. Invite the user at Step 13.1.

- [ ] **Step 13.1: Invite the user to contribute**

Before writing any fixture file, pause and ask:

> "I'm about to write the 4 architecture-ide fixtures in the new format. These describe concept-lang itself, so the operational principles and action effects are genuinely your call — they model how the tool works. Do you want to write them yourself (I'll scaffold the headers and state sections), or should I take a first pass and have you review?"

Wait for the user's answer before proceeding.

- [ ] **Step 13.2: Create `Workspace.concept`**

If the user is authoring: provide this scaffold in the conversation and let them fill in the `operational principle` and refine the action bodies:

```
concept Workspace [Concept, Sync]

  purpose
    hold a collection of concepts and syncs that together describe a system

  state
    concepts: set Concept
    syncs: set Sync

  actions
    add_concept [ concept: Concept ] => [ workspace: Workspace ]
      place the concept in the workspace so it can be referenced by syncs
      effects:
        concepts += concept

    remove_concept [ concept: Concept ] => [ workspace: Workspace ]
      remove the concept if no sync depends on it
      effects:
        concepts -= concept

    add_sync [ sync: Sync ] => [ workspace: Workspace ]
      register a sync that ties concepts together
      effects:
        syncs += sync

    remove_sync [ sync: Sync ] => [ workspace: Workspace ]
      unregister a sync
      effects:
        syncs -= sync

  operational principle
    after add_concept [ concept: c ] => [ workspace: w ]
    and  add_sync    [ sync: s    ] => [ workspace: w ]
    then remove_sync  [ sync: s    ] => [ workspace: w ]
    and  remove_concept [ concept: c ] => [ workspace: w ]
```

If the user asks you to author from scratch, write the file as shown above.

Write the agreed-upon content to `tests/fixtures/architecture_ide/concepts/Workspace.concept`.

- [ ] **Step 13.3: Create `Concept.concept`**

Same flow as 13.2 — offer the following scaffold and defer to user preference on details:

```
concept Concept [Name, Designer]

  purpose
    define a named, self-contained unit of software functionality with explicit state and operations

  state
    named: set Name
    purposeful: set Name
    specified: set Name

  actions
    introduce [ name: Name ] => [ name: Name ]
      register a new concept by name
      effects:
        named += name

    articulate [ name: Name ] => [ name: Name ]
      state the concept's purpose
      effects:
        purposeful += name

    specify [ name: Name ] => [ name: Name ]
      fill in state, actions, and operational principle
      effects:
        specified += name

    revise [ name: Name ] => [ name: Name ]
      mark a specified concept as dirty for re-specification
      effects:
        specified -= name

    retire [ name: Name ] => [ name: Name ]
      remove a concept entirely
      effects:
        named -= name
        purposeful -= name
        specified -= name

  operational principle
    after introduce   [ name: c ] => [ name: c ]
    and  articulate   [ name: c ] => [ name: c ]
    and  specify      [ name: c ] => [ name: c ]
    then revise       [ name: c ] => [ name: c ]
    and  specify      [ name: c ] => [ name: c ]
```

Write to `tests/fixtures/architecture_ide/concepts/Concept.concept`.

- [ ] **Step 13.4: Create `DesignSession.concept`**

Scaffold (adjust to user preference):

```
concept DesignSession [Designer, Topic]

  purpose
    structure an iterative conversation in which a designer refines a single topic

  state
    sessions: set Topic
    active: set Topic

  actions
    start [ topic: Topic ; designer: Designer ] => [ topic: Topic ]
      begin a new design session on the topic
      effects:
        sessions += topic
        active += topic

    advance [ topic: Topic ] => [ topic: Topic ]
      move the session forward by one refinement step
      effects:

    finish [ topic: Topic ] => [ topic: Topic ]
      close the session; topic remains in sessions but no longer active
      effects:
        active -= topic

  operational principle
    after start   [ topic: t ; designer: d ] => [ topic: t ]
    and  advance  [ topic: t ] => [ topic: t ]
    then finish   [ topic: t ] => [ topic: t ]
```

Write to `tests/fixtures/architecture_ide/concepts/DesignSession.concept`.

- [ ] **Step 13.5: Create `Diagram.concept`**

Scaffold:

```
concept Diagram [Subject, Format]

  purpose
    produce a visual representation of a subject in a chosen output format

  state
    rendered: Subject -> Format

  actions
    render [ subject: Subject ; format: Format ] => [ subject: Subject ]
      generate a diagram for the subject in the given format
      effects:
        rendered[subject] := format

    invalidate [ subject: Subject ] => [ subject: Subject ]
      drop the rendering so the next render call regenerates
      effects:
        rendered -= subject

  operational principle
    after render     [ subject: s ; format: f ] => [ subject: s ]
    then invalidate  [ subject: s ] => [ subject: s ]
    and  render      [ subject: s ; format: f ] => [ subject: s ]
```

Write to `tests/fixtures/architecture_ide/concepts/Diagram.concept`.

- [ ] **Step 13.6: Commit the concept fixtures**

```bash
git add tests/fixtures/architecture_ide/concepts/
git commit -m "test: architecture-ide concept fixtures in paper format"
```

---

## Task 14: Architecture-ide sync fixtures (LEARNING MODE CONTRIBUTION)

**Files:**
- Create: `tests/fixtures/architecture_ide/syncs/specify_draws_diagram.sync`
- Create: `tests/fixtures/architecture_ide/syncs/session_introduces.sync`
- Create: `tests/fixtures/architecture_ide/syncs/workspace_tracks_concept.sync`

> **🎓 Learning mode opportunity**: Syncs encode *design decisions* about how concepts compose. The user's judgment matters here — should specifying a concept automatically render its diagram, or only on demand? The answer is a design call, not a technical one. Invite the user again.

- [ ] **Step 14.1: Invite the user**

Ask: "Same thing for syncs — these encode how the 4 architecture-ide concepts wire together. I've got proposals, but they're your architecture. Review and tweak, or take them as-is?"

- [ ] **Step 14.2: Create `specify_draws_diagram.sync`**

Scaffold:

```
sync SpecifyDrawsDiagram

  when
    Concept/specify: [ name: ?name ] => [ name: ?name ]
  then
    Diagram/render: [ subject: ?name ; format: "svg" ]
```

Write to `tests/fixtures/architecture_ide/syncs/specify_draws_diagram.sync`.

- [ ] **Step 14.3: Create `session_introduces.sync`**

Scaffold:

```
sync SessionIntroduces

  when
    DesignSession/start: [ topic: ?topic ; designer: ?designer ] => [ topic: ?topic ]
  then
    Concept/introduce: [ name: ?topic ]
```

Write to `tests/fixtures/architecture_ide/syncs/session_introduces.sync`.

- [ ] **Step 14.4: Create `workspace_tracks_concept.sync`**

Scaffold:

```
sync WorkspaceTracksConcept

  when
    Concept/introduce: [ name: ?name ] => [ name: ?name ]
  then
    Workspace/add_concept: [ concept: ?name ]
```

Write to `tests/fixtures/architecture_ide/syncs/workspace_tracks_concept.sync`.

- [ ] **Step 14.5: Commit the sync fixtures**

```bash
git add tests/fixtures/architecture_ide/syncs/
git commit -m "test: architecture-ide sync fixtures in paper format"
```

---

## Task 15: Test — all architecture-ide fixtures parse clean

**Files:**
- Modify: `tests/test_parse.py`

- [ ] **Step 15.1: Write the fixture parse test**

Append to `tests/test_parse.py`:

```python
from pathlib import Path

from concept_lang.parse import parse_concept_file, parse_sync_file


FIXTURES_ROOT = Path(__file__).parent / "fixtures"


class TestArchitectureIdeFixtures:
    def test_all_concepts_parse(self):
        concepts_dir = FIXTURES_ROOT / "architecture_ide" / "concepts"
        files = sorted(concepts_dir.glob("*.concept"))
        assert len(files) == 4, f"Expected 4 concept fixtures, found {len(files)}"
        for f in files:
            ast = parse_concept_file(f)
            assert ast.name  # smoke check
            assert ast.purpose  # must be set
            assert ast.operational_principle.steps, f"{f.name}: empty op principle"

    def test_all_syncs_parse(self):
        syncs_dir = FIXTURES_ROOT / "architecture_ide" / "syncs"
        files = sorted(syncs_dir.glob("*.sync"))
        assert len(files) == 3, f"Expected 3 sync fixtures, found {len(files)}"
        for f in files:
            sync = parse_sync_file(f)
            assert sync.name
            assert sync.when
            assert sync.then
```

- [ ] **Step 15.2: Run the test**

Run: `uv run pytest tests/test_parse.py::TestArchitectureIdeFixtures -v`
Expected: 2 passed.

If any fixture fails to parse, the grammar or the fixture file is wrong; fix one or the other before proceeding. Prefer fixing the fixture (grammar is what we're defining).

- [ ] **Step 15.3: Commit**

```bash
git add tests/test_parse.py
git commit -m "test: architecture-ide fixture workspace parses clean"
```

---

## Task 16: Realworld concept fixtures — `User`, `Password`, `Profile`

**Files:**
- Create: `tests/fixtures/realworld/concepts/User.concept`
- Create: `tests/fixtures/realworld/concepts/Password.concept`
- Create: `tests/fixtures/realworld/concepts/Profile.concept`

- [ ] **Step 16.1: Create `User.concept` (paper Appendix B.1)**

Write `tests/fixtures/realworld/concepts/User.concept` with exactly this content (lifted from the paper):

```
concept User [U]

  purpose
    to associate identifying information with users

  state
    users: set U
    name: U -> string
    email: U -> string

  actions
    register [ user: U ; name: string ; email: string ] => [ user: U ]
      associate user with users
      associate name and email unique + valid
      return the user reference

    register [ user: U ; name: string ; email: string ] => [ error: string ]
      if either name/email is invalid or not unique
      return the error description

    update [ user: U ; name: string ] => [ user: U ]
      if name is unique, update user's name
      return the user reference

    update [ user: U ; name: string ] => [ error: string ]
      if name is not-unique, describe error
      return the error description

    update [ user: U ; email: string ] => [ user: U ]
      if email is unique + valid, update id's email
      return the user reference

    update [ user: U ; email: string ] => [ error: string ]
      if email is not-unique or invalid
      return the error description

  operational principle
    after register [ user: x ; name: "xavier" ; email: "x@ex.com" ] => [ user: x ]
    and update [ user: x ; name: "xavier" ] => [ user: x ]
    then update [ user: x ; name: "xavier" ] => [ user: x ]
```

- [ ] **Step 16.2: Create `Password.concept` (paper §4)**

Write `tests/fixtures/realworld/concepts/Password.concept`:

```
concept Password [U]

  purpose
    to securely store and validate user credentials

  state
    password: U -> string
    salt: U -> string

  actions
    set [ user: U ; password: string ] => [ user: U ]
      generate a random salt for the user
      compute a hash of the password with the salt
      store the hash and the salt
      return the user reference
      effects:
        password[user] := hash
        salt[user] := generated_salt

    set [ user: U ; password: string ] => [ error: string ]
      if password does not meet complexity requirements
      return the error description

    check [ user: U ; password: string ] => [ valid: boolean ]
      retrieve salt for the user
      compute hash of the provided password with that salt
      compare with the stored hash
      return true if hashes match, false otherwise

    validate [ password: string ] => [ valid: boolean ]
      check that the password meets requirements
      return true if valid, false otherwise

  operational principle
    after set [ user: x ; password: "secret" ] => [ user: x ]
    then check [ user: x ; password: "secret" ] => [ valid: true ]
    and check [ user: x ; password: "wrong" ] => [ valid: false ]
```

- [ ] **Step 16.3: Create `Profile.concept` (paper Appendix B.2)**

Write `tests/fixtures/realworld/concepts/Profile.concept`:

```
concept Profile [P, U]

  purpose
    to associate descriptive information with users

  state
    profiles: set P
    profile: U -> P
    bio: P -> string
    image: P -> string

  actions
    register [ profile: P ; user: U ] => [ profile: P ]
      add profile to profiles
      associate user with profile
      add a default blank bio and image to profile
      return profile
      effects:
        profiles += profile

    update [ profile: P ; bio: string ] => [ profile: P ]
      update profile with bio
      return profile
      effects:
        bio[profile] := bio

    update [ profile: P ; image: string ] => [ profile: P ]
      if image is valid URL, base64, etc.
      update profile with image
      return profile
      effects:
        image[profile] := image

    update [ profile: P ; image: string ] => [ error: string ]
      if image is invalid, describe error
      return error

  operational principle
    after register [ profile: p ; user: u ] => [ profile: p ]
    and update [ profile: p ; bio: "Hello world" ] => [ profile: p ]
    and update [ profile: p ; image: "pic.jpg" ] => [ profile: p ]
    then update [ profile: p ; bio: "Hello world" ] => [ profile: p ]
```

- [ ] **Step 16.4: Quick parse smoke check**

Run: `uv run python -c "from concept_lang.parse import parse_concept_file; parse_concept_file('tests/fixtures/realworld/concepts/User.concept'); parse_concept_file('tests/fixtures/realworld/concepts/Password.concept'); parse_concept_file('tests/fixtures/realworld/concepts/Profile.concept'); print('ok')"`
Expected: `ok`.

If any file fails, the paper-lifted content is fine — the grammar needs a fix. Trace the exact error, update `concept.lark` and/or the transformer, re-run until clean. Make a separate commit for the fix before committing the fixtures.

- [ ] **Step 16.5: Commit**

```bash
git add tests/fixtures/realworld/concepts/
git commit -m "test: realworld User, Password, Profile concepts (paper §4, App B)"
```

---

## Task 17: Realworld concept fixtures — `Article`, `Web`, `JWT`

**Files:**
- Create: `tests/fixtures/realworld/concepts/Article.concept`
- Create: `tests/fixtures/realworld/concepts/Web.concept`
- Create: `tests/fixtures/realworld/concepts/JWT.concept`

- [ ] **Step 17.1: Create `Article.concept` (abbreviated from the paper's case study)**

Write `tests/fixtures/realworld/concepts/Article.concept`:

```
concept Article [A, U]

  purpose
    to publish authored content that other users can read

  state
    articles: set A
    title: A -> string
    description: A -> string
    body: A -> string
    slug: A -> string
    author: A -> U
    createdAt: A -> string
    updatedAt: A -> string

  actions
    create [ article: A ; title: string ; description: string ; body: string ; author: U ] => [ article: A ]
      publish a new article with the given title, description, body, and author
      assign a slug derived from the title
      record the creation timestamp
      effects:
        articles += article
        title[article] := title
        description[article] := description
        body[article] := body
        author[article] := author

    update [ article: A ; body: string ] => [ article: A ]
      replace the article body and update the modified timestamp
      effects:
        body[article] := body

    delete [ article: A ] => [ article: A ]
      remove the article from the published set
      effects:
        articles -= article

  operational principle
    after create [ article: a ; title: "Hello" ; description: "intro" ; body: "text" ; author: u ] => [ article: a ]
    then update [ article: a ; body: "new text" ] => [ article: a ]
    and delete [ article: a ] => [ article: a ]
```

- [ ] **Step 17.2: Create `Web.concept` (bootstrap concept)**

Write `tests/fixtures/realworld/concepts/Web.concept`:

```
concept Web

  purpose
    translate external HTTP traffic into concept actions and back

  state
    requests: set string

  actions
    request [ method: string ; path: string ] => [ request: string ]
      record an incoming HTTP request
      effects:
        requests += request

    respond [ request: string ; body: string ; code: int ] => [ request: string ]
      send the final response for a request

    format [ type: string ; request: string ] => [ request: string ]
      format a response body for a particular content type

  operational principle
    after request [ method: "GET" ; path: "/articles" ] => [ request: r ]
    then respond [ request: r ; body: "..." ; code: 200 ] => [ request: r ]
```

- [ ] **Step 17.3: Create `JWT.concept` (bootstrap concept)**

Write `tests/fixtures/realworld/concepts/JWT.concept`:

```
concept JWT [U]

  purpose
    mint and verify bearer tokens that identify users

  state
    tokens: set string
    token: U -> string

  actions
    generate [ user: U ] => [ token: string ]
      mint a fresh signed token for the user
      effects:
        tokens += token
        token[user] := token

    verify [ token: string ] => [ user: U ]
      validate the token signature and return the identified user

    verify [ token: string ] => [ error: string ]
      if the token is missing, malformed, or expired
      return the error description

  operational principle
    after generate [ user: x ] => [ token: t ]
    then verify [ token: t ] => [ user: x ]
```

- [ ] **Step 17.4: Parse smoke check**

Run: `uv run python -c "from concept_lang.parse import parse_concept_file; parse_concept_file('tests/fixtures/realworld/concepts/Article.concept'); parse_concept_file('tests/fixtures/realworld/concepts/Web.concept'); parse_concept_file('tests/fixtures/realworld/concepts/JWT.concept'); print('ok')"`
Expected: `ok`.

- [ ] **Step 17.5: Commit**

```bash
git add tests/fixtures/realworld/concepts/
git commit -m "test: realworld Article, Web, JWT bootstrap concepts"
```

---

## Task 18: Realworld sync fixtures — registration flow (`register_user`, `register_set_password`, `register_error`)

**Files:**
- Create: `tests/fixtures/realworld/syncs/register_user.sync`
- Create: `tests/fixtures/realworld/syncs/register_set_password.sync`
- Create: `tests/fixtures/realworld/syncs/register_error.sync`

- [ ] **Step 18.1: Create `register_user.sync` (paper §5.1)**

Write `tests/fixtures/realworld/syncs/register_user.sync`:

```
sync RegisterUser

  when
    Web/request: [ method: "register" ; username: ?username ; email: ?email ] => [ request: ?request ]
  where
    bind (uuid() as ?user)
  then
    User/register: [ user: ?user ; name: ?username ; email: ?email ]
```

- [ ] **Step 18.2: Create `register_set_password.sync` (paper §5.2)**

Write `tests/fixtures/realworld/syncs/register_set_password.sync`:

```
sync RegisterSetPassword

  when
    Web/request: [ method: "register" ; password: ?password ] => [ ]
    User/register: [ ] => [ user: ?user ]
  then
    Password/set: [ user: ?user ; password: ?password ]
```

- [ ] **Step 18.3: Create `register_error.sync` (paper §5.3)**

Write `tests/fixtures/realworld/syncs/register_error.sync`:

```
sync RegisterError

  when
    Web/request: [ ] => [ request: ?request ]
    User/register: [ ] => [ error: ?error ]
  then
    Web/respond: [ request: ?request ; body: ?error ; code: 422 ]
```

- [ ] **Step 18.4: Parse smoke check**

Run: `uv run python -c "from concept_lang.parse import parse_sync_file; parse_sync_file('tests/fixtures/realworld/syncs/register_user.sync'); parse_sync_file('tests/fixtures/realworld/syncs/register_set_password.sync'); parse_sync_file('tests/fixtures/realworld/syncs/register_error.sync'); print('ok')"`
Expected: `ok`.

- [ ] **Step 18.5: Commit**

```bash
git add tests/fixtures/realworld/syncs/
git commit -m "test: realworld registration sync fixtures (paper §5.1–5.3)"
```

---

## Task 19: Realworld sync fixtures — `register_default_profile`, `new_user_token`, `format_article`

**Files:**
- Create: `tests/fixtures/realworld/syncs/register_default_profile.sync`
- Create: `tests/fixtures/realworld/syncs/new_user_token.sync`
- Create: `tests/fixtures/realworld/syncs/format_article.sync`

- [ ] **Step 19.1: Create `register_default_profile.sync` (paper §5.4)**

Write `tests/fixtures/realworld/syncs/register_default_profile.sync`:

```
sync RegisterDefaultProfile

  when
    User/register: [ ] => [ user: ?user ]
  where
    bind (uuid() as ?profile)
  then
    Profile/register: [ profile: ?profile ; user: ?user ]
```

- [ ] **Step 19.2: Create `new_user_token.sync` (paper §5.4)**

Write `tests/fixtures/realworld/syncs/new_user_token.sync`:

```
sync NewUserToken

  when
    User/register: [ ] => [ user: ?user ]
  then
    JWT/generate: [ user: ?user ]
```

- [ ] **Step 19.3: Create `format_article.sync` (paper §5.5 — simplified)**

Write `tests/fixtures/realworld/syncs/format_article.sync`:

```
sync FormatArticle

  when
    Web/format: [ type: "article" ; article: ?article ; request: ?request ] => [ ]
  where
    Article: {
      ?article title: ?title ;
               description: ?description ;
               body: ?body ;
               author: ?author
    }
    User: { ?author name: ?authorName }
    optional Tag: { ?article tag: ?tag }
    optional Favorite: { ?article count: ?count }
  then
    Web/respond: [ request: ?request ; body: ?title ; code: 200 ]
```

(The full paper example has a richer `Web/respond` body shape; we simplify because the nested body literal is not yet in our grammar. We keep the `where` clause intact so the OPTIONAL and multi-triple shared-subject behavior is exercised.)

- [ ] **Step 19.4: Parse smoke check**

Run: `uv run python -c "from concept_lang.parse import parse_sync_file; parse_sync_file('tests/fixtures/realworld/syncs/register_default_profile.sync'); parse_sync_file('tests/fixtures/realworld/syncs/new_user_token.sync'); parse_sync_file('tests/fixtures/realworld/syncs/format_article.sync'); print('ok')"`
Expected: `ok`.

- [ ] **Step 19.5: Commit**

```bash
git add tests/fixtures/realworld/syncs/
git commit -m "test: realworld default profile, JWT, format article syncs (paper §5.4–5.5)"
```

---

## Task 20: Test — all realworld fixtures parse clean

**Files:**
- Modify: `tests/test_parse.py`

- [ ] **Step 20.1: Write the realworld parse test**

Append to `tests/test_parse.py`:

```python
class TestRealworldFixtures:
    def test_all_concepts_parse(self):
        concepts_dir = FIXTURES_ROOT / "realworld" / "concepts"
        files = sorted(concepts_dir.glob("*.concept"))
        assert len(files) == 6, f"Expected 6 concept fixtures, found {len(files)}"
        for f in files:
            ast = parse_concept_file(f)
            assert ast.name
            assert ast.purpose, f"{f.name}: missing purpose"
            # Bootstrap Web is the one concept that might legitimately have no type params
            # — just assert parse succeeds for every file.

    def test_all_syncs_parse(self):
        syncs_dir = FIXTURES_ROOT / "realworld" / "syncs"
        files = sorted(syncs_dir.glob("*.sync"))
        assert len(files) == 6, f"Expected 6 sync fixtures, found {len(files)}"
        for f in files:
            sync = parse_sync_file(f)
            assert sync.name
            assert sync.when
            assert sync.then
```

- [ ] **Step 20.2: Run the realworld test**

Run: `uv run pytest tests/test_parse.py::TestRealworldFixtures -v`
Expected: 2 passed.

If any fixture fails, fix the grammar/transformer (not the fixture — fixtures are paper-faithful).

- [ ] **Step 20.3: Commit**

```bash
git add tests/test_parse.py
git commit -m "test: realworld fixture workspace parses clean"
```

---

## Task 21: P1 gate — meta-test covering every positive fixture

**Files:**
- Modify: `tests/test_parse.py`

- [ ] **Step 21.1: Write the gate test**

Append to `tests/test_parse.py`:

```python
class TestP1Gate:
    """
    The P1 gate from the paper-alignment spec: every positive fixture
    must parse cleanly into a ConceptAST or SyncAST without exceptions,
    and every ConceptAST must have a non-empty purpose and operational
    principle, and every SyncAST must have a non-empty when and then.
    """

    def test_all_positive_fixtures_parse(self):
        concept_files = list(FIXTURES_ROOT.rglob("*.concept"))
        sync_files = list(FIXTURES_ROOT.rglob("*.sync"))

        # Expected totals: 4 (architecture_ide) + 6 (realworld) concepts; 3 + 6 syncs.
        assert len(concept_files) == 10, f"Found {len(concept_files)} concept files"
        assert len(sync_files) == 9, f"Found {len(sync_files)} sync files"

        for f in concept_files:
            ast = parse_concept_file(f)
            assert ast.name, f"{f}: empty name"
            assert ast.purpose, f"{f}: empty purpose"
            assert ast.operational_principle.steps, f"{f}: empty operational principle"

        for f in sync_files:
            sync = parse_sync_file(f)
            assert sync.name, f"{f}: empty name"
            assert sync.when, f"{f}: empty when"
            assert sync.then, f"{f}: empty then"
```

- [ ] **Step 21.2: Run the full test suite**

Run: `uv run pytest tests/test_parse.py tests/test_ast.py -v`
Expected: all tests pass (parser + AST + fixture gates).

- [ ] **Step 21.3: Run the whole project's test suite to confirm nothing v1-side broke**

Run: `uv run pytest -v`
Expected: all passing, including the pre-existing `test_validator.py` and `test_diff.py` (v1 code is untouched).

- [ ] **Step 21.4: Commit the gate**

```bash
git add tests/test_parse.py
git commit -m "test(gate): P1 gate — all positive fixtures parse clean"
```

- [ ] **Step 21.5: Tag the milestone**

```bash
git tag p1-parser-complete -m "P1 gate passed: new parser + AST cover all fixtures"
```

- [ ] **Step 21.6: Final status check**

Run: `git log --oneline -25`
Expected: ~20 small commits all in the `feat(ast)` / `feat(parse)` / `test` / `build` namespace, ending with `test(gate)` and the tag.

---

## What's next (not in this plan)

After this plan lands and the `p1-parser-complete` tag is in place, the follow-up plans are:

- **P2 — Validator**: implement rules `C1`–`S5` with negative fixtures, one rule per task.
- **P3 — Workspace loader**: `load_workspace()`, cross-file reference resolution, `Workspace` diagnostics aggregation.
- **P4 — Tooling migration**: rewire MCP tools, `diff.py`, `explorer.py`, `app_parser.py` to the new AST.
- **P5 — Skills rewrite**: `build`, `build-sync`, `review`, `scaffold`, `explore`.
- **P6 — Examples + docs**: update `architecture-ide/concepts/*` in place, rewrite `README.md`, add `docs/methodology.md`.
- **P7 — Delete v1**: remove old parser/models/validator/tests.

Each deserves its own plan, written after the preceding phase lands so we're planning on verified ground.
