"""
MCP tool registrations for concept-lang 0.2.0.

The code-generation tools (`codegen_tools`) are intentionally NOT
re-exported: per the paper-alignment spec §5.3 they stay on v1 until a
dedicated migration and are not exposed via the MCP server in P4. The
source file is preserved so a future phase can rewire it quickly.
"""

from .app_tools import register_app_tools
from .concept_tools import register_concept_tools
from .diagram_tools import register_diagram_tools
from .diff_tools import register_diff_tools
from .explorer_tools import register_explorer_tools
from .scaffold_tools import register_scaffold_tools
from .sync_tools import register_sync_tools
from .workspace_tools import register_workspace_tools

__all__ = [
    "register_app_tools",
    "register_concept_tools",
    "register_diagram_tools",
    "register_diff_tools",
    "register_explorer_tools",
    "register_scaffold_tools",
    "register_sync_tools",
    "register_workspace_tools",
]
