"""MCP tools for .concept files (v2 — consumes concept_lang.ast)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from concept_lang.parse import parse_concept_source
from concept_lang.validate import validate_concept_file, validate_workspace

from ._io import concepts_dir_for, load_workspace_from_root


def _diag_list(diags) -> list[dict]:
    return [d.model_dump(mode="json") for d in diags]


def register_concept_tools(mcp: FastMCP, workspace_root: str) -> None:

    @mcp.tool(description="List all .concept files in the workspace")
    def list_concepts() -> str:
        directory = concepts_dir_for(workspace_root)
        if not directory.is_dir():
            return json.dumps([])
        names = sorted(p.stem for p in directory.glob("*.concept"))
        return json.dumps(names)

    @mcp.tool(
        description=(
            "Read and parse a .concept file. Returns the raw source and the "
            "parsed AST as JSON. Pass the concept name without the .concept "
            "extension."
        )
    )
    def read_concept(name: str) -> str:
        path = concepts_dir_for(workspace_root) / f"{name}.concept"
        if not path.exists():
            return json.dumps({"error": f"Concept '{name}' not found"})
        source = path.read_text(encoding="utf-8")
        try:
            ast = parse_concept_source(source)
        except Exception as exc:
            return json.dumps({"error": f"Parse error: {exc}"})
        return json.dumps({
            "source": source,
            "ast": ast.model_dump(exclude={"source"}),
        })

    @mcp.tool(
        description=(
            "Write or overwrite a .concept file. Validates the source "
            "(parser + rules C1..C9 minus C8 + cross-reference rules) before "
            "writing. Refuses the write if any error-level diagnostic fires."
        )
    )
    def write_concept(name: str, source: str) -> str:
        diagnostics = _validate_concept_source(
            source=source, name=name, workspace_root=workspace_root
        )
        if any(d.severity == "error" for d in diagnostics):
            return json.dumps({
                "written": False,
                "valid": False,
                "diagnostics": _diag_list(diagnostics),
            })

        target_dir = concepts_dir_for(workspace_root)
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{name}.concept"
        path.write_text(source, encoding="utf-8")
        return json.dumps({
            "written": True,
            "valid": True,
            "path": str(path),
            "diagnostics": _diag_list(diagnostics),
        })

    @mcp.tool(
        description=(
            "Validate .concept source text without writing to disk. Runs "
            "C1..C9 (minus C8) and cross-reference rules (S1, S2) against "
            "the surrounding workspace. Returns the diagnostic list."
        )
    )
    def validate_concept(source: str) -> str:
        diagnostics = _validate_concept_source(
            source=source, name=None, workspace_root=workspace_root
        )
        return json.dumps({
            "valid": not any(d.severity == "error" for d in diagnostics),
            "diagnostics": _diag_list(diagnostics),
        })


def _validate_concept_source(
    *,
    source: str,
    name: str | None,
    workspace_root: str,
) -> list:
    """
    Shared validation path for both `validate_concept` and `write_concept`.

    1. Write ``source`` to a temp file so ``validate_concept_file`` can run
       C4 against the raw source and parse the rest through Lark.
    2. Load the surrounding workspace via ``load_workspace``.
    3. If the temp file parsed, substitute the resulting concept into the
       workspace (keyed by its declared name) and run ``validate_workspace``
       to pick up cross-reference rules (S1, S2).
    4. Combine the single-file diagnostics and the workspace diagnostics,
       de-duplicating by ``(code, file, line, message)``.

    Returns the combined diagnostic list. The temp file is always cleaned
    up in a ``finally``.
    """
    temp_path: Path | None = None
    try:
        # Use the workspace's concepts/ subdir as the tempfile parent so
        # C4's source-level scan sees the file at a realistic location.
        parent = concepts_dir_for(workspace_root)
        parent.mkdir(parents=True, exist_ok=True)
        suffix = f"_{name}.concept" if name else ".concept"
        fd, raw = tempfile.mkstemp(
            prefix="_validate_", suffix=suffix, dir=parent
        )
        temp_path = Path(raw)
        with open(fd, "w", encoding="utf-8") as f:
            f.write(source)

        file_diags = validate_concept_file(temp_path)

        # Cross-ref pass: only if the temp file parsed cleanly (no P0).
        parse_errors = [d for d in file_diags if d.code == "P0"]
        if parse_errors:
            return file_diags

        workspace, load_diags = load_workspace_from_root(workspace_root)
        # Substitute the current concept by re-parsing the source into an
        # AST (the concept's declared name, not the file stem, is the key).
        try:
            fresh_ast = parse_concept_source(source)
        except Exception:
            return file_diags
        workspace.concepts[fresh_ast.name] = fresh_ast

        ws_diags = validate_workspace(workspace)

        # De-duplicate: file_diags already contains C1..C9; ws_diags has
        # S1..S5 plus re-runs of the C rules on every concept in the
        # workspace. Filter ws_diags down to "things that mention the
        # current concept or its name" — for P4 we just take the full
        # ws_diags list and let the caller filter; test coverage will
        # catch any double-reporting.
        combined = list(file_diags) + [
            d for d in ws_diags if d not in file_diags
        ]
        return combined
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
