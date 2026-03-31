"""MCP tools for language-agnostic code generation from concept specs."""

import json
import os

from mcp.server.fastmcp import FastMCP

from ..codegen import get_backend, list_backends
from ..parser import ParseError, parse_file


def register_codegen_tools(mcp: FastMCP, concepts_dir: str) -> None:

    @mcp.tool(
        description=(
            "Generate implementation stubs from a concept spec in a target language. "
            "Supported languages: python, typescript, go. "
            "Pass the concept name (without .concept extension) and target language. "
            "Returns the generated source code that can be used as a starting point "
            "for implementation — with state management, action method signatures, "
            "and pre/post condition hooks."
        )
    )
    def generate_code(name: str, language: str) -> str:
        available = list_backends()
        lang = language.lower()
        if lang not in available:
            return json.dumps({
                "error": f"Unsupported language: {language!r}. Available: {', '.join(available)}"
            })

        path = os.path.join(concepts_dir, f"{name}.concept")
        try:
            ast = parse_file(path)
        except FileNotFoundError:
            return json.dumps({"error": f"Concept '{name}' not found"})
        except ParseError as e:
            return json.dumps({"error": f"Parse error: {e}"})

        backend = get_backend(lang)
        code = backend.generate(ast)
        return json.dumps({
            "concept": ast.name,
            "language": backend.language,
            "file_extension": backend.file_extension,
            "code": code,
        })

    @mcp.tool(
        description="List available target languages for code generation from concept specs."
    )
    def list_codegen_languages() -> str:
        return json.dumps({"languages": list_backends()})
