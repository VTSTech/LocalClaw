"""
LocalClaw — Built-in Tools
A curated set of safe, practical tools for local agents.
Import whichever you need and add them to a ToolRegistry.

    from localclaw.tools.builtins import BUILTIN_REGISTRY
    agent = Agent(model="llama3.1:8b", tools=BUILTIN_REGISTRY)
"""

from __future__ import annotations

import ast
import io
import math
import os
import subprocess
import sys
import textwrap
import traceback
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from typing import Any

import urllib.request
import urllib.error

from ..core.tools import ToolRegistry, Tool, ToolParam


BUILTIN_REGISTRY = ToolRegistry()
tool = BUILTIN_REGISTRY.tool


# ================================================================== #
#  Calculator                                                           #
# ================================================================== #

@tool(
    description="Evaluate a mathematical expression. Supports standard math functions.",
    param_descriptions={"expression": "A Python-compatible math expression, e.g. '2 ** 10' or 'math.sqrt(144)'"},
)
def calculator(expression: str) -> str:
    """Safe math evaluator using Python's math module."""
    allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
    allowed_names.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum})
    try:
        tree = ast.parse(expression, mode="eval")
        # Safety: reject any node types that could cause harm
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.Call)):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id not in allowed_names:
                        return f"[Blocked] Function '{node.func.id}' is not allowed."
        result = eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, allowed_names)
        return str(result)
    except Exception as e:
        return f"[Calculator error] {e}"


# ================================================================== #
#  Python REPL                                                         #
# ================================================================== #

_repl_globals: dict = {}   # persistent across calls within a session


@tool(
    description="Execute Python code in a persistent session and return stdout + result.",
    param_descriptions={"code": "Valid Python code to execute"},
)
def python_repl(code: str) -> str:
    """Run arbitrary Python code (local execution — no sandboxing)."""
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(textwrap.dedent(code), _repl_globals)  # noqa: S102
        output = stdout_buf.getvalue()
        errors = stderr_buf.getvalue()
        return (output + errors).strip() or "[No output]"
    except Exception:
        return traceback.format_exc()


@tool(
    description="Reset the Python REPL session, clearing all variables.",
)
def python_repl_reset() -> str:
    """Clears the REPL global namespace."""
    _repl_globals.clear()
    return "REPL session reset."


# ================================================================== #
#  Shell                                                               #
# ================================================================== #

@tool(
    description="Run a shell command and return its output. Use with caution.",
    param_descriptions={
        "command": "Shell command to execute",
        "timeout": "Maximum seconds to wait (default 30)",
    },
)
def shell(command: str, timeout: int = 30) -> str:
    """Execute a shell command via subprocess."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        return output.strip() or f"[Exit code {result.returncode}]"
    except subprocess.TimeoutExpired:
        return f"[Timeout] Command exceeded {timeout}s"
    except Exception as e:
        return f"[Shell error] {e}"


# ================================================================== #
#  File I/O                                                            #
# ================================================================== #

@tool(
    description="Read a file from the local filesystem and return its contents.",
    param_descriptions={"path": "Absolute or relative file path"},
)
def read_file(path: str) -> str:
    """Read and return file contents as text."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[File read error] {e}"


@tool(
    description="Write text content to a file on the local filesystem.",
    param_descriptions={
        "path": "Absolute or relative file path",
        "content": "Text to write",
        "append": "If true, append instead of overwriting (default false)",
    },
)
def write_file(path: str, content: str, append: bool = False) -> str:
    """Write (or append) content to a file."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        p.open(mode, encoding="utf-8").write(content)
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        return f"[File write error] {e}"


@tool(
    description="List files and directories at the given path.",
    param_descriptions={"path": "Directory path to list (default: current directory)"},
)
def list_directory(path: str = ".") -> str:
    """List directory contents."""
    try:
        entries = sorted(Path(path).iterdir(), key=lambda p: (p.is_file(), p.name))
        lines = []
        for e in entries:
            indicator = "/" if e.is_dir() else ""
            size = f"  ({e.stat().st_size:,}B)" if e.is_file() else ""
            lines.append(f"{e.name}{indicator}{size}")
        return "\n".join(lines) or "[Empty directory]"
    except Exception as e:
        return f"[Directory error] {e}"


# ================================================================== #
#  HTTP fetch                                                          #
# ================================================================== #

@tool(
    description="Fetch the text content of a URL via HTTP GET.",
    param_descriptions={
        "url": "The URL to fetch",
        "max_chars": "Maximum characters to return (default 3000)",
    },
)
def http_get(url: str, max_chars: int = 3000) -> str:
    """Retrieve the text content of a web page or API endpoint."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LocalClaw/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        return text[:max_chars] + ("..." if len(text) > max_chars else "")
    except Exception as e:
        return f"[HTTP error] {e}"


# ================================================================== #
#  Memory / notes                                                      #
# ================================================================== #

_notes: dict[str, str] = {}


@tool(
    description="Save a note under a given key for later retrieval.",
    param_descriptions={"key": "Note identifier", "value": "Content to store"},
)
def save_note(key: str, value: str) -> str:
    """Persist a key-value note in the agent's scratchpad."""
    _notes[key] = value
    return f"Saved note '{key}'."


@tool(
    description="Retrieve a previously saved note by key.",
    param_descriptions={"key": "Note identifier to look up"},
)
def get_note(key: str) -> str:
    """Retrieve a note from the scratchpad."""
    if key in _notes:
        return _notes[key]
    available = list(_notes.keys())
    return f"[No note found for '{key}'. Available keys: {available}]"


@tool(description="List all saved note keys.")
def list_notes() -> str:
    """Return all note keys currently stored."""
    if not _notes:
        return "[No notes saved yet]"
    return "\n".join(f"- {k}" for k in _notes)
