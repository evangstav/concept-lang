"""
New parser entry point for concept-lang 0.2.0.

Lives alongside `concept_lang.parser` (v1) until P7. All functions
here return AST nodes from `concept_lang.ast`, never from
`concept_lang.models`.
"""

from pathlib import Path

from lark import Lark

from concept_lang.ast import ConceptAST
from concept_lang.grammars import read_grammar
from concept_lang.transformers.concept_transformer import ConceptTransformer


_concept_parser: Lark | None = None


def _get_concept_parser() -> Lark:
    global _concept_parser
    if _concept_parser is None:
        _concept_parser = Lark(
            read_grammar("concept.lark"),
            parser="earley",
            maybe_placeholders=False,
        )
    return _concept_parser


def parse_concept_source(source: str) -> ConceptAST:
    """Parse concept source text into a ConceptAST."""
    tree = _get_concept_parser().parse(source)
    ast = ConceptTransformer().transform(tree)
    return ast.model_copy(update={"source": source})


def parse_concept_file(path: str | Path) -> ConceptAST:
    """Parse a `.concept` file from disk."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_concept_source(text)
