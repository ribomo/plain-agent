"""Typed chat messages and conversation history storage."""

from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass
import json
from typing import overload

from plain_agent.message_types import AssistantMessageDict, ChatMessage, ToolMessage, UserMessage


@dataclass(frozen=True)
class ContextSize:
    """Exact size of the serialized conversation history."""

    message_count: int
    char_count: int
    byte_count: int


class ConversationHistory:
    """Stores chat messages while exposing list-like read access."""
    _messages: list[ChatMessage]

    def __init__(self, system_prompt: str) -> None:
        self._messages = [
            {"role": "system", "content": system_prompt},
        ]

    def append(self, message: ChatMessage) -> None:
        self._messages.append(message)

    def append_user(self, content: str) -> None:
        message: UserMessage = {"role": "user", "content": content}
        self.append(message)

    def append_assistant(self, content: str) -> None:
        message: AssistantMessageDict = {"role": "assistant", "content": content}
        self.append(message)

    def append_tool(self, tool_call_id: str, content: str) -> None:
        message: ToolMessage = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }
        self.append(message)

    def replace(self, messages: list[ChatMessage]) -> None:
        self._messages = messages

    def to_messages(self) -> list[ChatMessage]:
        return deepcopy(self._messages)

    def context_size(self) -> ContextSize:
        serialized = json.dumps(
            self._messages,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return ContextSize(
            message_count=len(self._messages),
            char_count=len(serialized),
            byte_count=len(serialized.encode("utf-8")),
        )

    def __iter__(self) -> Iterator[ChatMessage]:
        return iter(self._messages)

    def __len__(self) -> int:
        return len(self._messages)

    @overload
    def __getitem__(self, index: int) -> ChatMessage:
        ...

    @overload
    def __getitem__(self, index: slice) -> list[ChatMessage]:
        ...

    def __getitem__(self, index: int | slice) -> ChatMessage | list[ChatMessage]:
        return self._messages[index]
