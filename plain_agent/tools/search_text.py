"""Tool for searching workspace text."""

from pathlib import Path

from plain_agent.tools.base_tool import BaseTool
from plain_agent.tools.permissions.file_permission import (
    FilePermissionError,
    WorkspacePermission,
)
from plain_agent.tools.utils import error, ok


class SearchTextTool(BaseTool):
    """Search for exact text inside workspace files."""

    name = "search_text"
    description = "Search for exact text inside workspace files."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Exact text to search for.",
            },
            "path": {
                "type": "string",
                "description": "Workspace-relative file or directory path.",
                "default": ".",
            },
        },
        "required": ["query"],
    }

    def __init__(self, max_results: int = 20) -> None:
        if max_results < 1:
            raise ValueError("max_results must be positive")
        self.max_results = max_results

    def run(self, root: Path, arguments: dict[str, object]) -> str:
        query = arguments.get("query")
        if not isinstance(query, str) or not query:
            return error("query is required")

        path = arguments.get("path", ".")
        if not isinstance(path, str):
            return error("path must be a string")
        try:
            permissions = WorkspacePermission(root)
            workspace_path = permissions.require_access(path)
        except FilePermissionError as exc:
            return error(str(exc))

        results = []
        try:
            for file_path in permissions.get_files_under_path(workspace_path):
                try:
                    with file_path.open(encoding="utf-8") as file:
                        for line_number, line in enumerate(file, start=1):
                            if query in line:
                                results.append(
                                    {
                                        "path": permissions.relative_to_workspace(file_path),
                                        "line": line_number,
                                        "text": line.strip(),
                                    }
                                )
                                if len(results) >= self.max_results:
                                    return ok(
                                        {
                                            "query": query,
                                            "results": results,
                                            "truncated": True,
                                        }
                                    )
                except (UnicodeDecodeError, OSError):
                    continue
        except FilePermissionError as exc:
            return error(str(exc))

        return ok({"query": query, "results": results, "truncated": False})
