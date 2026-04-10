"""
concept-lang 0.2.0 validator.

Lives alongside the v1 `concept_lang.validator` until P7. Consumes AST
values produced by `concept_lang.parse` and emits `Diagnostic` records.

Public API (grows across the tasks of the P2 plan):
    Diagnostic
    validate_workspace
    validate_concept_file
    validate_sync_file
"""

from concept_lang.validate.diagnostic import Diagnostic
from concept_lang.validate.sync_rules import rule_s1_references_resolve

__all__ = [
    "Diagnostic",
    "rule_s1_references_resolve",
]
