"""
Static validation and consistency checking for concept specs.

Validates beyond syntax:
- Sync invocations reference actions that actually exist
- State subset chains reference declared state
- Action pre/post clauses reference declared state variables
- Cross-concept dependency graph is acyclic
- No orphaned syncs (trigger concepts exist in the workspace)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .models import ConceptAST, SyncClause


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class ValidationIssue:
    severity: Severity
    message: str
    location: str  # e.g. "Workspace.sync[0]" or "Workspace.actions.open.pre"

    def to_dict(self) -> dict:
        return {"severity": self.severity.value, "message": self.message, "location": self.location}


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(i.severity == Severity.ERROR for i in self.issues)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "error_count": sum(1 for i in self.issues if i.severity == Severity.ERROR),
            "warning_count": sum(1 for i in self.issues if i.severity == Severity.WARNING),
            "issues": [i.to_dict() for i in self.issues],
        }


# ---------------------------------------------------------------------------
# Clause analysis helpers
# ---------------------------------------------------------------------------

# Matches state variable references in pre/post clauses:
#   "x in names", "names += x", "names -= x", "rel[k] += v", "rel -= k->", "rel[k] = v"
_STATE_REF_PATTERN = re.compile(
    r"(\w+)"           # identifier
    r"(?:\[[^\]]*\])?"  # optional index [...]
    r"\s*"
    r"(?:[+\-]?=|in\b)"  # operator: +=, -=, =, or 'in'
)

_IN_PATTERN = re.compile(r"(\w+)\s+in\s+(\w+)")
_ASSIGN_PATTERN = re.compile(r"(\w+)(?:\[[^\]]*\])?\s*[+\-]?=")
_NOT_IN_PATTERN = re.compile(r"(\w+)\s+not\s+in\s+(\w+)")


def _extract_state_refs(clause: str) -> set[str]:
    """Extract state variable names referenced in a pre/post clause."""
    refs: set[str] = set()
    for m in _IN_PATTERN.finditer(clause):
        refs.add(m.group(2))
    for m in _NOT_IN_PATTERN.finditer(clause):
        refs.add(m.group(2))
    for m in _ASSIGN_PATTERN.finditer(clause):
        refs.add(m.group(1))
    return refs


# ---------------------------------------------------------------------------
# Single-concept validation
# ---------------------------------------------------------------------------

def validate_concept(ast: ConceptAST) -> ValidationResult:
    """Validate a single concept's internal consistency."""
    result = ValidationResult()
    _check_unique_names(ast, result)
    _check_state_consistency(ast, result)
    _check_action_clauses(ast, result)
    _check_sync_invocations(ast, result)
    return result


def _check_unique_names(ast: ConceptAST, result: ValidationResult) -> None:
    """Check for duplicate state/action names."""
    loc = ast.name

    seen_state: set[str] = set()
    for s in ast.state:
        if s.name in seen_state:
            result.issues.append(ValidationIssue(
                Severity.ERROR, f"Duplicate state variable '{s.name}'", f"{loc}.state"
            ))
        seen_state.add(s.name)

    seen_action: set[str] = set()
    for a in ast.actions:
        if a.name in seen_action:
            result.issues.append(ValidationIssue(
                Severity.ERROR, f"Duplicate action '{a.name}'", f"{loc}.actions"
            ))
        seen_action.add(a.name)


def _check_state_consistency(ast: ConceptAST, result: ValidationResult) -> None:
    """Check that subset declarations reference existing base sets."""
    loc = ast.name
    state_names = {s.name for s in ast.state}

    for s in ast.state:
        expr = s.type_expr.strip()

        # Subset form: "parent" (just a name referencing another state as parent set)
        # Relation form: "parent -> set Type"
        # Base set form: "set Type"
        if expr.startswith("set "):
            continue  # base set, always valid

        # Relation form: "parent -> set Type" or "parent -> Type"
        if " -> " in expr:
            parent_name = expr.split("->")[0].strip()
            if parent_name not in state_names:
                result.issues.append(ValidationIssue(
                    Severity.ERROR,
                    f"State '{s.name}' references undefined parent '{parent_name}'",
                    f"{loc}.state.{s.name}",
                ))
            continue

        # Subset form: just a name (should reference another state variable)
        if expr in state_names:
            continue  # valid subset reference

        # Could be a type name (like "User") - that's also valid for scalar state
        # Only warn if it looks like it might be a state reference but doesn't exist
        # Heuristic: if it starts lowercase, it's likely intended as a state ref
        if expr[0].islower() and expr not in state_names:
            result.issues.append(ValidationIssue(
                Severity.ERROR,
                f"State '{s.name}' references undefined state variable '{expr}'",
                f"{loc}.state.{s.name}",
            ))


def _check_action_clauses(ast: ConceptAST, result: ValidationResult) -> None:
    """Check that action pre/post clauses reference declared state variables."""
    state_names = {s.name for s in ast.state}
    loc = ast.name

    for action in ast.actions:
        for kind, clause_block in [("pre", action.pre), ("post", action.post)]:
            if clause_block is None:
                continue
            for clause in clause_block.clauses:
                refs = _extract_state_refs(clause)
                for ref in refs:
                    if ref not in state_names:
                        result.issues.append(ValidationIssue(
                            Severity.ERROR,
                            f"Action '{action.name}' {kind} references undefined "
                            f"state variable '{ref}'",
                            f"{loc}.actions.{action.name}.{kind}",
                        ))


def _check_sync_invocations(ast: ConceptAST, result: ValidationResult) -> None:
    """Check that sync invocations reference actions that actually exist."""
    action_names = {a.name for a in ast.actions}
    action_param_counts = {a.name: len(a.params) for a in ast.actions}
    loc = ast.name

    for idx, clause in enumerate(ast.sync):
        sync_loc = f"{loc}.sync[{idx}]"
        for inv in clause.invocations:
            if inv.action not in action_names:
                result.issues.append(ValidationIssue(
                    Severity.ERROR,
                    f"Sync invokes undefined action '{inv.action}'",
                    sync_loc,
                ))
            else:
                expected = action_param_counts[inv.action]
                actual = len(inv.params)
                if actual != expected:
                    result.issues.append(ValidationIssue(
                        Severity.WARNING,
                        f"Sync invokes '{inv.action}' with {actual} params, "
                        f"expected {expected}",
                        sync_loc,
                    ))


# ---------------------------------------------------------------------------
# Cross-concept validation
# ---------------------------------------------------------------------------

def validate_workspace(concepts: list[ConceptAST]) -> ValidationResult:
    """Validate consistency across all concepts in a workspace."""
    result = ValidationResult()

    # First, validate each concept individually
    for ast in concepts:
        single = validate_concept(ast)
        result.issues.extend(single.issues)

    concept_map = {c.name: c for c in concepts}
    concept_names = set(concept_map.keys())

    _check_sync_triggers(concepts, concept_map, result)
    _check_orphaned_syncs(concepts, concept_names, result)
    _check_dependency_cycles(concepts, concept_names, result)

    return result


def _check_sync_triggers(
    concepts: list[ConceptAST],
    concept_map: dict[str, ConceptAST],
    result: ValidationResult,
) -> None:
    """Check that sync trigger concepts/actions exist."""
    for ast in concepts:
        for idx, clause in enumerate(ast.sync):
            sync_loc = f"{ast.name}.sync[{idx}]"
            tc = clause.trigger_concept

            if tc not in concept_map:
                # External concept - can't validate, just note it
                result.issues.append(ValidationIssue(
                    Severity.WARNING,
                    f"Sync triggers on '{tc}.{clause.trigger_action}' but "
                    f"concept '{tc}' is not in the workspace",
                    sync_loc,
                ))
                continue

            # Check that the trigger action exists on the target concept
            target = concept_map[tc]
            target_actions = {a.name for a in target.actions}
            if clause.trigger_action not in target_actions:
                result.issues.append(ValidationIssue(
                    Severity.ERROR,
                    f"Sync triggers on '{tc}.{clause.trigger_action}' but "
                    f"concept '{tc}' has no action '{clause.trigger_action}'",
                    sync_loc,
                ))


def _check_orphaned_syncs(
    concepts: list[ConceptAST],
    concept_names: set[str],
    result: ValidationResult,
) -> None:
    """Check for concepts whose syncs reference only non-existent concepts."""
    for ast in concepts:
        if not ast.sync:
            continue
        all_external = all(
            clause.trigger_concept not in concept_names for clause in ast.sync
        )
        if all_external and len(ast.sync) > 0:
            result.issues.append(ValidationIssue(
                Severity.WARNING,
                f"All sync clauses in '{ast.name}' reference concepts "
                f"outside the workspace",
                f"{ast.name}.sync",
            ))


def _check_dependency_cycles(
    concepts: list[ConceptAST],
    concept_names: set[str],
    result: ValidationResult,
) -> None:
    """Check that the concept dependency graph is acyclic."""
    # Build adjacency list from sync triggers and generic params
    deps: dict[str, set[str]] = {c.name: set() for c in concepts}

    for ast in concepts:
        # Generic param dependencies
        for param in ast.params:
            if param in concept_names:
                deps[ast.name].add(param)

        # Sync dependencies
        for clause in ast.sync:
            if clause.trigger_concept in concept_names:
                deps[ast.name].add(clause.trigger_concept)

    # Detect cycles using DFS with coloring
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {name: WHITE for name in concept_names}
    path: list[str] = []

    def dfs(node: str) -> list[str] | None:
        color[node] = GRAY
        path.append(node)
        for neighbor in deps.get(node, set()):
            if color[neighbor] == GRAY:
                # Found cycle - extract it
                cycle_start = path.index(neighbor)
                return path[cycle_start:] + [neighbor]
            if color[neighbor] == WHITE:
                cycle = dfs(neighbor)
                if cycle:
                    return cycle
        path.pop()
        color[node] = BLACK
        return None

    for name in concept_names:
        if color[name] == WHITE:
            cycle = dfs(name)
            if cycle:
                cycle_str = " -> ".join(cycle)
                result.issues.append(ValidationIssue(
                    Severity.ERROR,
                    f"Dependency cycle detected: {cycle_str}",
                    "dependency_graph",
                ))
                return  # Report first cycle only
