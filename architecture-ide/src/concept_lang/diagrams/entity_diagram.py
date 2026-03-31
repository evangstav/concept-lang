"""
Generate a Mermaid classDiagram from a ConceptAST's state declarations.

Mapping rules:
  name: set T       → entity class T; concept --> T relation
  name: parent      → subset declaration; shown as +name: ⊆ parent (attribute, no arrow)
  X -> set Y        → resolved X class --> Y class (many)
  X -> Y            → resolved X class --> Y class (one)
  anything else     → +name: type attribute on concept class

Single merged class block per concept — no duplicate class entries.
Self-referential relations (concept holds its own element type) are shown
as a containment note rather than a looping arrow.
"""

import re
from ..models import ConceptAST


def entity_diagram(concept: ConceptAST) -> str:
    lines = ["classDiagram"]

    # --- Pass 1: classify all declarations ---

    # set_alias: field_name -> element_type  (e.g. "named" -> "ConceptName")
    set_alias: dict[str, str] = {}
    # subset_of: field_name -> parent_field  (e.g. "purposeful" -> "named")
    subset_of: dict[str, str] = {}
    known_sets: set[str] = set()

    for decl in concept.state:
        m = re.match(r"^set\s+(\w+)$", decl.type_expr)
        if m:
            set_alias[decl.name] = m.group(1)
            known_sets.add(decl.name)
        elif "->" not in decl.type_expr:
            # No arrow → plain identifier = subset reference (e.g. "purposeful: named")
            parts = decl.type_expr.strip().split()
            candidate = parts[0] if parts else ""
            if candidate and candidate[0].islower():
                subset_of[decl.name] = candidate
            known_sets.add(decl.name)
        else:
            known_sets.add(decl.name)

    def resolve_field(name: str) -> str:
        """Resolve a field name to its element type."""
        if name in set_alias:
            return set_alias[name]
        if name in subset_of:
            return resolve_field(subset_of[name])
        return name

    # --- Pass 2: build class body attributes and external relations ---

    attrs: list[str] = []          # lines inside class { }
    relation_lines: list[str] = [] # lines outside class { }
    external_classes: set[str] = set()

    for decl in concept.state:
        # Base set: name: set T
        if re.match(r"^set\s+\w+$", decl.type_expr):
            entity_type = set_alias[decl.name]
            attrs.append(f"        +{decl.name} set~{entity_type}~")
            # Only add relation if entity_type is external (not the concept itself)
            if entity_type != concept.name:
                external_classes.add(entity_type)
                relation_lines.append(
                    f'    {concept.name} "1" o-- "*" {entity_type} : {decl.name}'
                )
            continue

        # Subset: name: parent (where parent is a known lowercase field)
        if decl.name in subset_of:
            parent = subset_of[decl.name]
            attrs.append(f"        +{decl.name} ⊆ {parent}")
            continue

        # Relation: X -> set Y  or  X -> Y
        m_rel = re.match(r"^(\w+)\s*->\s*(set\s+)?(\w+)$", decl.type_expr)
        if m_rel:
            lhs_type = resolve_field(m_rel.group(1))
            is_many = m_rel.group(2) is not None
            rhs_type = m_rel.group(3)
            card = '"*"' if is_many else '"1"'
            if lhs_type != concept.name:
                external_classes.add(lhs_type)
            if rhs_type != concept.name:
                external_classes.add(rhs_type)
            relation_lines.append(
                f'    {lhs_type} "1" --> {card} {rhs_type} : {decl.name}'
            )
            continue

        # Scalar attribute
        attrs.append(f"        +{decl.name} {decl.type_expr}")

    # --- Emit single merged class block ---
    lines.append(f"    class {concept.name} {{")
    lines.append(f'        +purpose "{_truncate(concept.purpose, 45)}"')
    for attr in attrs:
        lines.append(attr)
    lines.append("    }")

    # Emit external entity classes
    for entity in sorted(external_classes):
        lines.append(f"    class {entity}")

    lines.extend(relation_lines)

    return "\n".join(lines)


def _truncate(s: str, n: int) -> str:
    return s[:n] + "..." if len(s) > n else s
