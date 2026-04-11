"""
concept-lang 0.3.0 public API.

The v2 surface (AST, parser, loader, validator, diff, explorer, MCP
server) is re-exported below.

Legacy v1 subsystem: `concept_lang.parser`, `concept_lang.models`,
`concept_lang.app_parser`, and `concept_lang.app_validator` are still
importable via their fully qualified paths because they back the v1
app-spec bridge (`concept_lang.tools.app_tools`). **Do not extend
these modules.** A follow-up plan migrates the `.app` format to a v2
AST and a v2 validator; at that point the legacy subsystem is
deleted outright.
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
