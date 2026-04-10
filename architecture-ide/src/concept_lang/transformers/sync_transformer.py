"""Transform a Lark parse tree for a .sync file into a SyncAST."""

from lark import Token, Transformer, v_args

from concept_lang.ast import (
    ActionPattern,
    PatternField,
    SyncAST,
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

    # --- sections ------------------------------------------------------------

    def when_clause(self, *patterns: ActionPattern) -> list[ActionPattern]:
        return list(patterns)

    def then_clause(self, *patterns: ActionPattern) -> list[ActionPattern]:
        return list(patterns)

    def sync_def(
        self,
        name: str,
        when: list[ActionPattern],
        then: list[ActionPattern],
    ) -> SyncAST:
        return SyncAST(
            name=name,
            when=when,
            where=None,
            then=then,
            source="",
        )

    def start(self, sync: SyncAST) -> SyncAST:
        return sync
