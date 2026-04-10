"""Tests for the new validator (concept_lang.validate)."""

from pathlib import Path

from concept_lang.ast import (
    Action,
    ActionCase,
    ConceptAST,
    OperationalPrinciple,
    StateDecl,
    TypedName,
    Workspace,
)
from concept_lang.validate.diagnostic import Diagnostic
from concept_lang.validate.helpers import WorkspaceIndex


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


# ---------------------------------------------------------------------------
# Sync validator rules (S1..S5) — shared helpers and tests
# ---------------------------------------------------------------------------

from concept_lang.ast import SyncAST
from concept_lang.parse import parse_sync_source
from concept_lang.validate import rule_s1_references_resolve


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
