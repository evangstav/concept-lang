"""
Concept diff and evolution tracking.

Structural diff of concept versions: detect state added/removed/renamed,
actions changed, sync clauses invalidated. Not text diff — semantic diff
that understands concept structure.

Answers: what changed, what syncs are now broken, what downstream concepts
are affected. Foundation for safe evolution of concept-based systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .models import Action, ConceptAST, StateDecl, SyncClause


class ChangeKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    RENAMED = "renamed"


@dataclass
class StateChange:
    kind: ChangeKind
    name: str
    old_name: str | None = None  # for renames
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
    details: list[str] = field(default_factory=list)  # what specifically changed

    def to_dict(self) -> dict:
        d: dict = {"kind": self.kind.value, "name": self.name}
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class SyncChange:
    kind: ChangeKind
    description: str
    old_clause: dict | None = None
    new_clause: dict | None = None

    def to_dict(self) -> dict:
        d: dict = {"kind": self.kind.value, "description": self.description}
        if self.old_clause:
            d["old_clause"] = self.old_clause
        if self.new_clause:
            d["new_clause"] = self.new_clause
        return d


@dataclass
class BrokenSync:
    """A sync clause in another concept that is invalidated by this diff."""
    concept_name: str
    sync_index: int
    reason: str

    def to_dict(self) -> dict:
        return {
            "concept": self.concept_name,
            "sync_index": self.sync_index,
            "reason": self.reason,
        }


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
    sync_changes: list[SyncChange] = field(default_factory=list)
    broken_syncs: list[BrokenSync] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return (
            self.params_changed
            or self.purpose_changed
            or bool(self.state_changes)
            or bool(self.action_changes)
            or bool(self.sync_changes)
        )

    def to_dict(self) -> dict:
        d: dict = {
            "concept": self.concept_name,
            "has_changes": self.has_changes,
        }
        if self.params_changed:
            d["params"] = {"old": self.old_params, "new": self.new_params}
        if self.purpose_changed:
            d["purpose_changed"] = True
        if self.state_changes:
            d["state_changes"] = [c.to_dict() for c in self.state_changes]
        if self.action_changes:
            d["action_changes"] = [c.to_dict() for c in self.action_changes]
        if self.sync_changes:
            d["sync_changes"] = [c.to_dict() for c in self.sync_changes]
        if self.broken_syncs:
            d["broken_syncs"] = [b.to_dict() for b in self.broken_syncs]
        return d


# ---------------------------------------------------------------------------
# Diff engine
# ---------------------------------------------------------------------------


def diff_concepts(old: ConceptAST, new: ConceptAST) -> ConceptDiff:
    """Compute a structural diff between two versions of a concept."""
    result = ConceptDiff(concept_name=new.name)

    # Params
    if old.params != new.params:
        result.params_changed = True
        result.old_params = old.params
        result.new_params = new.params

    # Purpose
    if old.purpose.strip() != new.purpose.strip():
        result.purpose_changed = True

    # State
    result.state_changes = _diff_state(old.state, new.state)

    # Actions
    result.action_changes = _diff_actions(old.actions, new.actions)

    # Sync
    result.sync_changes = _diff_syncs(old.sync, new.sync)

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
    renamed: set[tuple[str, str]] = set()  # (old_name, new_name)

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

    # Modified: same name, different type_expr
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


def _compare_action(old: Action, new: Action) -> list[str]:
    details: list[str] = []
    if old.params != new.params:
        details.append(f"params: {old.params} -> {new.params}")

    old_pre = old.pre.clauses if old.pre else []
    new_pre = new.pre.clauses if new.pre else []
    if old_pre != new_pre:
        details.append("pre conditions changed")

    old_post = old.post.clauses if old.post else []
    new_post = new.post.clauses if new.post else []
    if old_post != new_post:
        details.append("post conditions changed")

    return details


def _sync_key(clause: SyncClause) -> str:
    """Create a structural key for matching sync clauses across versions."""
    return f"{clause.trigger_concept}.{clause.trigger_action}"


def _sync_summary(clause: SyncClause) -> dict:
    return {
        "trigger": f"{clause.trigger_concept}.{clause.trigger_action}",
        "params": clause.trigger_params,
        "invocations": [f"{inv.action}({', '.join(inv.params)})" for inv in clause.invocations],
    }


def _diff_syncs(old: list[SyncClause], new: list[SyncClause]) -> list[SyncChange]:
    changes: list[SyncChange] = []

    # Group by trigger key for matching
    old_by_key: dict[str, list[SyncClause]] = {}
    for c in old:
        old_by_key.setdefault(_sync_key(c), []).append(c)

    new_by_key: dict[str, list[SyncClause]] = {}
    for c in new:
        new_by_key.setdefault(_sync_key(c), []).append(c)

    old_keys = set(old_by_key)
    new_keys = set(new_by_key)

    for key in sorted(old_keys - new_keys):
        for clause in old_by_key[key]:
            changes.append(SyncChange(
                kind=ChangeKind.REMOVED,
                description=f"Removed sync on {key}",
                old_clause=_sync_summary(clause),
            ))

    for key in sorted(new_keys - old_keys):
        for clause in new_by_key[key]:
            changes.append(SyncChange(
                kind=ChangeKind.ADDED,
                description=f"Added sync on {key}",
                new_clause=_sync_summary(clause),
            ))

    for key in sorted(old_keys & new_keys):
        old_clauses = old_by_key[key]
        new_clauses = new_by_key[key]
        # Compare each pair; if counts differ or content differs, mark modified
        if len(old_clauses) != len(new_clauses):
            changes.append(SyncChange(
                kind=ChangeKind.MODIFIED,
                description=f"Changed sync count on {key}: {len(old_clauses)} -> {len(new_clauses)}",
            ))
        else:
            for oc, nc in zip(old_clauses, new_clauses):
                if _syncs_differ(oc, nc):
                    changes.append(SyncChange(
                        kind=ChangeKind.MODIFIED,
                        description=f"Modified sync on {key}",
                        old_clause=_sync_summary(oc),
                        new_clause=_sync_summary(nc),
                    ))

    return changes


def _syncs_differ(a: SyncClause, b: SyncClause) -> bool:
    if a.trigger_params != b.trigger_params:
        return True
    if a.trigger_result != b.trigger_result:
        return True
    if a.where_clauses != b.where_clauses:
        return True
    if len(a.invocations) != len(b.invocations):
        return True
    for ai, bi in zip(a.invocations, b.invocations):
        if ai.action != bi.action or ai.params != bi.params:
            return True
    return False


# ---------------------------------------------------------------------------
# Impact analysis: find broken syncs in downstream concepts
# ---------------------------------------------------------------------------


def find_broken_syncs(
    diff: ConceptDiff,
    workspace: list[ConceptAST],
) -> list[BrokenSync]:
    """Given a diff of one concept, find sync clauses in other concepts
    that are now broken by the changes."""
    broken: list[BrokenSync] = []
    concept_name = diff.concept_name

    # Build sets of removed/renamed actions
    removed_actions: set[str] = set()
    renamed_actions: dict[str, str] = {}  # old_name -> new_name (not used yet)
    modified_action_params: set[str] = set()

    for ac in diff.action_changes:
        if ac.kind == ChangeKind.REMOVED:
            removed_actions.add(ac.name)
        elif ac.kind == ChangeKind.MODIFIED:
            if any("params:" in d for d in ac.details):
                modified_action_params.add(ac.name)

    # Check all concepts in workspace for syncs that trigger on the changed concept
    for ast in workspace:
        if ast.name == concept_name:
            continue
        for idx, clause in enumerate(ast.sync):
            if clause.trigger_concept != concept_name:
                continue

            if clause.trigger_action in removed_actions:
                broken.append(BrokenSync(
                    concept_name=ast.name,
                    sync_index=idx,
                    reason=f"Action '{clause.trigger_action}' was removed from '{concept_name}'",
                ))
            elif clause.trigger_action in modified_action_params:
                broken.append(BrokenSync(
                    concept_name=ast.name,
                    sync_index=idx,
                    reason=(
                        f"Action '{clause.trigger_action}' in '{concept_name}' "
                        f"had its parameters changed"
                    ),
                ))

    return broken


def diff_concepts_with_impact(
    old: ConceptAST,
    new: ConceptAST,
    workspace: list[ConceptAST] | None = None,
) -> ConceptDiff:
    """Diff two concept versions and optionally find broken downstream syncs."""
    result = diff_concepts(old, new)
    if workspace:
        result.broken_syncs = find_broken_syncs(result, workspace)
    return result
