"""Bounded anonymous HTTP MCP client for Parallel's web tools."""

import json
import math
from uuid import uuid4

import httpx

PARALLEL_MCP_URL = "https://search.parallel.ai/mcp"
PARALLEL_DESTINATION = "search.parallel.ai"
USER_AGENT = "plain-agent (https://github.com/ribomo/plain-agent)"
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_SEARCH_CONTENT_CHARS = 5_000
MAX_FETCH_CONTENT_CHARS = 12_000


class ParallelWebError(RuntimeError):
    """Raised when Parallel cannot provide a valid, bounded response."""


class ParallelWebClient:
    """Search and fetch through a fixed endpoint with one conversation identity."""

    destination = PARALLEL_DESTINATION

    def __init__(
        self,
        timeout_seconds: float = 25.0,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        if max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")
        self.timeout = httpx.Timeout(timeout_seconds, connect=5.0)
        self.max_response_bytes = max_response_bytes
        self.transport = transport
        self.session_id = uuid4().hex

    def search(self, query: str) -> str:
        return self._call_tool(
            "web_search",
            {"objective": query, "search_queries": [query]},
            MAX_SEARCH_CONTENT_CHARS,
        )

    def fetch(self, url: str) -> str:
        return self._call_tool(
            "web_fetch",
            {"urls": [url]},
            MAX_FETCH_CONTENT_CHARS,
        )

    def _call_tool(
        self,
        tool: str,
        arguments: dict[str, object],
        max_content_chars: int,
    ) -> str:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool,
                "arguments": {**arguments, "session_id": self.session_id},
            },
        }
        try:
            with httpx.Client(
                timeout=self.timeout,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                with client.stream(
                    "POST",
                    PARALLEL_MCP_URL,
                    headers={
                        "Accept": "application/json, text/event-stream",
                        "User-Agent": USER_AGENT,
                    },
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    body = self._read_response(response)
        except httpx.TimeoutException as exc:
            raise ParallelWebError(f"Parallel {tool} timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise ParallelWebError(
                f"Parallel {tool} failed with HTTP status {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ParallelWebError(f"Parallel {tool} request failed") from exc

        return self._parse_response(body, max_content_chars)

    def _read_response(self, response: httpx.Response) -> bytes:
        try:
            declared_length = int(response.headers.get("content-length", "0"))
        except ValueError:
            declared_length = 0
        if declared_length > self.max_response_bytes:
            raise ParallelWebError("Parallel response exceeded the size limit")
        body = bytearray()
        for chunk in response.iter_bytes():
            if len(body) + len(chunk) > self.max_response_bytes:
                raise ParallelWebError("Parallel response exceeded the size limit")
            body.extend(chunk)
        return bytes(body)

    def _parse_response(self, body: bytes, max_content_chars: int) -> str:
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ParallelWebError("Parallel returned invalid JSON") from exc

        # HTTP MCP can return JSON or SSE, including multiline data fields.
        candidates = [text.strip()]
        data: list[str] = []
        for line in [*text.splitlines(), ""]:
            if line.startswith("data:"):
                data.append(line[5:].removeprefix(" "))
            elif not line and data:
                candidates.append("\n".join(data))
                data = []
        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict) or payload.get("id") != 1:
                continue
            if "error" in payload:
                raise ParallelWebError("Parallel returned an MCP error")
            result = payload.get("result")
            if not isinstance(result, dict):
                continue
            if result.get("isError"):
                raise ParallelWebError("Parallel could not complete the web request")
            content = result.get("content")
            if not isinstance(content, list):
                continue
            parts = [
                item["text"]
                for item in content
                if isinstance(item, dict)
                and item.get("type") == "text"
                and isinstance(item.get("text"), str)
            ]
            if parts:
                return "\n".join(parts)[:max_content_chars]
        raise ParallelWebError("Parallel returned an invalid response")
