"""
LocalClaw — Ollama Client
Zero-dependency wrapper around the local Ollama HTTP API.
Uses only Python stdlib (urllib + json) — no pip install required.

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any, Iterator


# ═══════════════════════════════════════════════════════════════════════════════
# OLLAMA HOST CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
# Uncomment ONE of the following lines to switch between local and remote Ollama:
#
# LOCAL OLLAMA (default):
# DEFAULT_BASE_URL = "http://localhost:11434"
#
# REMOTE OLLAMA (cloudflare tunnel):
#DEFAULT_BASE_URL = "https://your-tunnel.trycloudflare.com"
#
# ═══════════════════════════════════════════════════════════════════════════════

# Default timeout: 30 minutes (1800 seconds) for remote connections
DEFAULT_TIMEOUT = 1800.0


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

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = DEFAULT_TIMEOUT):
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
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
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
        
        Based on Ollama's native tool-calling support:
        https://github.com/ollama/ollama/blob/main/docs/api.md#generate-chat-completion
        
        Model families confirmed to support tools:
        - Llama 3.x (Meta)
        - Mistral/Mixtral (Mistral AI)
        - Qwen 2/2.5/3 (Alibaba)
        - Command-R (Cohere)
        - DeepSeek V2/V3 (DeepSeek)
        - Phi-3 (Microsoft)
        - And others listed below
        
        Note: Some models may have native support but behave poorly:
        - functiongemma: Designed for tools but often returns empty/refuses
        - granite: Has support but may refuse due to safety filters
        - gemma3: Limited tool support, ReAct fallback often works better
        """
        tool_families = (
            # Meta Llama family
            "llama", "llama3", "llama3.1", "llama3.2", "llama3.3",
            "llama3-groq-tool-use",
            
            # Mistral AI family
            "mistral", "mixtral", "mistral-nemo", "mistral-small", "mistral-large",
            "codestral", "ministral",
            
            # Alibaba Qwen family
            "qwen2", "qwen2.5", "qwen3", "qwen35",
            "qwen2.5-coder", "qwen2-math",
            
            # Cohere family
            "command-r", "command-r7b",
            
            # DeepSeek family (strong tool support)
            "deepseek", "deepseek-coder", "deepseek-v2", "deepseek-v3",
            
            # Microsoft Phi family
            "phi-3", "phi3", "phi-4",
            
            # Google Gemma family (limited support)
            "functiongemma",  # Specifically designed for function calling
            "gemma3",  # Uncomment if you want to enable for gemma3
            
            # IBM Granite family (may refuse due to safety filters)
            "granite", "granitemoe",  # Uncomment if needed
            
            # 01.ai Yi family
            "yi-", "yi1.5", "yi34b",
            
            # InternLM family
            "internlm2", "internlm2.5",
            
            # Upstage Solar
            "solar",
            
            # ChatGLM / GLM-4
            "glm4", "chatglm",
            
            # Other tool-capable models
            "firefunction", "hermes", "nemotron",
            "cogito", "athene",
        )
        return any(f in model.lower() for f in tool_families)

    def __repr__(self):
        return f"OllamaClient(base_url={self.base_url!r})"