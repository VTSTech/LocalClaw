#!/usr/bin/env python3
"""
🦞 LocalClaw — BitnetClient
Drop-in replacement for OllamaClient that uses Microsoft's bitnet.cpp
(llama-server) as the inference backend instead of Ollama.

Architecture:
  - Wraps bitnet.cpp's llama-server HTTP process
  - Exposes the same interface as OllamaClient: chat(), list_models(),
    model_supports_tools(), is_running()
  - Normalises OpenAI-format responses → Ollama-format so agent.py is
    completely unmodified
  - Manages llama-server lifecycle (start/stop/health-check)
  - Falls back gracefully to ReAct tool-calling (no native function
    calling in current bitnet models)

Supported models (as of bitnet.cpp 2025):
  - microsoft/BitNet-b1.58-2B-4T   (~0.4 GB, recommended)
  - 1bitLLM/bitnet_b1_58-3B        (~0.7 GB)
  - HF1BitLLM/Llama3-8B-1.58-100B-tokens
  - tiiuae/Falcon3-1B-Instruct-1.58bit
  - tiiuae/Falcon3-3B-Instruct-1.58bit
  - tiiuae/Falcon3-7B-Instruct-1.58bit

Quick start (Colab / Linux):
    # 1. Clone and build bitnet.cpp
    git clone --recursive https://github.com/microsoft/BitNet.git
    cd BitNet
    pip install -r requirements.txt
    python setup_env.py --hf-repo microsoft/BitNet-b1.58-2B-4T -q i2_s

    # 2. Copy this file into your LocalClaw directory
    cp bitnet_client.py localclaw/

    # 3. Run LocalClaw with --backend bitnet
    python cli.py chat --backend bitnet --bitnet-dir /path/to/BitNet --tools shell,read_file

Written by VTSTech community — https://github.com/VTSTech/LocalClaw
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Known BitNet models (HF repo → local dir name after setup_env.py)
# ─────────────────────────────────────────────────────────────────────────────

KNOWN_MODELS: dict[str, dict] = {
    "bitnet-b1.58-2b-4t": {
        "hf_repo":   "microsoft/BitNet-b1.58-2B-4T",
        "dir_name":  "BitNet-b1.58-2B-4T",
        "size":      "~0.4 GB",
        "quant":     "i2_s",
        "ctx":       4096,
        "recommend": True,
    },
    "bitnet-b1.58-3b": {
        "hf_repo":   "1bitLLM/bitnet_b1_58-3B",
        "dir_name":  "bitnet_b1_58-3B",
        "size":      "~0.7 GB",
        "quant":     "i2_s",
        "ctx":       4096,
        "recommend": False,
    },
    "llama3-8b-1.58": {
        "hf_repo":   "HF1BitLLM/Llama3-8B-1.58-100B-tokens",
        "dir_name":  "Llama3-8B-1.58-100B-tokens",
        "size":      "~2.0 GB",
        "quant":     "i2_s",
        "ctx":       8192,
        "recommend": False,
    },
    "falcon3-1b-1.58": {
        "hf_repo":   "tiiuae/Falcon3-1B-Instruct-1.58bit",
        "dir_name":  "Falcon3-1B-Instruct-1.58bit",
        "size":      "~0.2 GB",
        "quant":     "tl1",
        "ctx":       4096,
        "recommend": False,
    },
    "falcon3-3b-1.58": {
        "hf_repo":   "tiiuae/Falcon3-3B-Instruct-1.58bit",
        "dir_name":  "Falcon3-3B-Instruct-1.58bit",
        "size":      "~0.7 GB",
        "quant":     "tl1",
        "ctx":       4096,
        "recommend": False,
    },
    "falcon3-7b-1.58": {
        "hf_repo":   "tiiuae/Falcon3-7B-Instruct-1.58bit",
        "dir_name":  "Falcon3-7B-Instruct-1.58bit",
        "size":      "~1.8 GB",
        "quant":     "tl1",
        "ctx":       8192,
        "recommend": False,
    },
}

DEFAULT_MODEL   = "bitnet-b1.58-2b-4t"
DEFAULT_PORT    = 8765
DEFAULT_THREADS = max(1, os.cpu_count() or 4)


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class BitnetError(Exception):
    pass

class BitnetNotFoundError(BitnetError):
    """Raised when bitnet.cpp directory or binary cannot be located."""

class BitnetModelNotFoundError(BitnetError):
    """Raised when the requested model file cannot be found."""

class BitnetServerError(BitnetError):
    """Raised when llama-server fails to start or becomes unresponsive."""


# ─────────────────────────────────────────────────────────────────────────────
# BitnetClient
# ─────────────────────────────────────────────────────────────────────────────

class BitnetClient:
    """
    Drop-in replacement for OllamaClient that drives bitnet.cpp's llama-server.

    Exposes the same public interface used by LocalClaw's Agent and CLI:
        is_running()         → bool
        list_models()        → list[str]
        model_supports_tools(model) → bool
        chat(model, messages, options, stream) → dict

    Parameters
    ----------
    bitnet_dir : str | Path
        Root directory of the cloned & built BitNet repository.
        Must contain build/bin/llama-server (Linux/macOS) or
        build/bin/Release/llama-server.exe (Windows).
    model : str
        Short model name (key from KNOWN_MODELS) or an explicit path to a
        .gguf file.
    host : str
        llama-server bind address (default "127.0.0.1").
    port : int
        llama-server port (default 8765, avoids clash with ACP on 8766).
    threads : int
        CPU threads to pass to llama-server (-t).
    ctx_size : int | None
        Context window size (-c).  None = use model default.
    gpu_layers : int
        Layers to offload to GPU (-ngl).  0 = CPU-only.
    timeout : float
        HTTP request timeout in seconds.
    auto_start : bool
        If True (default), start llama-server automatically on first use.
    verbose : bool
        Print llama-server stdout/stderr.
    """

    def __init__(
        self,
        bitnet_dir: str | Path | None = None,
        model: str = DEFAULT_MODEL,
        host: str = "127.0.0.1",
        port: int = DEFAULT_PORT,
        threads: int = DEFAULT_THREADS,
        ctx_size: int | None = None,
        gpu_layers: int = 0,
        timeout: float = 120.0,
        auto_start: bool = True,
        verbose: bool = False,
    ):
        self.bitnet_dir  = Path(bitnet_dir).expanduser().resolve() if bitnet_dir else self._find_bitnet_dir()
        self.model_name  = model
        self.host        = host
        self.port        = port
        self.threads     = threads
        self.ctx_size    = ctx_size
        self.gpu_layers  = gpu_layers
        self.timeout     = timeout
        self.auto_start  = auto_start
        self.verbose     = verbose

        self.base_url    = f"http://{host}:{port}"
        self._process: subprocess.Popen | None = None
        self._gguf_path: Path | None = None
        self._started    = False

    # ── Setup helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _find_bitnet_dir() -> Path:
        """Try common locations for the BitNet repo."""
        candidates = [
            Path.cwd() / "BitNet",
            Path.cwd() / "bitnet",
            Path.home() / "BitNet",
            Path("/content/BitNet"),   # Colab
            Path("/opt/BitNet"),
        ]
        for c in candidates:
            if (c / "build").exists() or (c / "setup_env.py").exists():
                return c.resolve()
        raise BitnetNotFoundError(
            "Could not locate BitNet directory. Pass bitnet_dir= explicitly, "
            "or set BITNET_DIR environment variable.\n"
            "  git clone --recursive https://github.com/microsoft/BitNet.git\n"
            "  cd BitNet && pip install -r requirements.txt\n"
            "  python setup_env.py --hf-repo microsoft/BitNet-b1.58-2B-4T -q i2_s"
        )

    def _find_binary(self) -> Path:
        """Locate the llama-server binary inside the BitNet build."""
        candidates = [
            self.bitnet_dir / "build" / "bin" / "llama-server",
            self.bitnet_dir / "build" / "bin" / "Release" / "llama-server",
            self.bitnet_dir / "build" / "bin" / "llama-server.exe",
            self.bitnet_dir / "build" / "bin" / "Release" / "llama-server.exe",
            # Some builds put it directly in build/
            self.bitnet_dir / "build" / "llama-server",
        ]
        for c in candidates:
            if c.exists():
                return c
        raise BitnetNotFoundError(
            f"llama-server binary not found in {self.bitnet_dir}/build/.\n"
            "Have you run setup_env.py yet?\n"
            "  python setup_env.py --hf-repo microsoft/BitNet-b1.58-2B-4T -q i2_s"
        )

    def _find_gguf(self, model_name: str) -> Path:
        """Locate the .gguf model file for the given model name."""
        # Explicit path
        p = Path(model_name)
        if p.suffix == ".gguf" and p.exists():
            return p.resolve()

        # Short name lookup
        info = KNOWN_MODELS.get(model_name.lower())
        if info:
            models_dir = self.bitnet_dir / "models" / info["dir_name"]
            gguf_files = list(models_dir.glob("*.gguf")) if models_dir.exists() else []
            if gguf_files:
                # Prefer i2_s or tl1 quantized files
                for f in gguf_files:
                    if info["quant"] in f.name.lower():
                        return f
                return gguf_files[0]

        # Fuzzy search in models/
        models_root = self.bitnet_dir / "models"
        if models_root.exists():
            matches = list(models_root.rglob("*.gguf"))
            if matches:
                # Prefer partial name match
                for m in matches:
                    if model_name.lower().replace("-", "") in m.stem.lower().replace("-", ""):
                        return m
                return matches[0]

        raise BitnetModelNotFoundError(
            f"No .gguf file found for model '{model_name}'.\n"
            f"Run setup_env.py to download and prepare a model:\n"
            f"  python setup_env.py --hf-repo microsoft/BitNet-b1.58-2B-4T -q i2_s\n"
            f"Searched: {self.bitnet_dir / 'models'}"
        )

    # ── Server lifecycle ───────────────────────────────────────────────────

    def _build_server_cmd(self) -> list[str]:
        """Build the llama-server launch command."""
        binary = self._find_binary()
        gguf   = self._find_gguf(self.model_name)
        self._gguf_path = gguf

        info     = KNOWN_MODELS.get(self.model_name.lower(), {})
        ctx      = self.ctx_size or info.get("ctx", 4096)

        cmd = [
            str(binary),
            "--model",   str(gguf),
            "--host",    self.host,
            "--port",    str(self.port),
            "--threads", str(self.threads),
            "--ctx-size", str(ctx),
            "--n-gpu-layers", str(self.gpu_layers),
        ]
        return cmd

    def start(self) -> None:
        """Start llama-server as a background subprocess."""
        if self._process and self._process.poll() is None:
            return  # Already running

        cmd = self._build_server_cmd()

        stdout = None if self.verbose else subprocess.DEVNULL
        stderr = None if self.verbose else subprocess.DEVNULL

        self._process = subprocess.Popen(
            cmd,
            stdout=stdout,
            stderr=stderr,
        )

        # Wait for server to become ready (up to 60s — model loading takes time)
        deadline = time.time() + 60
        while time.time() < deadline:
            if self._health_check():
                self._started = True
                return
            if self._process.poll() is not None:
                raise BitnetServerError(
                    f"llama-server exited early (code {self._process.returncode}).\n"
                    f"Run with verbose=True to see server output."
                )
            time.sleep(0.5)

        self._process.terminate()
        raise BitnetServerError(
            f"llama-server did not become ready within 60s on {self.base_url}.\n"
            f"Try running manually: {' '.join(cmd)}"
        )

    def stop(self) -> None:
        """Terminate llama-server."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        self._started = False

    def _health_check(self) -> bool:
        """Return True if llama-server is responding on /health."""
        try:
            req = urllib.request.Request(
                f"{self.base_url}/health",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                body = json.loads(resp.read())
                return body.get("status") == "ok"
        except Exception:
            return False

    def _ensure_running(self) -> None:
        """Start server on demand if auto_start is set."""
        if self._started and self._process and self._process.poll() is None:
            return
        if self.auto_start:
            self.start()
        else:
            raise BitnetServerError(
                f"llama-server is not running on {self.base_url}. "
                "Call start() first or pass auto_start=True."
            )

    # ── OllamaClient-compatible public API ─────────────────────────────────

    def is_running(self) -> bool:
        """
        Return True if the backend is reachable.
        Matches OllamaClient.is_running() signature.
        """
        if self.auto_start:
            try:
                self._ensure_running()
                return True
            except Exception:
                return False
        return self._health_check()

    def list_models(self) -> list[str]:
        """
        Return list of available model short-names.
        Matches OllamaClient.list_models() signature.
        """
        # If we know which gguf is loaded, return that name
        if self._gguf_path:
            return [self.model_name]

        # Return all known models whose gguf files exist locally
        available = []
        for name, info in KNOWN_MODELS.items():
            models_dir = self.bitnet_dir / "models" / info["dir_name"]
            if models_dir.exists() and list(models_dir.glob("*.gguf")):
                available.append(name)

        return available if available else [self.model_name]

    def model_supports_tools(self, model: str) -> bool:
        """
        BitNet models do not support native function calling.
        LocalClaw will fall back to ReAct text-based tool use.
        Matches OllamaClient.model_supports_tools() signature.
        """
        return False

    def chat(
        self,
        model: str,
        messages: list[dict],
        options: dict | None = None,
        stream: bool = False,
    ) -> dict:
        """
        Send a chat request to llama-server and return an Ollama-format response.

        Normalises OpenAI /v1/chat/completions response →
        Ollama {"message": {"role": ..., "content": ...}} format
        so agent.py requires zero changes.

        Parameters
        ----------
        model    : ignored (llama-server serves one model at a time)
        messages : list of {"role": ..., "content": ...}
        options  : dict with optional keys: temperature, num_predict, num_ctx
        stream   : if True, returns a generator of content chunks

        Returns
        -------
        dict  matching Ollama response format:
          {"message": {"role": "assistant", "content": "..."}}
        """
        self._ensure_running()

        opts = options or {}
        payload: dict[str, Any] = {
            "model":    "bitnet",
            "messages": messages,
            "stream":   stream,
        }

        # Map Ollama option names → OpenAI names
        if "temperature" in opts:
            payload["temperature"] = opts["temperature"]
        if "num_predict" in opts:
            payload["max_tokens"] = opts["num_predict"]
        # num_ctx is a server-start-time option, not per-request in llama-server

        body = json.dumps(payload).encode()
        req  = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        if stream:
            return self._stream_chat(req)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body_str = e.read().decode() if e.fp else ""
            raise BitnetServerError(f"HTTP {e.code}: {body_str}") from e
        except urllib.error.URLError as e:
            raise BitnetServerError(f"Connection error: {e.reason}") from e

        return self._normalise_response(data)

    def _normalise_response(self, data: dict) -> dict:
        """
        Convert OpenAI /v1/chat/completions response to Ollama format.

        OpenAI:
            {"choices": [{"message": {"role": "assistant", "content": "..."}}]}
        Ollama:
            {"message": {"role": "assistant", "content": "..."}}
        """
        choices = data.get("choices", [])
        if not choices:
            return {"message": {"role": "assistant", "content": ""}}

        msg = choices[0].get("message", {})

        # Build Ollama-compatible response dict
        ollama_resp = {
            "message": {
                "role":    msg.get("role", "assistant"),
                "content": msg.get("content", "") or "",
            },
            # Passthrough usage stats if present
            "prompt_eval_count":  data.get("usage", {}).get("prompt_tokens", 0),
            "eval_count":         data.get("usage", {}).get("completion_tokens", 0),
            "model":              data.get("model", self.model_name),
            "done":               True,
        }

        # Tool calls: not supported by bitnet models, but normalise if present
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            ollama_resp["message"]["tool_calls"] = [
                {
                    "function": {
                        "name":      tc["function"]["name"],
                        "arguments": tc["function"].get("arguments", "{}"),
                    }
                }
                for tc in tool_calls
            ]

        return ollama_resp

    def _stream_chat(self, req: urllib.request.Request):
        """
        Generator that yields content chunks from SSE stream.
        Matches OllamaClient's streaming interface.
        """
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line or not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        return
                    try:
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except urllib.error.URLError as e:
            raise BitnetServerError(f"Stream error: {e.reason}") from e

    # ── Context manager support ────────────────────────────────────────────

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

    # ── Setup helper ───────────────────────────────────────────────────────

    @staticmethod
    def setup(
        bitnet_dir: str | Path,
        model: str = DEFAULT_MODEL,
        clone: bool = True,
    ) -> None:
        """
        One-shot setup helper: clone, build, and download the model.
        Equivalent to running setup_env.py manually.

        Parameters
        ----------
        bitnet_dir : path where BitNet will be cloned / already exists
        model      : short model name from KNOWN_MODELS (default: bitnet-b1.58-2b-4t)
        clone      : if True, git clone if directory doesn't exist
        """
        bitnet_dir = Path(bitnet_dir).expanduser().resolve()
        info = KNOWN_MODELS.get(model.lower())
        if not info:
            raise ValueError(f"Unknown model '{model}'. Known: {list(KNOWN_MODELS)}")

        # Clone if needed
        if not bitnet_dir.exists() and clone:
            print(f"Cloning BitNet into {bitnet_dir}...")
            subprocess.run(
                ["git", "clone", "--recursive",
                 "https://github.com/microsoft/BitNet.git",
                 str(bitnet_dir)],
                check=True,
            )

        # Install Python requirements
        req_file = bitnet_dir / "requirements.txt"
        if req_file.exists():
            print("Installing Python requirements...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q"],
                check=True,
                cwd=bitnet_dir,
            )

        # Run setup_env.py (builds + downloads + quantises model)
        print(f"Setting up {info['hf_repo']} ({info['size']})...")
        subprocess.run(
            [
                sys.executable, "setup_env.py",
                "--hf-repo", info["hf_repo"],
                "--quant-type", info["quant"],
            ],
            check=True,
            cwd=bitnet_dir,
        )
        print(f"Setup complete. Model ready at {bitnet_dir / 'models' / info['dir_name']}")


# ─────────────────────────────────────────────────────────────────────────────
# Standalone test / quick-start
# ─────────────────────────────────────────────────────────────────────────────

def _test(bitnet_dir: str, model: str = DEFAULT_MODEL):
    """Quick sanity-check: start server, send one message, print response."""
    print(f"Starting BitnetClient  model={model}  dir={bitnet_dir}")
    client = BitnetClient(bitnet_dir=bitnet_dir, model=model, verbose=True)

    print("Starting llama-server...")
    client.start()
    print(f"Server ready at {client.base_url}")

    messages = [{"role": "user", "content": "What is 2 + 2? Reply in one sentence."}]
    print("\nSending test message...")
    resp = client.chat(model, messages)
    print(f"Response: {resp['message']['content']}")

    client.stop()
    print("Done.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BitnetClient standalone test/setup")
    sub = parser.add_subparsers(dest="cmd")

    p_test = sub.add_parser("test", help="Start server and send a test message")
    p_test.add_argument("--dir",   default=None, help="BitNet repo directory")
    p_test.add_argument("--model", default=DEFAULT_MODEL, help="Model short name")

    p_setup = sub.add_parser("setup", help="Clone BitNet and download a model")
    p_setup.add_argument("--dir",   required=True, help="Where to clone BitNet")
    p_setup.add_argument("--model", default=DEFAULT_MODEL, help="Model to download")

    p_list = sub.add_parser("models", help="List supported models")

    args = parser.parse_args()

    if args.cmd == "test":
        _test(args.dir or os.environ.get("BITNET_DIR", "./BitNet"), args.model)

    elif args.cmd == "setup":
        BitnetClient.setup(args.dir, args.model)

    elif args.cmd == "models":
        print(f"\n{'Model':<25} {'Size':<10} {'Quant':<8} {'HF Repo'}")
        print("-" * 80)
        for name, info in KNOWN_MODELS.items():
            rec = " ★" if info["recommend"] else ""
            print(f"  {name + rec:<25} {info['size']:<10} {info['quant']:<8} {info['hf_repo']}")
        print()

    else:
        parser.print_help()