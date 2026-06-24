"""Interactive terminal loop for the plain agent."""

from collections.abc import Iterable
from typing import Protocol

from plain_agent.streaming import TextDelta, ToolResult


class StreamingAgent(Protocol):
    """Agent interface used by the terminal loop."""

    def respond_stream(self, user_input: str) -> Iterable[TextDelta | ToolResult]:
        """Return streamed text and tool-result events for one user prompt."""


def approve_run_command(command: str) -> bool:
    """Ask the user whether a requested shell command may run."""
    while True:
        answer = input(f"\nApprove command `{command}`? [y/N] ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"", "n", "no"}:
            return False
        print("Please answer y or n.")


def run_interactive_terminal(agent: StreamingAgent) -> None:
    """Read prompts, stream responses, show tool results, and repeat."""
    print("Simple agent client. Type 'exit' to quit.")

    while True:
        try:
            user_input = input("> ").strip()
        except EOFError:
            print()
            break

        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue

        for event in agent.respond_stream(user_input):
            if isinstance(event, TextDelta):
                print(event.content, end="", flush=True)
            elif isinstance(event, ToolResult):
                status = "ok" if event.ok else "error"
                print(f"\n[tool {event.name}: {status}]")
        print()
