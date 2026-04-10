"""
Validator rules for a single `SyncAST` (paper rules S1..S5).

Each rule is a pure function that takes the sync AST plus a
`WorkspaceIndex` (for cross-reference lookups) and returns a list of
`Diagnostic` records. Line/column information is best-effort: the P1
parser does not yet attach source positions to AST nodes, so most
diagnostics produced here use `line=None`.
"""

import re
from pathlib import Path

from concept_lang.ast import ActionPattern, SyncAST
from concept_lang.validate.diagnostic import Diagnostic
from concept_lang.validate.helpers import WorkspaceIndex

_VAR_RE = re.compile(r"\?[A-Za-z_][A-Za-z0-9_]*")


def _iter_patterns(sync: SyncAST) -> list[tuple[str, ActionPattern]]:
    """Yield (section_label, pattern) pairs for all action patterns in the sync."""
    out: list[tuple[str, ActionPattern]] = []
    for p in sync.when:
        out.append(("when", p))
    for p in sync.then:
        out.append(("then", p))
    return out


def rule_s1_references_resolve(
    sync: SyncAST,
    index: WorkspaceIndex,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    S1: Every `Concept/action` in `when`/`then` resolves to a known
    concept + action in the workspace.
    """
    diagnostics: list[Diagnostic] = []
    for section, pattern in _iter_patterns(sync):
        if pattern.concept not in index.concept_names:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    file=file,
                    line=None,
                    column=None,
                    code="S1",
                    message=(
                        f"sync '{sync.name}' {section} references unknown "
                        f"concept '{pattern.concept}' "
                        f"(in '{pattern.concept}/{pattern.action}')"
                    ),
                )
            )
            continue
        if index.action_cases(pattern.concept, pattern.action) is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    file=file,
                    line=None,
                    column=None,
                    code="S1",
                    message=(
                        f"sync '{sync.name}' {section} references action "
                        f"'{pattern.concept}/{pattern.action}' which is not "
                        f"declared on concept '{pattern.concept}'"
                    ),
                )
            )
    return diagnostics
