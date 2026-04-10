"""
concept-lang 0.2.0 validator.

Lives alongside the v1 `concept_lang.validator` until P7. Consumes AST
values produced by `concept_lang.parse` and emits `Diagnostic` records.

Public API (grows across the tasks of the P2 plan):
    Diagnostic
    rule_c1_state_independence
    rule_c2_effects_independence
    rule_c3_op_principle_independence
    rule_c4_no_inline_sync
    rule_c5_has_purpose
    rule_c6_has_actions
    validate_workspace
    validate_concept_file
    validate_sync_file
"""

from concept_lang.validate.concept_rules import (
    rule_c1_state_independence,
    rule_c2_effects_independence,
    rule_c3_op_principle_independence,
    rule_c4_no_inline_sync,
    rule_c5_has_purpose,
    rule_c6_has_actions,
)
from concept_lang.validate.diagnostic import Diagnostic

__all__ = [
    "Diagnostic",
    "rule_c1_state_independence",
    "rule_c2_effects_independence",
    "rule_c3_op_principle_independence",
    "rule_c4_no_inline_sync",
    "rule_c5_has_purpose",
    "rule_c6_has_actions",
]
