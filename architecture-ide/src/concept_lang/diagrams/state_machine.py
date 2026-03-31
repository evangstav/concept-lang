"""
Generate a Mermaid stateDiagram-v2 from a ConceptAST.

Handles two set patterns:

1. Simple sets:  active: set User
   - Actions that += active  →  [*] --> active
   - Actions that -= active  →  active --> [*]

2. Subset progressions:  named: set T  |  purposeful: named  |  specified: purposeful
   - Builds a chain: [*] → named → purposeful → specified → [*]
   - Each action maps to one primary transition based on what it modifies.
   - Primary transition priority:
     a) base set removed  → base --> [*]
     b) deepest subset added  → parent --> subset
     c) base set added  → [*] --> base
     d) deepest subset removed  → subset --> parent
"""

import re
from ..models import ConceptAST


def state_machine(concept: ConceptAST) -> str:
    lines = ["stateDiagram-v2"]

    # Classify state declarations
    base_sets: dict[str, str] = {}   # name -> element type  (e.g. named -> ConceptName)
    subsets: dict[str, str] = {}     # name -> parent name   (e.g. purposeful -> named)

    known_sets: set[str] = set()
    for decl in concept.state:
        m = re.match(r"^set\s+(\w+)$", decl.type_expr)
        if m:
            base_sets[decl.name] = m.group(1)
            known_sets.add(decl.name)
        else:
            # Possible subset: type_expr is a plain identifier that names a set
            parts = decl.type_expr.strip().split()
            candidate_parent = parts[0] if parts else decl.name
            subsets[decl.name] = candidate_parent
            known_sets.add(decl.name)

    if not known_sets:
        # No sets at all — show a flat single-state machine
        state = f"{concept.name}_active"
        lines.append(f"    state {state}")
        for action in concept.actions:
            lines.append(f"    [*] --> {state} : {action.name}")
        return "\n".join(lines)

    # Build depth map: how far each set is from [*] in the chain
    # base sets have depth 1; their subsets depth 2; etc.
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
        return None  # base set, parent is [*]

    def deepest(names: set[str]) -> str | None:
        candidates = [(depth.get(n, 0), n) for n in names if n in known_sets]
        return max(candidates, key=lambda x: x[0])[1] if candidates else None

    def shallowest(names: set[str]) -> str | None:
        candidates = [(depth.get(n, 0), n) for n in names if n in known_sets]
        return min(candidates, key=lambda x: x[0])[1] if candidates else None

    for action in concept.actions:
        if action.post is None:
            principal = next(iter(base_sets), None) or next(iter(known_sets))
            lines.append(f"    {principal} --> {principal} : {action.name}")
            continue

        added: set[str] = set()
        removed: set[str] = set()

        for clause in action.post.clauses:
            m_add = re.match(r"^(\w+)\s*\+=", clause)
            if m_add and m_add.group(1) in known_sets:
                added.add(m_add.group(1))
            m_rem = re.match(r"^(\w+)\s*-=", clause)
            if m_rem and m_rem.group(1) in known_sets:
                removed.add(m_rem.group(1))

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
