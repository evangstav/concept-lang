"""Base class for language-specific code generation backends."""

from abc import ABC, abstractmethod

from ..models import ConceptAST


class CodegenBackend(ABC):
    """Abstract base for concept-to-code generators.

    Each backend translates a ConceptAST into implementation stubs
    for a specific target language.
    """

    @property
    @abstractmethod
    def language(self) -> str:
        """Target language name (e.g. 'python', 'typescript', 'go')."""

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """File extension for generated files (e.g. '.py', '.ts', '.go')."""

    @abstractmethod
    def generate(self, ast: ConceptAST) -> str:
        """Generate implementation stub source code from a ConceptAST."""
