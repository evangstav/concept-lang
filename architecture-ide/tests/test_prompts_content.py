"""Pin the MCP prompt bodies for v2 format (P5 decision (N))."""

from __future__ import annotations

from concept_lang.prompts import register_prompts


class _FakeMCP:
    def __init__(self):
        self.prompts: dict[str, object] = {}

    def prompt(self):
        def decorator(fn):
            self.prompts[fn.__name__] = fn
            return fn
        return decorator


def _make():
    mcp = _FakeMCP()
    register_prompts(mcp)
    return mcp


class TestBuildConceptPrompt:
    def test_teaches_named_io(self):
        mcp = _make()
        body = mcp.prompts["build_concept"](description="x")[0]["content"]["text"]
        assert "=>" in body
        assert "error: string" in body

    def test_no_v1_inline_sync(self):
        mcp = _make()
        body = mcp.prompts["build_concept"](description="x")[0]["content"]["text"]
        assert "sync" in body  # allowed to mention syncs
        # But not as a section header inside the concept
        assert "syncs live in separate" in body.lower()

    def test_no_v1_prepost(self):
        mcp = _make()
        body = mcp.prompts["build_concept"](description="x")[0]["content"]["text"]
        assert "pre:" not in body
        assert "post:" not in body


class TestReviewConceptsPrompt:
    def test_uses_validate_workspace(self):
        mcp = _make()
        body = mcp.prompts["review_concepts"](concept_names="")[0]["content"]["text"]
        assert "validate_workspace" in body

    def test_groups_by_rule_category(self):
        mcp = _make()
        body = mcp.prompts["review_concepts"](concept_names="")[0]["content"]["text"]
        for cat in ("Independence", "Completeness", "Sync", "Parse"):
            assert cat in body

    def test_walks_three_legibility_properties(self):
        mcp = _make()
        body = mcp.prompts["review_concepts"](concept_names="")[0]["content"]["text"]
        for prop in ("Incrementality", "Integrity", "Transparency"):
            assert prop in body

    def test_no_deprecated_alias(self):
        mcp = _make()
        body = mcp.prompts["review_concepts"](concept_names="")[0]["content"]["text"]
        # The prompt may mention that get_dependency_graph is deprecated.
        # What it must NOT do is TELL the user to call it.
        assert "get_workspace_graph" in body

    def test_handles_empty_scope(self):
        mcp = _make()
        body = mcp.prompts["review_concepts"](concept_names="")[0]["content"]["text"]
        assert "the whole workspace" in body
