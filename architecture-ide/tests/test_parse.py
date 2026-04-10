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


class TestConceptActionHeaders:
    def test_single_action_no_body(self):
        src = """
concept Counter

  purpose
    increment a value

  actions
    increment [ amount: int ] => [ total: int ]
"""
        ast = parse_concept_source(src)
        assert len(ast.actions) == 1
        action = ast.actions[0]
        assert action.name == "increment"
        assert len(action.cases) == 1
        case = action.cases[0]
        assert [(i.name, i.type_expr) for i in case.inputs] == [("amount", "int")]
        assert [(o.name, o.type_expr) for o in case.outputs] == [("total", "int")]

    def test_empty_output(self):
        src = """
concept Logger

  purpose
    record events

  actions
    log [ message: string ] => [ ]
"""
        ast = parse_concept_source(src)
        action = ast.actions[0]
        assert action.cases[0].outputs == []

    def test_multiple_cases_grouped_by_name(self):
        src = """
concept Password [U]

  purpose
    store credentials

  actions
    set [ user: U ; password: string ] => [ user: U ]
    set [ user: U ; password: string ] => [ error: string ]
"""
        ast = parse_concept_source(src)
        assert len(ast.actions) == 1
        set_action = ast.actions[0]
        assert set_action.name == "set"
        assert len(set_action.cases) == 2
        assert set_action.cases[0].outputs[0].name == "user"
        assert set_action.cases[1].outputs[0].name == "error"


class TestConceptActionBody:
    def test_natural_language_body(self):
        src = """
concept Password [U]

  purpose
    credentials

  state
    password: U -> string

  actions
    set [ user: U ; password: string ] => [ user: U ]
      generate a random salt
      compute the hash
      return the user
"""
        ast = parse_concept_source(src)
        case = ast.actions[0].cases[0]
        assert case.body == [
            "generate a random salt",
            "compute the hash",
            "return the user",
        ]
        assert case.effects == []

    def test_effects_clause(self):
        src = """
concept Password [U]

  purpose
    credentials

  state
    password: U -> string
    salt: U -> string

  actions
    set [ user: U ; password: string ] => [ user: U ]
      generate a random salt
      effects:
        password[user] := hash
        salt[user] := generated_salt
"""
        ast = parse_concept_source(src)
        case = ast.actions[0].cases[0]
        assert case.body == ["generate a random salt"]
        assert len(case.effects) == 2
        assert case.effects[0].field == "password"
        assert case.effects[0].op == ":="
        assert case.effects[0].rhs == "hash"
        assert case.effects[1].field == "salt"
