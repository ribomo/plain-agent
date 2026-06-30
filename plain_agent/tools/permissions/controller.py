"""User approval flow for protected tool actions."""

from plain_agent.sandbox import CommandRequest


class ApprovalUI:
    """UI that displays a command request and waits for the user's choice."""

    def request_approval(self, request: CommandRequest) -> bool:
        """Return whether the user approved the request."""
        raise NotImplementedError


class ApprovalDeniedError(PermissionError):
    """Raised when a tool action is not approved."""


class PermissionController:
    """Require the configured UI to approve protected tool actions."""

    def __init__(self, approval_ui: ApprovalUI | None = None) -> None:
        self.set_approval_ui(approval_ui)

    def set_approval_ui(self, approval_ui: ApprovalUI | None) -> None:
        """Bind or unbind the UI that approves protected tool actions."""
        if approval_ui is not None and not isinstance(approval_ui, ApprovalUI):
            raise TypeError("approval_ui must be an ApprovalUI")
        self.approval_ui = approval_ui

    def require_approval(self, request: CommandRequest) -> None:
        """Require approval before the caller continues its side effect."""
        if self.approval_ui is None or not self.approval_ui.request_approval(request):
            raise ApprovalDeniedError("tool action was not approved")
