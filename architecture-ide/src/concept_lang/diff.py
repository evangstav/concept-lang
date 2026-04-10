"""
Concept diff and evolution tracking (v2 — consumes concept_lang.ast).

Structural diff of concept versions: detect state added/removed/renamed,
actions changed (by case shape), effects changed, operational principle
changed. The sync section moved out of concepts in 0.2.0 — use
`diff_syncs(old_sync, new_sync)` on two `SyncAST` values for sync-level
changes.

Answers: what changed, what downstream syncs are broken, what concepts
are affected. Foundation for safe evolution of concept-based systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from concept_lang.ast import (
    Action,
    ActionCase,
    ConceptAST,
    OperationalPrinciple,
    OPStep,
    StateDecl,
    SyncAST,
    Workspace,
)


class ChangeKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    RENAMED = "renamed"


@dataclass
class StateChange:
    kind: ChangeKind
    name: str
    old_name: str | None = None
    old_type_expr: str | None = None
    new_type_expr: str | None = None

    def to_dict(self) -> dict:
        d: dict = {"kind": self.kind.value, "name": self.name}
        if self.old_name:
            d["old_name"] = self.old_name
        if self.old_type_expr is not None:
            d["old_type_expr"] = self.old_type_expr
        if self.new_type_expr is not None:
            d["new_type_expr"] = self.new_type_expr
        return d


@dataclass
class ActionChange:
    kind: ChangeKind
    name: str
    details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict = {"kind": self.kind.value, "name": self.name}
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class OPChange:
    """A single edit in the operational principle step list."""
    kind: ChangeKind
    step_index: int
    description: str

    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "step_index": self.step_index,
            "description": self.description,
        }


@dataclass
class BrokenSync:
    """A sync in the workspace that is invalidated by a concept diff."""
    sync_name: str
    reason: str

    def to_dict(self) -> dict:
        return {"sync": self.sync_name, "reason": self.reason}


@dataclass
class ConceptDiff:
    """Full structural diff between two versions of a concept."""
    concept_name: str
    params_changed: bool = False
    old_params: list[str] = field(default_factory=list)
    new_params: list[str] = field(default_factory=list)
    purpose_changed: bool = False
    state_changes: list[StateChange] = field(default_factory=list)
    action_changes: list[ActionChange] = field(default_factory=list)
    op_changes: list[OPChange] = field(default_factory=list)
    broken_syncs: list[BrokenSync] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return (
            self.params_changed
            or self.purpose_changed
            or bool(self.state_changes)
            or bool(self.action_changes)
            or bool(self.op_changes)
        )

    def to_dict(self) -> dict:
        d: dict = {"concept": self.concept_name, "has_changes": self.has_changes}
        if self.params_changed:
            d["params"] = {"old": self.old_params, "new": self.new_params}
        if self.purpose_changed:
            d["purpose_changed"] = True
        if self.state_changes:
            d["state_changes"] = [c.to_dict() for c in self.state_changes]
        if self.action_changes:
            d["action_changes"] = [c.to_dict() for c in self.action_changes]
        if self.op_changes:
            d["op_changes"] = [c.to_dict() for c in self.op_changes]
        if self.broken_syncs:
            d["broken_syncs"] = [b.to_dict() for b in self.broken_syncs]
        return d


@dataclass
class SyncDiff:
    """Structural diff between two versions of a single `.sync` file."""
    sync_name: str
    when_changed: bool = False
    where_changed: bool = False
    then_changed: bool = False

    @property
    def has_changes(self) -> bool:
        return self.when_changed or self.where_changed or self.then_changed

    def to_dict(self) -> dict:
        return {
            "sync": self.sync_name,
            "has_changes": self.has_changes,
            "when_changed": self.when_changed,
            "where_changed": self.where_changed,
            "then_changed": self.then_changed,
        }


# ---------------------------------------------------------------------------
# Concept diff
# ---------------------------------------------------------------------------


def diff_concepts(old: ConceptAST, new: ConceptAST) -> ConceptDiff:
    """Compute a structural diff between two versions of a concept."""
    result = ConceptDiff(concept_name=new.name)

    if old.params != new.params:
        result.params_changed = True
        result.old_params = old.params
        result.new_params = new.params

    if old.purpose.strip() != new.purpose.strip():
        result.purpose_changed = True

    result.state_changes = _diff_state(old.state, new.state)
    result.action_changes = _diff_actions(old.actions, new.actions)
    result.op_changes = _diff_op_principle(
        old.operational_principle, new.operational_principle
    )

    return result


def _diff_state(old: list[StateDecl], new: list[StateDecl]) -> list[StateChange]:
    changes: list[StateChange] = []
    old_by_name = {s.name: s for s in old}
    new_by_name = {s.name: s for s in new}

    old_names = set(old_by_name)
    new_names = set(new_by_name)

    # Detect renames: same type_expr, one removed + one added
    removed = old_names - new_names
    added = new_names - old_names
    renamed: set[tuple[str, str]] = set()

    for r in list(removed):
        for a in list(added):
            if old_by_name[r].type_expr == new_by_name[a].type_expr:
                renamed.add((r, a))
                removed.discard(r)
                added.discard(a)
                break

    for old_name, new_name in renamed:
        changes.append(StateChange(
            kind=ChangeKind.RENAMED,
            name=new_name,
            old_name=old_name,
            old_type_expr=old_by_name[old_name].type_expr,
            new_type_expr=new_by_name[new_name].type_expr,
        ))

    for name in sorted(removed):
        changes.append(StateChange(
            kind=ChangeKind.REMOVED,
            name=name,
            old_type_expr=old_by_name[name].type_expr,
        ))

    for name in sorted(added):
        changes.append(StateChange(
            kind=ChangeKind.ADDED,
            name=name,
            new_type_expr=new_by_name[name].type_expr,
        ))

    for name in sorted(old_names & new_names):
        if old_by_name[name].type_expr != new_by_name[name].type_expr:
            changes.append(StateChange(
                kind=ChangeKind.MODIFIED,
                name=name,
                old_type_expr=old_by_name[name].type_expr,
                new_type_expr=new_by_name[name].type_expr,
            ))

    return changes


def _diff_actions(old: list[Action], new: list[Action]) -> list[ActionChange]:
    changes: list[ActionChange] = []
    old_by_name = {a.name: a for a in old}
    new_by_name = {a.name: a for a in new}

    old_names = set(old_by_name)
    new_names = set(new_by_name)

    for name in sorted(old_names - new_names):
        changes.append(ActionChange(kind=ChangeKind.REMOVED, name=name))

    for name in sorted(new_names - old_names):
        changes.append(ActionChange(kind=ChangeKind.ADDED, name=name))

    for name in sorted(old_names & new_names):
        details = _compare_action(old_by_name[name], new_by_name[name])
        if details:
            changes.append(ActionChange(
                kind=ChangeKind.MODIFIED, name=name, details=details
            ))

    return changes


def _case_signature(case: ActionCase) -> tuple[str, str]:
    """Canonical shape of a case's inputs/outputs, ignoring body/effects."""
    ins = ", ".join(f"{tn.name}: {tn.type_expr}" for tn in case.inputs)
    outs = ", ".join(f"{tn.name}: {tn.type_expr}" for tn in case.outputs)
    return (ins, outs)


def _compare_action(old: Action, new: Action) -> list[str]:
    details: list[str] = []

    if len(old.cases) != len(new.cases):
        details.append(f"case count: {len(old.cases)} -> {len(new.cases)}")
        return details

    for idx, (oc, nc) in enumerate(zip(old.cases, new.cases)):
        old_sig = _case_signature(oc)
        new_sig = _case_signature(nc)
        if old_sig != new_sig:
            details.append(
                f"case {idx} signature: ({old_sig[0]}) => ({old_sig[1]}) "
                f"-> ({new_sig[0]}) => ({new_sig[1]})"
            )
            continue

        old_effects = [e.raw for e in oc.effects]
        new_effects = [e.raw for e in nc.effects]
        if old_effects != new_effects:
            details.append(f"case {idx} effects changed")

        if oc.body != nc.body:
            details.append(f"case {idx} body changed")

    return details


def _diff_op_principle(
    old: OperationalPrinciple, new: OperationalPrinciple
) -> list[OPChange]:
    """Coarse diff: per-step index, report added / removed / modified."""
    changes: list[OPChange] = []
    n_old = len(old.steps)
    n_new = len(new.steps)
    common = min(n_old, n_new)

    for idx in range(common):
        if _op_step_differs(old.steps[idx], new.steps[idx]):
            changes.append(OPChange(
                kind=ChangeKind.MODIFIED,
                step_index=idx,
                description=(
                    f"step {idx}: {old.steps[idx].keyword} "
                    f"{old.steps[idx].action_name} changed"
                ),
            ))

    for idx in range(common, n_old):
        changes.append(OPChange(
            kind=ChangeKind.REMOVED,
            step_index=idx,
            description=f"step {idx}: {old.steps[idx].action_name} removed",
        ))

    for idx in range(common, n_new):
        changes.append(OPChange(
            kind=ChangeKind.ADDED,
            step_index=idx,
            description=f"step {idx}: {new.steps[idx].action_name} added",
        ))

    return changes


def _op_step_differs(a: OPStep, b: OPStep) -> bool:
    return (
        a.keyword != b.keyword
        or a.action_name != b.action_name
        or a.inputs != b.inputs
        or a.outputs != b.outputs
    )


# ---------------------------------------------------------------------------
# Sync diff
# ---------------------------------------------------------------------------


def diff_syncs(old: SyncAST, new: SyncAST) -> SyncDiff:
    """Compute a structural diff between two versions of a sync."""
    result = SyncDiff(sync_name=new.name)

    if [p.model_dump() for p in old.when] != [p.model_dump() for p in new.when]:
        result.when_changed = True
    if [p.model_dump() for p in old.then] != [p.model_dump() for p in new.then]:
        result.then_changed = True

    old_where = old.where.model_dump() if old.where else None
    new_where = new.where.model_dump() if new.where else None
    if old_where != new_where:
        result.where_changed = True

    return result


# ---------------------------------------------------------------------------
# Impact analysis: find broken syncs in the workspace
# ---------------------------------------------------------------------------


def find_broken_syncs(
    diff: ConceptDiff,
    workspace: Workspace,
) -> list[BrokenSync]:
    """
    Given a diff of one concept, find syncs in the workspace that are
    now broken by the changes.
    """
    broken: list[BrokenSync] = []
    concept_name = diff.concept_name

    removed_actions: set[str] = set()
    modified_action_cases: set[str] = set()

    for ac in diff.action_changes:
        if ac.kind == ChangeKind.REMOVED:
            removed_actions.add(ac.name)
        elif ac.kind == ChangeKind.MODIFIED:
            if any("signature" in d for d in ac.details):
                modified_action_cases.add(ac.name)

    for sync_name, sync in workspace.syncs.items():
        # Check every action pattern in when/then for references to
        # Concept/action where Concept == concept_name.
        all_patterns = list(sync.when) + list(sync.then)
        for pat in all_patterns:
            if pat.concept != concept_name:
                continue
            if pat.action in removed_actions:
                broken.append(BrokenSync(
                    sync_name=sync_name,
                    reason=(
                        f"Action '{pat.action}' was removed from "
                        f"'{concept_name}'"
                    ),
                ))
                break
            if pat.action in modified_action_cases:
                broken.append(BrokenSync(
                    sync_name=sync_name,
                    reason=(
                        f"Action '{pat.action}' in '{concept_name}' "
                        f"had its case signature changed"
                    ),
                ))
                break

    return broken


def diff_concepts_with_impact(
    old: ConceptAST,
    new: ConceptAST,
    workspace: Workspace | None = None,
) -> ConceptDiff:
    """Diff two concept versions and optionally find broken downstream syncs."""
    result = diff_concepts(old, new)
    if workspace is not None:
        result.broken_syncs = find_broken_syncs(result, workspace)
    return result
