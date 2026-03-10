"""
🦞 LocalClaw R01 — Built-in Tools
A curated set of safe, practical tools for local agents.
Import whichever you need and add them to a ToolRegistry.

    from localclaw.tools.builtins import BUILTIN_REGISTRY
    agent = Agent(model="llama3.1:8b", tools=BUILTIN_REGISTRY)

For isolated state per agent (separate REPL sessions and note stores),
use make_builtin_registry() instead:

    from localclaw.tools.builtins import make_builtin_registry
    agent = Agent(model="llama3.1:8b", tools=make_builtin_registry())

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

from __future__ import annotations

import ast
import io
import math
import os
import re
import subprocess
import sys
import textwrap
import traceback
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path
from typing import Any

import urllib.request
import urllib.error
import urllib.parse

from ..core.tools import ToolRegistry, Tool, ToolParam


# ================================================================== #
#  Factory — produces a registry with fully isolated stateful tools    #
# ================================================================== #

def make_builtin_registry() -> ToolRegistry:
    """
    Create a fresh ToolRegistry containing all built-in tools.
    Stateful tools (python_repl, notes) get their own isolated state,
    so multiple agents will never share REPL globals or note stores.
    """
    registry = ToolRegistry()

    # ================================================================== #
    #  Calculator                                                          #
    # ================================================================== #

    @registry.tool(
        description="Evaluate a mathematical expression. Supports +, -, *, /, **, sqrt(), log(), sin(), cos(), and all Python math functions.",
        param_descriptions={"expression": "A Python math expression, e.g. '2 ** 10', 'sqrt(144)', 'math.log(100)'"},
    )
    def calculator(expression: str) -> str:
        """Safe math evaluator using Python's math module."""
        allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
        allowed_names.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum})
        try:
            tree = ast.parse(expression, mode="eval")
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
    #  Shell                                                               #
    # ================================================================== #

    @registry.tool(
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

    @registry.tool(
        description="Read a file from the local filesystem and return its contents.",
        param_descriptions={"path": "Absolute or relative file path"},
    )
    def read_file(path: str) -> str:
        """Read and return file contents as text."""
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[File read error] {e}"

    @registry.tool(
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
            with p.open(mode, encoding="utf-8") as fh:
                fh.write(content)
            return f"Written {len(content)} chars to {path}"
        except Exception as e:
            return f"[File write error] {e}"

    @registry.tool(
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

    @registry.tool(
        description="Fetch the text content of a URL via HTTP GET.",
        param_descriptions={
            "url": "The URL to fetch",
            "max_chars": "Maximum characters to return (default 3000)",
        },
    )
    def http_get(url: str, max_chars: int = 3000) -> str:
        """Retrieve the text content of a web page or API endpoint."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LocalClaw-R01/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            return text[:max_chars] + ("..." if len(text) > max_chars else "")
        except Exception as e:
            return f"[HTTP error] {e}"

    # ================================================================== #
    #  Web Search                                                          #
    # ================================================================== #

    @registry.tool(
        description="Search the web using DuckDuckGo and return top results. Use for finding current information, news, or answers to questions.",
        param_descriptions={
            "query": "Search query (what to search for)",
            "num_results": "Number of results to return (default 5, max 10)",
        },
    )
    def web_search(query: str, num_results: int = 5) -> str:
        """Search the web via DuckDuckGo HTML (no API key required)."""
        try:
            num_results = min(max(1, num_results), 10)  # Clamp to 1-10
            # DuckDuckGo HTML search endpoint
            search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(
                search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html",
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            
            # Parse results from HTML
            results = []
            # DuckDuckGo HTML results are in <a class="result__a"> tags
            pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html)
            
            for url, title in matches[:num_results]:
                # Clean up the URL (DuckDuckGo uses redirects)
                if url.startswith("//"):
                    url = "https:" + url
                # Extract actual URL from DuckDuckGo redirect if present
                if "uddg=" in url:
                    parsed = urllib.parse.urlparse(url)
                    params = urllib.parse.parse_qs(parsed.query)
                    if "uddg" in params:
                        url = params["uddg"][0]
                
                title = re.sub(r'<[^>]+>', '', title).strip()
                results.append(f"• {title}\n  {url}")
            
            if not results:
                return f"[No results found for: {query}]"
            
            return f"Search results for '{query}':\n\n" + "\n\n".join(results)
        except Exception as e:
            return f"[Search error] {e}"


    # ================================================================== #
    #  Python REPL  (stateful — isolated per registry instance)           #
    # ================================================================== #

    _repl_globals: dict = {}  # isolated per registry instance

    @registry.tool(
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

    @registry.tool(
        description="Reset the Python REPL session, clearing all variables.",
    )
    def python_repl_reset() -> str:
        """Clears the REPL global namespace."""
        _repl_globals.clear()
        return "REPL session reset."

    # ================================================================== #
    #  Memory / notes  (stateful — isolated per registry instance)        #
    # ================================================================== #

    _notes: dict[str, str] = {}  # isolated per registry instance

    @registry.tool(
        description="Save a note under a given key for later retrieval.",
        param_descriptions={"key": "Note identifier", "value": "Content to store"},
    )
    def save_note(key: str, value: str) -> str:
        """Persist a key-value note in the agent's scratchpad."""
        _notes[key] = value
        return f"Saved note '{key}'."

    @registry.tool(
        description="Retrieve a previously saved note by key.",
        param_descriptions={"key": "Note identifier to look up"},
    )
    def get_note(key: str) -> str:
        """Retrieve a note from the scratchpad."""
        if key in _notes:
            return _notes[key]
        available = list(_notes.keys())
        return f"[No note found for '{key}'. Available keys: {available}]"

    @registry.tool(description="List all saved note keys.")
    def list_notes() -> str:
        """Return all note keys currently stored."""
        if not _notes:
            return "[No notes saved yet]"
        return "\n".join(f"- {k}" for k in _notes)

    return registry


# ================================================================== #
#  Shared default registry                                             #
#  Fine for single-agent scripts; use make_builtin_registry() for     #
#  multi-agent scenarios to get isolated state per agent.             #
# ================================================================== #

BUILTIN_REGISTRY = make_builtin_registry()