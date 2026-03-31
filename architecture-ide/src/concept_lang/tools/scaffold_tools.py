"""
scaffold_concepts — analyse an existing codebase and return a structured payload
for Claude to extract draft .concept specs.

Workflow:
  1. Scan source_dir for source files, filtering noise, prioritising domain files
  2. Build a truncated code payload (≤40k chars)
  3. Return the payload + system prompt so Claude Code can do the analysis
     (Claude Code uses the subscription; no ANTHROPIC_API_KEY required)
"""

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

_SOURCE_EXTS = {".py", ".ts", ".js", ".go", ".java", ".rb", ".rs", ".swift", ".kt", ".cs"}

_SKIP_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__", ".git",
    "dist", "build", ".next", ".nuxt", "coverage", ".mypy_cache",
    ".pytest_cache", "target", "vendor",
}

_PRIORITY_PATTERNS = [
    "model", "schema", "entity", "domain", "service", "route",
    "controller", "handler", "type", "interface", "store", "repo",
]

_METHODOLOGY = """\
You are an expert in Daniel Jackson's concept design methodology from "The Essence of Software".

A concept spec has this format:
    concept Name [Param, ...]
      purpose
        One sentence stating the essential service this concept provides.

      state
        name: set T            (a set of elements of type T)
        name: parent           (a subset of an existing set)
        name: T -> set U       (a relation from elements of T to elements of U)

      actions
        action_name (param: Type, ...)
          pre: condition clause
          post: state_change    (use += to add, -= to remove from sets)

      sync
        when OtherConcept.action (params) then local_action (params)

Key principles:
- Each concept must have a SINGLE, INDEPENDENT purpose
- State should be minimal — only what's needed to define action semantics
- Prefer subset progressions (named: set T / purposeful: named / specified: purposeful)
  over flat attribute lists when entities have a lifecycle
- Concepts are INDEPENDENT — no concept should embed another's logic
"""


def _collect_files(source_dir: str, max_files: int) -> list[tuple[str, str]]:
    """Return list of (relative_path, truncated_content) tuples."""
    root = Path(source_dir).resolve()
    candidates: list[tuple[int, Path]] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in _SOURCE_EXTS:
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        name_lower = path.stem.lower()
        if any(x in name_lower for x in ("test", "spec", "mock", "fixture", "migration")):
            continue
        is_priority = any(pat in name_lower for pat in _PRIORITY_PATTERNS)
        candidates.append((0 if is_priority else 1, path))

    candidates.sort(key=lambda x: (x[0], str(x[1])))
    selected = [p for _, p in candidates[:max_files]]

    result = []
    for path in selected:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            truncated = "\n".join(lines[:150])
            if len(lines) > 150:
                truncated += f"\n... ({len(lines) - 150} more lines)"
            result.append((str(path.relative_to(root)), truncated))
        except OSError:
            pass

    return result


def _build_payload(files: list[tuple[str, str]]) -> str:
    parts = []
    total = 0
    for rel_path, content in files:
        chunk = f"### {rel_path}\n```\n{content}\n```\n"
        if total + len(chunk) > 40_000:
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n".join(parts)


def register_scaffold_tools(mcp: FastMCP, concepts_dir: str) -> None:

    @mcp.tool(
        description=(
            "Collect source files from an existing codebase to scaffold Jackson-style .concept specs. "
            "Returns the file payload and methodology context. "
            "After calling this tool, YOU (Claude) should analyse the payload, identify 3–8 core concepts, "
            "and call write_concept(name, source) for each one. "
            "No API key required — you perform the analysis using your existing session."
        )
    )
    def scaffold_concepts(source_dir: str, max_files: int = 20) -> str:
        if not os.path.isdir(source_dir):
            return json.dumps({"error": f"source_dir not found: {source_dir}"})

        try:
            files = _collect_files(source_dir, max_files)
            if not files:
                return json.dumps({"error": "No source files found in source_dir"})

            payload = _build_payload(files)
            return json.dumps({
                "files_analysed": len(files),
                "file_list": [f for f, _ in files],
                "concepts_dir": concepts_dir,
                "instructions": (
                    "Analyse the source code below and identify 3–8 core concepts in Jackson's sense. "
                    "For each concept, call write_concept(name=..., source=...) with a valid .concept spec. "
                    "Focus on domain entities with lifecycle, not utilities or infrastructure. "
                    "Use subset progressions where entities move through stages."
                ),
                "methodology": _METHODOLOGY,
                "source_code": payload,
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
