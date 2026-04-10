"""
LEGACY FENCE (0.3.0): v1 Pydantic AST types.

This module is one of four fenced-off legacy survivors kept in the tree
to back the app-spec bridge in `concept_lang.tools.app_tools`. It is
NOT the v2 AST — that lives at `concept_lang.ast` with paper-aligned
multi-case actions, operational principle, and optional source
positions.

Do not import from here in new code. The only legitimate consumers
are `concept_lang.parser`, `concept_lang.app_parser`,
`concept_lang.app_validator`, and `concept_lang.tools.app_tools` —
all of which back the same legacy app-spec bridge path.
"""

from pydantic import BaseModel


class StateDecl(BaseModel):
    name: str
    type_expr: str  # e.g. "set User", "active -> set Resource", "User"


class PrePost(BaseModel):
    clauses: list[str]  # raw clause strings e.g. ["active += u", "access -= u->"]


class Action(BaseModel):
    name: str
    params: list[str]  # e.g. ["u: User", "r: Resource"]
    pre: PrePost | None = None
    post: PrePost | None = None


class SyncInvocation(BaseModel):
    action: str            # e.g. "open"
    params: list[str]      # e.g. ["u", "s"]


class SyncClause(BaseModel):
    # when clause
    trigger_concept: str   # e.g. "Auth"
    trigger_action: str    # e.g. "login"
    trigger_params: list[str]  # e.g. ["u: User"]
    trigger_result: str | None = None  # e.g. "s: Session" (output binding)
    # where clause (optional conditions)
    where_clauses: list[str] = []  # e.g. ["u in registered"]
    # then clause (one or more local action invocations)
    invocations: list[SyncInvocation]


class ConceptAST(BaseModel):
    name: str
    params: list[str]       # generic type parameters e.g. ["User", "Resource"]
    purpose: str            # free-text purpose description
    state: list[StateDecl]
    actions: list[Action]
    sync: list[SyncClause]
    source: str             # raw source text


class ConceptBinding(BaseModel):
    """A concept instantiation in an app spec, with its type parameter bindings."""
    name: str                   # concept name e.g. "Password"
    bindings: list[str]         # type param bindings e.g. ["User"] for Password[User]


class AppSpec(BaseModel):
    """An app spec declaring which concepts compose into a system."""
    name: str                   # app name e.g. "SocialNetwork"
    purpose: str                # free-text description
    concepts: list[ConceptBinding]
    source: str                 # raw source text
