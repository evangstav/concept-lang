"""Diagnostic record emitted by every validator rule."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class Diagnostic(BaseModel):
    """
    One diagnostic record produced by the validator.

    A `file=None` diagnostic is workspace-scoped (for example, a cross-file
    rule reporting that a sync references a concept that does not exist
    anywhere in the workspace).

    `line` and `column` are best-effort: the P1 parser does not yet attach
    source positions to AST nodes, so most P2 diagnostics use
    `line=None`/`column=None`. A follow-up plan will wire Lark's position
    metadata through the transformers.
    """

    severity: Literal["error", "warning", "info"]
    file: Path | None = None
    line: int | None = None
    column: int | None = None
    code: str
    message: str
