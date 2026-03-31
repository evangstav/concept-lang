"""
Parser for .app files (concept composition specs).

Format:
    app Name
      purpose
        Free text description

      concepts
        User
        Password [User]
        Article [User]
        Follow [User, User]
"""

import re
from .models import AppSpec, ConceptBinding


class AppParseError(Exception):
    pass


def _get_indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _strip_inline_comment(s: str) -> str:
    idx = s.find("//")
    return s[:idx].rstrip() if idx >= 0 else s.rstrip()


def parse_app(source: str) -> AppSpec:
    lines = source.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1

    if i >= len(lines):
        raise AppParseError("Empty source")

    # --- app header ---
    header = _strip_inline_comment(lines[i]).strip()
    i += 1

    m = re.match(r"^app\s+(\w+)$", header)
    if not m:
        raise AppParseError(f"Expected 'app Name', got: {header!r}")

    app_name = m.group(1)
    purpose = ""
    concepts: list[ConceptBinding] = []

    SECTION_KEYWORDS = {"purpose", "concepts"}

    def collect_section_lines(start: int, section_indent: int) -> tuple[list[str], int]:
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

        if stripped in SECTION_KEYWORDS:
            section_indent = _get_indent(line)
            body_lines, i = collect_section_lines(i + 1, section_indent)
            if stripped == "purpose":
                purpose = _parse_purpose(body_lines)
            elif stripped == "concepts":
                concepts = _parse_concepts(body_lines)
        else:
            i += 1

    if not concepts:
        raise AppParseError("App spec must declare at least one concept")

    return AppSpec(
        name=app_name,
        purpose=purpose,
        concepts=concepts,
        source=source,
    )


def _parse_purpose(lines: list[str]) -> str:
    parts = []
    for line in lines:
        stripped = _strip_inline_comment(line).strip()
        if stripped:
            parts.append(stripped)
    return " ".join(parts)


_CONCEPT_BINDING = re.compile(
    r"^(\w+)"                   # concept name
    r"(?:\s*\[([^\]]*)\])?"     # optional [Param, Param]
    r"$"
)


def _parse_concepts(lines: list[str]) -> list[ConceptBinding]:
    bindings: list[ConceptBinding] = []
    for line in lines:
        stripped = _strip_inline_comment(line).strip()
        if not stripped:
            continue
        m = _CONCEPT_BINDING.match(stripped)
        if not m:
            raise AppParseError(f"Invalid concept binding: {stripped!r}")
        name = m.group(1)
        raw_params = m.group(2) or ""
        params = [p.strip() for p in raw_params.split(",") if p.strip()]
        bindings.append(ConceptBinding(name=name, bindings=params))
    return bindings


def parse_app_file(path: str) -> AppSpec:
    with open(path, encoding="utf-8") as f:
        source = f.read()
    return parse_app(source)
