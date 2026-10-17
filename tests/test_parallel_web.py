import json
import unittest
from unittest.mock import patch

import httpx

from plain_agent.cli import main
from plain_agent.config import AppConfig
from plain_agent.tools.permissions.controller import PermissionController
from plain_agent.tools.permissions.request import ApprovalDecision
from plain_agent.tools.registry import ToolRegistry
from plain_agent.tools.web.providers.parallel import (
    PARALLEL_MCP_URL,
    USER_AGENT,
    ParallelWebClient,
)
from tests.test_agent import (
    FakeLLMClient,
    SimpleAgent,
    stream_response,
    stream_response_with_tool_calls,
    tool_call_delta,
)

HTTPX_CLIENT = httpx.Client


def mcp_result(text: str) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": text}]},
    }


class ParallelWebTest(unittest.TestCase):
    def setUp(self) -> None:
        self.requests: list[httpx.Request] = []
        self.approvals = []
        self.response = httpx.Response(
            200, json=mcp_result("Python: https://python.org\nRelease notes")
        )

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return self.response

        self.transport = httpx.MockTransport(handler)

        def client_factory(**kwargs):
            kwargs["transport"] = self.transport
            return HTTPX_CLIENT(**kwargs)

        self.client_patch = patch("httpx.Client", side_effect=client_factory)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

        def approve(request):
            self.approvals.append(request)
            return ApprovalDecision.ALLOW_ONCE

        self.permissions = PermissionController(approve)

    def registry(self, **kwargs) -> ToolRegistry:
        return ToolRegistry(
            enable_commands=False,
            permission_controller=self.permissions,
            web_provider="parallel",
            **kwargs,
        )

    def test_registry_dispatches_search_and_fetch_with_shared_anonymous_identity(self) -> None:
        config = AppConfig.from_env({"PLAIN_AGENT_WEB_PROVIDER": "parallel"})
        registry = ToolRegistry(
            enable_commands=False,
            permission_controller=self.permissions,
            web_provider=config.network.provider,
        )
        search = json.loads(registry.run("web_search", {"query": "  Python release  "}))
        fetch = json.loads(registry.run("web_fetch", {"url": "https://python.org"}))

        self.assertTrue(search["ok"])
        self.assertIn("https://python.org", search["content"])
        self.assertTrue(fetch["ok"])
        self.assertIn("Release notes", fetch["content"])
        payloads = [json.loads(request.content) for request in self.requests]
        self.assertEqual(payloads[0]["params"]["name"], "web_search")
        self.assertEqual(payloads[1]["params"]["name"], "web_fetch")
        search_args = payloads[0]["params"]["arguments"]
        fetch_args = payloads[1]["params"]["arguments"]
        self.assertEqual(search_args["objective"], "Python release")
        self.assertEqual(search_args["search_queries"], ["Python release"])
        self.assertEqual(fetch_args["urls"], ["https://python.org"])
        self.assertEqual(search_args["session_id"], fetch_args["session_id"])
        self.assertEqual(len(search_args["session_id"]), 32)
        for request in self.requests:
            self.assertEqual(str(request.url), PARALLEL_MCP_URL)
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.headers["User-Agent"], USER_AGENT)
            self.assertEqual(request.headers["Accept"], "application/json, text/event-stream")
            self.assertNotIn("authorization", request.headers)
            self.assertNotIn("x-api-key", request.headers)
            self.assertEqual(request.extensions["timeout"]["read"], 25.0)
        self.assertEqual([r.destination for r in self.approvals], ["search.parallel.ai"] * 2)
        self.assertEqual([r.target for r in self.approvals], ["Python release", "https://python.org"])

    def test_cli_passes_provider_to_agent(self) -> None:
        with (
            patch("plain_agent.cli.load_dotenv"),
            patch.dict("os.environ", {"PLAIN_AGENT_WEB_PROVIDER": "parallel"}, clear=True),
            patch("plain_agent.cli.OpenAICompatibleClient"),
            patch("plain_agent.cli.ConversationCompactor"),
            patch("plain_agent.cli.SimpleAgent") as agent,
            patch("plain_agent.cli.PlainAgentApp"),
        ):
            main()

        self.assertEqual(agent.call_args.kwargs["web_provider"], "parallel")
        self.assertTrue(agent.call_args.kwargs["enable_network"])

    def test_agent_loop_consumes_search_and_fetch_results(self) -> None:
        calls = [
            tool_call_delta(0, "search", "web_search", '{"query":"Python release"}', "function"),
            tool_call_delta(1, "fetch", "web_fetch", '{"url":"https://python.org"}', "function"),
        ]
        llm = FakeLLMClient([
            stream_response_with_tool_calls([calls]),
            stream_response(["Here are the release notes."]),
        ])
        agent = SimpleAgent(
            llm_client=llm,
            model="test-model",
            permission_controller=self.permissions,
            web_provider="parallel",
        )

        events = list(agent.respond_stream("Find Python release notes"))

        self.assertTrue(events[0].ok)
        self.assertTrue(events[1].ok)
        messages = llm.chat.completions.calls[1]["messages"]
        results = [m for m in messages if m["role"] == "tool"]
        self.assertEqual(len(results), 2)
        self.assertTrue(all("Release notes" in json.loads(m["content"])["content"] for m in results))
        self.assertEqual(len(self.requests), 2)

    def test_denied_and_disabled_tools_never_connect(self) -> None:
        self.permissions.set_approval_handler(lambda request: ApprovalDecision.REJECT)
        registry = self.registry()
        for name, args in (("web_search", {"query": "query"}), ("web_fetch", {"url": "https://example.com"})):
            self.assertFalse(json.loads(registry.run(name, args))["ok"])
        disabled = self.registry(enable_network=False)
        self.assertFalse(disabled.has("web_search"))
        self.assertFalse(disabled.has("web_fetch"))
        self.assertEqual(self.requests, [])

    def test_invalid_inputs_never_request_approval_or_connect(self) -> None:
        registry = self.registry()
        for name, args in (
            ("web_search", {"query": " "}),
            ("web_search", {"query": "x" * 2001}),
            ("web_fetch", {"url": "file:///etc/passwd"}),
            ("web_fetch", {"url": "https://user:secret@example.com"}),
        ):
            self.assertFalse(json.loads(registry.run(name, args))["ok"])
        self.assertEqual(self.approvals, [])
        self.assertEqual(self.requests, [])

    def test_exa_remains_default_and_invalid_provider_is_rejected(self) -> None:
        registry = ToolRegistry(enable_commands=False, permission_controller=self.permissions)
        registry.run("web_search", {"query": "query"})
        self.assertEqual(str(self.requests[0].url), "https://mcp.exa.ai/mcp")
        self.assertEqual(self.approvals[0].destination, "mcp.exa.ai")
        with self.assertRaisesRegex(ValueError, "web_provider"):
            ToolRegistry(enable_commands=False, web_provider="unknown")

    def test_json_and_multiline_sse_preserve_all_text_blocks_and_bound_output(self) -> None:
        payload = mcp_result("x" * 6000)
        payload["result"]["content"].append({"type": "text", "text": "tail"})
        formatted = json.dumps(payload, indent=2)
        self.response = httpx.Response(200, text="event: message\n" + "\n".join(
            "data: " + line for line in formatted.splitlines()
        ) + "\n\n")
        registry = self.registry()
        self.assertEqual(len(json.loads(registry.run("web_search", {"query": "q"}))["content"]), 5000)
        fetched = json.loads(registry.run("web_fetch", {"url": "https://python.org"}))
        self.assertTrue(fetched["content"].endswith("\ntail"))
        self.response = httpx.Response(200, json=mcp_result("x" * 13000))
        self.assertEqual(len(json.loads(registry.run("web_fetch", {"url": "https://python.org"}))["content"]), 12000)

    def test_failures_are_tool_errors_without_leaking_provider_details(self) -> None:
        responses = [
            httpx.Response(429, text="secret quota body"),
            httpx.Response(302, headers={"location": "https://elsewhere.example"}),
            httpx.Response(200, content=b"not-json secret"),
            httpx.Response(200, content=b"\xff"),
            httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "error": {"message": "secret"}}),
            httpx.Response(200, json={"id": 1, "result": {"isError": True, "content": [{"type": "text", "text": "secret"}]}}),
            httpx.Response(200, json={"id": 1, "result": {}}),
        ]
        registry = self.registry()
        for response in responses:
            with self.subTest(response=response):
                self.response = response
                for name, args in (("web_search", {"query": "q"}), ("web_fetch", {"url": "https://python.org"})):
                    result = json.loads(registry.run(name, args))
                    self.assertFalse(result["ok"])
                    self.assertNotIn("secret", result["error"])
        self.assertEqual(len(self.requests), 2 * len(responses))

    def test_timeout_connection_error_and_interruption(self) -> None:
        registry = self.registry()
        for exception, message in ((httpx.ReadTimeout("secret"), "timed out"), (httpx.ConnectError("secret"), "request failed")):
            def fail(request):
                raise exception

            self.transport.handler = fail
            for name, args in (("web_search", {"query": "q"}), ("web_fetch", {"url": "https://python.org"})):
                result = json.loads(registry.run(name, args))
                self.assertFalse(result["ok"])
                self.assertIn(message, result["error"])
                self.assertNotIn("secret", result["error"])

        def interrupt(request):
            raise KeyboardInterrupt()

        self.transport.handler = interrupt
        with self.assertRaises(KeyboardInterrupt):
            registry.run("web_search", {"query": "q"})

    def test_declared_and_streamed_response_size_limits(self) -> None:
        class Chunks(httpx.SyncByteStream):
            def __iter__(self):
                yield b"1234"
                yield b"5678"

        for response in (httpx.Response(200, content=b"12345678"), httpx.Response(200, stream=Chunks())):
            self.response = response
            client = ParallelWebClient(max_response_bytes=5)
            with self.assertRaisesRegex(RuntimeError, "size limit"):
                client.search("query")

    def test_client_limits_must_be_positive_and_finite(self) -> None:
        for value in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                ParallelWebClient(timeout_seconds=value)
        with self.assertRaises(ValueError):
            ParallelWebClient(max_response_bytes=0)


if __name__ == "__main__":
    unittest.main()
