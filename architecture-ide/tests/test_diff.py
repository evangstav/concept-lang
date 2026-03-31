"""Tests for concept diff and evolution tracking."""

import pytest
from concept_lang.models import (
    Action, ConceptAST, PrePost, StateDecl, SyncClause, SyncInvocation,
)
from concept_lang.diff import (
    ChangeKind, ConceptDiff, diff_concepts, diff_concepts_with_impact,
    find_broken_syncs,
)
from concept_lang.parser import parse_concept


def _make_concept(
    name: str = "Test",
    params: list[str] | None = None,
    state: list[StateDecl] | None = None,
    actions: list[Action] | None = None,
    sync: list[SyncClause] | None = None,
    purpose: str = "test concept",
) -> ConceptAST:
    return ConceptAST(
        name=name,
        params=params or [],
        purpose=purpose,
        state=state or [],
        actions=actions or [],
        sync=sync or [],
        source="",
    )


# ---------------------------------------------------------------------------
# No changes
# ---------------------------------------------------------------------------


class TestNoChanges:
    def test_identical_concepts(self):
        c = _make_concept(
            state=[StateDecl(name="items", type_expr="set Item")],
            actions=[Action(name="add", params=["x: Item"])],
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
        old = _make_concept(params=["User"])
        new = _make_concept(params=["User", "Resource"])
        diff = diff_concepts(old, new)
        assert diff.params_changed
        assert diff.old_params == ["User"]
        assert diff.new_params == ["User", "Resource"]

    def test_params_removed(self):
        old = _make_concept(params=["User", "Resource"])
        new = _make_concept(params=["User"])
        diff = diff_concepts(old, new)
        assert diff.params_changed

    def test_params_unchanged(self):
        old = _make_concept(params=["User"])
        new = _make_concept(params=["User"])
        diff = diff_concepts(old, new)
        assert not diff.params_changed


# ---------------------------------------------------------------------------
# Purpose changes
# ---------------------------------------------------------------------------


class TestPurposeChanges:
    def test_purpose_changed(self):
        old = _make_concept(purpose="old purpose")
        new = _make_concept(purpose="new purpose")
        diff = diff_concepts(old, new)
        assert diff.purpose_changed

    def test_purpose_whitespace_ignored(self):
        old = _make_concept(purpose="same purpose  ")
        new = _make_concept(purpose="  same purpose")
        diff = diff_concepts(old, new)
        assert not diff.purpose_changed


# ---------------------------------------------------------------------------
# State changes
# ---------------------------------------------------------------------------


class TestStateChanges:
    def test_state_added(self):
        old = _make_concept(state=[StateDecl(name="items", type_expr="set Item")])
        new = _make_concept(state=[
            StateDecl(name="items", type_expr="set Item"),
            StateDecl(name="active", type_expr="items"),
        ])
        diff = diff_concepts(old, new)
        assert len(diff.state_changes) == 1
        sc = diff.state_changes[0]
        assert sc.kind == ChangeKind.ADDED
        assert sc.name == "active"
        assert sc.new_type_expr == "items"

    def test_state_removed(self):
        old = _make_concept(state=[
            StateDecl(name="items", type_expr="set Item"),
            StateDecl(name="active", type_expr="items"),
        ])
        new = _make_concept(state=[StateDecl(name="items", type_expr="set Item")])
        diff = diff_concepts(old, new)
        assert len(diff.state_changes) == 1
        sc = diff.state_changes[0]
        assert sc.kind == ChangeKind.REMOVED
        assert sc.name == "active"

    def test_state_modified(self):
        old = _make_concept(state=[StateDecl(name="items", type_expr="set Item")])
        new = _make_concept(state=[StateDecl(name="items", type_expr="set Resource")])
        diff = diff_concepts(old, new)
        assert len(diff.state_changes) == 1
        sc = diff.state_changes[0]
        assert sc.kind == ChangeKind.MODIFIED
        assert sc.old_type_expr == "set Item"
        assert sc.new_type_expr == "set Resource"

    def test_state_renamed(self):
        """Same type_expr, old name removed, new name added -> rename."""
        old = _make_concept(state=[StateDecl(name="members", type_expr="set User")])
        new = _make_concept(state=[StateDecl(name="users", type_expr="set User")])
        diff = diff_concepts(old, new)
        assert len(diff.state_changes) == 1
        sc = diff.state_changes[0]
        assert sc.kind == ChangeKind.RENAMED
        assert sc.name == "users"
        assert sc.old_name == "members"

    def test_multiple_state_changes(self):
        old = _make_concept(state=[
            StateDecl(name="items", type_expr="set Item"),
            StateDecl(name="active", type_expr="items"),
        ])
        new = _make_concept(state=[
            StateDecl(name="items", type_expr="set Item"),
            StateDecl(name="archived", type_expr="items"),
        ])
        diff = diff_concepts(old, new)
        # 'active' renamed to 'archived' (same type_expr "items")
        assert len(diff.state_changes) == 1
        assert diff.state_changes[0].kind == ChangeKind.RENAMED


# ---------------------------------------------------------------------------
# Action changes
# ---------------------------------------------------------------------------


class TestActionChanges:
    def test_action_added(self):
        old = _make_concept(actions=[Action(name="add", params=["x: Item"])])
        new = _make_concept(actions=[
            Action(name="add", params=["x: Item"]),
            Action(name="remove", params=["x: Item"]),
        ])
        diff = diff_concepts(old, new)
        assert len(diff.action_changes) == 1
        ac = diff.action_changes[0]
        assert ac.kind == ChangeKind.ADDED
        assert ac.name == "remove"

    def test_action_removed(self):
        old = _make_concept(actions=[
            Action(name="add", params=["x: Item"]),
            Action(name="remove", params=["x: Item"]),
        ])
        new = _make_concept(actions=[Action(name="add", params=["x: Item"])])
        diff = diff_concepts(old, new)
        assert len(diff.action_changes) == 1
        assert diff.action_changes[0].kind == ChangeKind.REMOVED
        assert diff.action_changes[0].name == "remove"

    def test_action_params_changed(self):
        old = _make_concept(actions=[Action(name="add", params=["x: Item"])])
        new = _make_concept(actions=[Action(name="add", params=["x: Item", "y: Tag"])])
        diff = diff_concepts(old, new)
        assert len(diff.action_changes) == 1
        ac = diff.action_changes[0]
        assert ac.kind == ChangeKind.MODIFIED
        assert any("params:" in d for d in ac.details)

    def test_action_pre_changed(self):
        old = _make_concept(actions=[Action(
            name="add", params=["x: Item"],
            pre=PrePost(clauses=["x not in items"]),
        )])
        new = _make_concept(actions=[Action(
            name="add", params=["x: Item"],
            pre=PrePost(clauses=["x not in items", "x not in archived"]),
        )])
        diff = diff_concepts(old, new)
        assert len(diff.action_changes) == 1
        assert any("pre" in d for d in diff.action_changes[0].details)

    def test_action_post_changed(self):
        old = _make_concept(actions=[Action(
            name="add", params=["x: Item"],
            post=PrePost(clauses=["items += x"]),
        )])
        new = _make_concept(actions=[Action(
            name="add", params=["x: Item"],
            post=PrePost(clauses=["items += x", "active += x"]),
        )])
        diff = diff_concepts(old, new)
        assert len(diff.action_changes) == 1
        assert any("post" in d for d in diff.action_changes[0].details)


# ---------------------------------------------------------------------------
# Sync changes
# ---------------------------------------------------------------------------


class TestSyncChanges:
    def test_sync_added(self):
        old = _make_concept()
        new = _make_concept(sync=[SyncClause(
            trigger_concept="Auth",
            trigger_action="login",
            trigger_params=["u"],
            invocations=[SyncInvocation(action="open", params=["u"])],
        )])
        diff = diff_concepts(old, new)
        assert len(diff.sync_changes) == 1
        assert diff.sync_changes[0].kind == ChangeKind.ADDED

    def test_sync_removed(self):
        old = _make_concept(sync=[SyncClause(
            trigger_concept="Auth",
            trigger_action="login",
            trigger_params=["u"],
            invocations=[SyncInvocation(action="open", params=["u"])],
        )])
        new = _make_concept()
        diff = diff_concepts(old, new)
        assert len(diff.sync_changes) == 1
        assert diff.sync_changes[0].kind == ChangeKind.REMOVED

    def test_sync_modified_params(self):
        old = _make_concept(sync=[SyncClause(
            trigger_concept="Auth",
            trigger_action="login",
            trigger_params=["u"],
            invocations=[SyncInvocation(action="open", params=["u"])],
        )])
        new = _make_concept(sync=[SyncClause(
            trigger_concept="Auth",
            trigger_action="login",
            trigger_params=["u", "s"],
            invocations=[SyncInvocation(action="open", params=["u", "s"])],
        )])
        diff = diff_concepts(old, new)
        assert len(diff.sync_changes) == 1
        assert diff.sync_changes[0].kind == ChangeKind.MODIFIED

    def test_sync_unchanged(self):
        clause = SyncClause(
            trigger_concept="Auth",
            trigger_action="login",
            trigger_params=["u"],
            invocations=[SyncInvocation(action="open", params=["u"])],
        )
        old = _make_concept(sync=[clause])
        new = _make_concept(sync=[clause])
        diff = diff_concepts(old, new)
        assert len(diff.sync_changes) == 0


# ---------------------------------------------------------------------------
# Broken sync detection (impact analysis)
# ---------------------------------------------------------------------------


class TestBrokenSyncs:
    def test_removed_action_breaks_downstream(self):
        auth_old = _make_concept(
            name="Auth",
            actions=[
                Action(name="login", params=["u: User"]),
                Action(name="logout", params=["u: User"]),
            ],
        )
        auth_new = _make_concept(
            name="Auth",
            actions=[Action(name="logout", params=["u: User"])],
        )
        session = _make_concept(
            name="Session",
            actions=[Action(name="open", params=["u: User"])],
            sync=[SyncClause(
                trigger_concept="Auth",
                trigger_action="login",
                trigger_params=["u"],
                invocations=[SyncInvocation(action="open", params=["u"])],
            )],
        )
        diff = diff_concepts_with_impact(auth_old, auth_new, [auth_new, session])
        assert len(diff.broken_syncs) == 1
        assert diff.broken_syncs[0].concept_name == "Session"
        assert "removed" in diff.broken_syncs[0].reason

    def test_modified_action_params_breaks_downstream(self):
        auth_old = _make_concept(
            name="Auth",
            actions=[Action(name="login", params=["u: User"])],
        )
        auth_new = _make_concept(
            name="Auth",
            actions=[Action(name="login", params=["u: User", "token: Token"])],
        )
        session = _make_concept(
            name="Session",
            actions=[Action(name="open", params=["u: User"])],
            sync=[SyncClause(
                trigger_concept="Auth",
                trigger_action="login",
                trigger_params=["u"],
                invocations=[SyncInvocation(action="open", params=["u"])],
            )],
        )
        diff = diff_concepts_with_impact(auth_old, auth_new, [auth_new, session])
        assert len(diff.broken_syncs) == 1
        assert "parameters changed" in diff.broken_syncs[0].reason

    def test_unrelated_change_no_breakage(self):
        auth_old = _make_concept(
            name="Auth",
            actions=[Action(name="login", params=["u: User"])],
        )
        auth_new = _make_concept(
            name="Auth",
            actions=[
                Action(name="login", params=["u: User"]),
                Action(name="reset", params=["u: User"]),
            ],
        )
        session = _make_concept(
            name="Session",
            actions=[Action(name="open", params=["u: User"])],
            sync=[SyncClause(
                trigger_concept="Auth",
                trigger_action="login",
                trigger_params=["u"],
                invocations=[SyncInvocation(action="open", params=["u"])],
            )],
        )
        diff = diff_concepts_with_impact(auth_old, auth_new, [auth_new, session])
        assert len(diff.broken_syncs) == 0

    def test_no_workspace_no_broken(self):
        old = _make_concept(actions=[Action(name="login", params=["u: User"])])
        new = _make_concept(actions=[])
        diff = diff_concepts_with_impact(old, new)
        assert len(diff.broken_syncs) == 0


# ---------------------------------------------------------------------------
# Integration: parse real concept source and diff
# ---------------------------------------------------------------------------


class TestIntegration:
    CONCEPT_V1 = """\
concept Auth [User]
  purpose
    Manage user authentication

  state
    registered: set User
    active: registered

  actions
    register (u: User)
      pre: u not in registered
      post: registered += u

    login (u: User)
      pre: u in registered
      post: active += u

    logout (u: User)
      pre: u in active
      post: active -= u
"""

    CONCEPT_V2 = """\
concept Auth [User]
  purpose
    Manage user authentication with tokens

  state
    registered: set User
    active: registered
    tokens: registered -> set Token

  actions
    register (u: User)
      pre: u not in registered
      post: registered += u

    login (u: User, t: Token)
      pre: u in registered
      post: active += u
            tokens[u] += t

    logout (u: User)
      pre: u in active
      post: active -= u
            tokens -= u->
"""

    def test_full_evolution(self):
        old = parse_concept(self.CONCEPT_V1)
        new = parse_concept(self.CONCEPT_V2)
        diff = diff_concepts(old, new)

        assert diff.has_changes
        assert diff.purpose_changed

        # State: 'tokens' added
        state_adds = [s for s in diff.state_changes if s.kind == ChangeKind.ADDED]
        assert len(state_adds) == 1
        assert state_adds[0].name == "tokens"

        # Actions: 'login' modified (params + post), 'logout' modified (post)
        action_mods = [a for a in diff.action_changes if a.kind == ChangeKind.MODIFIED]
        assert len(action_mods) == 2
        login_mod = next(a for a in action_mods if a.name == "login")
        assert any("params:" in d for d in login_mod.details)
        assert any("post" in d for d in login_mod.details)
        logout_mod = next(a for a in action_mods if a.name == "logout")
        assert any("post" in d for d in logout_mod.details)

    def test_to_dict_roundtrip(self):
        old = parse_concept(self.CONCEPT_V1)
        new = parse_concept(self.CONCEPT_V2)
        diff = diff_concepts(old, new)
        d = diff.to_dict()

        assert d["concept"] == "Auth"
        assert d["has_changes"] is True
        assert "state_changes" in d
        assert "action_changes" in d
