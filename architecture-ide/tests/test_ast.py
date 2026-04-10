"""Round-trip tests for the new AST (concept_lang.ast)."""

import pytest
from pydantic import ValidationError

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
        round_tripped = EffectClause.model_validate(dumped)
        assert round_tripped == ec

    def test_op_literal(self):
        with pytest.raises(ValidationError):
            EffectClause(raw="x", field="x", op="<>", rhs="y")  # type: ignore[arg-type]

    @pytest.mark.parametrize("op", [":=", "+=", "-="])
    def test_op_round_trip(self, op):
        ec = EffectClause(
            raw=f"field {op} value",
            field="field",
            op=op,
            rhs="value",
        )
        dumped = ec.model_dump()
        assert dumped["op"] == op
        round_tripped = EffectClause.model_validate(dumped)
        assert round_tripped == ec


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


class TestWorkspace:
    def test_empty_workspace(self):
        ws = Workspace(concepts={}, syncs={})
        assert ws.concepts == {}
        assert ws.syncs == {}

    def test_workspace_lookup(self):
        # Reuse fixtures from TestConceptAST and TestSyncAST
        password = TestConceptAST()._make_password_concept()
        register = TestSyncAST()._make_register_sync()
        ws = Workspace(
            concepts={"Password": password},
            syncs={"RegisterUser": register},
        )
        assert ws.concepts["Password"].purpose.startswith("to securely")
        assert ws.syncs["RegisterUser"].when[0].concept == "Web"


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
