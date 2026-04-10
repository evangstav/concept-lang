"""Tests for the new Lark-based parser (concept_lang.parse)."""

from concept_lang.parse import parse_concept_source
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
