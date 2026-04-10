"""Tests for the interactive HTML explorer (v2 — consumes concept_lang.ast)."""

import re

from concept_lang.ast import (
    Action,
    ActionCase,
    ActionPattern,
    ConceptAST,
    EffectClause,
    OperationalPrinciple,
    OPStep,
    StateDecl,
    SyncAST,
    TypedName,
    Workspace,
)
from concept_lang.explorer import (
    _build_graph_data,
    _build_sync_index,
    _to_v1_concept,
    _workspace_graph_mermaid,
    generate_explorer,
)


def _tiny_workspace() -> Workspace:
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
                        inputs=[],
                        outputs=[TypedName(name="total", type_expr="int")],
                        body=["increment"],
                    )
                ],
            )
        ],
        operational_principle=OperationalPrinciple(steps=[
            OPStep(keyword="after", action_name="inc", inputs=[], outputs=[("total", "1")]),
        ]),
        source="",
    )
    logger = ConceptAST(
        name="Logger",
        params=[],
        purpose="log events",
        state=[],
        actions=[
            Action(
                name="write",
                cases=[
                    ActionCase(
                        inputs=[TypedName(name="msg", type_expr="string")],
                        outputs=[],
                        body=["write to log"],
                    )
                ],
            )
        ],
        operational_principle=OperationalPrinciple(steps=[
            OPStep(
                keyword="after",
                action_name="write",
                inputs=[("msg", '"hi"')],
                outputs=[],
            ),
        ]),
        source="",
    )
    log_inc = SyncAST(
        name="LogInc",
        when=[ActionPattern(concept="Counter", action="inc", input_pattern=[], output_pattern=[])],
        where=None,
        then=[ActionPattern(concept="Logger", action="write", input_pattern=[], output_pattern=[])],
        source="",
    )
    return Workspace(
        concepts={"Counter": counter, "Logger": logger},
        syncs={"LogInc": log_inc},
    )


class TestGraphData:
    def test_one_node_per_concept(self):
        ws = _tiny_workspace()
        data = _build_graph_data(ws)
        names = {n["id"] for n in data["nodes"]}
        assert names == {"Counter", "Logger"}

    def test_one_edge_per_sync_triple(self):
        ws = _tiny_workspace()
        data = _build_graph_data(ws)
        assert len(data["edges"]) == 1
        edge = data["edges"][0]
        assert edge["source"] == "Counter"
        assert edge["target"] == "Logger"
        assert edge["syncName"] == "LogInc"
        assert edge["type"] == "sync"
        assert edge["internal"] is True

    def test_external_concept_reference_is_surfaced(self):
        ws = _tiny_workspace()
        # Add a sync that mentions a concept that doesn't exist.
        ws.syncs["Orphan"] = SyncAST(
            name="Orphan",
            when=[ActionPattern(concept="Counter", action="inc", input_pattern=[], output_pattern=[])],
            then=[ActionPattern(concept="Ghost", action="haunt", input_pattern=[], output_pattern=[])],
            source="",
        )
        data = _build_graph_data(ws)
        ghost = next((n for n in data["nodes"] if n["id"] == "Ghost"), None)
        assert ghost is not None
        assert ghost.get("external") is True

    def test_empty_workspace(self):
        data = _build_graph_data(Workspace())
        assert data == {"nodes": [], "edges": []}


class TestSyncIndex:
    def test_sync_index_captures_when_and_then(self):
        ws = _tiny_workspace()
        index = _build_sync_index(ws)
        assert "Counter.inc" in index
        assert any(e["sync"] == "LogInc" and e["role"] == "when" for e in index["Counter.inc"])
        assert "Logger.write" in index
        assert any(e["sync"] == "LogInc" and e["role"] == "then" for e in index["Logger.write"])


class TestWorkspaceGraphMermaid:
    def test_mermaid_contains_sync_edge(self):
        ws = _tiny_workspace()
        s = _workspace_graph_mermaid(ws)
        assert s.startswith("graph TD")
        assert re.search(r"Counter\s*-->\|sync LogInc\|\s*Logger", s)


class TestGenerateExplorer:
    def test_generate_returns_html_with_embedded_json(self):
        ws = _tiny_workspace()
        html = generate_explorer(ws)
        assert "<html" in html
        # The concept data payload got injected.
        assert '"Counter"' in html
        # The sync edge made it into the injected graph data.
        assert '"syncName": "LogInc"' in html

    def test_generate_empty_workspace(self):
        html = generate_explorer(Workspace())
        assert "<html" in html
        assert "No concepts" in html


class TestV1Adapter:
    def test_to_v1_concept_preserves_core_fields(self):
        concept = ConceptAST(
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
                )
            ],
            operational_principle=OperationalPrinciple(steps=[]),
            source="",
        )
        v1 = _to_v1_concept(concept)
        assert v1.name == "Auth"
        assert v1.params == ["U"]
        assert v1.purpose == "authenticate users"
        assert len(v1.state) == 1
        assert v1.state[0].name == "registered"
        assert v1.state[0].type_expr == "set U"
        assert len(v1.actions) == 1
        assert v1.actions[0].name == "register"
        assert v1.actions[0].params == ["user: U"]
        assert v1.actions[0].post is not None
        assert v1.actions[0].post.clauses == ["registered += user"]
        # Syncs are always empty because v2 holds them in separate files.
        assert v1.sync == []

    def test_to_v1_concept_action_with_no_effects_has_no_post(self):
        concept = ConceptAST(
            name="Noop",
            params=[],
            purpose="does nothing",
            state=[],
            actions=[
                Action(
                    name="ping",
                    cases=[ActionCase(inputs=[], outputs=[], body=["ping"])],
                )
            ],
            operational_principle=OperationalPrinciple(steps=[]),
            source="",
        )
        v1 = _to_v1_concept(concept)
        assert len(v1.actions) == 1
        assert v1.actions[0].post is None
        assert v1.actions[0].pre is None

    def test_to_v1_concept_multi_case_collapses_to_first_case(self):
        success = ActionCase(
            inputs=[TypedName(name="x", type_expr="int")],
            outputs=[TypedName(name="x", type_expr="int")],
            body=["success"],
            effects=[EffectClause(raw="count += 1", field="count", op="+=", rhs="1")],
        )
        failure = ActionCase(
            inputs=[TypedName(name="x", type_expr="int")],
            outputs=[TypedName(name="err", type_expr="string")],
            body=["failure"],
        )
        concept = ConceptAST(
            name="Multi",
            params=[],
            purpose="multi-case",
            state=[],
            actions=[Action(name="step", cases=[success, failure])],
            operational_principle=OperationalPrinciple(steps=[]),
            source="",
        )
        v1 = _to_v1_concept(concept)
        # Only the first case's inputs/effects end up in the v1 action.
        assert v1.actions[0].params == ["x: int"]
        assert v1.actions[0].post is not None
        assert v1.actions[0].post.clauses == ["count += 1"]
