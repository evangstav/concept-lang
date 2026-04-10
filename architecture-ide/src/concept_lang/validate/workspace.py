"""
Workspace-level aggregator: runs every rule across every concept and
sync and returns the combined list of diagnostics. Also hosts the
single-file `validate_concept_file` and `validate_sync_file` wrappers
used by the MCP tool path.
"""

from pathlib import Path

from concept_lang.ast import ConceptAST, SyncAST, Workspace
from concept_lang.validate.concept_rules import (
    rule_c1_state_independence,
    rule_c2_effects_independence,
    rule_c3_op_principle_independence,
    rule_c4_no_inline_sync,
    rule_c5_has_purpose,
    rule_c6_has_actions,
    rule_c7_action_has_success_case,
    rule_c9_has_op_principle,
)
from concept_lang.validate.diagnostic import Diagnostic
from concept_lang.validate.helpers import WorkspaceIndex
from concept_lang.validate.sync_rules import (
    rule_s1_references_resolve,
    rule_s2_pattern_fields_exist,
    rule_s3_then_vars_bound,
    rule_s4_where_vars_bound,
    rule_s5_multiple_concepts,
)


def validate_workspace(
    workspace: Workspace,
    *,
    concept_files: dict[str, Path] | None = None,
    sync_files: dict[str, Path] | None = None,
) -> list[Diagnostic]:
    """
    Run every concept and sync rule against the given workspace.

    `concept_files` and `sync_files` optionally map the concept/sync name
    to the source file it came from so that emitted diagnostics carry a
    useful `file` path. They default to `None`, which is appropriate when
    the workspace was built in-memory (e.g. in unit tests).
    """
    concept_files = concept_files or {}
    sync_files = sync_files or {}

    index = WorkspaceIndex.build(workspace)
    diagnostics: list[Diagnostic] = []

    for name, concept in workspace.concepts.items():
        file = concept_files.get(name)
        diagnostics.extend(rule_c1_state_independence(concept, file=file))
        diagnostics.extend(rule_c2_effects_independence(concept, file=file))
        diagnostics.extend(rule_c3_op_principle_independence(concept, file=file))
        # C4 runs on the raw source, not the AST.
        diagnostics.extend(rule_c4_no_inline_sync(concept.source, file=file))
        diagnostics.extend(rule_c5_has_purpose(concept, file=file))
        diagnostics.extend(rule_c6_has_actions(concept, file=file))
        diagnostics.extend(rule_c7_action_has_success_case(concept, file=file))
        diagnostics.extend(rule_c9_has_op_principle(concept, file=file))

    for name, sync in workspace.syncs.items():
        file = sync_files.get(name)
        diagnostics.extend(rule_s1_references_resolve(sync, index, file=file))
        diagnostics.extend(rule_s2_pattern_fields_exist(sync, index, file=file))
        diagnostics.extend(rule_s3_then_vars_bound(sync, index, file=file))
        diagnostics.extend(rule_s4_where_vars_bound(sync, index, file=file))
        diagnostics.extend(rule_s5_multiple_concepts(sync, index, file=file))

    return diagnostics
