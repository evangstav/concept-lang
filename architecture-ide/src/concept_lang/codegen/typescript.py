"""TypeScript code generation backend."""

from ..models import Action, ConceptAST, StateDecl
from .base import CodegenBackend


def _type_to_ts(type_expr: str) -> str:
    """Convert concept type expressions to TypeScript types."""
    expr = type_expr.strip()
    if expr.startswith("set "):
        inner = expr[4:].strip()
        return f"Set<{inner}>"
    if "->" in expr:
        parts = expr.split("->", 1)
        key = parts[0].strip()
        val = parts[1].strip()
        val_type = _type_to_ts(val)
        return f"Map<{key}, {val_type}>"
    return expr


def _param_name(p: str) -> str:
    return p.split(":")[0].strip()


def _param_type(p: str) -> str:
    if ":" in p:
        return p.split(":", 1)[1].strip()
    return "unknown"


def _state_init(s: StateDecl) -> str:
    """Return TypeScript default initializer for a state declaration."""
    expr = s.type_expr.strip()
    if expr.startswith("set "):
        return f"new Set()"
    if "->" in expr:
        return f"new Map()"
    if not expr[0].isupper() and " " not in expr:
        return "new Set()"
    return "undefined as any"


class TypeScriptBackend(CodegenBackend):

    @property
    def language(self) -> str:
        return "typescript"

    @property
    def file_extension(self) -> str:
        return ".ts"

    def generate(self, ast: ConceptAST) -> str:
        lines: list[str] = []
        lines.append(f"/**")
        lines.append(f" * Concept: {ast.name}")
        if ast.purpose:
            lines.append(f" *")
            lines.append(f" * {ast.purpose}")
        lines.append(f" */")
        lines.append(f"")

        # Type params
        type_params = ""
        if ast.params:
            type_params = f"<{', '.join(ast.params)}>"

        lines.append(f"export class {ast.name}{type_params} {{")

        # State fields
        for s in ast.state:
            ts_type = _type_to_ts(s.type_expr)
            init = _state_init(s)
            lines.append(f"  {s.name}: {ts_type} = {init};")

        if ast.state:
            lines.append(f"")

        # Actions
        for action in ast.actions:
            lines.extend(_generate_action(action))
            lines.append(f"")

        lines.append(f"}}")
        lines.append(f"")
        return "\n".join(lines)


def _generate_action(action: Action) -> list[str]:
    lines: list[str] = []

    # Parameter list
    params_parts: list[str] = []
    for p in action.params:
        name = _param_name(p)
        ptype = _param_type(p)
        params_parts.append(f"{name}: {ptype}")

    sig = ", ".join(params_parts)
    lines.append(f"  {action.name}({sig}): void {{")

    # Pre-condition hook
    if action.pre:
        for clause in action.pre.clauses:
            lines.append(f"    // pre: {clause}")
        param_names = ", ".join(_param_name(p) for p in action.params)
        lines.append(f"    this.checkPre{_capitalize(action.name)}({param_names});")

    # Post-conditions as comments
    if action.post:
        for clause in action.post.clauses:
            lines.append(f"    // post: {clause}")

    lines.append(f"    throw new Error(\"Not implemented: {action.name}\"); // TODO")
    lines.append(f"  }}")

    # Pre-condition hook
    if action.pre:
        lines.append(f"")
        lines.append(f"  private checkPre{_capitalize(action.name)}({sig}): void {{")
        for clause in action.pre.clauses:
            lines.append(f"    // Assert: {clause}")
        lines.append(f"  }}")

    return lines


def _capitalize(s: str) -> str:
    return s[0].upper() + s[1:] if s else s
