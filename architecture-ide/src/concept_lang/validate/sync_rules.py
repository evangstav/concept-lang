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


def rule_s2_pattern_fields_exist(
    sync: SyncAST,
    index: WorkspaceIndex,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    S2: Input/output pattern field names referenced in an action pattern
    must exist in at least one case of that action's signature.

    An unknown action is silently ignored here - S1 handles that.
    An empty pattern list matches anything, so empty patterns never fire.
    """
    diagnostics: list[Diagnostic] = []
    for section, pattern in _iter_patterns(sync):
        cases = index.action_cases(pattern.concept, pattern.action)
        if cases is None:
            continue  # handled by S1
        allowed = index.action_field_names(pattern.concept, pattern.action)
        for pf in list(pattern.input_pattern) + list(pattern.output_pattern):
            if pf.name in allowed:
                continue
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    file=file,
                    line=None,
                    column=None,
                    code="S2",
                    message=(
                        f"sync '{sync.name}' {section} pattern "
                        f"'{pattern.concept}/{pattern.action}' references "
                        f"unknown field '{pf.name}' (declared fields: "
                        f"{sorted(allowed)!r})"
                    ),
                )
            )
    return diagnostics


def _vars_in_pattern(pattern: ActionPattern) -> set[str]:
    """Return the set of `?var` tokens that appear in an action pattern."""
    seen: set[str] = set()
    for pf in list(pattern.input_pattern) + list(pattern.output_pattern):
        if pf.kind == "var":
            seen.add(pf.value)
    return seen


def _bindings_from_when(sync: SyncAST) -> set[str]:
    """Variables bound by any `when` pattern (both inputs and outputs)."""
    bound: set[str] = set()
    for pattern in sync.when:
        bound |= _vars_in_pattern(pattern)
    return bound


def _bindings_from_where(sync: SyncAST) -> set[str]:
    """
    Variables introduced by the `where` clause:
      - each `bind (expr as ?var)` introduces `?var`
      - each state query triple binds its subject + object `?var` tokens
    """
    bound: set[str] = set()
    if sync.where is None:
        return bound
    for bind in sync.where.binds:
        bound.add(bind.variable)
    for query in sync.where.queries:
        for triple in query.triples:
            if triple.subject.startswith("?"):
                bound.add(triple.subject)
            if triple.object.startswith("?"):
                bound.add(triple.object)
    return bound


def rule_s3_then_vars_bound(
    sync: SyncAST,
    index: WorkspaceIndex,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    S3: Every `?var` used in `then` is bound in `when` or `where`.

    The `index` argument is unused for this rule - it is kept in the
    signature so every sync rule has a uniform shape that
    `validate_workspace` can dispatch uniformly.
    """
    _ = index  # unused; kept for signature uniformity
    bound: set[str] = _bindings_from_when(sync) | _bindings_from_where(sync)
    diagnostics: list[Diagnostic] = []
    for pattern in sync.then:
        for var in _vars_in_pattern(pattern):
            if var in bound:
                continue
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    file=file,
                    line=None,
                    column=None,
                    code="S3",
                    message=(
                        f"sync '{sync.name}' then clause references "
                        f"unbound variable '{var}' (bind it in `when` or "
                        f"in a `where` bind/state query)"
                    ),
                )
            )
    return diagnostics


def rule_s4_where_vars_bound(
    sync: SyncAST,
    index: WorkspaceIndex,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    S4: Every `?var` used as the **subject** of a `where` state query
    triple must be bound by:
      - a `when` pattern,
      - an earlier `bind` in the same `where`,
      - or an earlier query in the same `where`.

    Object variables are not checked here - the paper treats them as
    introduced by the query itself (SPARQL pattern matching).
    """
    _ = index
    if sync.where is None:
        return []
    diagnostics: list[Diagnostic] = []
    bound: set[str] = _bindings_from_when(sync)
    for bind in sync.where.binds:
        bound.add(bind.variable)
    # Walk queries in source order, accumulating bindings as we go.
    for query in sync.where.queries:
        for triple in query.triples:
            if triple.subject.startswith("?") and triple.subject not in bound:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        file=file,
                        line=None,
                        column=None,
                        code="S4",
                        message=(
                            f"sync '{sync.name}' where clause state query on "
                            f"concept '{query.concept}' uses unbound subject "
                            f"'{triple.subject}' (bind it in `when` or in an "
                            f"earlier `where` item)"
                        ),
                    )
                )
            # After inspecting this triple, both its subject and object are
            # considered bound for subsequent triples.
            if triple.subject.startswith("?"):
                bound.add(triple.subject)
            if triple.object.startswith("?"):
                bound.add(triple.object)
    return diagnostics
