"""Tool for reading workspace files."""

from pathlib import Path

from plain_agent.tools.base_tool import BaseTool
from plain_agent.tools.permissions.file_permission import (
    FilePermissionError,
    WorkspacePermission,
)
from plain_agent.tools.utils import error, ok


class ReadFileTool(BaseTool):
    """Read a UTF-8 text file inside the workspace."""

    name = "read_file"
    description = "Read a UTF-8 text file inside the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Workspace-relative file path.",
            }
        },
        "required": ["path"],
    }

    def __init__(self, max_chars: int = 12_000) -> None:
        if max_chars < 1:
            raise ValueError("max_chars must be positive")
        self.max_chars = max_chars

    def run(self, root: Path, arguments: dict[str, object]) -> str:
        path = arguments.get("path")
        if not isinstance(path, str):
            return error("path is required")

        try:
            permissions = WorkspacePermission(root)
            workspace_path = permissions.require_access(path)
        except FilePermissionError as exc:
            return error(str(exc))

        if not workspace_path.is_file():
            return error(f"path is not a file: {path}")

        try:
            with workspace_path.open(encoding="utf-8") as file:
                text = file.read(self.max_chars + 1)
        except UnicodeDecodeError:
            return error(f"file is not valid UTF-8 text: {path}")
        except OSError as exc:
            return error(f"could not read file: {exc}")

        truncated = len(text) > self.max_chars
        if truncated:
            text = text[: self.max_chars]

        return ok(
            {
                "path": permissions.relative_to_workspace(workspace_path),
                "content": text,
                "truncated": truncated,
            }
        )
