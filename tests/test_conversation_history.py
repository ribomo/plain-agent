import json
import unittest

from plain_agent.conversation_history import ConversationHistory


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


if __name__ == "__main__":
    unittest.main()
