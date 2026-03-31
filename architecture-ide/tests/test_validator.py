"""Tests for static validation and consistency checking."""

import pytest
from concept_lang.models import (
    Action, ConceptAST, PrePost, StateDecl, SyncClause, SyncInvocation,
)
from concept_lang.parser import parse_concept
from concept_lang.validator import (
    Severity, validate_concept, validate_workspace,
)


def _make_concept(
    name: str = "Test",
    params: list[str] | None = None,
    state: list[StateDecl] | None = None,
    actions: list[Action] | None = None,
    sync: list[SyncClause] | None = None,
) -> ConceptAST:
    return ConceptAST(
        name=name,
        params=params or [],
        purpose="test concept",
        state=state or [],
        actions=actions or [],
        sync=sync or [],
        source="",
    )


# ---------------------------------------------------------------------------
# Unique names
# ---------------------------------------------------------------------------


class TestUniqueNames:
    def test_duplicate_state(self):
        ast = _make_concept(state=[
            StateDecl(name="items", type_expr="set Item"),
            StateDecl(name="items", type_expr="set Item"),
        ])
        result = validate_concept(ast)
        assert not result.valid
        assert any("Duplicate state" in i.message for i in result.issues)

    def test_duplicate_action(self):
        ast = _make_concept(actions=[
            Action(name="add", params=["x: Item"]),
            Action(name="add", params=["y: Item"]),
        ])
        result = validate_concept(ast)
        assert not result.valid
        assert any("Duplicate action" in i.message for i in result.issues)

    def test_unique_names_pass(self):
        ast = _make_concept(
            state=[StateDecl(name="items", type_expr="set Item")],
            actions=[Action(name="add", params=["x: Item"])],
        )
        result = validate_concept(ast)
        assert result.valid


# ---------------------------------------------------------------------------
# State consistency
# ---------------------------------------------------------------------------


class TestStateConsistency:
    def test_valid_subset(self):
        ast = _make_concept(state=[
            StateDecl(name="all", type_expr="set User"),
            StateDecl(name="active", type_expr="all"),
        ])
        result = validate_concept(ast)
        assert result.valid

    def test_invalid_subset_ref(self):
        ast = _make_concept(state=[
            StateDecl(name="active", type_expr="nonexistent"),
        ])
        result = validate_concept(ast)
        assert not result.valid
        assert any("undefined state variable" in i.message for i in result.issues)

    def test_valid_relation(self):
        ast = _make_concept(state=[
            StateDecl(name="users", type_expr="set User"),
            StateDecl(name="roles", type_expr="users -> set Role"),
        ])
        result = validate_concept(ast)
        assert result.valid

    def test_invalid_relation_parent(self):
        ast = _make_concept(state=[
            StateDecl(name="roles", type_expr="missing -> set Role"),
        ])
        result = validate_concept(ast)
        assert not result.valid
        assert any("undefined parent" in i.message for i in result.issues)

    def test_uppercase_type_not_flagged(self):
        """Uppercase type_expr like 'User' is treated as a type, not a state ref."""
        ast = _make_concept(state=[
            StateDecl(name="current", type_expr="User"),
        ])
        result = validate_concept(ast)
        assert result.valid


# ---------------------------------------------------------------------------
# Action pre/post clause references
# ---------------------------------------------------------------------------


class TestActionClauses:
    def test_valid_pre_post(self):
        ast = _make_concept(
            state=[
                StateDecl(name="items", type_expr="set Item"),
                StateDecl(name="active", type_expr="items"),
            ],
            actions=[Action(
                name="activate",
                params=["x: Item"],
                pre=PrePost(clauses=["x in items"]),
                post=PrePost(clauses=["active += x"]),
            )],
        )
        result = validate_concept(ast)
        assert result.valid

    def test_pre_references_undefined_state(self):
        ast = _make_concept(
            state=[StateDecl(name="items", type_expr="set Item")],
            actions=[Action(
                name="activate",
                params=["x: Item"],
                pre=PrePost(clauses=["x in nonexistent"]),
            )],
        )
        result = validate_concept(ast)
        assert not result.valid
        assert any("undefined state variable 'nonexistent'" in i.message for i in result.issues)

    def test_post_references_undefined_state(self):
        ast = _make_concept(
            state=[StateDecl(name="items", type_expr="set Item")],
            actions=[Action(
                name="remove",
                params=["x: Item"],
                post=PrePost(clauses=["missing -= x"]),
            )],
        )
        result = validate_concept(ast)
        assert not result.valid

    def test_not_in_clause(self):
        ast = _make_concept(
            state=[StateDecl(name="items", type_expr="set Item")],
            actions=[Action(
                name="add",
                params=["x: Item"],
                pre=PrePost(clauses=["x not in items"]),
                post=PrePost(clauses=["items += x"]),
            )],
        )
        result = validate_concept(ast)
        assert result.valid

    def test_indexed_state_ref(self):
        """contains[w] += c should recognize 'contains' as the state ref."""
        ast = _make_concept(
            state=[
                StateDecl(name="workspaces", type_expr="set Workspace"),
                StateDecl(name="contains", type_expr="workspaces -> set Item"),
            ],
            actions=[Action(
                name="add",
                params=["w: Workspace", "c: Item"],
                pre=PrePost(clauses=["w in workspaces"]),
                post=PrePost(clauses=["contains[w] += c"]),
            )],
        )
        result = validate_concept(ast)
        assert result.valid


# ---------------------------------------------------------------------------
# Sync invocation validation
# ---------------------------------------------------------------------------


class TestSyncInvocations:
    def test_valid_sync(self):
        ast = _make_concept(
            actions=[Action(name="process", params=["x: Item"])],
            sync=[SyncClause(
                trigger_concept="Other",
                trigger_action="create",
                trigger_params=["x"],
                invocations=[SyncInvocation(action="process", params=["x"])],
            )],
        )
        result = validate_concept(ast)
        assert result.valid

    def test_sync_references_undefined_action(self):
        ast = _make_concept(
            actions=[Action(name="process", params=["x: Item"])],
            sync=[SyncClause(
                trigger_concept="Other",
                trigger_action="create",
                trigger_params=["x"],
                invocations=[SyncInvocation(action="nonexistent", params=["x"])],
            )],
        )
        result = validate_concept(ast)
        assert not result.valid
        assert any("undefined action 'nonexistent'" in i.message for i in result.issues)

    def test_sync_wrong_param_count(self):
        ast = _make_concept(
            actions=[Action(name="process", params=["x: Item", "y: Other"])],
            sync=[SyncClause(
                trigger_concept="Other",
                trigger_action="create",
                trigger_params=["x"],
                invocations=[SyncInvocation(action="process", params=["x"])],
            )],
        )
        result = validate_concept(ast)
        # Should have a warning about param count mismatch
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert any("2" in i.message and "1" in i.message for i in warnings)


# ---------------------------------------------------------------------------
# Cross-concept validation
# ---------------------------------------------------------------------------


class TestWorkspaceValidation:
    def _concept_a(self):
        return _make_concept(
            name="Auth",
            actions=[Action(name="login", params=["u: User"])],
        )

    def _concept_b(self):
        return _make_concept(
            name="Session",
            actions=[Action(name="open", params=["u: User"])],
            sync=[SyncClause(
                trigger_concept="Auth",
                trigger_action="login",
                trigger_params=["u"],
                invocations=[SyncInvocation(action="open", params=["u"])],
            )],
        )

    def test_valid_cross_concept(self):
        result = validate_workspace([self._concept_a(), self._concept_b()])
        assert result.valid

    def test_trigger_action_missing(self):
        session = _make_concept(
            name="Session",
            actions=[Action(name="open", params=["u: User"])],
            sync=[SyncClause(
                trigger_concept="Auth",
                trigger_action="nonexistent",
                trigger_params=["u"],
                invocations=[SyncInvocation(action="open", params=["u"])],
            )],
        )
        result = validate_workspace([self._concept_a(), session])
        assert not result.valid
        assert any("no action 'nonexistent'" in i.message for i in result.issues)

    def test_trigger_concept_missing_warns(self):
        session = _make_concept(
            name="Session",
            actions=[Action(name="open", params=["u: User"])],
            sync=[SyncClause(
                trigger_concept="Missing",
                trigger_action="something",
                trigger_params=["u"],
                invocations=[SyncInvocation(action="open", params=["u"])],
            )],
        )
        result = validate_workspace([session])
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert any("not in the workspace" in i.message for i in warnings)

    def test_dependency_cycle(self):
        a = _make_concept(
            name="A",
            actions=[Action(name="do_a", params=[])],
            sync=[SyncClause(
                trigger_concept="B",
                trigger_action="do_b",
                trigger_params=[],
                invocations=[SyncInvocation(action="do_a", params=[])],
            )],
        )
        b = _make_concept(
            name="B",
            actions=[Action(name="do_b", params=[])],
            sync=[SyncClause(
                trigger_concept="A",
                trigger_action="do_a",
                trigger_params=[],
                invocations=[SyncInvocation(action="do_b", params=[])],
            )],
        )
        result = validate_workspace([a, b])
        assert not result.valid
        assert any("cycle" in i.message.lower() for i in result.issues)


# ---------------------------------------------------------------------------
# Integration: parsing + validation on real concept files
# ---------------------------------------------------------------------------


class TestRealConcepts:
    WORKSPACE_SRC = """\
concept Workspace [ConceptName]
  purpose
    Organize a collection of concepts into a coherent, named design project

  state
    workspaces: set Workspace
    contains: workspaces -> set ConceptName
    active: workspaces

  actions
    create (w: Workspace)
      post: workspaces += w

    open (w: Workspace)
      pre: w in workspaces
      post: active += w

    close (w: Workspace)
      pre: w in active
      post: active -= w

    add (w: Workspace, c: ConceptName)
      pre: w in workspaces
      post: contains[w] += c

    remove (w: Workspace, c: ConceptName)
      pre: c in contains[w]
      post: contains[w] -= c

    delete (w: Workspace)
      pre: w in workspaces
      post: workspaces -= w
           active -= w
           contains -= w->

  sync
    when Concept.introduce (c) then add (w, c)
    when Concept.retire (c) then remove (w, c)
"""

    CONCEPT_SRC = """\
concept Concept [Designer]
  purpose
    Define a named, self-contained unit of software functionality

  state
    named: set ConceptName
    purposeful: named
    specified: purposeful

  actions
    introduce (c: ConceptName)
      pre: c not in named
      post: named += c

    articulate (c: ConceptName)
      pre: c in named
      post: purposeful += c

    specify (c: ConceptName)
      pre: c in purposeful
      post: specified += c

    revise (c: ConceptName)
      pre: c in specified
      post: specified -= c

    retire (c: ConceptName)
      pre: c in named
      post: named -= c
           purposeful -= c
           specified -= c
"""

    def test_workspace_concept_valid(self):
        ast = parse_concept(self.WORKSPACE_SRC)
        result = validate_concept(ast)
        assert result.valid, [i.to_dict() for i in result.issues]

    def test_concept_concept_valid(self):
        ast = parse_concept(self.CONCEPT_SRC)
        result = validate_concept(ast)
        assert result.valid, [i.to_dict() for i in result.issues]

    def test_workspace_cross_validates(self):
        workspace_ast = parse_concept(self.WORKSPACE_SRC)
        concept_ast = parse_concept(self.CONCEPT_SRC)
        result = validate_workspace([workspace_ast, concept_ast])
        # Should pass — sync triggers reference valid actions
        assert result.valid, [i.to_dict() for i in result.issues]
