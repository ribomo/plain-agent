from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch

from plain_agent.conversation_history import ContextSize
from plain_agent.sandbox import CommandRequest, SandboxMode
from plain_agent.streaming import AutoCompaction, TextDelta, ToolResult
from plain_agent.terminal_loop import (
    approve_run_command,
    run_interactive_terminal,
)
from plain_agent.ui.terminal_renderer import format_token_count


class FakeAgent:
    def __init__(self, compact_result: bool = False, auto_compact: bool = False) -> None:
        self.prompts = []
        self.compact_result = compact_result
        self.compact_calls = 0
        self.auto_compact = auto_compact
        self.startup_warnings = []

    def respond_stream(self, user_input: str):
        self.prompts.append(user_input)
        if self.auto_compact:
            yield AutoCompaction(
                before=ContextSize(message_count=8, char_count=8_400, byte_count=8_400),
                after=ContextSize(message_count=4, char_count=4_200, byte_count=4_200),
            )
        yield TextDelta("Hello")
        yield TextDelta(" there")
        yield ToolResult(
            call_id="call_1",
            name="list_files",
            result='{"ok": true}',
            ok=True,
        )
        yield TextDelta("Done")

    def context_size(self) -> ContextSize:
        return ContextSize(message_count=4, char_count=8_400, byte_count=8_400)

    def compact_history(self) -> bool:
        self.compact_calls += 1
        return self.compact_result


class FakeMarkdownAgent(FakeAgent):
    def respond_stream(self, user_input: str):
        self.prompts.append(user_input)
        yield TextDelta("Use **bold** text")


class TerminalLoopTest(unittest.TestCase):
    def test_run_interactive_terminal_streams_text_and_tool_results(self) -> None:
        agent = FakeAgent()
        output = StringIO()

        with patch("builtins.input", side_effect=["", "Hi", "exit"]) as mock_input:
            with redirect_stdout(output):
                run_interactive_terminal(agent)

        self.assertEqual([call.args[0] for call in mock_input.call_args_list], ["> ", "> ", "> "])
        self.assertEqual(agent.prompts, ["Hi"])
        self.assertIn("Plain Agent Type 'exit' to quit.\n", output.getvalue())
        self.assertIn(
            "Hello there\n[tool list_files: ok]\nDone\n",
            output.getvalue(),
        )
        self.assertIn("[conversation history: 4 messages, ~2.1k tokens]\n\n", output.getvalue())

    def test_run_interactive_terminal_renders_live_markdown_text(self) -> None:
        agent = FakeMarkdownAgent()
        output = StringIO()

        with patch("builtins.input", side_effect=["Hi", "exit"]):
            with redirect_stdout(output):
                run_interactive_terminal(agent)

        self.assertIn("Use bold text\n", output.getvalue())
        self.assertNotIn("**bold**", output.getvalue())

    def test_run_interactive_terminal_compacts_on_command(self) -> None:
        agent = FakeAgent(compact_result=True)
        output = StringIO()

        with patch("builtins.input", side_effect=["/compact", "exit"]):
            with redirect_stdout(output):
                run_interactive_terminal(agent)

        self.assertEqual(agent.prompts, [])
        self.assertEqual(agent.compact_calls, 1)
        self.assertIn("[conversation: compacted]\n", output.getvalue())
        self.assertIn("[conversation history: 4 messages, ~2.1k tokens]\n\n", output.getvalue())

    def test_run_interactive_terminal_reports_auto_compaction_events(self) -> None:
        agent = FakeAgent(auto_compact=True)
        output = StringIO()

        with patch("builtins.input", side_effect=["Hi", "exit"]):
            with redirect_stdout(output):
                run_interactive_terminal(agent)

        self.assertIn("[conversation auto-compacted: ~2.1k -> ~1.1k tokens]\n", output.getvalue())
        self.assertIn("Hello there\n", output.getvalue())

    def test_run_interactive_terminal_reports_when_compact_has_nothing_to_do(self) -> None:
        agent = FakeAgent(compact_result=False)
        output = StringIO()

        with patch("builtins.input", side_effect=["/compact", "exit"]):
            with redirect_stdout(output):
                run_interactive_terminal(agent)

        self.assertEqual(agent.prompts, [])
        self.assertEqual(agent.compact_calls, 1)
        self.assertIn("[conversation compact: nothing to compact]\n\n", output.getvalue())

    def test_run_interactive_terminal_handles_eof(self) -> None:
        output = StringIO()

        with patch("builtins.input", side_effect=EOFError):
            with redirect_stdout(output):
                run_interactive_terminal(FakeAgent())

        self.assertTrue(output.getvalue().endswith("\n\n"))

    def test_run_interactive_terminal_shows_sandbox_warning(self) -> None:
        agent = FakeAgent()
        agent.startup_warnings = ["run_command is disabled: install Bubblewrap"]
        output = StringIO()

        with patch("builtins.input", side_effect=["exit"]):
            with redirect_stdout(output):
                run_interactive_terminal(agent)

        self.assertIn(
            "[warning: run_command is disabled: install Bubblewrap]",
            output.getvalue(),
        )

    def test_format_token_count_uses_k_suffix_for_large_counts(self) -> None:
        self.assertEqual(format_token_count(999), "999")
        self.assertEqual(format_token_count(2_100), "2.1k")

    def test_approve_run_command_accepts_yes(self) -> None:
        output = StringIO()

        with patch("builtins.input", side_effect=["maybe", "yes"]) as mock_input:
            with redirect_stdout(output):
                approved = approve_run_command(
                    CommandRequest(("pwd",), SandboxMode.READ_ONLY, Path.cwd())
                )

        self.assertTrue(approved)
        self.assertEqual(
            mock_input.call_args_list[0].args[0],
            "\nApprove [read-only] command `pwd`? [y/N] ",
        )
        self.assertEqual(output.getvalue(), "Please answer y or n.\n")

    def test_approve_run_command_rejects_default(self) -> None:
        with patch("builtins.input", return_value=""):
            approved = approve_run_command(
                CommandRequest(("pwd",), SandboxMode.WORKSPACE_WRITE, Path.cwd())
            )

        self.assertFalse(approved)

    def test_approve_run_command_escapes_terminal_controls(self) -> None:
        with patch("builtins.input", return_value="") as mock_input:
            approve_run_command(
                CommandRequest(("printf", "\x1b[2K\rspoof"), SandboxMode.READ_ONLY, Path.cwd())
            )

        prompt = mock_input.call_args.args[0]
        self.assertNotIn("\x1b", prompt)
        self.assertNotIn("\r", prompt)
        self.assertIn(r"\x1b[2K\rspoof", prompt)


if __name__ == "__main__":
    unittest.main()
