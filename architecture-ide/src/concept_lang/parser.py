"""
Parser for .concept files.

Format:
    concept Name [Param, ...]
      purpose
        Free text description
        spanning multiple lines

      state
        name: type_expr
        ...

      actions
        action_name (param: Type, ...)
          pre: clause
               continuation
          post: clause
                continuation

      sync
        when Concept.action (params) then local_action (params)
        ...
"""

import re
from .models import Action, ConceptAST, PrePost, StateDecl, SyncClause


class ParseError(Exception):
    pass


def _get_indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _strip_inline_comment(s: str) -> str:
    idx = s.find("//")
    return s[:idx].rstrip() if idx >= 0 else s.rstrip()


def parse_concept(source: str) -> ConceptAST:
    lines = source.splitlines()
    # Strip blank lines at start
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1

    if i >= len(lines):
        raise ParseError("Empty source")

    # --- concept header ---
    header = _strip_inline_comment(lines[i]).strip()
    i += 1

    m = re.match(r"^concept\s+(\w+)(?:\s*\[([^\]]*)\])?$", header)
    if not m:
        raise ParseError(f"Expected 'concept Name [Params]', got: {header!r}")

    concept_name = m.group(1)
    raw_params = m.group(2) or ""
    params = [p.strip() for p in raw_params.split(",") if p.strip()]

    # Collect sections: purpose, state, actions, sync
    # A section starts at indent==2 with a keyword
    purpose = ""
    state: list[StateDecl] = []
    actions: list[Action] = []
    sync: list[SyncClause] = []

    SECTION_KEYWORDS = {"purpose", "state", "actions", "sync"}

    def collect_section_lines(start: int, section_indent: int) -> tuple[list[str], int]:
        """Collect lines belonging to this section (indent > section_indent)."""
        result = []
        j = start
        while j < len(lines):
            line = lines[j]
            stripped = line.strip()
            if not stripped:
                result.append("")
                j += 1
                continue
            ind = _get_indent(line)
            if ind <= section_indent:
                break
            result.append(line)
            j += 1
        return result, j

    while i < len(lines):
        line = lines[i]
        stripped = _strip_inline_comment(line).strip()
        if not stripped:
            i += 1
            continue

        ind = _get_indent(line)
        if stripped in SECTION_KEYWORDS:
            section_indent = ind
            body_lines, i = collect_section_lines(i + 1, section_indent)
            if stripped == "purpose":
                purpose = _parse_purpose(body_lines)
            elif stripped == "state":
                state = _parse_state(body_lines, section_indent)
            elif stripped == "actions":
                actions = _parse_actions(body_lines, section_indent)
            elif stripped == "sync":
                sync = _parse_sync(body_lines)
        else:
            i += 1

    return ConceptAST(
        name=concept_name,
        params=params,
        purpose=purpose,
        state=state,
        actions=actions,
        sync=sync,
        source=source,
    )


def _parse_purpose(lines: list[str]) -> str:
    parts = []
    for line in lines:
        stripped = _strip_inline_comment(line).strip()
        if stripped:
            parts.append(stripped)
    return " ".join(parts)


def _parse_state(lines: list[str], section_indent: int) -> list[StateDecl]:
    decls: list[StateDecl] = []
    for line in lines:
        stripped = _strip_inline_comment(line).strip()
        if not stripped:
            continue
        # name: type_expr
        m = re.match(r"^(\w+)\s*:\s*(.+)$", stripped)
        if m:
            decls.append(StateDecl(name=m.group(1), type_expr=m.group(2).strip()))
    return decls


def _parse_actions(lines: list[str], section_indent: int) -> list[Action]:
    """
    Actions block. Each action starts at a fixed indent with:
        name (param: Type, ...)
    followed by optional pre/post at deeper indent.
    """
    actions: list[Action] = []
    if not lines:
        return actions

    # Find the indent level of action names (first non-blank line)
    action_indent = None
    for line in lines:
        if line.strip():
            action_indent = _get_indent(line)
            break

    if action_indent is None:
        return actions

    # Group lines by action
    current_action_lines: list[str] = []
    current_header: str | None = None

    def flush() -> None:
        if current_header is not None:
            actions.append(_parse_single_action(current_header, current_action_lines))

    for line in lines:
        stripped = _strip_inline_comment(line).strip()
        if not stripped:
            continue
        ind = _get_indent(line)
        if ind == action_indent:
            flush()
            current_header = stripped
            current_action_lines = []
        elif ind > action_indent and current_header is not None:
            current_action_lines.append(line)

    flush()
    return actions


def _parse_single_action(header: str, body_lines: list[str]) -> Action:
    # header: "name (param: Type, ...)" or "name ()"
    # Allow optional return type: "name (params) -> Type"
    m = re.match(r"^(\w+)\s*\(([^)]*)\)(?:\s*->[^)]*)?$", header)
    if not m:
        raise ParseError(f"Invalid action header: {header!r}")

    name = m.group(1)
    raw_params = m.group(2).strip()
    params = [p.strip() for p in raw_params.split(",") if p.strip()]

    pre: PrePost | None = None
    post: PrePost | None = None

    if not body_lines:
        return Action(name=name, params=params)

    # Find indent of pre/post keywords
    kw_indent = None
    for line in body_lines:
        if line.strip():
            kw_indent = _get_indent(line)
            break

    if kw_indent is None:
        return Action(name=name, params=params)

    # Collect pre/post clauses; continuations are deeper
    current_kw: str | None = None
    current_clauses: list[str] = []

    result: dict[str, list[str]] = {}

    for line in body_lines:
        stripped = _strip_inline_comment(line).strip()
        if not stripped:
            continue
        ind = _get_indent(line)
        if ind == kw_indent:
            if current_kw and current_clauses:
                result[current_kw] = current_clauses[:]
            # "pre: clause" or "post: clause"
            m2 = re.match(r"^(pre|post)\s*:\s*(.*)$", stripped)
            if m2:
                current_kw = m2.group(1)
                first_clause = m2.group(2).strip()
                current_clauses = [first_clause] if first_clause else []
            else:
                current_kw = None
                current_clauses = []
        elif ind > kw_indent and current_kw:
            # continuation clause
            current_clauses.append(stripped)

    if current_kw and current_clauses:
        result[current_kw] = current_clauses

    if "pre" in result:
        pre = PrePost(clauses=result["pre"])
    if "post" in result:
        post = PrePost(clauses=result["post"])

    return Action(name=name, params=params, pre=pre, post=post)


def _parse_sync(lines: list[str]) -> list[SyncClause]:
    """
    Parse sync clauses:
        when Concept.action (params) then local_action (params)
    """
    clauses: list[SyncClause] = []
    for line in lines:
        stripped = _strip_inline_comment(line).strip()
        if not stripped:
            continue
        m = re.match(
            r"^when\s+(\w+)\.(\w+)\s*\(([^)]*)\)\s+then\s+(\w+)\s*\(([^)]*)\)$",
            stripped,
        )
        if m:
            trigger_params = [p.strip() for p in m.group(3).split(",") if p.strip()]
            local_params = [p.strip() for p in m.group(5).split(",") if p.strip()]
            clauses.append(
                SyncClause(
                    trigger_concept=m.group(1),
                    trigger_action=m.group(2),
                    trigger_params=trigger_params,
                    local_action=m.group(4),
                    local_params=local_params,
                )
            )
    return clauses


def parse_file(path: str) -> ConceptAST:
    with open(path, encoding="utf-8") as f:
        source = f.read()
    return parse_concept(source)
