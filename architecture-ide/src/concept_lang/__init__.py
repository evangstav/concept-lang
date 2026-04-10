"""
concept-lang 0.2.0 public API.

The v1 modules (`concept_lang.parser`, `concept_lang.models`,
`concept_lang.validator`, `concept_lang.app_parser`,
`concept_lang.app_validator`) are still importable via their fully
qualified paths for the sake of the app-spec tool path and legacy tests,
but the package-level namespace only exposes the v2 surface.
"""

from concept_lang.ast import (
    Action,
    ActionCase,
    ActionPattern,
    BindClause,
    ConceptAST,
    EffectClause,
    OPStep,
    OperationalPrinciple,
    PatternField,
    StateDecl,
    StateQuery,
    SyncAST,
    Triple,
    TypedName,
    WhereClause,
    Workspace,
)
from concept_lang.loader import load_workspace
from concept_lang.parse import (
    parse_concept_file,
    parse_concept_source,
    parse_sync_file,
    parse_sync_source,
)
from concept_lang.server import create_server
from concept_lang.validate import (
    Diagnostic,
    validate_concept_file,
    validate_sync_file,
    validate_workspace,
)

__all__ = [
    # AST
    "Action",
    "ActionCase",
    "ActionPattern",
    "BindClause",
    "ConceptAST",
    "EffectClause",
    "OPStep",
    "OperationalPrinciple",
    "PatternField",
    "StateDecl",
    "StateQuery",
    "SyncAST",
    "Triple",
    "TypedName",
    "WhereClause",
    "Workspace",
    # Parser
    "parse_concept_file",
    "parse_concept_source",
    "parse_sync_file",
    "parse_sync_source",
    # Loader
    "load_workspace",
    # Validator
    "Diagnostic",
    "validate_concept_file",
    "validate_sync_file",
    "validate_workspace",
    # MCP server
    "create_server",
]
