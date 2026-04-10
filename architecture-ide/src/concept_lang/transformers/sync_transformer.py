"""Transform a Lark parse tree for a .sync file into a SyncAST."""

from lark import Token, Transformer, v_args

from concept_lang.ast import (
    ActionPattern,
    BindClause,
    PatternField,
    StateQuery,
    SyncAST,
    Triple,
    WhereClause,
)


@v_args(inline=True)
class SyncTransformer(Transformer):

    # --- atoms ---------------------------------------------------------------

    def NAME(self, token: Token) -> str:
        return str(token)

    def VAR(self, token: Token) -> str:
        return str(token)

    def LITERAL(self, token: Token) -> str:
        return str(token)

    def BIND_EXPR(self, token: Token) -> str:
        return str(token).strip()

    # --- pattern pieces ------------------------------------------------------

    def pattern_value(self, tok: str) -> tuple[str, str]:
        # tok is either a VAR (starts with ?) or a LITERAL string
        kind = "var" if tok.startswith("?") else "literal"
        return kind, tok

    def pattern_field(self, name: str, value: tuple[str, str]) -> PatternField:
        kind, raw = value
        return PatternField(name=name, kind=kind, value=raw)  # type: ignore[arg-type]

    def pattern_list(self, *fields: PatternField) -> list[PatternField]:
        return list(fields)

    def action_pattern(
        self,
        concept: str,
        action: str,
        input_pattern: list[PatternField],
        output_pattern: list[PatternField] | None = None,
    ) -> ActionPattern:
        return ActionPattern(
            concept=concept,
            action=action,
            input_pattern=input_pattern,
            output_pattern=output_pattern if output_pattern is not None else [],
        )

    # --- where pieces --------------------------------------------------------

    def triple(self, subject: str, predicate: str, obj: str) -> Triple:
        return Triple(subject=subject, predicate=predicate, object=obj)

    def predicate_only(self, predicate: str, obj: str) -> tuple[str, str]:
        return (predicate, obj)

    def triple_list(self, first: Triple, *rest) -> list[Triple]:
        triples = [first]
        shared_subject = first.subject
        for item in rest:
            # item is a (predicate, object) tuple from predicate_only
            predicate, obj = item
            triples.append(
                Triple(subject=shared_subject, predicate=predicate, object=obj)
            )
        return triples

    def state_query(self, concept: str, triples: list[Triple]) -> StateQuery:
        return StateQuery(concept=concept, triples=triples, is_optional=False)

    def optional_query(self, concept: str, triples: list[Triple]) -> StateQuery:
        return StateQuery(concept=concept, triples=triples, is_optional=True)

    def bind_clause(self, expression: str, variable: str) -> BindClause:
        return BindClause(expression=expression.strip(), variable=variable)

    def where_item(self, item):
        return item

    def where_clause(self, *items) -> WhereClause:
        queries: list[StateQuery] = []
        binds: list[BindClause] = []
        for item in items:
            if isinstance(item, StateQuery):
                queries.append(item)
            elif isinstance(item, BindClause):
                binds.append(item)
        return WhereClause(queries=queries, binds=binds)

    # --- sections ------------------------------------------------------------

    def when_clause(self, *patterns: ActionPattern) -> list[ActionPattern]:
        return list(patterns)

    def then_clause(self, *patterns: ActionPattern) -> list[ActionPattern]:
        return list(patterns)

    def sync_def(self, name: str, *rest) -> SyncAST:
        when: list[ActionPattern] = []
        then: list[ActionPattern] = []
        where: WhereClause | None = None
        if len(rest) == 2:
            when, then = rest
        elif len(rest) == 3:
            when, where, then = rest
        return SyncAST(name=name, when=when, where=where, then=then, source="")

    def start(self, sync: SyncAST) -> SyncAST:
        return sync
