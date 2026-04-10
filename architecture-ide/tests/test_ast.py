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
        round_tripped = EffectClause.model_validate(dumped)
        assert round_tripped == ec

    def test_op_literal(self):
        import pytest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            EffectClause(raw="x", field="x", op="<>", rhs="y")  # type: ignore[arg-type]
