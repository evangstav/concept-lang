"""Tests for the new Lark-based parser (concept_lang.parse)."""

from pathlib import Path

from concept_lang.parse import parse_concept_file
from concept_lang.parse import parse_concept_source
from concept_lang.parse import parse_sync_file
from concept_lang.parse import parse_sync_source


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


class TestConceptOperationalPrinciple:
    def test_two_step_principle(self):
        src = """
concept Password [U]

  purpose
    credentials

  state
    password: U -> string

  actions
    set [ user: U ; password: string ] => [ user: U ]
    check [ user: U ; password: string ] => [ valid: boolean ]

  operational principle
    after set [ user: x ; password: "secret" ] => [ user: x ]
    then check [ user: x ; password: "secret" ] => [ valid: true ]
"""
        ast = parse_concept_source(src)
        op = ast.operational_principle
        assert len(op.steps) == 2
        assert op.steps[0].keyword == "after"
        assert op.steps[0].action_name == "set"
        assert op.steps[0].inputs == [("user", "x"), ("password", '"secret"')]
        assert op.steps[0].outputs == [("user", "x")]
        assert op.steps[1].keyword == "then"
        assert op.steps[1].action_name == "check"

    def test_and_step(self):
        src = """
concept Counter

  purpose
    count things

  actions
    inc [ ] => [ n: int ]
    read [ ] => [ n: int ]

  operational principle
    after inc [ ] => [ n: 1 ]
    and read [ ] => [ n: 1 ]
"""
        ast = parse_concept_source(src)
        assert ast.operational_principle.steps[1].keyword == "and"


class TestSyncBasic:
    def test_simple_when_then(self):
        src = """
sync LogEveryRequest

  when
    Web/request: [ ] => [ request: ?request ]
  then
    Log/append: [ event: ?request ]
"""
        sync = parse_sync_source(src)
        assert sync.name == "LogEveryRequest"
        assert len(sync.when) == 1
        assert sync.when[0].concept == "Web"
        assert sync.when[0].action == "request"
        assert sync.when[0].input_pattern == []
        assert len(sync.when[0].output_pattern) == 1
        assert sync.when[0].output_pattern[0].name == "request"
        assert sync.when[0].output_pattern[0].kind == "var"
        assert sync.when[0].output_pattern[0].value == "?request"
        assert len(sync.then) == 1
        assert sync.then[0].concept == "Log"
        assert sync.then[0].action == "append"

    def test_literal_in_when(self):
        src = """
sync OnRegister

  when
    Web/request: [ method: "register" ] => [ ]
  then
    Audit/log: [ kind: "register" ]
"""
        sync = parse_sync_source(src)
        assert sync.when[0].input_pattern[0].kind == "literal"
        assert sync.when[0].input_pattern[0].value == '"register"'
        assert sync.then[0].input_pattern[0].value == '"register"'



class TestSyncWhere:
    def test_bind_only(self):
        src = """
sync Register

  when
    Web/request: [ method: "register" ] => [ ]
  where
    bind (uuid() as ?user)
  then
    User/register: [ user: ?user ]
"""
        sync = parse_sync_source(src)
        assert sync.where is not None
        assert len(sync.where.binds) == 1
        assert sync.where.binds[0].variable == "?user"
        assert "uuid" in sync.where.binds[0].expression

    def test_state_query(self):
        src = """
sync FormatArticle

  when
    Web/format: [ article: ?article ] => [ ]
  where
    Article: {
      ?article title: ?title ;
               body: ?body
    }
  then
    Web/respond: [ title: ?title ]
"""
        sync = parse_sync_source(src)
        assert sync.where is not None
        assert len(sync.where.queries) == 1
        q = sync.where.queries[0]
        assert q.concept == "Article"
        assert q.is_optional is False
        assert len(q.triples) == 2
        assert q.triples[0].subject == "?article"
        assert q.triples[0].predicate == "title"
        assert q.triples[0].object == "?title"
        assert q.triples[1].subject == "?article"  # shared subject propagated
        assert q.triples[1].predicate == "body"

    def test_optional_state_query(self):
        src = """
sync FormatWithTags

  when
    Web/format: [ article: ?article ] => [ ]
  where
    optional Tag: { ?article tag: ?tag }
  then
    Web/respond: [ tag: ?tag ]
"""
        sync = parse_sync_source(src)
        assert sync.where.queries[0].is_optional is True


class TestArchitectureIdeFixtures:
    FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "architecture_ide"

    def test_all_concepts_parse(self):
        concepts_dir = self.FIXTURES_ROOT / "concepts"
        files = sorted(concepts_dir.glob("*.concept"))
        assert len(files) == 4, f"Expected 4 concept fixtures, found {len(files)}"
        for f in files:
            ast = parse_concept_file(f)
            assert ast.name, f"{f.name}: empty name"
            assert ast.purpose, f"{f.name}: empty purpose"
            assert ast.operational_principle.steps, f"{f.name}: empty op principle"

    def test_all_syncs_parse(self):
        syncs_dir = self.FIXTURES_ROOT / "syncs"
        files = sorted(syncs_dir.glob("*.sync"))
        assert len(files) == 3, f"Expected 3 sync fixtures, found {len(files)}"
        for f in files:
            sync = parse_sync_file(f)
            assert sync.name, f"{f.name}: empty name"
            assert sync.when, f"{f.name}: empty when"
            assert sync.then, f"{f.name}: empty then"


class TestRealworldFixtures:
    FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "realworld"

    def test_all_concepts_parse(self):
        concepts_dir = self.FIXTURES_ROOT / "concepts"
        files = sorted(concepts_dir.glob("*.concept"))
        assert len(files) == 6, f"Expected 6 concept fixtures, found {len(files)}"
        for f in files:
            ast = parse_concept_file(f)
            assert ast.name, f"{f.name}: empty name"
            assert ast.purpose, f"{f.name}: missing purpose"

    def test_all_syncs_parse(self):
        syncs_dir = self.FIXTURES_ROOT / "syncs"
        files = sorted(syncs_dir.glob("*.sync"))
        assert len(files) == 6, f"Expected 6 sync fixtures, found {len(files)}"
        for f in files:
            sync = parse_sync_file(f)
            assert sync.name, f"{f.name}: empty name"
            assert sync.when, f"{f.name}: empty when"
            assert sync.then, f"{f.name}: empty then"


class TestP1Gate:
    """
    The P1 gate from the paper-alignment spec: every positive fixture
    must parse cleanly into a ConceptAST or SyncAST without exceptions,
    and every ConceptAST must have a non-empty purpose and operational
    principle, and every SyncAST must have a non-empty when and then.
    """
    FIXTURES_ROOT = Path(__file__).parent / "fixtures"

    def test_all_positive_fixtures_parse(self):
        concept_files = sorted(self.FIXTURES_ROOT.rglob("*.concept"))
        sync_files = sorted(self.FIXTURES_ROOT.rglob("*.sync"))

        # Expected totals: 4 (architecture_ide) + 6 (realworld) concepts; 3 + 6 syncs.
        assert len(concept_files) == 10, f"Found {len(concept_files)} concept files"
        assert len(sync_files) == 9, f"Found {len(sync_files)} sync files"

        for f in concept_files:
            ast = parse_concept_file(f)
            assert ast.name, f"{f}: empty name"
            assert ast.purpose, f"{f}: empty purpose"
            assert ast.operational_principle.steps, f"{f}: empty operational principle"

        for f in sync_files:
            sync = parse_sync_file(f)
            assert sync.name, f"{f}: empty name"
            assert sync.when, f"{f}: empty when"
            assert sync.then, f"{f}: empty then"
