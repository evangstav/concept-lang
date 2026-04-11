"""Shared helpers for the MCP tool layer (v2 — workspace-root aware)."""

from __future__ import annotations

from pathlib import Path

from concept_lang.ast import Workspace
from concept_lang.loader import load_workspace
from concept_lang.validate.diagnostic import Diagnostic


def resolve_workspace_root(raw: str) -> Path:
    """
    Turn a raw string (from an env var or MCP server arg) into a
    canonical workspace root path.

    Heuristic:
    * If ``raw`` points at a directory whose basename is ``concepts`` or
      ``syncs`` (without the leading dot), treat its **parent** as the
      workspace root. This keeps legacy installations that set
      ``CONCEPTS_DIR=./concepts`` working without changes.
    * Otherwise (including ``.concepts`` — the 0.3.1+ hidden-directory
      convention) treat ``raw`` itself as the workspace root.
    """
    p = Path(raw).expanduser()
    if p.name in ("concepts", "syncs"):
        return p.parent
    return p


def load_workspace_from_root(
    workspace_root: str,
) -> tuple[Workspace, list[Diagnostic]]:
    """
    Call ``concept_lang.loader.load_workspace`` with a resolved root.

    Returns a ``(Workspace, diagnostics)`` tuple identical to the loader's.
    This helper exists so that every MCP tool uses the same resolution
    heuristic without repeating the Path massaging.
    """
    root = resolve_workspace_root(workspace_root)
    return load_workspace(root)


def concepts_dir_for(workspace_root: str) -> Path:
    """Return the canonical ``<root>/concepts`` directory."""
    return resolve_workspace_root(workspace_root) / "concepts"


def syncs_dir_for(workspace_root: str) -> Path:
    """Return the canonical ``<root>/syncs`` directory."""
    return resolve_workspace_root(workspace_root) / "syncs"
