"""
LocalClaw — Ollama Client
Zero-dependency wrapper around the local Ollama HTTP API.
Uses only Python stdlib (urllib + json) — no pip install required.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any, Iterator


DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaError(Exception):
    pass


class OllamaClient:
    """
    Synchronous interface to the local Ollama server.
    Zero external dependencies — uses only Python stdlib.

    Parameters
    ----------
    base_url : str
        URL of the Ollama server (default: http://localhost:11434)
    timeout : float
        Request timeout in seconds
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    #  Low-level helpers                                                   #
    # ------------------------------------------------------------------ #

    def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.base_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise OllamaError(f"HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise OllamaError(f"Connection error: {e.reason}") from e

    def _get(self, endpoint: str) -> dict:
        url = f"{self.base_url}{endpoint}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise OllamaError(f"HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise OllamaError(f"Connection error: {e.reason}") from e

    def _stream(self, endpoint: str, payload: dict) -> Iterator[dict]:
        """Yield JSON objects from a streaming Ollama response."""
        url = f"{self.base_url}{endpoint}"
        stream_payload = {**payload, "stream": True}
        data = json.dumps(stream_payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
        except urllib.error.URLError as e:
            raise OllamaError(f"Stream error: {e.reason}") from e

    # ------------------------------------------------------------------ #
    #  Chat API                                                            #
    # ------------------------------------------------------------------ #

    def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        options: dict | None = None,
    ) -> dict | Iterator[dict]:
        """
        Call /api/chat. Returns a dict (stream=False) or Iterator[dict] (stream=True).
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        if options:
            payload["options"] = options

        if stream:
            return self._stream("/api/chat", payload)
        return self._post("/api/chat", payload)

    # ------------------------------------------------------------------ #
    #  Utility                                                             #
    # ------------------------------------------------------------------ #

    def list_models(self) -> list[str]:
        """Return names of locally available models."""
        try:
            data = self._get("/api/tags")
            return [m["name"] for m in data.get("models", [])]
        except OllamaError:
            return []

    def is_running(self) -> bool:
        """Return True if the Ollama server is reachable."""
        try:
            self._get("/api/tags")
            return True
        except Exception:
            return False

    def model_supports_tools(self, model: str) -> bool:
        """
        Heuristic check for native tool-calling support.
        Models not in this list fall back to text-based ReAct parsing.
        """
        tool_families = (
            "llama3", "llama3.1", "llama3.2", "llama3.3",
            "mistral", "mixtral", "mistral-nemo",
            "qwen2", "qwen2.5", "qwen3", "qwen35",
            "command-r", "firefunction", "hermes",
            "llama3-groq-tool-use", "nemotron",
        )
        return any(f in model.lower() for f in tool_families)

    def __repr__(self):
        return f"OllamaClient(base_url={self.base_url!r})"