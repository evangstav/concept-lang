"""Tests for v2 Mermaid diagram generators (P7 rewrite)."""

from __future__ import annotations

from concept_lang.ast import (
    Action,
    ActionCase,
    ConceptAST,
    EffectClause,
    OperationalPrinciple,
    OPStep,
    StateDecl,
    TypedName,
)
from concept_lang.diagrams import entity_diagram, state_machine


def _counter() -> ConceptAST:
    """A minimal v2 concept with one scalar state field and one effect."""
    return ConceptAST(
        name="Counter",
        params=[],
        purpose="count things",
        state=[StateDecl(name="total", type_expr="int")],
        actions=[
            Action(
                name="inc",
                cases=[
                    ActionCase(
                        inputs=[],
                        outputs=[TypedName(name="total", type_expr="int")],
                        body=["increment the total"],
                        effects=[
                            EffectClause(
                                raw="total += 1",
                                field="total",
                                op="+=",
                                rhs="1",
                            )
                        ],
                    )
                ],
            )
        ],
        operational_principle=OperationalPrinciple(
            steps=[
                OPStep(
                    keyword="after",
                    action_name="inc",
                    inputs=[],
                    outputs=[("total", "1")],
                )
            ]
        ),
        source="",
    )


def _auth() -> ConceptAST:
    """A v2 concept with a set state field and an add-then-remove action pair."""
    return ConceptAST(
        name="Auth",
        params=["U"],
        purpose="authenticate users",
        state=[StateDecl(name="registered", type_expr="set U")],
        actions=[
            Action(
                name="register",
                cases=[
                    ActionCase(
                        inputs=[TypedName(name="user", type_expr="U")],
                        outputs=[TypedName(name="user", type_expr="U")],
                        body=["register the user"],
                        effects=[
                            EffectClause(
                                raw="registered += user",
                                field="registered",
                                op="+=",
                                rhs="user",
                            )
                        ],
                    )
                ],
            ),
            Action(
                name="unregister",
                cases=[
                    ActionCase(
                        inputs=[TypedName(name="user", type_expr="U")],
                        outputs=[TypedName(name="user", type_expr="U")],
                        body=["remove the user"],
                        effects=[
                            EffectClause(
                                raw="registered -= user",
                                field="registered",
                                op="-=",
                                rhs="user",
                            )
                        ],
                    )
                ],
            ),
        ],
        operational_principle=OperationalPrinciple(steps=[]),
        source="",
    )


class TestStateMachine:
    def test_counter_header(self):
        m = state_machine(_counter())
        assert m.startswith("stateDiagram-v2")

    def test_counter_has_inc_transition(self):
        # Counter has no set state, so inc renders against the default flat state.
        m = state_machine(_counter())
        assert "inc" in m

    def test_auth_register_is_entry_transition(self):
        m = state_machine(_auth())
        # register += registered  →  [*] --> registered
        assert "[*] --> registered : register" in m

    def test_auth_unregister_is_exit_transition(self):
        m = state_machine(_auth())
        # unregister -= registered  →  registered --> [*]
        assert "registered --> [*] : unregister" in m


class TestEntityDiagram:
    def test_counter_header(self):
        m = entity_diagram(_counter())
        assert m.startswith("classDiagram")

    def test_counter_class_block(self):
        m = entity_diagram(_counter())
        assert "class Counter" in m
        # v1 behavior that the v2 rewrite preserves: because "int" starts
        # with a lowercase letter, it is classified as a subset parent, so
        # total renders as "⊆ int". This is a latent imprecision in the v1
        # generator but P7 is strictly a rewrite, not a bug fix, so the
        # behavior is pinned as-is.
        assert "+total ⊆ int" in m

    def test_auth_class_block_names_set(self):
        m = entity_diagram(_auth())
        assert "class Auth" in m
        assert "+registered set~U~" in m

    def test_auth_external_class(self):
        m = entity_diagram(_auth())
        # The set element type U is external to the concept class.
        assert "class U" in m
