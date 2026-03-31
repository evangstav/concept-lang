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
        // single-line form
        when Concept.action (params) then local_action (params)
        // multi-line when/where/then form
        when Concept.action (params) -> result
          where condition_clause
          then action1 (params)
               action2 (params)
"""

import re
from .models import Action, ConceptAST, PrePost, StateDecl, SyncClause, SyncInvocation


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


def _parse_invocation(text: str) -> SyncInvocation | None:
    """Parse a single action invocation like 'open (u, s)' or 'track (s)'."""
    m = re.match(r"^(\w+)\s*\(([^)]*)\)$", text.strip())
    if not m:
        return None
    params = [p.strip() for p in m.group(2).split(",") if p.strip()]
    return SyncInvocation(action=m.group(1), params=params)


def _parse_sync(lines: list[str]) -> list[SyncClause]:
    """
    Parse sync clauses in when/where/then pattern.

    Single-line form (backward compatible):
        when Concept.action (params) then local_action (params)

    Multi-line form:
        when Concept.action (params) -> result
          where condition
          then action1 (params)
               action2 (params)
    """
    clauses: list[SyncClause] = []
    if not lines:
        return clauses

    # Find the indent level of 'when' lines (first non-blank line)
    when_indent = None
    for line in lines:
        if line.strip():
            when_indent = _get_indent(line)
            break
    if when_indent is None:
        return clauses

    # Group lines by 'when' block
    blocks: list[list[str]] = []
    current_block: list[str] = []

    for line in lines:
        stripped = _strip_inline_comment(line).strip()
        if not stripped:
            continue
        ind = _get_indent(line)
        if ind == when_indent and stripped.startswith("when "):
            if current_block:
                blocks.append(current_block)
            current_block = [stripped]
        elif current_block:
            current_block.append(stripped)

    if current_block:
        blocks.append(current_block)

    for block in blocks:
        clause = _parse_sync_block(block)
        if clause:
            clauses.append(clause)

    return clauses


_WHEN_PATTERN = re.compile(
    r"^when\s+(\w+)\.(\w+)\s*\(([^)]*)\)"  # when Concept.action (params)
    r"(?:\s*->\s*(.+?))?"                    # optional -> result
    r"(?:\s+then\s+(.+))?$"                  # optional inline then
)


def _parse_sync_block(block: list[str]) -> SyncClause | None:
    """Parse a when/where/then block (single or multi-line)."""
    if not block:
        return None

    header = block[0]
    m = _WHEN_PATTERN.match(header)
    if not m:
        return None

    trigger_concept = m.group(1)
    trigger_action = m.group(2)
    trigger_params = [p.strip() for p in m.group(3).split(",") if p.strip()]
    trigger_result = m.group(4).strip() if m.group(4) else None
    inline_then = m.group(5)

    # Single-line form: when C.a (p) then local (p)
    if inline_then:
        inv = _parse_invocation(inline_then)
        if inv:
            return SyncClause(
                trigger_concept=trigger_concept,
                trigger_action=trigger_action,
                trigger_params=trigger_params,
                trigger_result=trigger_result,
                invocations=[inv],
            )
        return None

    # Multi-line form: parse where/then from remaining lines
    where_clauses: list[str] = []
    invocations: list[SyncInvocation] = []
    current_section: str | None = None

    for line in block[1:]:
        stripped = line.strip()
        if not stripped:
            continue

        # Check for section keywords
        where_match = re.match(r"^where\s+(.+)$", stripped)
        then_match = re.match(r"^then\s+(.+)$", stripped)

        if where_match:
            current_section = "where"
            where_clauses.append(where_match.group(1).strip())
        elif then_match:
            current_section = "then"
            inv = _parse_invocation(then_match.group(1))
            if inv:
                invocations.append(inv)
        elif current_section == "where":
            where_clauses.append(stripped)
        elif current_section == "then":
            inv = _parse_invocation(stripped)
            if inv:
                invocations.append(inv)

    # Multi-line must have at least a then clause
    if not invocations:
        return None

    return SyncClause(
        trigger_concept=trigger_concept,
        trigger_action=trigger_action,
        trigger_params=trigger_params,
        trigger_result=trigger_result,
        where_clauses=where_clauses,
        invocations=invocations,
    )


def parse_file(path: str) -> ConceptAST:
    with open(path, encoding="utf-8") as f:
        source = f.read()
    return parse_concept(source)
