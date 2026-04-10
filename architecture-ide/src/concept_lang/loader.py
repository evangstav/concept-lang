"""
Directory-walking workspace loader for concept-lang 0.2.0.

`load_workspace(root)` reads every `.concept` file under `root/concepts/`
and every `.sync` file under `root/syncs/`, parses each into an AST,
and returns a populated `Workspace` plus a list of parse-error
`Diagnostic` records for any file that failed to parse. This is the
single entry point the MCP tool layer (P4) will use to read a workspace
from disk.

Partial loads are the happy path: a broken `Web.concept` produces a P0
diagnostic and is skipped, while the other concepts and every sync still
load normally. This mirrors the paper's "best effort, show everything"
philosophy — diagnostics are additive, never gating.

Diagnostic code convention
--------------------------
* ``L0`` — loader-level error: the workspace root directory does not
  exist. Emitted at most once per call, always with ``file=root``.
* ``P0`` — parse-level error: a single ``.concept`` or ``.sync`` file
  could not be parsed by Lark. The offending file is skipped; the rest
  of the workspace loads normally. Line is extracted from the Lark
  exception when available, otherwise ``None``.

Note: `.app` files are *not* loaded. The app-spec parser lives in the
untouched v1 module `concept_lang.app_parser` and will be migrated in
P4. Including it here would couple P3 to the v1 data model.
"""

from pathlib import Path

from concept_lang.ast import ConceptAST, SyncAST, Workspace
from concept_lang.parse import parse_concept_file, parse_sync_file
from concept_lang.validate.diagnostic import Diagnostic


def _extract_parse_line(exc: Exception) -> int | None:
    """Best-effort extraction of a 1-based source line from a Lark error."""
    line = getattr(exc, "line", None)
    if isinstance(line, int):
        return line
    return None


def load_workspace(root: Path) -> tuple[Workspace, list[Diagnostic]]:
    """
    Walk a workspace directory and parse every concept and sync file.

    Directory convention (enforced by the paper-alignment spec but
    discovered here by simple glob):

        <root>/concepts/**/*.concept
        <root>/syncs/**/*.sync

    Files under other subdirectories are ignored. Subdirectories below
    `concepts/` and `syncs/` are searched recursively so nested
    organisations (e.g. `concepts/auth/Password.concept`) are supported.

    Returns a ``(Workspace, diagnostics)`` tuple. ``Workspace`` contains
    every file that parsed successfully, keyed by the concept's / sync's
    own declared name (not the file name). ``diagnostics`` contains:

    * one ``L0`` error if ``root`` does not exist (in which case the
      workspace is empty), and
    * one ``P0`` error per file that failed to parse.

    A missing ``concepts/`` or ``syncs/`` subdirectory is *not* an error:
    "syncs only" and "concepts only" workspaces are valid.
    """
    diagnostics: list[Diagnostic] = []
    concepts: dict[str, ConceptAST] = {}
    syncs: dict[str, SyncAST] = {}

    if not root.exists():
        diagnostics.append(
            Diagnostic(
                severity="error",
                file=root,
                line=None,
                column=None,
                code="L0",
                message=f"workspace root does not exist: {root}",
            )
        )
        return Workspace(concepts=concepts, syncs=syncs), diagnostics

    concepts_dir = root / "concepts"
    syncs_dir = root / "syncs"

    if concepts_dir.is_dir():
        for path in sorted(concepts_dir.rglob("*.concept")):
            try:
                concept = parse_concept_file(path)
            except Exception as exc:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        file=path,
                        line=_extract_parse_line(exc),
                        column=None,
                        code="P0",
                        message=f"parse error: {exc}",
                    )
                )
                continue
            concepts[concept.name] = concept

    if syncs_dir.is_dir():
        for path in sorted(syncs_dir.rglob("*.sync")):
            try:
                sync = parse_sync_file(path)
            except Exception as exc:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        file=path,
                        line=_extract_parse_line(exc),
                        column=None,
                        code="P0",
                        message=f"parse error: {exc}",
                    )
                )
                continue
            syncs[sync.name] = sync

    return Workspace(concepts=concepts, syncs=syncs), diagnostics
