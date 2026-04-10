"""Transform a Lark parse tree for a .concept file into a ConceptAST."""

from lark import Token, Transformer, v_args

from concept_lang.ast import (
    ConceptAST,
    OperationalPrinciple,
)


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

    # --- sections ------------------------------------------------------------

    def type_params(self, *names: str) -> list[str]:
        return list(names)

    def purpose_body(self, *lines: str) -> str:
        return " ".join(l for l in lines if l)

    def purpose_section(self, body: str) -> str:
        return body

    # --- top level -----------------------------------------------------------

    def concept_def(self, name: str, *rest) -> ConceptAST:
        # rest may start with a type_params list; purpose is last
        params: list[str] = []
        purpose: str = ""
        for item in rest:
            if isinstance(item, list):
                params = item
            elif isinstance(item, str):
                purpose = item
        return ConceptAST(
            name=name,
            params=params,
            purpose=purpose,
            state=[],
            actions=[],
            operational_principle=OperationalPrinciple(steps=[]),
            source="",
        )

    def start(self, concept: ConceptAST) -> ConceptAST:
        return concept
