"""
Shared cross-reference indices used by validator rules.

A `WorkspaceIndex` is built once per `validate_workspace` call and passed
into the individual rule functions. This keeps rules O(1) on their common
lookups (is this concept known? what fields does this action have?).
"""

from dataclasses import dataclass, field

from concept_lang.ast import ActionCase, Workspace


@dataclass
class WorkspaceIndex:
    """Precomputed cross-reference tables for a `Workspace`."""

    concept_names: set[str] = field(default_factory=set)
    # (concept_name, action_name) -> list of action cases
    _action_cases: dict[tuple[str, str], list[ActionCase]] = field(default_factory=dict)
    # concept_name -> set of declared state field names
    _state_fields: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def build(cls, workspace: Workspace) -> "WorkspaceIndex":
        idx = cls()
        for name, concept in workspace.concepts.items():
            idx.concept_names.add(name)
            idx._state_fields[name] = {s.name for s in concept.state}
            for action in concept.actions:
                idx._action_cases[(name, action.name)] = list(action.cases)
        return idx

    def action_cases(self, concept: str, action: str) -> list[ActionCase] | None:
        """Return the list of cases for `concept/action`, or None if unknown."""
        return self._action_cases.get((concept, action))

    def state_field_names(self, concept: str) -> set[str]:
        """Return the set of state field names for `concept` (empty if unknown)."""
        return self._state_fields.get(concept, set())

    def action_field_names(self, concept: str, action: str) -> set[str]:
        """
        Union of input and output field names across all cases of
        `concept/action`. Empty if the action is unknown.
        """
        cases = self.action_cases(concept, action)
        if cases is None:
            return set()
        names: set[str] = set()
        for case in cases:
            for inp in case.inputs:
                names.add(inp.name)
            for out in case.outputs:
                names.add(out.name)
        return names
