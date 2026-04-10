"""Tests for the new Lark-based parser (concept_lang.parse)."""

from concept_lang.parse import parse_concept_source


class TestConceptHeader:
    def test_parses_name_and_purpose(self):
        src = """
concept Timer

  purpose
    measure elapsed durations between events
"""
        ast = parse_concept_source(src)
        assert ast.name == "Timer"
        assert ast.params == []
        assert ast.purpose == "measure elapsed durations between events"

    def test_parses_type_parameters(self):
        src = """
concept Session [User, Token]

  purpose
    track authenticated user sessions
"""
        ast = parse_concept_source(src)
        assert ast.name == "Session"
        assert ast.params == ["User", "Token"]

    def test_multi_line_purpose_body(self):
        src = """
concept Rubric

  purpose
    evaluate candidate submissions
    against a shared set of criteria
    and return a weighted score
"""
        ast = parse_concept_source(src)
        assert ast.name == "Rubric"
        assert ast.purpose == (
            "evaluate candidate submissions "
            "against a shared set of criteria "
            "and return a weighted score"
        )

    def test_purpose_body_contains_future_section_keywords(self):
        # Regression guard for the grammar invariant documented in
        # concept.lark: section keywords remain bare string literals so the
        # contextual lexer picks them over PURPOSE_LINE only when a new
        # section is expected. The words "state", "actions", "effects",
        # and "operational" must be legal inside a purpose body.
        src = """
concept Journal

  purpose
    record state changes and track actions the user performed
    so the effects of each operational decision remain auditable
"""
        ast = parse_concept_source(src)
        assert ast.name == "Journal"
        assert "state changes" in ast.purpose
        assert "actions the user performed" in ast.purpose
        assert "effects" in ast.purpose
        assert "operational decision" in ast.purpose


class TestConceptState:
    def test_simple_set(self):
        src = """
concept Tracker

  purpose
    track items that are currently active

  state
    active: set Item
"""
        ast = parse_concept_source(src)
        assert len(ast.state) == 1
        assert ast.state[0].name == "active"
        assert ast.state[0].type_expr == "set Item"

    def test_relation(self):
        src = """
concept Password [U]

  purpose
    store credentials

  state
    password: U -> string
    salt: U -> string
"""
        ast = parse_concept_source(src)
        assert len(ast.state) == 2
        assert ast.state[1].name == "salt"
        assert ast.state[1].type_expr == "U -> string"
