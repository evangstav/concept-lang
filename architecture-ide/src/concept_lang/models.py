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
