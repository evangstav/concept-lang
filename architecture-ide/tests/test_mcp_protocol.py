"""MCP protocol-level smoke test (P5 — P4 carry-over concerns #4 and #6).

This test creates a real ``FastMCP`` server via
``concept_lang.server.create_server`` and drives a handful of tools and
prompts through the in-process FastMCP API, asserting that the wire
responses round-trip without JSON or type errors. It does NOT start a
stdio subprocess — the in-process path exercises the same tool code
(the decorator, the function body, the JSON serialization, the response
envelope) as the stdio path minus only the framing, which has its own
upstream tests in the mcp package.

The ``_FakeMCP`` shim used by ``test_mcp_tools.py`` catches signature
issues but not wire-protocol issues. This file closes that gap:

* round-trips ``list_concepts``, ``read_concept``, ``validate_workspace``,
  and ``write_concept`` through the real ``FastMCP`` tool manager;
* exercises ``write_concept`` end-to-end against a fresh ``tmp_path``
  workspace, including disk persistence and a ``read_concept`` round-trip
  (P4 carry-over concern #6);
* renders both registered prompts (``build_concept`` and
  ``review_concepts``) through the real ``FastMCP`` prompt manager,
  verifying that the default-valued ``concept_names`` argument in
  ``review_concepts`` serializes correctly.

If this test fails, the tool layer is broken at a lower level than
the ``_FakeMCP`` tests can see. Read the error carefully.

The helper ``_call_tool_sync`` / ``_render_prompt_sync`` reach into
``FastMCP`` internals (``_tool_manager`` and ``_prompt_manager``).
These are the only places that depend on internal ``mcp`` layout; if
the package exposes a public in-process API in the future, swap the
internals out here and nowhere else.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from concept_lang.server import create_server


# The ``mcp/clean`` fixture (Counter + Logger + log.sync) already exists
# from P4 and is gated out of both ``TestP1Gate`` (excludes ``mcp``) and
# ``TestP3Gate`` (iterates only ``architecture_ide`` + ``realworld``),
# so reusing it here adds no surface to the positive-fixture gates.
FIXTURE = Path(__file__).parent / "fixtures" / "mcp" / "clean"


@pytest.fixture(scope="module")
def server():
    return create_server(str(FIXTURE))


def _call_tool_sync(server, name: str, arguments: dict[str, Any] | None = None) -> str:
    """Synchronously drive a FastMCP tool through the in-process API.

    Every tool in concept-lang is currently a plain (non-async) function,
    but the helper handles coroutine functions as well so future async
    tools do not silently break the smoke test.
    """
    arguments = arguments or {}
    tool = server._tool_manager._tools[name]
    fn = tool.fn
    if inspect.iscoroutinefunction(fn):
        result = asyncio.run(fn(**arguments))
    else:
        result = fn(**arguments)
    return result


def _render_prompt_sync(server, name: str, arguments: dict[str, Any] | None = None):
    """Synchronously render a FastMCP prompt through the in-process API."""
    return asyncio.run(server._prompt_manager.render_prompt(name, arguments))


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


class TestToolRegistration:
    def test_expected_tools_are_registered(self, server):
        names = set(server._tool_manager._tools.keys())
        expected = {
            "list_concepts",
            "read_concept",
            "write_concept",
            "validate_concept",
            "list_syncs",
            "read_sync",
            "write_sync",
            "validate_sync",
            "validate_workspace",
            "get_workspace_graph",
        }
        missing = expected - names
        assert not missing, f"expected tools not registered: {missing}"


# ---------------------------------------------------------------------------
# list_concepts
# ---------------------------------------------------------------------------


class TestListConcepts:
    def test_returns_json_array_of_names(self, server):
        raw = _call_tool_sync(server, "list_concepts")
        assert isinstance(raw, str), (
            f"list_concepts should return a JSON string, got {type(raw).__name__}"
        )
        data = json.loads(raw)
        assert isinstance(data, list), f"expected list, got {type(data).__name__}"
        # The mcp/clean fixture ships Counter + Logger.
        assert "Counter" in data
        assert "Logger" in data


# ---------------------------------------------------------------------------
# read_concept
# ---------------------------------------------------------------------------


class TestReadConcept:
    def test_returns_source_and_ast(self, server):
        raw = _call_tool_sync(server, "read_concept", {"name": "Counter"})
        assert isinstance(raw, str)
        data = json.loads(raw)
        assert "source" in data
        assert "ast" in data
        assert data["ast"]["name"] == "Counter"
        # The Counter fixture has at least one action.
        assert isinstance(data["ast"].get("actions"), list)
        assert len(data["ast"]["actions"]) >= 1

    def test_unknown_concept_returns_error(self, server):
        raw = _call_tool_sync(server, "read_concept", {"name": "Ghost"})
        assert isinstance(raw, str)
        data = json.loads(raw)
        assert "error" in data


# ---------------------------------------------------------------------------
# validate_workspace
# ---------------------------------------------------------------------------


class TestValidateWorkspace:
    def test_returns_envelope_with_diagnostics_list(self, server):
        raw = _call_tool_sync(server, "validate_workspace")
        assert isinstance(raw, str)
        data = json.loads(raw)
        assert "valid" in data
        assert "diagnostics" in data
        assert isinstance(data["diagnostics"], list)
        # Every diagnostic on the wire has the canonical shape. The
        # mcp/clean fixture happens to produce zero diagnostics today,
        # but we intentionally do not depend on that — we only assert
        # every diagnostic (if any) has code/severity/message.
        for d in data["diagnostics"]:
            assert "code" in d, f"diagnostic missing 'code': {d}"
            assert "severity" in d, f"diagnostic missing 'severity': {d}"
            assert "message" in d, f"diagnostic missing 'message': {d}"


# ---------------------------------------------------------------------------
# write_concept — P4 carry-over concern #6
# ---------------------------------------------------------------------------


class TestWriteConcept:
    """Exercise ``write_concept`` end-to-end against a fresh tmp workspace
    so the positive-fixture gate doesn't have to. This round-trips a new
    concept through the FastMCP tool layer, verifies the file lands on
    disk, and reads it back via ``read_concept``.
    """

    _NOTE_SOURCE = """\
concept Note [N]

  purpose
    store short textual notes keyed by a note identifier

  state
    notes: set N
    text: N -> string

  actions
    create [ note: N ; text: string ] => [ note: N ]
      create a new note with the given text
      effects:
        notes += note
        text[note] := text

    create [ note: N ; text: string ] => [ error: string ]
      if the note already exists
      return the error description

  operational principle
    after create [ note: n ; text: "hello" ] => [ note: n ]
    then create [ note: n ; text: "hello" ] => [ error: "already exists" ]
"""

    def test_write_then_read_round_trip(self, tmp_path):
        srv = create_server(str(tmp_path))
        raw = _call_tool_sync(
            srv, "write_concept", {"name": "Note", "source": self._NOTE_SOURCE}
        )
        assert isinstance(raw, str)
        data = json.loads(raw)
        assert data.get("written") is True, (
            "write_concept refused to write the Note fixture: "
            + json.dumps(data, indent=2)
        )

        # Verify the file actually lands on disk.
        written_path = tmp_path / "concepts" / "Note.concept"
        assert written_path.exists(), (
            f"write_concept claimed success but {written_path} does not exist"
        )
        assert written_path.read_text(encoding="utf-8") == self._NOTE_SOURCE

        # Round-trip through read_concept on the same server.
        raw2 = _call_tool_sync(srv, "read_concept", {"name": "Note"})
        data2 = json.loads(raw2)
        assert "error" not in data2, (
            f"read_concept failed after write_concept: {data2}"
        )
        assert data2["ast"]["name"] == "Note"
        assert data2["source"] == self._NOTE_SOURCE


# ---------------------------------------------------------------------------
# Prompts — default-valued argument round-trip
# ---------------------------------------------------------------------------


class TestPrompts:
    def test_build_concept_renders_with_required_arg(self, server):
        messages = _render_prompt_sync(
            server, "build_concept", {"description": "a simple counter"}
        )
        assert isinstance(messages, list)
        assert len(messages) >= 1
        first = messages[0]
        assert getattr(first, "role", None) == "user"
        text = getattr(first.content, "text", None)
        assert isinstance(text, str)
        assert "simple counter" in text
        # The 0.2.0 prompt body pins the new section layout:
        assert "concept-lang 0.2.0" in text

    def test_review_concepts_default_arg_serializes(self, server):
        """``review_concepts`` declares ``concept_names: str = ""`` — the
        default-valued argument must round-trip through FastMCP without
        tripping pydantic's signature validator. This was flagged in the
        Batch 5 report as a prompt-signature sharp edge."""
        messages = _render_prompt_sync(server, "review_concepts")
        assert isinstance(messages, list)
        assert len(messages) >= 1
        text = messages[0].content.text
        assert isinstance(text, str)
        # Default scope renders the "whole workspace" wording.
        assert "whole workspace" in text

    def test_review_concepts_explicit_arg_serializes(self, server):
        """Passing the argument explicitly as a string should also round-trip.
        FastMCP enforces the declared type (``str``) via pydantic; this test
        pins the contract so a future rewrite that accidentally widens the
        type to ``list[str]`` gets caught."""
        messages = _render_prompt_sync(
            server, "review_concepts", {"concept_names": "Counter, Logger"}
        )
        assert isinstance(messages, list)
        assert len(messages) >= 1
        text = messages[0].content.text
        assert "Counter, Logger" in text
