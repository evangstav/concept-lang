"""Integration tests for the MCP tool layer (v2).

These tests call the tool functions directly via a fake FastMCP. They do
not exercise the MCP protocol itself — that's reserved for the P5 skills
pipeline.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable

import pytest

from concept_lang.tools.concept_tools import register_concept_tools
from concept_lang.tools.diff_tools import register_diff_tools
from concept_lang.tools.explorer_tools import register_explorer_tools
from concept_lang.tools.sync_tools import register_sync_tools
from concept_lang.tools.workspace_tools import register_workspace_tools


FIXTURES = Path(__file__).parent / "fixtures" / "mcp"


class _FakeMCP:
    """Minimal stand-in for FastMCP that captures @mcp.tool() decorations."""

    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Any]] = {}
        self.resources: dict[str, Callable[..., Any]] = {}

    def tool(self, *args, **kwargs):  # matches FastMCP.tool decorator
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.tools[fn.__name__] = fn
            return fn
        return decorator

    def resource(self, pattern: str):
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.resources[pattern] = fn
            return fn
        return decorator


def _make_mcp(workspace_root: Path) -> _FakeMCP:
    mcp = _FakeMCP()
    register_concept_tools(mcp, str(workspace_root))
    register_sync_tools(mcp, str(workspace_root))
    register_workspace_tools(mcp, str(workspace_root))
    register_diff_tools(mcp, str(workspace_root))
    register_explorer_tools(mcp, str(workspace_root))
    return mcp


def _call(mcp: _FakeMCP, _tool_name: str, **kwargs) -> Any:
    raw = mcp.tools[_tool_name](**kwargs)
    if isinstance(raw, str) and raw.startswith(("{", "[")):
        return json.loads(raw)
    return raw


def _copy_workspace(src: Path, dst: Path) -> None:
    """Copy a fixture workspace tree into a writable temp directory."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


# ---------------------------------------------------------------------------
# Concept tools
# ---------------------------------------------------------------------------


class TestListConcepts:
    def test_clean_workspace_lists_counter_and_logger(self):
        mcp = _make_mcp(FIXTURES / "clean")
        body = _call(mcp, "list_concepts")
        assert body == ["Counter", "Logger"]

    def test_empty_workspace_lists_nothing(self):
        mcp = _make_mcp(FIXTURES / "empty")
        body = _call(mcp, "list_concepts")
        assert body == []


class TestReadConcept:
    def test_reads_existing_concept(self):
        mcp = _make_mcp(FIXTURES / "clean")
        body = _call(mcp, "read_concept", name="Counter")
        assert "source" in body
        assert "concept Counter" in body["source"]
        assert body["ast"]["name"] == "Counter"

    def test_missing_concept_returns_error(self):
        mcp = _make_mcp(FIXTURES / "clean")
        body = _call(mcp, "read_concept", name="Nope")
        assert "error" in body


class TestValidateConcept:
    def test_clean_source_has_no_errors(self):
        mcp = _make_mcp(FIXTURES / "clean")
        source = (FIXTURES / "clean" / "concepts" / "Counter.concept").read_text()
        body = _call(mcp, "validate_concept", source=source)
        assert body["valid"] is True
        assert all(d["severity"] != "error" for d in body["diagnostics"])

    def test_purpose_missing_source_fires_c5(self):
        mcp = _make_mcp(FIXTURES / "clean")
        source = (FIXTURES / "with_error" / "concepts" / "Counter.concept").read_text()
        body = _call(mcp, "validate_concept", source=source)
        assert body["valid"] is False
        codes = {d["code"] for d in body["diagnostics"]}
        assert "C5" in codes


class TestWriteConcept:
    def test_refuses_invalid_write(self, tmp_path):
        # Copy the clean fixture into a writable temp workspace.
        workspace = tmp_path / "ws"
        _copy_workspace(FIXTURES / "clean", workspace)
        mcp = _make_mcp(workspace)

        bad_source = (FIXTURES / "with_error" / "concepts" / "Counter.concept").read_text()
        body = _call(mcp, "write_concept", name="Broken", source=bad_source)
        assert body["written"] is False
        assert body["valid"] is False
        assert not (workspace / "concepts" / "Broken.concept").exists()

    def test_accepts_valid_write(self, tmp_path):
        workspace = tmp_path / "ws"
        _copy_workspace(FIXTURES / "clean", workspace)
        mcp = _make_mcp(workspace)

        good = (FIXTURES / "clean" / "concepts" / "Counter.concept").read_text()
        body = _call(mcp, "write_concept", name="Counter2", source=good)
        assert body["written"] is True
        assert (workspace / "concepts" / "Counter2.concept").exists()


# ---------------------------------------------------------------------------
# Sync tools
# ---------------------------------------------------------------------------


class TestListSyncs:
    def test_clean_workspace_lists_log(self):
        mcp = _make_mcp(FIXTURES / "clean")
        body = _call(mcp, "list_syncs")
        assert body == ["log"]  # filename stem is `log`

    def test_empty_workspace_lists_nothing(self):
        mcp = _make_mcp(FIXTURES / "empty")
        body = _call(mcp, "list_syncs")
        assert body == []


class TestReadSync:
    def test_reads_existing_sync(self):
        mcp = _make_mcp(FIXTURES / "clean")
        body = _call(mcp, "read_sync", name="log")
        assert "sync LogInc" in body["source"]
        assert body["ast"]["name"] == "LogInc"

    def test_missing_sync_returns_error(self):
        mcp = _make_mcp(FIXTURES / "clean")
        body = _call(mcp, "read_sync", name="nope")
        assert "error" in body


class TestValidateSync:
    def test_clean_sync_has_no_errors(self):
        mcp = _make_mcp(FIXTURES / "clean")
        source = (FIXTURES / "clean" / "syncs" / "log.sync").read_text()
        body = _call(mcp, "validate_sync", source=source)
        # The clean fixture has both Counter and Logger concepts, so S1
        # should not fire.
        errors = [d for d in body["diagnostics"] if d["severity"] == "error"]
        assert errors == []


# ---------------------------------------------------------------------------
# Workspace tools
# ---------------------------------------------------------------------------


class TestValidateWorkspace:
    def test_clean_workspace_reports_no_errors(self):
        mcp = _make_mcp(FIXTURES / "clean")
        body = _call(mcp, "validate_workspace")
        errors = [d for d in body["diagnostics"] if d["severity"] == "error"]
        assert errors == []
        assert body["concept_count"] == 2
        assert body["sync_count"] == 1

    def test_with_error_workspace_reports_c5(self):
        mcp = _make_mcp(FIXTURES / "with_error")
        body = _call(mcp, "validate_workspace")
        codes = {d["code"] for d in body["diagnostics"]}
        assert "C5" in codes
        assert body["valid"] is False


class TestGetWorkspaceGraph:
    def test_clean_workspace_has_counter_and_sync_edge(self):
        mcp = _make_mcp(FIXTURES / "clean")
        s = mcp.tools["get_workspace_graph"]()
        assert s.startswith("graph TD")
        assert "Counter" in s
        assert "Logger" in s
        assert "LogInc" in s

    def test_empty_workspace_returns_placeholder(self):
        mcp = _make_mcp(FIXTURES / "empty")
        s = mcp.tools["get_workspace_graph"]()
        assert "No concepts" in s or "No syncs" in s

    def test_dependency_graph_alias_matches_workspace_graph(self):
        mcp = _make_mcp(FIXTURES / "clean")
        new = mcp.tools["get_workspace_graph"]()
        old = mcp.tools["get_dependency_graph"]()
        assert new == old


# ---------------------------------------------------------------------------
# Diff tools (smoke tests)
# ---------------------------------------------------------------------------


class TestDiffTools:
    def test_diff_concept_identical(self):
        mcp = _make_mcp(FIXTURES / "clean")
        source = (FIXTURES / "clean" / "concepts" / "Counter.concept").read_text()
        body = _call(mcp, "diff_concept", old_source=source, new_source=source)
        assert body["has_changes"] is False


# ---------------------------------------------------------------------------
# Explorer tools (smoke)
# ---------------------------------------------------------------------------


class TestExplorerTools:
    def test_get_explorer_html_returns_html(self):
        mcp = _make_mcp(FIXTURES / "clean")
        html = mcp.tools["get_explorer_html"]()
        assert "<html" in html
        assert "Counter" in html


# ---------------------------------------------------------------------------
# P4 gate — end-to-end pipeline against positive fixtures
# ---------------------------------------------------------------------------


class TestP4Gate:
    """
    End-to-end: every P4 MCP tool runs against a positive fixture workspace
    and produces a well-formed response.
    """

    REALWORLD = Path(__file__).parent / "fixtures" / "realworld"
    ARCHITECTURE_IDE = Path(__file__).parent / "fixtures" / "architecture_ide"

    @pytest.mark.parametrize("root", [REALWORLD, ARCHITECTURE_IDE])
    def test_whole_pipeline_on_positive_fixture(self, root: Path):
        mcp = _make_mcp(root)

        # list
        concepts = _call(mcp, "list_concepts")
        syncs = _call(mcp, "list_syncs")
        assert isinstance(concepts, list)
        assert isinstance(syncs, list)
        assert len(concepts) > 0

        # read one concept and one sync (if present)
        first_concept = concepts[0]
        read = _call(mcp, "read_concept", name=first_concept)
        assert "source" in read
        assert read["ast"]["name"]

        if syncs:
            first_sync = syncs[0]
            read_s = _call(mcp, "read_sync", name=first_sync)
            assert "source" in read_s

        # validate whole workspace
        vw = _call(mcp, "validate_workspace")
        errors = [d for d in vw["diagnostics"] if d["severity"] == "error"]
        assert errors == [], (
            f"positive fixture {root.name} should validate cleanly, got: "
            + json.dumps(errors, indent=2)
        )

        # workspace graph
        g = mcp.tools["get_workspace_graph"]()
        assert g.startswith("graph TD")
        for name in concepts:
            assert name in g

        # explorer HTML
        html = mcp.tools["get_explorer_html"]()
        assert "<html" in html
        for name in concepts:
            assert name in html
