"""Tests for the new validator (concept_lang.validate)."""

from pathlib import Path

from concept_lang.ast import (
    Action,
    ActionCase,
    ConceptAST,
    OperationalPrinciple,
    OPStep,
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
        operational_principle=OperationalPrinciple(
            steps=[
                OPStep(
                    keyword="after",
                    action_name="inc",
                    inputs=[("amount", "1")],
                    outputs=[("total", "1")],
                )
            ]
        ),
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
        operational_principle=OperationalPrinciple(
            steps=[
                OPStep(
                    keyword="after",
                    action_name="append",
                    inputs=[("event", '"hi"')],
                    outputs=[("entry", '"hi"')],
                )
            ]
        ),
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
