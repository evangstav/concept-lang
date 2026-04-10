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
