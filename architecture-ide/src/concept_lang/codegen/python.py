"""Python code generation backend."""

from ..models import Action, ConceptAST, StateDecl
from .base import CodegenBackend


def _type_to_python(type_expr: str) -> str:
    """Convert concept type expressions to Python type hints."""
    expr = type_expr.strip()
    if expr.startswith("set "):
        inner = expr[4:].strip()
        return f"set[{inner}]"
    if "->" in expr:
        parts = expr.split("->", 1)
        key = parts[0].strip()
        val = parts[1].strip()
        val_type = _type_to_python(val)
        return f"dict[{key}, {val_type}]"
    return expr


def _param_name(p: str) -> str:
    """Extract parameter name from 'name: Type' or plain 'name'."""
    return p.split(":")[0].strip()


def _param_type(p: str) -> str:
    """Extract parameter type from 'name: Type', defaulting to 'Any'."""
    if ":" in p:
        return p.split(":", 1)[1].strip()
    return "Any"


def _format_clauses(clauses: list[str], label: str) -> list[str]:
    """Format pre/post condition clauses as comment lines."""
    lines: list[str] = []
    for clause in clauses:
        lines.append(f"        # {label}: {clause}")
    return lines


class PythonBackend(CodegenBackend):

    @property
    def language(self) -> str:
        return "python"

    @property
    def file_extension(self) -> str:
        return ".py"

    def generate(self, ast: ConceptAST) -> str:
        lines: list[str] = []
        lines.append(f'"""Concept: {ast.name}')
        if ast.purpose:
            lines.append(f"")
            lines.append(f"{ast.purpose}")
        lines.append(f'"""')
        lines.append(f"")
        lines.append(f"from __future__ import annotations")
        lines.append(f"")
        lines.append(f"from typing import Any")
        lines.append(f"")
        lines.append(f"")

        # Type params as comment
        if ast.params:
            params_str = ", ".join(ast.params)
            lines.append(f"# Type parameters: {params_str}")
            lines.append(f"")
            lines.append(f"")

        lines.append(f"class {ast.name}:")

        # State fields
        if ast.state:
            lines.append(f"")
            lines.append(f"    def __init__(self) -> None:")
            for s in ast.state:
                py_type = _type_to_python(s.type_expr)
                init_val = _state_init_value(s)
                lines.append(f"        self.{s.name}: {py_type} = {init_val}")
        else:
            lines.append(f"")
            lines.append(f"    def __init__(self) -> None:")
            lines.append(f"        pass")

        # Actions
        for action in ast.actions:
            lines.append(f"")
            lines.extend(_generate_action(action))

        lines.append(f"")
        return "\n".join(lines)


def _state_init_value(s: StateDecl) -> str:
    """Return the Python default value for a state declaration."""
    expr = s.type_expr.strip()
    if expr.startswith("set "):
        return "set()"
    if "->" in expr:
        return "{}"
    # Subset state (type_expr is another state name) — default to set
    # since subset progressions are sets in practice
    if not expr[0].isupper() and " " not in expr:
        return "set()"
    return "None  # type: Any"


def _generate_action(action: Action) -> list[str]:
    """Generate a method stub for a single action."""
    lines: list[str] = []

    # Build parameter list
    params = ["self"]
    for p in action.params:
        name = _param_name(p)
        ptype = _param_type(p)
        params.append(f"{name}: {ptype}")

    sig = ", ".join(params)
    lines.append(f"    def {action.name}({sig}) -> None:")

    # Pre-conditions as comments + assertion hooks
    if action.pre:
        for clause in action.pre.clauses:
            lines.append(f"        # pre: {clause}")
        lines.append(f"        self._check_pre_{action.name}({', '.join(_param_name(p) for p in action.params)})")

    # Post-conditions as comments
    if action.post:
        for clause in action.post.clauses:
            lines.append(f"        # post: {clause}")

    lines.append(f"        raise NotImplementedError  # TODO: implement {action.name}")

    # Pre-condition hook method
    if action.pre:
        lines.append(f"")
        param_names = [_param_name(p) for p in action.params]
        hook_params = ["self"] + [f"{_param_name(p)}: {_param_type(p)}" for p in action.params]
        lines.append(f"    def _check_pre_{action.name}({', '.join(hook_params)}) -> None:")
        for clause in action.pre.clauses:
            lines.append(f"        # Assert: {clause}")
        lines.append(f"        pass  # TODO: implement precondition check")

    return lines
