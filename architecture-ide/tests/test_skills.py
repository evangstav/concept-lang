"""
Skill-lint contract tests (concept-lang 0.2.0 — P5 Tasks 1 & 2).

These tests enforce a contract between the skills directory
(`skills/*/SKILL.md` at the repo root) and the MCP tool layer
(`concept_lang.server.create_server()`).

The contract, pinned in the P5 implementation plan (design decisions
(A)–(C), (J) and the "Lint contract" block), is:

  1. Every SKILL.md has a parseable YAML frontmatter with a non-empty
     `description` and a comma-separated `allowed-tools` list whose
     entries all match real registered MCP tools.
  2. Every tool named in `allowed-tools` uses the
     `mcp__concept-lang__<name>` namespace.
  3. For skills that take arguments, `argument-hint` is a non-empty
     string. The `explore` skill is arg-free and exempt.
  4. For build / build-sync / scaffold / explore,
     `disable-model-invocation` is `true`. For `review`, the field is
     optional. (Not enforced in this scaffold — pinned by later tasks.)
  5. The body of each *rewritten* skill contains no forbidden phrase
     from the FORBIDDEN_PHRASES list. Skills in `_rewritten_skills` are
     the ones that have already been rewritten for v2; non-rewritten
     skills are exempt from the forbidden-phrase check while the
     rewrite sequence is in flight.

This scaffold (Task 2) enforces (1), (2), (3) plus an
`allowed-tools`-must-resolve check against the real registry (with an
explicit ignore list for tools that P5 has not yet wired into the
registry). It runs FORBIDDEN_PHRASES only against skills in the
`_rewritten_skills` set — which starts EMPTY — so the scaffold goes
green on the v1 skills as they stand today. Later rewrite tasks
(Batch 2+) add their skill name to `_rewritten_skills` and the
forbidden-phrase check activates for them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from concept_lang.server import create_server


# tests/test_skills.py lives at architecture-ide/tests/test_skills.py.
# parents[0] = tests/, parents[1] = architecture-ide/, parents[2] = repo root.
REPO_ROOT = Path(__file__).parents[2]
SKILLS_DIR = REPO_ROOT / "skills"


# ---------------------------------------------------------------------------
# Forbidden-phrase list (design decision (J)).
#
# Every entry is a (regex, rationale) pair. Rewritten skills (those in
# _REWRITTEN_SKILLS) MUST NOT contain any of these patterns in their body.
# Non-rewritten skills are exempt.
# ---------------------------------------------------------------------------
FORBIDDEN_PHRASES: list[tuple[str, str]] = [
    (
        r"\bget_dependency_graph\b",
        "Removed in 0.3.0 — rewritten skills must call get_workspace_graph. "
        "The alias was deleted in P7.",
    ),
    (
        r"\bcodegen_tools\b",
        "codegen_tools is out of scope for v2 skills and scheduled for P7 removal.",
    ),
    (
        r"(?m)^\s*sync\s*$",
        "v1 inline `sync` section header — syncs are now separate .sync files.",
    ),
    (
        r"(?m)^\s*pre:\s",
        "v1 `pre:` keyword — v2 uses hybrid natural-language bodies plus `effects:`.",
    ),
    (
        r"(?m)^\s*post:\s",
        "v1 `post:` keyword — v2 uses hybrid natural-language bodies plus `effects:`.",
    ),
    (
        r"SyncClause\.trigger_concept",
        "v1 internal wire format — the AST is now concept_lang.ast.SyncAST.",
    ),
]


# ---------------------------------------------------------------------------
# Known-ignore list for tools that a skill references but that are not (yet)
# registered by the MCP server. Keyed by skill directory name → set of tool
# names (the bare name, without the `mcp__concept-lang__` prefix). As P5
# Batches 2+ land new tools, entries drop out of this dict. The dict lets
# the scaffold pass even if a pre-rewrite skill names a tool that P4
# removed.
# ---------------------------------------------------------------------------
KNOWN_IGNORE_TOOLS: dict[str, set[str]] = {
    # All current v2 skills only reference tools that resolve via the P4
    # registry. The get_dependency_graph back-compat alias was removed in
    # 0.3.0 (P7) so no skill may reference it — any match is a regression
    # and the FORBIDDEN_PHRASES entry above catches it.
}


# ---------------------------------------------------------------------------
# Skills that have been rewritten for v2 and are therefore subject to the
# full FORBIDDEN_PHRASES lint. Starts EMPTY. Each P5 rewrite batch
# (T3/build, T4/build-sync, T5/review, T6/scaffold, T7/explore) adds its
# skill name to this set as it lands.
# ---------------------------------------------------------------------------
_REWRITTEN_SKILLS: set[str] = {"build", "build-sync", "review", "scaffold", "explore"}


# Skills that are arg-free by design and exempt from the `argument-hint`
# required-field check.
_ARG_FREE_SKILLS: set[str] = {"explore"}


def _discover_skills() -> list[Path]:
    """Return a sorted list of SKILL.md paths under skills/*/."""
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def _rewritten_skill_paths() -> list[Path]:
    """Return SKILL.md paths for skills that have been rewritten for v2.

    Used as the parametrize source for TestForbiddenPhrases so that
    non-rewritten skills are skipped rather than xfailed. As rewrite
    tasks land, they add the skill name to `_REWRITTEN_SKILLS`.
    """
    return [p for p in _discover_skills() if p.parent.name in _REWRITTEN_SKILLS]


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a SKILL.md file into (frontmatter_dict, body_string).

    Raises ValueError if the frontmatter is malformed.
    """
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with '---' on the first line")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("SKILL.md frontmatter must close with '---'")
    frontmatter_text = text[4:end]
    body = text[end + 5 :]
    data = yaml.safe_load(frontmatter_text)
    if not isinstance(data, dict):
        raise ValueError("SKILL.md frontmatter must be a YAML mapping")
    return data, body


def _parse_allowed_tools(raw: object) -> list[str]:
    """Normalize `allowed-tools` to a list of bare strings."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    raise ValueError(
        f"allowed-tools must be a list or comma-separated string, "
        f"got {type(raw).__name__}"
    )


def _real_mcp_tool_names(workspace_root: Path) -> set[str]:
    """Return the set of tool names the real MCP server registers.

    FastMCP exposes registered tools via its internal `_tool_manager`
    attribute as of mcp 1.2+. Its public `list_tools()` coroutine returns
    the same set but requires an event loop, which the lint does not
    want. If a future mcp release renames the private attribute, this
    helper fails loudly — the rename is a trivial fix.
    """
    server = create_server(str(workspace_root))
    tool_manager = getattr(server, "_tool_manager", None)
    assert tool_manager is not None, (
        "FastMCP._tool_manager not found; skill-lint needs a way to "
        "enumerate registered tools without going async. Check mcp version."
    )
    return set(tool_manager._tools.keys())


@pytest.fixture(scope="module")
def real_tool_names(tmp_path_factory) -> set[str]:
    """Snapshot of tool names registered by the real server.

    Uses a throwaway workspace so create_server has a valid path to point
    at; tool enumeration does not depend on workspace contents.
    """
    tmp = tmp_path_factory.mktemp("skill_lint_workspace")
    (tmp / "concepts").mkdir()
    (tmp / "syncs").mkdir()
    return _real_mcp_tool_names(tmp)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSkillFilesExist:
    def test_skills_directory_exists(self) -> None:
        assert SKILLS_DIR.is_dir(), f"skills/ directory missing at {SKILLS_DIR}"

    def test_at_least_one_skill(self) -> None:
        assert _discover_skills(), "no SKILL.md files found under skills/"


class TestFrontmatterParses:
    @pytest.mark.parametrize(
        "skill_path", _discover_skills(), ids=lambda p: p.parent.name
    )
    def test_frontmatter_is_valid_yaml(self, skill_path: Path) -> None:
        text = skill_path.read_text()
        data, _body = _split_frontmatter(text)
        assert isinstance(data, dict)

    @pytest.mark.parametrize(
        "skill_path", _discover_skills(), ids=lambda p: p.parent.name
    )
    def test_description_is_non_empty_string(self, skill_path: Path) -> None:
        text = skill_path.read_text()
        data, _body = _split_frontmatter(text)
        desc = data.get("description")
        assert (
            isinstance(desc, str) and desc.strip()
        ), f"{skill_path.parent.name}: missing or empty 'description' field"

    @pytest.mark.parametrize(
        "skill_path", _discover_skills(), ids=lambda p: p.parent.name
    )
    def test_argument_hint_present_unless_arg_free(self, skill_path: Path) -> None:
        name = skill_path.parent.name
        text = skill_path.read_text()
        data, _body = _split_frontmatter(text)
        if name in _ARG_FREE_SKILLS:
            return
        hint = data.get("argument-hint")
        assert (
            isinstance(hint, str) and hint.strip()
        ), (
            f"{name}: missing or empty 'argument-hint' field. "
            f"Arg-free skills must be listed in _ARG_FREE_SKILLS."
        )

    @pytest.mark.parametrize(
        "skill_path", _discover_skills(), ids=lambda p: p.parent.name
    )
    def test_allowed_tools_parses(self, skill_path: Path) -> None:
        text = skill_path.read_text()
        data, _body = _split_frontmatter(text)
        tools = _parse_allowed_tools(data.get("allowed-tools"))
        assert tools, (
            f"{skill_path.parent.name}: allowed-tools must list at least one tool"
        )


class TestAllowedToolsNamespace:
    @pytest.mark.parametrize(
        "skill_path", _discover_skills(), ids=lambda p: p.parent.name
    )
    def test_every_tool_uses_concept_lang_namespace(self, skill_path: Path) -> None:
        text = skill_path.read_text()
        data, _body = _split_frontmatter(text)
        tools = _parse_allowed_tools(data.get("allowed-tools"))
        for tool in tools:
            assert tool.startswith("mcp__concept-lang__"), (
                f"{skill_path.parent.name}: tool '{tool}' does not use the "
                f"'mcp__concept-lang__' namespace"
            )


class TestAllowedToolsResolve:
    @pytest.mark.parametrize(
        "skill_path", _discover_skills(), ids=lambda p: p.parent.name
    )
    def test_every_tool_is_registered_or_ignored(
        self, skill_path: Path, real_tool_names: set[str]
    ) -> None:
        name = skill_path.parent.name
        text = skill_path.read_text()
        data, _body = _split_frontmatter(text)
        tools = _parse_allowed_tools(data.get("allowed-tools"))
        ignored = KNOWN_IGNORE_TOOLS.get(name, set())
        for tool in tools:
            bare = tool.removeprefix("mcp__concept-lang__")
            if bare in ignored:
                continue
            assert bare in real_tool_names, (
                f"{name}: tool '{tool}' is not registered by the MCP server "
                f"and is not in KNOWN_IGNORE_TOOLS[{name!r}]. "
                f"Registered tools: {sorted(real_tool_names)}"
            )


class TestForbiddenPhrases:
    """Forbidden-phrase lint — only runs against skills in _REWRITTEN_SKILLS.

    The set starts EMPTY. Each P5 rewrite batch adds its skill name as it
    lands. Non-rewritten skills are exempt while the rewrite sequence is
    in flight, which keeps the scaffold green without needing xfail
    markers.
    """

    @pytest.mark.parametrize(
        "skill_path", _rewritten_skill_paths(), ids=lambda p: p.parent.name
    )
    def test_no_forbidden_phrase(self, skill_path: Path) -> None:
        text = skill_path.read_text()
        _data, body = _split_frontmatter(text)
        failures: list[str] = []
        for pattern, rationale in FORBIDDEN_PHRASES:
            if re.search(pattern, body):
                failures.append(f"  - `{pattern}`: {rationale}")
        assert not failures, (
            f"{skill_path.parent.name}: forbidden phrases found in body:\n"
            + "\n".join(failures)
        )
