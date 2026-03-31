"""Go code generation backend."""

import re

from ..models import Action, ConceptAST, StateDecl
from .base import CodegenBackend


def _type_to_go(type_expr: str) -> str:
    """Convert concept type expressions to Go types."""
    expr = type_expr.strip()
    if expr.startswith("set "):
        inner = expr[4:].strip()
        return f"map[{inner}]bool"
    if "->" in expr:
        parts = expr.split("->", 1)
        key = parts[0].strip()
        val = parts[1].strip()
        val_type = _type_to_go(val)
        return f"map[{key}]{val_type}"
    if not expr[0].isupper() and " " not in expr:
        return f"map[string]bool"
    return expr


def _param_name(p: str) -> str:
    return p.split(":")[0].strip()


def _param_type(p: str) -> str:
    if ":" in p:
        return p.split(":", 1)[1].strip()
    return "interface{}"


def _to_snake(name: str) -> str:
    """Convert CamelCase to snake_case for Go package naming."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _state_init(s: StateDecl) -> str:
    """Return Go initializer expression."""
    go_type = _type_to_go(s.type_expr)
    if go_type.startswith("map["):
        return f"make({go_type})"
    return f"*new({go_type})"


class GoBackend(CodegenBackend):

    @property
    def language(self) -> str:
        return "go"

    @property
    def file_extension(self) -> str:
        return ".go"

    def generate(self, ast: ConceptAST) -> str:
        pkg = _to_snake(ast.name)
        lines: list[str] = []

        lines.append(f"// Concept: {ast.name}")
        if ast.purpose:
            lines.append(f"// {ast.purpose}")
        lines.append(f"package {pkg}")
        lines.append(f"")
        lines.append(f'import "errors"')
        lines.append(f"")

        # Struct
        lines.append(f"type {ast.name} struct {{")
        for s in ast.state:
            go_type = _type_to_go(s.type_expr)
            lines.append(f"\t{_exported(s.name)} {go_type}")
        lines.append(f"}}")
        lines.append(f"")

        # Constructor
        lines.append(f"func New{ast.name}() *{ast.name} {{")
        lines.append(f"\treturn &{ast.name}{{")
        for s in ast.state:
            init = _state_init(s)
            lines.append(f"\t\t{_exported(s.name)}: {init},")
        lines.append(f"\t}}")
        lines.append(f"}}")
        lines.append(f"")

        # Actions
        for action in ast.actions:
            lines.extend(_generate_action(ast.name, action))
            lines.append(f"")

        return "\n".join(lines)


def _exported(name: str) -> str:
    """Capitalize first letter for Go export."""
    return name[0].upper() + name[1:] if name else name


def _generate_action(struct_name: str, action: Action) -> list[str]:
    lines: list[str] = []

    # Parameter list
    params_parts: list[str] = []
    for p in action.params:
        name = _param_name(p)
        ptype = _param_type(p)
        params_parts.append(f"{name} {ptype}")

    sig = ", ".join(params_parts)
    # Use first letter of struct as receiver, but avoid conflicts with param names
    receiver = struct_name[0].lower()
    param_names = {_param_name(p) for p in action.params}
    if receiver in param_names:
        receiver = receiver + "0"

    lines.append(f"func ({receiver} *{struct_name}) {_exported(action.name)}({sig}) error {{")

    # Pre-condition hook
    if action.pre:
        for clause in action.pre.clauses:
            lines.append(f"\t// pre: {clause}")
        param_names = ", ".join(_param_name(p) for p in action.params)
        lines.append(f"\tif err := {receiver}.checkPre{_exported(action.name)}({param_names}); err != nil {{")
        lines.append(f"\t\treturn err")
        lines.append(f"\t}}")

    # Post-conditions as comments
    if action.post:
        for clause in action.post.clauses:
            lines.append(f"\t// post: {clause}")

    lines.append(f'\treturn errors.New("not implemented: {action.name}") // TODO')
    lines.append(f"}}")

    # Pre-condition hook
    if action.pre:
        lines.append(f"")
        lines.append(f"func ({receiver} *{struct_name}) checkPre{_exported(action.name)}({sig}) error {{")
        for clause in action.pre.clauses:
            lines.append(f"\t// Assert: {clause}")
        lines.append(f"\treturn nil // TODO: implement precondition check")
        lines.append(f"}}")

    return lines
