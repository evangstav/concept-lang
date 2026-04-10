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
