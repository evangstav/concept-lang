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


# --- Concept ---------------------------------------------------------------


class ActionCase(BaseModel):
    """
    One case of a multi-case action. A concept's action may have several
    cases sharing a name (e.g. one success case, one error case).
    """
    inputs: list[TypedName]
    outputs: list[TypedName]
    body: list[str] = []              # natural-language description lines
    effects: list[EffectClause] = []  # optional formal state deltas


class Action(BaseModel):
    """An action with one or more cases sharing a name."""
    name: str
    cases: list[ActionCase]


class OPStep(BaseModel):
    """
    One step in an `operational principle`. Keywords are:
      * `after` for the first (initial) step,
      * `then` / `and` for subsequent steps.
    """
    keyword: Literal["after", "then", "and"]
    action_name: str
    inputs: list[tuple[str, str]]     # e.g. [("user", "x"), ("password", '"secret"')]
    outputs: list[tuple[str, str]]


class OperationalPrinciple(BaseModel):
    """Archetypal scenario using the concept's own actions."""
    steps: list[OPStep]


class StateDecl(BaseModel):
    """A state field declaration (Alloy-style type expression)."""
    name: str
    type_expr: str                    # e.g. "set U", "U -> string"


class ConceptAST(BaseModel):
    """Top-level AST for a `.concept` file."""
    name: str
    params: list[str]                 # generic type parameters, e.g. ["U"]
    purpose: str                      # free-text purpose description
    state: list[StateDecl]
    actions: list[Action]
    operational_principle: OperationalPrinciple
    source: str                       # raw source text for diagnostics
