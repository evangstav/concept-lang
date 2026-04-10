"""
Validator rules for a single `ConceptAST` (paper rules C1..C9 except C8).

Each rule is a pure function that takes the concept AST (and, when it
needs cross-file context, a `WorkspaceIndex`) and returns a list of
`Diagnostic` records. Line/column information is best-effort: the P1
parser does not yet attach source positions to AST nodes, so most
diagnostics produced here use `line=None`.
"""

import re
from pathlib import Path

from concept_lang.ast import ActionCase, ConceptAST
from concept_lang.validate.diagnostic import Diagnostic

# Primitive types that a concept's state may reference without declaring
# them as type parameters. Matches the paper's Alloy-style type expressions.
_PRIMITIVE_TYPES: frozenset[str] = frozenset({
    "bool",
    "boolean",
    "int",
    "integer",
    "float",
    "number",
    "string",
    "str",
    "text",
    "date",
    "datetime",
    "time",
    "duration",
})

# Reserved words that may appear inside a type expression but are not
# themselves type references (they are constructors or operators).
_TYPE_EXPR_RESERVED: frozenset[str] = frozenset({
    "set",
    "seq",
    "opt",
    "map",
    "lone",
    "one",
    "some",
})

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _tokens_in(type_expr: str) -> list[str]:
    """Return the identifier tokens that appear in a type expression."""
    return _IDENT_RE.findall(type_expr)


def rule_c1_state_independence(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C1: State declarations may only reference own type params + primitives.

    Any identifier token in `type_expr` that is not the concept's own type
    parameter, a primitive type, or a reserved type-expression keyword is
    flagged as a foreign reference.
    """
    diagnostics: list[Diagnostic] = []
    allowed: set[str] = set(concept.params) | _PRIMITIVE_TYPES | _TYPE_EXPR_RESERVED
    for decl in concept.state:
        for tok in _tokens_in(decl.type_expr):
            if tok in allowed:
                continue
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    file=file,
                    line=None,
                    column=None,
                    code="C1",
                    message=(
                        f"state field '{decl.name}' references unknown type "
                        f"'{tok}' (a concept may only reference its own type "
                        f"parameters {sorted(concept.params)!r} and primitive "
                        f"types)"
                    ),
                )
            )
    return diagnostics


def rule_c2_effects_independence(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C2: Effects clauses may only reference state fields declared on this concept.
    """
    diagnostics: list[Diagnostic] = []
    own_fields: set[str] = {decl.name for decl in concept.state}
    for action in concept.actions:
        for case in action.cases:
            for effect in case.effects:
                if effect.field in own_fields:
                    continue
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        file=file,
                        line=None,
                        column=None,
                        code="C2",
                        message=(
                            f"action '{action.name}' has an effect on field "
                            f"'{effect.field}', which is not declared in "
                            f"concept '{concept.name}' (declared fields: "
                            f"{sorted(own_fields)!r})"
                        ),
                    )
                )
    return diagnostics


def rule_c3_op_principle_independence(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C3: Operational principle may only invoke actions of this concept.
    """
    diagnostics: list[Diagnostic] = []
    own_actions: set[str] = {a.name for a in concept.actions}
    for step in concept.operational_principle.steps:
        if step.action_name in own_actions:
            continue
        diagnostics.append(
            Diagnostic(
                severity="error",
                file=file,
                line=None,
                column=None,
                code="C3",
                message=(
                    f"operational principle step '{step.keyword} "
                    f"{step.action_name}' references action '{step.action_name}' "
                    f"which is not declared in concept '{concept.name}' "
                    f"(declared actions: {sorted(own_actions)!r})"
                ),
            )
        )
    return diagnostics


# An indented `sync` section header line. We require leading whitespace
# (section headers inside a concept are indented) followed by `sync` as a
# whole word. This avoids matching identifiers like `resync`.
_INLINE_SYNC_RE = re.compile(r"^[ \t]+sync\b", re.MULTILINE)


def rule_c4_no_inline_sync(
    source: str,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C4: Concepts may not contain an inline `sync` section.

    In the new format syncs are top-level files. This rule exists to give
    a clear error when migrating v1 concept files that still embed syncs
    inside the concept body.

    Operates on raw source text because a concept file containing an
    inline `sync` section is not parseable by the new grammar - so the AST
    path is unavailable.
    """
    diagnostics: list[Diagnostic] = []
    for match in _INLINE_SYNC_RE.finditer(source):
        line_no = source.count("\n", 0, match.start()) + 1
        diagnostics.append(
            Diagnostic(
                severity="error",
                file=file,
                line=line_no,
                column=None,
                code="C4",
                message=(
                    "inline `sync` section is not allowed in concept files - "
                    "move it to a top-level `.sync` file"
                ),
            )
        )
    return diagnostics


def rule_c5_has_purpose(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C5: Every concept has a non-empty `purpose`.
    """
    if concept.purpose and concept.purpose.strip():
        return []
    return [
        Diagnostic(
            severity="error",
            file=file,
            line=None,
            column=None,
            code="C5",
            message=f"concept '{concept.name}' has an empty purpose",
        )
    ]


def rule_c6_has_actions(
    concept: ConceptAST,
    *,
    file: Path | None = None,
) -> list[Diagnostic]:
    """
    C6: Every concept has at least one action.
    """
    if concept.actions:
        return []
    return [
        Diagnostic(
            severity="error",
            file=file,
            line=None,
            column=None,
            code="C6",
            message=f"concept '{concept.name}' has no actions",
        )
    ]
