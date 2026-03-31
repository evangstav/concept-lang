"""
Validate an AppSpec against its concept definitions.

Checks:
1. All declared concepts have corresponding .concept files
2. Type parameter binding counts match concept definitions
3. Type parameter bindings reference concepts declared in the app
4. All sync dependencies are satisfied (sync triggers reference app concepts)
"""

from .models import AppSpec, ConceptAST


class ValidationError:
    def __init__(self, level: str, message: str):
        self.level = level  # "error" or "warning"
        self.message = message

    def to_dict(self) -> dict:
        return {"level": self.level, "message": self.message}


def validate_app(app: AppSpec, loaded_concepts: dict[str, ConceptAST]) -> list[ValidationError]:
    """Validate an app spec against loaded concept definitions.

    Args:
        app: The parsed app spec.
        loaded_concepts: Map of concept name -> ConceptAST for all .concept files on disk.

    Returns:
        List of validation errors/warnings. Empty list means valid.
    """
    errors: list[ValidationError] = []
    declared_names = {c.name for c in app.concepts}

    for binding in app.concepts:
        # Check concept file exists
        if binding.name not in loaded_concepts:
            errors.append(ValidationError(
                "error",
                f"Concept '{binding.name}' not found — no matching .concept file",
            ))
            continue

        concept = loaded_concepts[binding.name]

        # Check binding count matches param count
        expected = len(concept.params)
        actual = len(binding.bindings)
        if actual != expected:
            errors.append(ValidationError(
                "error",
                f"Concept '{binding.name}' expects {expected} type parameter(s) "
                f"({', '.join(concept.params)}), got {actual}: [{', '.join(binding.bindings)}]",
            ))
            continue

        # Check bindings reference declared concepts
        for param_name, bound_to in zip(concept.params, binding.bindings):
            if bound_to not in declared_names:
                errors.append(ValidationError(
                    "warning",
                    f"'{binding.name}[{bound_to}]': type param '{param_name}' bound to "
                    f"'{bound_to}' which is not declared in the app",
                ))

        # Check sync dependencies are satisfied
        for clause in concept.sync:
            if clause.trigger_concept not in declared_names:
                errors.append(ValidationError(
                    "warning",
                    f"'{binding.name}' syncs on '{clause.trigger_concept}.{clause.trigger_action}' "
                    f"but '{clause.trigger_concept}' is not declared in the app",
                ))

    return errors
