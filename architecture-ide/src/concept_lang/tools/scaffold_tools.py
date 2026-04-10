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
You are an expert in Daniel Jackson's concept design methodology as used by concept-lang 0.2.0.

A concept file has this shape:

    concept <Name> [<TypeParam1>, <TypeParam2>, ...]

      purpose
        <one sentence — the essential service this concept provides>

      state
        <field>: <type-expression>
        <field>: <type-expression>
        ...

      actions
        <action_name> [ <in1>: <T1> ; <in2>: <T2> ] => [ <out1>: <U1> ]
          <1-4 lines of hybrid natural-language describing the success case>
          effects: <optional += / -= statements on state fields>

        <action_name> [ <in1>: <T1> ; <in2>: <T2> ] => [ error: string ]
          <describe when this case fires>

        ... (every action should have at least one success case AND at least one error case)

      operational principle
        after <action_name> [ <in>: <val> ] => [ <out>: <val> ]
        and   <action_name> [ <in>: <val> ] => [ <out>: <val> ]
        then  <action_name> [ <in>: <val> ] => [ <out>: <val> ]

Key rules:
- Each concept has a SINGLE, INDEPENDENT purpose. A concept file stands on its own.
- State is minimal — only the fields needed by the action semantics.
- Actions always have named inputs AND named outputs, inside square brackets.
- Every distinct outcome is its own case block. Do NOT collapse success and error into one case with conditional returns.
- There is NO inline sync section in a concept file. Syncs live in separate .sync files.
- The operational principle is its own section, with 2-4 after/and/then steps that walk through a typical scenario.

Syncs are separate .sync files with this shape:

    sync <SyncName>

      when
        <Concept>/<action>: [ <input_patterns> ] => [ <output_patterns> ]

      where
        bind (<expression> as ?<variable>)

      then
        <Concept>/<action>: [ <input_patterns> ]

Syncs compose existing concepts — they may NOT reference actions that do not exist.
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
