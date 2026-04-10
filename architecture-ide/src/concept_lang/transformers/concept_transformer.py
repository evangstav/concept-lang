"""Transform a Lark parse tree for a .concept file into a ConceptAST."""

from lark import Token, Transformer, v_args
from lark.tree import Meta

from concept_lang.ast import (
    Action,
    ActionCase,
    ConceptAST,
    EffectClause,
    OPStep,
    OperationalPrinciple,
    StateDecl,
    TypedName,
)


def _pos(meta: Meta) -> tuple[int | None, int | None]:
    """Extract (line, column) from a Lark Meta, tolerating empty metas."""
    if meta is None or meta.empty:
        return (None, None)
    return (meta.line, meta.column)


@v_args(inline=True)
class ConceptTransformer(Transformer):
    """
    Transformer from concept.lark parse tree to ConceptAST.

    Each method here corresponds to a grammar rule; Lark calls them
    bottom-up with the already-transformed child values.
    """

    # --- atoms ---------------------------------------------------------------

    def NAME(self, token: Token) -> str:
        return str(token)

    def PURPOSE_LINE(self, token: Token) -> str:
        return str(token).strip()

    def TYPE_EXPR(self, token: Token) -> str:
        return str(token).strip()

    def TYPE_REF(self, token: Token) -> str:
        return str(token).strip()

    def BODY_LINE(self, token: Token) -> str:
        return str(token).strip()

    def FIELD_REF(self, token: Token) -> str:
        return str(token).strip()

    def EFFECT_OP(self, token: Token) -> str:
        return str(token).strip()

    def EFFECT_RHS(self, token: Token) -> str:
        return str(token).strip()

    def OP_KEYWORD(self, token: Token) -> str:
        return str(token)

    def OP_VALUE(self, token: Token) -> str:
        return str(token).strip()

    # --- sections ------------------------------------------------------------

    def type_params(self, *names: str) -> list[str]:
        return list(names)

    def purpose_body(self, *lines: str) -> str:
        return " ".join(l for l in lines if l)

    def purpose_section(self, body: str) -> str:
        return body

    @v_args(meta=True, inline=True)
    def state_decl(self, meta: Meta, name: str, type_expr: str) -> StateDecl:
        line, col = _pos(meta)
        return StateDecl(name=name, type_expr=type_expr, line=line, column=col)

    def state_section(self, *decls: StateDecl) -> list[StateDecl]:
        return list(decls)

    def typed_name(self, name: str, type_ref: str) -> TypedName:
        return TypedName(name=name, type_expr=type_ref)

    def typed_name_list(self, *names: TypedName) -> list[TypedName]:
        return list(names)

    @v_args(meta=True, inline=True)
    def effect_line(
        self, meta: Meta, field_ref: str, op: str, rhs: str
    ) -> EffectClause:
        # field_ref might be "password[user]" — strip subscript for .field
        field_name = field_ref.split("[", 1)[0]
        line, col = _pos(meta)
        return EffectClause(
            raw=f"{field_ref} {op} {rhs}",
            field=field_name,
            op=op,  # type: ignore[arg-type]
            rhs=rhs,
            line=line,
            column=col,
        )

    def effects_clause(self, *effects: EffectClause) -> list[EffectClause]:
        return list(effects)

    def case_body(self, *items) -> tuple[list[str], list[EffectClause]]:
        body_lines: list[str] = []
        effects: list[EffectClause] = []
        for item in items:
            if isinstance(item, str):
                body_lines.append(item)
            elif isinstance(item, list):
                effects = item  # single effects_clause result
        return body_lines, effects

    @v_args(meta=True, inline=True)
    def action_case(self, meta: Meta, name: str, *rest) -> tuple[str, ActionCase]:
        inputs: list[TypedName] = []
        outputs: list[TypedName] = []
        body_lines: list[str] = []
        effects: list[EffectClause] = []

        list_args = [r for r in rest if isinstance(r, list)]
        tuple_args = [r for r in rest if isinstance(r, tuple)]

        if len(list_args) == 2:
            inputs, outputs = list_args
        elif len(list_args) == 1:
            idx_first_list = next(i for i, r in enumerate(rest) if isinstance(r, list))
            if idx_first_list == 0:
                inputs = list_args[0]
            else:
                outputs = list_args[0]

        if tuple_args:
            body_lines, effects = tuple_args[0]

        line, col = _pos(meta)
        return name, ActionCase(
            inputs=inputs,
            outputs=outputs,
            body=body_lines,
            effects=effects,
            line=line,
            column=col,
        )

    def actions_section(self, *cases: tuple[str, ActionCase]) -> list[Action]:
        grouped: dict[str, list[ActionCase]] = {}
        order: list[str] = []
        first_pos: dict[str, tuple[int | None, int | None]] = {}
        for name, case in cases:
            if name not in grouped:
                grouped[name] = []
                order.append(name)
                first_pos[name] = (case.line, case.column)
            grouped[name].append(case)
        return [
            Action(
                name=n,
                cases=grouped[n],
                line=first_pos[n][0],
                column=first_pos[n][1],
            )
            for n in order
        ]

    # --- operational principle ----------------------------------------------

    def op_arg(self, name: str, value: str) -> tuple[str, str]:
        # NOTE: Deliberately a tuple, not a PatternField. OP step args use bare
        # identifiers as unification witnesses (e.g., `user: x`), while sync
        # PatternFields use `?var` prefixing. The two shapes are intentionally
        # separate — consolidating them would conflate different semantics.
        return (name, value)

    def op_arg_list(self, *args: tuple[str, str]) -> list[tuple[str, str]]:
        return list(args)

    @v_args(meta=True, inline=True)
    def op_step(self, meta: Meta, keyword: str, action_name: str, *rest) -> OPStep:
        inputs: list[tuple[str, str]] = []
        outputs: list[tuple[str, str]] = []
        list_args = [r for r in rest if isinstance(r, list)]
        if len(list_args) == 2:
            inputs, outputs = list_args
        elif len(list_args) == 1:
            idx_first = next(i for i, r in enumerate(rest) if isinstance(r, list))
            if idx_first == 0:
                inputs = list_args[0]
            else:
                outputs = list_args[0]
        line, col = _pos(meta)
        return OPStep(
            keyword=keyword,  # type: ignore[arg-type]
            action_name=action_name,
            inputs=inputs,
            outputs=outputs,
            line=line,
            column=col,
        )

    @v_args(meta=True, inline=True)
    def op_section(self, meta: Meta, *steps: OPStep) -> OperationalPrinciple:
        line, col = _pos(meta)
        return OperationalPrinciple(steps=list(steps), line=line, column=col)

    # --- top level -----------------------------------------------------------

    @v_args(meta=True, inline=True)
    def concept_def(self, meta: Meta, name: str, *rest) -> ConceptAST:
        params: list[str] = []
        purpose: str = ""
        state: list[StateDecl] = []
        actions: list[Action] = []
        op_principle = OperationalPrinciple(steps=[])
        for item in rest:
            if isinstance(item, OperationalPrinciple):
                op_principle = item
            elif isinstance(item, list) and item:
                head = item[0]
                if isinstance(head, str):
                    params = item
                elif isinstance(head, StateDecl):
                    state = item
                elif isinstance(head, Action):
                    actions = item
            elif isinstance(item, str):
                purpose = item
        line, col = _pos(meta)
        return ConceptAST(
            name=name,
            params=params,
            purpose=purpose,
            state=state,
            actions=actions,
            operational_principle=op_principle,
            source="",
            line=line,
            column=col,
        )

    def start(self, concept: ConceptAST) -> ConceptAST:
        return concept
