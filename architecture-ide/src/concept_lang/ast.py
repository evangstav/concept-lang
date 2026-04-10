"""
New AST for concept-lang 0.2.0.

This module defines the Pydantic data classes that the new parser
(concept_lang.parse) produces. It lives alongside the v1 models
(concept_lang.models) until P7 of the paper-alignment project.

See docs/superpowers/specs/2026-04-10-paper-alignment-design.md §4.1.
"""

from typing import Literal

from pydantic import BaseModel


class TypedName(BaseModel):
    """A named parameter with a type, e.g. `user: U`."""
    name: str
    type_expr: str


class EffectClause(BaseModel):
    """
    A single line in an action case's optional `effects:` subsection.

    Examples:
        password[user] := hash
        tags -= tag
    """
    raw: str                          # the whole clause as written
    field: str                        # e.g. "password"
    op: Literal[":=", "+=", "-="]
    rhs: str                          # right-hand side kept as raw text
