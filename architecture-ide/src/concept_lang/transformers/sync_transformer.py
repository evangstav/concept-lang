"""Transform a Lark parse tree for a .sync file into a SyncAST."""

from lark import Token, Transformer, v_args
from lark.tree import Meta

from concept_lang.ast import (
    ActionPattern,
    BindClause,
    PatternField,
    StateQuery,
    SyncAST,
    Triple,
    WhereClause,
)


def _pos(meta: Meta) -> tuple[int | None, int | None]:
    """Extract (line, column) from a Lark Meta, tolerating empty metas."""
    if meta is None or meta.empty:
        return (None, None)
    return (meta.line, meta.column)


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

    @v_args(meta=True, inline=True)
    def action_pattern(
        self,
        meta: Meta,
        concept: str,
        action: str,
        input_pattern: list[PatternField],
        output_pattern: list[PatternField] | None = None,
    ) -> ActionPattern:
        line, col = _pos(meta)
        return ActionPattern(
            concept=concept,
            action=action,
            input_pattern=input_pattern,
            output_pattern=output_pattern if output_pattern is not None else [],
            line=line,
            column=col,
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

    @v_args(meta=True, inline=True)
    def state_query(
        self, meta: Meta, concept: str, triples: list[Triple]
    ) -> StateQuery:
        line, col = _pos(meta)
        return StateQuery(
            concept=concept, triples=triples, is_optional=False,
            line=line, column=col,
        )

    @v_args(meta=True, inline=True)
    def optional_query(
        self, meta: Meta, concept: str, triples: list[Triple]
    ) -> StateQuery:
        line, col = _pos(meta)
        return StateQuery(
            concept=concept, triples=triples, is_optional=True,
            line=line, column=col,
        )

    @v_args(meta=True, inline=True)
    def bind_clause(
        self, meta: Meta, expression: str, variable: str
    ) -> BindClause:
        line, col = _pos(meta)
        return BindClause(
            expression=expression.strip(),
            variable=variable,
            line=line,
            column=col,
        )

    def where_item(self, item):
        return item

    @v_args(meta=True, inline=True)
    def where_clause(self, meta: Meta, *items) -> WhereClause:
        queries: list[StateQuery] = []
        binds: list[BindClause] = []
        for item in items:
            if isinstance(item, StateQuery):
                queries.append(item)
            elif isinstance(item, BindClause):
                binds.append(item)
        line, col = _pos(meta)
        return WhereClause(
            queries=queries, binds=binds, line=line, column=col,
        )

    # --- sections ------------------------------------------------------------

    def when_clause(self, *patterns: ActionPattern) -> list[ActionPattern]:
        return list(patterns)

    def then_clause(self, *patterns: ActionPattern) -> list[ActionPattern]:
        return list(patterns)

    @v_args(meta=True, inline=True)
    def sync_def(self, meta: Meta, name: str, *rest) -> SyncAST:
        when: list[ActionPattern] = []
        then: list[ActionPattern] = []
        where: WhereClause | None = None
        if len(rest) == 2:
            when, then = rest
        elif len(rest) == 3:
            when, where, then = rest
        line, col = _pos(meta)
        return SyncAST(
            name=name,
            when=when,
            where=where,
            then=then,
            source="",
            line=line,
            column=col,
        )

    def start(self, sync: SyncAST) -> SyncAST:
        return sync
