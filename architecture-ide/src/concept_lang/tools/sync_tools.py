"""MCP tools for .sync files (v2 — new)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from concept_lang.parse import parse_sync_source
from concept_lang.validate import validate_sync_file

from ._io import load_workspace_from_root, syncs_dir_for


def _diag_list(diags) -> list[dict]:
    return [d.model_dump(mode="json") for d in diags]


def register_sync_tools(mcp: FastMCP, workspace_root: str) -> None:

    @mcp.tool(description="List all .sync files in the workspace")
    def list_syncs() -> str:
        directory = syncs_dir_for(workspace_root)
        if not directory.is_dir():
            return json.dumps([])
        names = sorted(p.stem for p in directory.glob("*.sync"))
        return json.dumps(names)

    @mcp.tool(
        description=(
            "Read and parse a .sync file. Returns the raw source and the "
            "parsed AST as JSON. Pass the sync name without the .sync "
            "extension."
        )
    )
    def read_sync(name: str) -> str:
        path = syncs_dir_for(workspace_root) / f"{name}.sync"
        if not path.exists():
            return json.dumps({"error": f"Sync '{name}' not found"})
        source = path.read_text(encoding="utf-8")
        try:
            ast = parse_sync_source(source)
        except Exception as exc:
            return json.dumps({"error": f"Parse error: {exc}"})
        return json.dumps({
            "source": source,
            "ast": ast.model_dump(exclude={"source"}),
        })

    @mcp.tool(
        description=(
            "Write or overwrite a .sync file. Validates the source (parser "
            "+ rules S1..S5 against the workspace concepts) before writing. "
            "Refuses the write if any error-level diagnostic fires."
        )
    )
    def write_sync(name: str, source: str) -> str:
        diagnostics = _validate_sync_source(
            source=source, name=name, workspace_root=workspace_root
        )
        if any(d.severity == "error" for d in diagnostics):
            return json.dumps({
                "written": False,
                "valid": False,
                "diagnostics": _diag_list(diagnostics),
            })

        target_dir = syncs_dir_for(workspace_root)
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{name}.sync"
        path.write_text(source, encoding="utf-8")
        return json.dumps({
            "written": True,
            "valid": True,
            "path": str(path),
            "diagnostics": _diag_list(diagnostics),
        })

    @mcp.tool(
        description=(
            "Validate .sync source text without writing to disk. Runs "
            "S1..S5 against the surrounding workspace concepts. Returns "
            "the diagnostic list."
        )
    )
    def validate_sync(source: str) -> str:
        diagnostics = _validate_sync_source(
            source=source, name=None, workspace_root=workspace_root
        )
        return json.dumps({
            "valid": not any(d.severity == "error" for d in diagnostics),
            "diagnostics": _diag_list(diagnostics),
        })


def _validate_sync_source(
    *,
    source: str,
    name: str | None,
    workspace_root: str,
) -> list:
    """
    Shared validation path for ``validate_sync`` and ``write_sync``.

    1. Write ``source`` to a temp ``.sync`` file under the workspace's
       ``syncs/`` directory.
    2. Load the surrounding workspace so its concepts are available for
       cross-reference rules (S1, S2).
    3. Call ``validate_sync_file(temp_path, extra_concepts=workspace.concepts)``.
    4. Clean up the temp file.
    """
    temp_path: Path | None = None
    try:
        parent = syncs_dir_for(workspace_root)
        parent.mkdir(parents=True, exist_ok=True)
        suffix = f"_{name}.sync" if name else ".sync"
        fd, raw = tempfile.mkstemp(
            prefix="_validate_", suffix=suffix, dir=parent
        )
        temp_path = Path(raw)
        with open(fd, "w", encoding="utf-8") as f:
            f.write(source)

        workspace, _load_diags = load_workspace_from_root(workspace_root)
        diagnostics = validate_sync_file(
            temp_path, extra_concepts=workspace.concepts
        )

        # The temp file name leaks into diagnostic messages via the
        # `file=` field. Callers that want a real name should look at
        # the sync's declared name (S1/S2 diagnostics include it in the
        # message string).
        return diagnostics
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
