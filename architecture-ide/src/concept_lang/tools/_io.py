"""Shared I/O helpers for concept file operations."""

import os
from ..models import ConceptAST
from ..parser import ParseError, parse_file


def list_concept_names(concepts_dir: str) -> list[str]:
    """Return sorted list of concept names (without .concept extension)."""
    try:
        return sorted(
            f[:-8] for f in os.listdir(concepts_dir) if f.endswith(".concept")
        )
    except FileNotFoundError:
        return []


def load_all_concepts(concepts_dir: str) -> list[ConceptAST]:
    """Load and parse all valid .concept files in concepts_dir."""
    concepts = []
    if not os.path.exists(concepts_dir):
        return concepts
    for name in list_concept_names(concepts_dir):
        path = os.path.join(concepts_dir, f"{name}.concept")
        try:
            concepts.append(parse_file(path))
        except (ParseError, OSError):
            pass
    return concepts
