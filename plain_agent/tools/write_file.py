"""Tool for creating or overwriting workspace files."""

from pathlib import Path

from plain_agent.tools.base_tool import BaseTool
from plain_agent.tools.permissions.file_permission import FilePermissionError, WorkspacePermission
from plain_agent.tools.utils import error, ok


class WriteFileTool(BaseTool):
    """Create or overwrite a file inside the workspace."""

    name = "write_file"
    description = "Create or overwrite a file inside the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Workspace-relative file path.",
            },
            "content": {
                "type": "string",
                "description": "Full file content.",
            },
        },
        "required": ["path", "content"],
    }

    def run(self, root: Path, arguments: dict[str, object]) -> str:
        path = arguments.get("path")
        content = arguments.get("content")
        if not isinstance(path, str):
            return error("path is required")
        if not isinstance(content, str) or not content:
            return error("content is required")

        try:
            permissions = WorkspacePermission(root)
            workspace_path = permissions.require_access(path, must_exist=False)
        except FilePermissionError as exc:
            return error(str(exc))

        if workspace_path.is_dir():
            return error(f"path is not a file: {path}")

        try:
            workspace_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            return error(f"could not write file: {exc}")

        return ok({
            "path": permissions.relative_to_workspace(workspace_path),
            "written": len(content),
        })
