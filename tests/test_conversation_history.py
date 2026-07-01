import json
import unittest

from plain_agent.conversation_history import ConversationExchange, ConversationHistory, estimate_token_count


class ConversationHistoryTest(unittest.TestCase):
    def test_context_size_uses_exact_stable_json_serialization(self) -> None:
        history = ConversationHistory("System")
        history.append_user("Hello café")
        history.append_assistant("Hi")

        messages = history.to_messages()
        serialized = json.dumps(messages, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        size = history.context_size()

        self.assertEqual(size.message_count, len(messages))
        self.assertEqual(size.char_count, len(serialized))
        self.assertEqual(size.byte_count, len(serialized.encode("utf-8")))
        self.assertGreater(size.byte_count, size.char_count)

    def test_exchanges_group_user_led_message_sequences(self) -> None:
        history = ConversationHistory("System")
        history.append_user("First")
        history.append_assistant("First answer")
        history.append_user("Second")
        history.append_assistant("Second answer")

        exchanges = history.exchanges()

        self.assertEqual(len(exchanges), 2)
        self.assertEqual(
            [[message["role"] for message in exchange.messages] for exchange in exchanges],
            [["user", "assistant"], ["user", "assistant"]],
        )
        self.assertEqual(exchanges[0].messages[0]["content"], "First")
        self.assertEqual(exchanges[1].messages[0]["content"], "Second")

    def test_exchanges_keep_tool_call_messages_together(self) -> None:
        history = ConversationHistory("System")
        history.append_user("Read a file")
        history.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": '{"path":"main.py"}'},
                    }
                ],
            }
        )
        history.append_tool("call_1", '{"ok": true, "content": "print()"}')
        history.append_assistant("Done")

        exchanges = history.exchanges()

        self.assertEqual(len(exchanges), 1)
        self.assertEqual(
            [message["role"] for message in exchanges[0].messages],
            ["user", "assistant", "tool", "assistant"],
        )
        self.assertEqual(exchanges[0].messages[2]["tool_call_id"], "call_1")

    def test_conversation_exchange_keeps_grouped_messages(self) -> None:
        messages = [{"role": "user", "content": "Original"}]

        exchange = ConversationExchange(messages)

        self.assertIs(exchange.messages, messages)
        self.assertEqual(exchange.messages[0]["content"], "Original")

    def test_messages_are_copied_at_input_and_output_boundaries(self) -> None:
        history = ConversationHistory("System")
        message = {"role": "user", "content": "Original"}
        history.append(message)

        message["content"] = "Changed outside"
        indexed = history[1]
        indexed["content"] = "Changed through index"
        iterated = next(iter(history))
        iterated["content"] = "Changed through iterator"

        self.assertEqual(history.to_messages()[0]["content"], "System")
        self.assertEqual(history.to_messages()[1]["content"], "Original")

    def test_estimate_token_count_uses_character_heuristic_and_rounds_up(self) -> None:
        self.assertEqual(estimate_token_count(0), 0)
        self.assertEqual(estimate_token_count(1), 1)
        self.assertEqual(estimate_token_count(4), 1)
        self.assertEqual(estimate_token_count(5), 2)
        self.assertEqual(estimate_token_count(8_400), 2_100)

if __name__ == "__main__":
    unittest.main()
