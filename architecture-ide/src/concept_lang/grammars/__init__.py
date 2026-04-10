"""Lark grammars for the new concept-lang DSL."""

from pathlib import Path

_GRAMMARS_DIR = Path(__file__).parent


def read_grammar(name: str) -> str:
    """Read a .lark grammar file from this package."""
    return (_GRAMMARS_DIR / name).read_text(encoding="utf-8")
