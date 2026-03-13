"""
🦞 LocalClaw ACP Plugin - Bridge to Agent Control Panel

This plugin connects LocalClaw agents to an ACP (Agent Control Panel) server,
enabling real-time monitoring, token tracking, and STOP/Resume control.

Usage:
    from localclaw import Agent
    from localclaw.tools.builtins import BUILTIN_REGISTRY
    from localclaw.acp_plugin import ACPPlugin

    # Create plugin
    acp = ACPPlugin(host="localhost", port=8766)

    # Attach to agent
    agent = Agent(
        model="qwen2.5-coder:0.5b",
        tools=BUILTIN_REGISTRY,
        on_step=acp.on_step,  # <-- Integration point
    )

    # Run - all activity logged to ACP
    result = agent.run("What is 2^20?")

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import base64
import json
import time
import urllib.request
import urllib.error
from typing import Any, Callable

# Import StepResult for type hints (optional - works without it)
try:
    from .core.agent import StepResult
except ImportError:
    # Allow standalone usage
    StepResult = Any


class ACPPlugin:
    """
    Plugin that bridges LocalClaw to ACP (Agent Control Panel).

    Features:
    - Logs all tool calls to ACP
    - Tracks tokens using ACP's estimation
    - Respects ACP STOP flag (raises StopIteration)
    - Syncs final answers as AI notes

    Parameters
    ----------
    host : str
        ACP server hostname (default: "localhost")
    port : int
        ACP server port (default: 8766)
    user : str
        ACP username (default: "admin")
    password : str
        ACP password (default: "changeme")
    base_url : str | None
        Full ACP URL (overrides host/port). Use for HTTPS tunnels.
        Example: "https://your-tunnel.trycloudflare.com"
    enabled : bool
        Whether plugin is active (default: True)
    on_stop : Callable[[str], None] | None
        Callback when STOP is detected (receives reason)
    debug : bool
        Print debug info (default: False)
    agent_name : str
        Name to use for activity attribution (default: "LocalClaw")
        v1.0.3: Helps identify which agent performed each action in multi-agent scenarios
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8766,
        user: str = "admin",
        password: str = "changeme",
        base_url: str | None = None,
        enabled: bool = True,
        on_stop: Callable[[str], None] | None = None,
        debug: bool = False,
        agent_name: str = "LocalClaw",
    ):
        self.base_url = base_url if base_url else f"http://{host}:{port}"
        self.auth = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.enabled = enabled
        self.on_stop = on_stop
        self.debug = debug
        self.agent_name = agent_name  # v1.0.3: Agent identity for attribution

        self._csrf_token: str | None = None
        self._csrf_expiry: float = 0
        self._current_activity_id: str | None = None
        self._activity_stack: list[str] = []  # Track nested activities
        self._step_count: int = 0
        self._last_stop_check: float = 0
        self._stop_flag: bool = False
        self._stop_reason: str | None = None

        # Tool name to ACP action type mapping
        self._action_map = {
            "read_file": "READ",
            "write_file": "WRITE",
            "shell": "BASH",
            "web_search": "SEARCH",
            "http_get": "API",
            "calculator": "SKILL",
            "python_repl": "SKILL",
            "python_repl_reset": "SKILL",
            "save_note": "TODO",
            "get_note": "READ",
            "list_notes": "READ",
            "list_directory": "READ",
        }

    # ------------------------------------------------------------------ #
    #  Internal HTTP Methods                                              #
    # ------------------------------------------------------------------ #

    def _log(self, message: str):
        """Debug logging."""
        if self.debug:
            print(f"  [ACP] {message}")

    def _request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict | None = None,
        timeout: float = 5.0,
    ) -> dict:
        """Make HTTP request to ACP server."""
        if not self.enabled:
            return {"success": False, "error": "Plugin disabled"}

        # Refresh CSRF token for POST requests
        if method == "POST":
            self._ensure_csrf_token()

        headers = {
            "Authorization": f"Basic {self.auth}",
            "Content-Type": "application/json",
        }
        if method == "POST" and self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token

        url = f"{self.base_url}{endpoint}"
        body = json.dumps(data).encode() if data else None

        req = urllib.request.Request(
            url,
            headers=headers,
            method=method,
            data=body,
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            return {"success": False, "error": f"HTTP {e.code}: {error_body}"}
        except urllib.error.URLError as e:
            return {"success": False, "error": f"Connection error: {e.reason}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _ensure_csrf_token(self):
        """Ensure we have a valid CSRF token."""
        now = time.time()
        # Refresh if no token or expired (> 50 minutes, tokens last 1 hour)
        if not self._csrf_token or (now - self._csrf_expiry) > 3000:
            resp = self._request("/api/csrf-token")
            self._csrf_token = resp.get("csrf_token", "")
            self._csrf_expiry = now
            self._log(f"CSRF token refreshed")

    def _check_stop_flag(self) -> bool:
        """Check if STOP flag is set on ACP server."""
        # Rate limit: only check every 2 seconds
        now = time.time()
        if (now - self._last_stop_check) < 2.0:
            return self._stop_flag

        self._last_stop_check = now
        status = self._request("/api/status")

        if status.get("stop_flag"):
            self._stop_flag = True
            self._stop_reason = status.get("stop_reason", "No reason given")
            self._log(f"STOP flag detected: {self._stop_reason}")
            return True

        return False

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def on_step(self, step: StepResult) -> None:
        """
        Callback for LocalClaw Agent - called on every step.

        This is the main integration point. Pass this method to the
        Agent constructor:

            agent = Agent(model="...", on_step=acp.on_step)

        Parameters
        ----------
        step : StepResult
            Step result from LocalClaw containing type, content, tool info.
        """
        if not self.enabled:
            return

        self._step_count += 1

        # Check STOP flag (raises to halt execution)
        if self._check_stop_flag():
            if self.on_stop:
                self.on_stop(self._stop_reason or "STOP requested")
            raise StopIteration(f"ACP STOP: {self._stop_reason}")

        step_type = getattr(step, "type", None)
        self._log(f"Step {self._step_count}: type={step_type}")

        # Handle different step types
        if step_type == "tool_call":
            self._handle_tool_call(step)
        elif step_type == "tool_result":
            self._handle_tool_result(step)
        elif step_type == "thought":
            self._handle_thought(step)
        elif step_type == "final":
            self._handle_final(step)

    def _handle_tool_call(self, step: StepResult) -> None:
        """Log a tool call to ACP."""
        tool_name = getattr(step, "tool_name", "unknown")
        tool_args = getattr(step, "tool_args", {}) or {}

        # Map tool name to ACP action type
        action = self._action_map.get(tool_name.lower(), tool_name.upper())

        # Create target string from args (truncate if too long)
        target = self._format_target(tool_name, tool_args)

        # Log to ACP
        resp = self._request("/api/start", "POST", {
            "action": action,
            "target": target,
            "details": f"LocalClaw tool: {tool_name}",
            "priority": "medium",
            "metadata": {
                "agent_name": self.agent_name,  # v1.0.3: Agent attribution
                "source": "localclaw",
                "tool": tool_name,
            }
        })

        activity_id = resp.get("activity_id")
        if activity_id:
            self._activity_stack.append(activity_id)
            self._current_activity_id = activity_id
            self._log(f"Started activity: {activity_id} ({action})")

    def _handle_tool_result(self, step: StepResult) -> None:
        """Complete the current activity in ACP."""
        content = getattr(step, "content", "")
        tool_name = getattr(step, "tool_name", "")

        # Pop from stack
        if self._activity_stack:
            activity_id = self._activity_stack.pop()
        else:
            activity_id = self._current_activity_id

        if not activity_id:
            self._log("No activity to complete")
            return

        # Check for error indicators
        error = None
        content_lower = content.lower() if content else ""
        if any(x in content_lower for x in ["[error]", "[failed]", "exception:", "error:"]):
            error = content[:200]  # Truncate error

        # Complete in ACP
        resp = self._request("/api/complete", "POST", {
            "activity_id": activity_id,
            "result": content[:500] if content else None,
            "error": error,
            "content_size": len(content) if content else 0,
        })

        self._log(f"Completed activity: {activity_id}")

        # Update current
        if self._activity_stack:
            self._current_activity_id = self._activity_stack[-1]
        else:
            self._current_activity_id = None

    def _handle_thought(self, step: StepResult) -> None:
        """Log agent thought process (optional, minimal tracking)."""
        content = getattr(step, "content", "")
        self._log(f"Thought: {content[:100]}...")

        # Could log as a note if desired, but may be noisy
        # self._request("/api/notes/add", "POST", {
        #     "category": "context",
        #     "content": f"Thought: {content[:200]}",
        #     "importance": "low"
        # })

    def _handle_final(self, step: StepResult) -> None:
        """Log final answer as an AI note."""
        content = getattr(step, "content", "")

        self._log(f"Final answer: {content[:100]}...")

        # Log final answer as note
        self._request("/api/notes/add", "POST", {
            "category": "context",
            "content": f"LocalClaw final: {content[:400]}",
            "importance": "normal",
        })

        # Complete any orphaned activities
        while self._activity_stack:
            orphan_id = self._activity_stack.pop()
            self._request("/api/complete", "POST", {
                "activity_id": orphan_id,
                "result": "[Completed by final handler]",
            })

    def _format_target(self, tool_name: str, args: dict) -> str:
        """Format tool arguments as a target string for ACP."""
        # Tool-specific formatting
        if tool_name == "read_file":
            return args.get("path", "unknown")
        elif tool_name == "write_file":
            return args.get("path", "unknown")
        elif tool_name == "shell":
            return args.get("command", "")[:100]
        elif tool_name == "calculator":
            return args.get("expression", "")[:100]
        elif tool_name == "web_search":
            return args.get("query", "")[:100]
        elif tool_name == "http_get":
            return args.get("url", "")[:100]
        elif tool_name == "python_repl":
            code = args.get("code", "")
            # First line only
            first_line = code.split("\n")[0] if code else ""
            return first_line[:100]
        elif tool_name == "save_note":
            return args.get("key", "unknown")
        elif tool_name == "get_note":
            return args.get("key", "unknown")
        else:
            # Generic: show first arg value
            if args:
                first_val = list(args.values())[0]
                return str(first_val)[:100]
            return tool_name

    # ------------------------------------------------------------------ #
    #  Utility Methods                                                    #
    # ------------------------------------------------------------------ #

    def get_status(self) -> dict:
        """Get current ACP status."""
        return self._request("/api/status")

    def get_session_tokens(self) -> int:
        """Get current session token count from ACP."""
        status = self.get_status()
        return status.get("session_tokens", 0)

    def add_note(self, category: str, content: str, importance: str = "normal") -> dict:
        """Add a note to ACP."""
        return self._request("/api/notes/add", "POST", {
            "category": category,
            "content": content,
            "importance": importance,
        })

    def sync_todos(self, todos: list[dict]) -> dict:
        """Sync TODO list to ACP.
        
        v1.0.3: Each TODO can include metadata with agent_name, tool, skill.
        """
        # Ensure each todo has metadata with agent attribution
        for todo in todos:
            if "metadata" not in todo:
                todo["metadata"] = {}
            if "agent_name" not in todo["metadata"]:
                todo["metadata"]["agent_name"] = self.agent_name
        return self._request("/api/todos/update", "POST", {"todos": todos})

    def reset(self):
        """Reset plugin state (for new session)."""
        self._activity_stack.clear()
        self._current_activity_id = None
        self._step_count = 0
        self._stop_flag = False
        self._stop_reason = None


# ------------------------------------------------------------------ #
#  Convenience Factory                                                 #
# ------------------------------------------------------------------ #

def create_acp_agent(
    model: str,
    tools: Any = None,
    acp_host: str = "localhost",
    acp_port: int = 8766,
    **agent_kwargs,
) -> tuple["Agent", ACPPlugin]:
    """
    Create a LocalClaw Agent pre-configured with ACP plugin.

    Returns both the agent and plugin for additional control.

    Usage:
        from localclaw.acp_plugin import create_acp_agent
        from localclaw.tools.builtins import BUILTIN_REGISTRY

        agent, acp = create_acp_agent(
            model="qwen2.5-coder:0.5b",
            tools=BUILTIN_REGISTRY,
        )

        result = agent.run("Calculate 2^20")
        print(f"Tokens used: {acp.get_session_tokens()}")
    """
    # Import here to avoid circular imports
    from . import Agent

    plugin = ACPPlugin(host=acp_host, port=acp_port)
    agent = Agent(
        model=model,
        tools=tools,
        on_step=plugin.on_step,
        **agent_kwargs,
    )
    return agent, plugin
