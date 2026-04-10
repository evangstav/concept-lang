"""Round-trip tests for the new AST (concept_lang.ast)."""

import pytest
from pydantic import ValidationError

from concept_lang.ast import (
    Action,
    ActionCase,
    ConceptAST,
    EffectClause,
    OPStep,
    OperationalPrinciple,
    StateDecl,
    TypedName,
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
