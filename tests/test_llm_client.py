import sys
import types
import unittest


class FakeOpenAI:
    last_kwargs = None

    def __init__(self, **kwargs):
        FakeOpenAI.last_kwargs = kwargs
        self.chat = object()


fake_openai_module = types.ModuleType("openai")
fake_openai_module.OpenAI = FakeOpenAI
sys.modules["openai"] = fake_openai_module

from plain_agent.llm_client import (
    OPENAI_BASE_URL,
    LLMClientError,
    OpenAICompatibleClient,
)


class LLMClientTest(unittest.TestCase):
    def test_client_creates_sdk_client_with_openai_defaults(self) -> None:
        client = OpenAICompatibleClient(api_key="test-key", timeout=12)

        self.assertEqual(client.base_url, OPENAI_BASE_URL)
        self.assertEqual(client.api_key, "test-key")
        self.assertEqual(client.timeout, 12)
        self.assertIsInstance(client.client, FakeOpenAI)
        self.assertEqual(
            FakeOpenAI.last_kwargs,
            {
                "base_url": OPENAI_BASE_URL,
                "timeout": 12,
                "api_key": "test-key",
            },
        )

    def test_client_accepts_custom_base_url(self) -> None:
        client = OpenAICompatibleClient(
            base_url="https://example.test/v1",
            api_key="test-key",
            timeout=12,
        )

        self.assertEqual(client.base_url, "https://example.test/v1")
        self.assertEqual(
            FakeOpenAI.last_kwargs,
            {
                "base_url": "https://example.test/v1",
                "timeout": 12,
                "api_key": "test-key",
            },
        )

    def test_client_requires_api_key(self) -> None:
        with self.assertRaisesRegex(LLMClientError, "api_key is required"):
            OpenAICompatibleClient(api_key=None)

    def test_client_delegates_chat_to_sdk_client(self) -> None:
        client = OpenAICompatibleClient(api_key="test-key")

        self.assertIs(client.chat, client.client.chat)

if __name__ == "__main__":
    unittest.main()
