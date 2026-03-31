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


class SyncClause(BaseModel):
    trigger_concept: str   # e.g. "Auth"
    trigger_action: str    # e.g. "login"
    trigger_params: list[str]
    local_action: str      # e.g. "open"
    local_params: list[str]


class ConceptAST(BaseModel):
    name: str
    params: list[str]       # generic type parameters e.g. ["User", "Resource"]
    purpose: str            # free-text purpose description
    state: list[StateDecl]
    actions: list[Action]
    sync: list[SyncClause]
    source: str             # raw source text
