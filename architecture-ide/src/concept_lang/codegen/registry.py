"""Backend registry for pluggable code generation targets."""

from .base import CodegenBackend
from .python import PythonBackend
from .typescript import TypeScriptBackend
from .go import GoBackend

_BACKENDS: dict[str, type[CodegenBackend]] = {
    "python": PythonBackend,
    "typescript": TypeScriptBackend,
    "go": GoBackend,
}


def get_backend(language: str) -> CodegenBackend:
    """Get a codegen backend by language name.

    Raises KeyError if the language is not registered.
    """
    cls = _BACKENDS.get(language.lower())
    if cls is None:
        raise KeyError(
            f"Unknown language: {language!r}. "
            f"Available: {', '.join(sorted(_BACKENDS))}"
        )
    return cls()


def list_backends() -> list[str]:
    """Return sorted list of available backend language names."""
    return sorted(_BACKENDS)
