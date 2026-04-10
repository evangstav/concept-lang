"""
Generate a Mermaid stateDiagram-v2 from a v2 ConceptAST.

Handles two state-declaration patterns:

1. Simple sets:  active: set User
   - Actions that add to `active`  →  [*] --> active
   - Actions that remove from `active`  →  active --> [*]

2. Subset progressions:  named: set T  |  purposeful: named  |  specified: purposeful
   - Builds a chain: [*] → named → purposeful → specified → [*]
   - Each action maps to one primary transition based on what it modifies.
   - Primary transition priority:
     a) base set removed  → base --> [*]
     b) deepest subset added  → parent --> subset
     c) base set added  → [*] --> base
     d) deepest subset removed  → subset --> parent

v2 notes: a v2 action can have multiple cases. This generator looks at
the first case's `effects` list because that is the same contract the
old `_to_v1_concept` adapter exposed (and the contract the existing MCP
`get_state_machine` tool pinned). If an action has no effects or no
cases, it renders as a self-loop on the principal state.
"""

from __future__ import annotations

import re

from concept_lang.ast import Action, ConceptAST


def _first_case_effects(action: Action) -> list[tuple[str, str]]:
    """Return [(field, op), …] for the first case's effect clauses."""
    if not action.cases:
        return []
    case = action.cases[0]
    return [(e.field, e.op) for e in case.effects]


def state_machine(concept: ConceptAST) -> str:
    lines = ["stateDiagram-v2"]

    base_sets: dict[str, str] = {}   # name -> element type
    subsets: dict[str, str] = {}     # name -> parent name
    known_sets: set[str] = set()

    for decl in concept.state:
        m = re.match(r"^set\s+(\w+)$", decl.type_expr)
        if m:
            base_sets[decl.name] = m.group(1)
            known_sets.add(decl.name)
        else:
            parts = decl.type_expr.strip().split()
            candidate_parent = parts[0] if parts else decl.name
            subsets[decl.name] = candidate_parent
            known_sets.add(decl.name)

    if not known_sets:
        # No sets at all — show a flat single-state machine.
        state = f"{concept.name}_active"
        lines.append(f"    state {state}")
        for action in concept.actions:
            lines.append(f"    [*] --> {state} : {action.name}")
        return "\n".join(lines)

    depth: dict[str, int] = {}
    for name in base_sets:
        depth[name] = 1

    changed = True
    while changed:
        changed = False
        for name, parent in subsets.items():
            if parent in depth and name not in depth:
                depth[name] = depth[parent] + 1
                changed = True

    def parent_of(name: str) -> str | None:
        if name in subsets:
            return subsets[name]
        return None

    def deepest(names: set[str]) -> str | None:
        candidates = [(depth.get(n, 0), n) for n in names if n in known_sets]
        return max(candidates, key=lambda x: x[0])[1] if candidates else None

    def shallowest(names: set[str]) -> str | None:
        candidates = [(depth.get(n, 0), n) for n in names if n in known_sets]
        return min(candidates, key=lambda x: x[0])[1] if candidates else None

    for action in concept.actions:
        added: set[str] = set()
        removed: set[str] = set()

        for field, op in _first_case_effects(action):
            if field in known_sets:
                if op == "+=":
                    added.add(field)
                elif op == "-=":
                    removed.add(field)

        if not added and not removed:
            principal = next(iter(base_sets), None) or next(iter(known_sets))
            lines.append(f"    {principal} --> {principal} : {action.name}")
            continue

        if removed & set(base_sets.keys()):
            # Priority a: base set removed → base --> [*]
            base = shallowest(removed & set(base_sets.keys()))
            lines.append(f"    {base} --> [*] : {action.name}")
        elif added - set(base_sets.keys()):
            # Priority b: deepest subset added → parent --> subset
            target = deepest(added - set(base_sets.keys()))
            p = parent_of(target) if target is not None else None
            if p is not None:
                lines.append(f"    {p} --> {target} : {action.name}")
        elif added & set(base_sets.keys()):
            # Priority c: base set added → [*] --> base
            base = deepest(added & set(base_sets.keys()))
            lines.append(f"    [*] --> {base} : {action.name}")
        elif removed - set(base_sets.keys()):
            # Priority d: deepest subset removed → subset --> parent
            target = deepest(removed - set(base_sets.keys()))
            p = parent_of(target) if target is not None else None
            if p is not None:
                lines.append(f"    {target} --> {p} : {action.name}")
        else:
            principal = next(iter(base_sets), None) or next(iter(known_sets))
            lines.append(f"    {principal} --> {principal} : {action.name}")

    return "\n".join(lines)
