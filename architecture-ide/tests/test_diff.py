"""Tests for concept diff and evolution tracking (v2 — consumes concept_lang.ast)."""

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
