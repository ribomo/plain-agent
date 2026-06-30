import unittest
from pathlib import Path

from plain_agent.sandbox import CommandRequest, SandboxMode
from plain_agent.tools.permissions.controller import (
    ApprovalUI,
    PermissionController,
    ApprovalDeniedError,
)


class RecordingApprovalUI(ApprovalUI):
    def __init__(self, approved: bool) -> None:
        self.approved = approved
        self.requests: list[CommandRequest] = []

    def request_approval(self, request: CommandRequest) -> bool:
        self.requests.append(request)
        return self.approved


class DuckTypedApprovalUI:
    def request_approval(self, request: CommandRequest) -> bool:
        return True


class PermissionControllerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.request = CommandRequest(
            argv=("pwd",),
            mode=SandboxMode.READ_ONLY,
            workspace=Path.cwd(),
        )

    def test_denies_when_no_approval_ui_is_configured(self) -> None:
        with self.assertRaises(ApprovalDeniedError):
            PermissionController().require_approval(self.request)

    def test_requires_explicit_approval_ui_class(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be an ApprovalUI"):
            PermissionController(DuckTypedApprovalUI())

    def test_uses_configured_approval_ui(self) -> None:
        approval_ui = RecordingApprovalUI(approved=True)
        controller = PermissionController(approval_ui)

        controller.require_approval(self.request)

        self.assertEqual(approval_ui.requests, [self.request])

    def test_raises_when_approval_ui_denies_request(self) -> None:
        controller = PermissionController(RecordingApprovalUI(approved=False))

        with self.assertRaises(ApprovalDeniedError):
            controller.require_approval(self.request)


if __name__ == "__main__":
    unittest.main()
