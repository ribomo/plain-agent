"""Tool for listing workspace files."""

from pathlib import Path

from simple_agent.tools.base_tool import BaseTool
from simple_agent.tools.permissions.file_permission import FilePermissionError, WorkspacePermission
from simple_agent.tools.utils import error, ok


class ListFilesTool(BaseTool):
    """List files and directories inside the workspace."""

    name = "list_files"
    description = "List files and directories inside the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Workspace-relative directory path.",
                "default": ".",
            }
        },
    }

    def run(self, root: Path, arguments: dict[str, object]) -> str:
        path = arguments.get("path", ".")
        try:
            permissions = WorkspacePermission(root)
            workspace_path = permissions.require_access(path)
        except FilePermissionError as exc:
            return error(str(exc))

        if not workspace_path.is_dir():
            return error(f"path is not a directory: {path}")

        entries = []
        for child in sorted(workspace_path.iterdir()):
            relative_path = child.relative_to(permissions.workspace)
            if permissions.is_sensitive_path(relative_path):
                continue
            suffix = "/" if child.is_dir() else ""
            entries.append(f"{relative_path}{suffix}")

        return ok({"path": permissions.relative_to_workspace(workspace_path), "entries": entries})
