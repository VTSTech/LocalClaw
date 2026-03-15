"""
🦞 LocalClaw ACP Plugin - Bridge to Agent Control Panel

This plugin connects LocalClaw agents to an ACP (Agent Control Panel) server,
enabling real-time monitoring, token tracking, and STOP/Resume control.

ACP Specification: v1.0.3
Compliance: Full (mandatory requirements, hints, orphan handling, nudge support, batch ops, shutdown)

Features:
- Logs all tool calls to ACP (using combined /api/action endpoint)
- Logs shell commands to /api/shell/add (MANDATORY per spec §5.0)
- Tracks tokens using ACP's estimation
- Respects ACP STOP flag (raises StopIteration)
- Processes hints field for context-aware decisions
- Handles orphan_warning by completing orphaned activities
- Processes nudge field for mid-task guidance
- Syncs final answers as AI notes
- Batch operations for efficient multi-file reads (v1.0.3)
- Graceful shutdown support (v1.0.2)

Usage:
    from localclaw import Agent
    from localclaw.tools.builtins import BUILTIN_REGISTRY
    from localclaw.acp_plugin import ACPPlugin

    # Create plugin (uses config.py defaults)
    acp = ACPPlugin()

    # Or with custom URL and callbacks:
    acp = ACPPlugin(
        base_url="http://localhost:8766",
        on_hint=lambda h: print(f"Hint: {h}"),
        on_nudge=lambda n: print(f"Nudge: {n['message']}"),
    )

    # Attach to agent
    agent = Agent(
        model="qwen2.5-coder:0.5b",
        tools=BUILTIN_REGISTRY,
        on_step=acp.on_step,  # <-- Integration point
    )

    # Run - all activity logged to ACP
    result = agent.run("What is 2^20?")

    # Batch operations (efficient for multiple files):
    result = acp.batch_start([
        {"action": "READ", "target": "/file1.py", "content_size": 5000},
        {"action": "READ", "target": "/file2.py", "content_size": 3000},
    ])

    # Graceful shutdown:
    acp.shutdown("Work complete")

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

# Import centralized config
from .config import ACP_BASE_URL as DEFAULT_ACP_URL
from .config import ACP_USER as DEFAULT_ACP_USER
from .config import ACP_PASS as DEFAULT_ACP_PASS


class ACPPlugin:
    """
    Plugin that bridges LocalClaw to ACP (Agent Control Panel).

    Features:
    - Logs all tool calls to ACP (using combined /api/action endpoint)
    - Logs shell commands to /api/shell/add (MANDATORY per spec §5.0)
    - Tracks tokens using ACP's estimation
    - Respects ACP STOP flag (raises StopIteration)
    - Processes hints field for context-aware decisions
    - Handles orphan_warning by completing orphaned activities
    - Processes nudge field for mid-task guidance
    - Syncs final answers as AI notes

    Parameters
    ----------
    base_url : str | None
        Full ACP URL. If None, uses DEFAULT_ACP_URL from config.
        Example: "https://your-tunnel.trycloudflare.com"
    user : str
        ACP username (default: from DEFAULT_ACP_USER)
    password : str
        ACP password (default: from DEFAULT_ACP_PASS)
    enabled : bool
        Whether plugin is active (default: True)
    on_stop : Callable[[str], None] | None
        Callback when STOP is detected (receives reason)
    on_hint : Callable[[dict], None] | None
        Callback when hints are received (receives hints dict)
    on_nudge : Callable[[dict], None] | None
        Callback when nudge is received (receives nudge dict)
    on_orphan : Callable[[list], None] | None
        Callback when orphans are detected (receives orphan list)
    debug : bool
        Print debug info (default: False)
    agent_name : str
        Name to use for activity attribution (default: "LocalClaw")
        v1.0.3: Helps identify which agent performed each action in multi-agent scenarios
    model_name : str | None
        Model identifier to display (e.g., "qwen2.5-coder:0.5b")
        v1.0.3: Shows agent_name · model_name format in ACP UI
    """

    def __init__(
        self,
        base_url: str | None = None,
        user: str = None,
        password: str = None,
        enabled: bool = True,
        on_stop: Callable[[str], None] | None = None,
        on_hint: Callable[[dict], None] | None = None,
        on_nudge: Callable[[dict], None] | None = None,
        on_orphan: Callable[[list], None] | None = None,
        debug: bool = False,
        agent_name: str = "LocalClaw",
        model_name: str | None = None,
    ):
        self.base_url = base_url if base_url else DEFAULT_ACP_URL
        self.auth = base64.b64encode(f"{user or DEFAULT_ACP_USER}:{password or DEFAULT_ACP_PASS}".encode()).decode()
        self.enabled = enabled
        self.on_stop = on_stop
        self.on_hint = on_hint          # v1.0.3: Hints callback
        self.on_nudge = on_nudge        # v1.0.3: Nudge callback
        self.on_orphan = on_orphan      # v1.0.3: Orphan callback
        self.debug = debug
        self.agent_name = agent_name
        self.model_name = model_name

        self._csrf_token: str | None = None
        self._csrf_expiry: float = 0
        self._current_activity_id: str | None = None
        self._activity_stack: list[str] = []  # Track nested activities
        self._step_count: int = 0
        self._last_stop_check: float = 0
        self._stop_flag: bool = False
        self._stop_reason: str | None = None

        # Track pending nudge for acknowledgment
        self._pending_nudge: dict | None = None

        # Tool name to ACP action type mapping
        self._action_map = {
            "read_file": "READ",
            "write_file": "WRITE",
            "edit_file": "EDIT",
            "shell": "BASH",
            "web_search": "SEARCH",
            "http_get": "API",
            "http_post": "API",
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

    def _build_metadata(self, tool_name: str = None) -> dict:
        """Build standard metadata dict for activities."""
        metadata = {
            "agent_name": self.agent_name,
            "source": "localclaw",
        }
        if self.model_name:
            metadata["model_name"] = self.model_name
        if tool_name:
            metadata["tool"] = tool_name
        return metadata

    def _process_response_fields(self, resp: dict) -> None:
        """
        Process ACP response fields: hints, orphan_warning, nudge.
        
        This is called after every /api/action request to handle
        all the important response fields per ACP spec.
        """
        # Process hints (v1.0.1 - contextual information)
        hints = resp.get("hints")
        if hints:
            self._log(f"Hints received: {list(hints.keys())}")
            if self.on_hint:
                self.on_hint(hints)
            # Check for loop detection
            if hints.get("loop_detected"):
                self._log(f"⚠️ Loop detected: {hints.get('loop_count')} repetitions")
                if hints.get("suggestion"):
                    self._log(f"Suggestion: {hints['suggestion']}")

        # Process orphan_warning (v1.0.2 - incomplete activities)
        orphan_warning = resp.get("orphan_warning")
        if orphan_warning:
            orphans = orphan_warning.get("tasks", [])
            self._log(f"⚠️ Orphan warning: {len(orphans)} orphaned activities")
            if self.on_orphan:
                self.on_orphan(orphans)
            # Complete orphaned activities
            self._complete_orphans(orphans)

        # Process nudge (v1.0.2 - human guidance)
        nudge = resp.get("nudge")
        if nudge:
            self._log(f"Nudge received: {nudge.get('message', '')[:50]}...")
            self._pending_nudge = nudge
            if self.on_nudge:
                self.on_nudge(nudge)
            # Auto-acknowledge if callback didn't handle it
            if nudge.get("requires_ack"):
                self.ack_nudge()

    def _complete_orphans(self, orphans: list) -> None:
        """Complete orphaned activities from previous session."""
        for orphan in orphans:
            orphan_id = orphan.get("id")
            if orphan_id:
                self._request("/api/complete", "POST", {
                    "activity_id": orphan_id,
                    "result": "[Completed by orphan handler]",
                })
                self._log(f"Completed orphan: {orphan_id}")

    # ------------------------------------------------------------------ #
    #  Public API - Shell Logging (MANDATORY per spec §5.0)              #
    # ------------------------------------------------------------------ #

    def log_shell(
        self,
        command: str,
        status: str = "completed",
        output_preview: str = "",
        error: bool = False,
    ) -> dict:
        """
        Log a shell command to ACP's Terminal history.

        This is MANDATORY per ACP spec §5.0:
        "Log every shell command via /api/shell/add"

        Parameters
        ----------
        command : str
            The shell command executed (max 500 chars)
        status : str
            "running", "completed", or "error" (default: "completed")
        output_preview : str
            First ~200 chars of output
        error : bool
            Whether the command resulted in an error

        Returns
        -------
        dict
            API response from ACP server
        """
        if not self.enabled:
            return {"success": False, "error": "Plugin disabled"}

        # Build metadata with agent attribution
        metadata = self._build_metadata()

        # Truncate per spec limits
        cmd_truncated = command[:500] if command else ""
        preview_truncated = output_preview[:200] if output_preview else ""

        return self._request("/api/shell/add", "POST", {
            "command": cmd_truncated,
            "status": "error" if error else status,
            "output_preview": preview_truncated,
            "metadata": metadata,
        })

    def ack_nudge(self) -> dict:
        """
        Acknowledge a pending nudge.

        Call this after processing a nudge that had requires_ack=true.
        """
        resp = self._request("/api/nudge/ack", "POST", {})
        self._pending_nudge = None
        self._log("Nudge acknowledged")
        return resp

    # ------------------------------------------------------------------ #
    #  Public API - Main Callback                                         #
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
        """
        Log a tool call to ACP using combined /api/action endpoint.
        
        Uses the recommended combined endpoint that can complete previous
        activity AND start new one in a single request (more efficient).
        """
        tool_name = getattr(step, "tool_name", "unknown")
        tool_args = getattr(step, "tool_args", {}) or {}

        # Map tool name to ACP action type
        action = self._action_map.get(tool_name.lower(), tool_name.upper())

        # Create target string from args (truncate if too long)
        target = self._format_target(tool_name, tool_args)

        # Build metadata
        metadata = self._build_metadata(tool_name)

        # Use combined /api/action endpoint (recommended per spec)
        # This checks stop_flag, starts new activity, returns hints/nudge/orphans
        resp = self._request("/api/action", "POST", {
            "action": action,
            "target": target,
            "details": f"LocalClaw tool: {tool_name}",
            "priority": "medium",
            "metadata": metadata,
        })

        # Process response fields (hints, orphan_warning, nudge)
        self._process_response_fields(resp)

        activity_id = resp.get("activity_id")
        if activity_id:
            self._activity_stack.append(activity_id)
            self._current_activity_id = activity_id
            self._log(f"Started activity: {activity_id} ({action})")

        # Special handling: Log shell commands to /api/shell/add
        if tool_name.lower() == "shell":
            cmd = tool_args.get("command", "")
            self.log_shell(cmd, status="running")

    def _handle_tool_result(self, step: StepResult) -> None:
        """
        Complete the current activity in ACP.
        
        Uses combined /api/action endpoint for efficiency when possible,
        falls back to /api/complete for final completion.
        """
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

        # Complete using combined endpoint (if we have a next action queued)
        # For now, use dedicated complete endpoint
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

        # Special handling: Update shell history for shell tool
        if tool_name.lower() == "shell":
            cmd = ""  # We don't have the original command here
            # The tool call handler already logged with "running" status
            # Update with final status
            self.log_shell(
                cmd or "[shell command]",
                status="error" if error else "completed",
                output_preview=content[:200] if content else "",
                error=bool(error),
            )

    def _handle_thought(self, step: StepResult) -> None:
        """
        Log agent thought process.
        
        v1.0.3: Could optionally log as CHAT action for token tracking,
        but this may be noisy. Currently just debug logs.
        """
        content = getattr(step, "content", "")
        self._log(f"Thought: {content[:100]}...")

        # Optional: Log thoughts as CHAT for token tracking
        # Uncomment if you want full thought tracking:
        # resp = self._request("/api/action", "POST", {
        #     "action": "CHAT",
        #     "target": "Agent reasoning",
        #     "details": content[:200],
        #     "metadata": self._build_metadata(),
        # })
        # self._process_response_fields(resp)
        # if resp.get("activity_id"):
        #     self._request("/api/complete", "POST", {
        #         "activity_id": resp["activity_id"],
        #         "result": "[thought logged]",
        #     })

    def _handle_final(self, step: StepResult) -> None:
        """Log final answer as an AI note and clean up."""
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
        elif tool_name == "edit_file":
            return args.get("path", "unknown")
        elif tool_name == "shell":
            return args.get("command", "")[:100]
        elif tool_name == "calculator":
            return args.get("expression", "")[:100]
        elif tool_name == "web_search":
            return args.get("query", "")[:100]
        elif tool_name == "http_get":
            return args.get("url", "")[:100]
        elif tool_name == "http_post":
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
    #  Chat Logging Methods                                                #
    # ------------------------------------------------------------------ #

    def log_chat(
        self,
        role: str,
        content: str,
        complete: bool = True,
    ) -> dict:
        """
        Log a chat message to ACP.

        This makes LocalClaw conversations visible in the ACP activity feed.

        Parameters
        ----------
        role : str
            "user" or "assistant"
        content : str
            The message content
        complete : bool
            Whether to immediately complete the activity (default: True)
            Set False for streaming responses, then call complete_chat()

        Returns
        -------
        dict
            API response with activity_id
        """
        if not self.enabled:
            return {"success": False, "error": "Plugin disabled"}

        # Build metadata
        metadata = self._build_metadata()
        metadata["chat_role"] = role

        # Truncate for display
        preview = content[:200] if content else ""

        # Create activity
        resp = self._request("/api/action", "POST", {
            "action": "CHAT",
            "target": f"{role.title()}: {preview[:50]}...",
            "details": content[:1000] if content else "",
            "priority": "normal",
            "metadata": metadata,
        })

        # Process response fields
        self._process_response_fields(resp)

        activity_id = resp.get("activity_id")
        if activity_id and complete:
            # Complete immediately for non-streaming
            self._request("/api/complete", "POST", {
                "activity_id": activity_id,
                "result": content[:500] if content else "",
            })
            self._log(f"Logged {role} message")

        return resp

    def log_user_message(self, content: str) -> dict:
        """Convenience method to log a user message."""
        return self.log_chat("user", content)

    def log_assistant_message(self, content: str) -> dict:
        """Convenience method to log an assistant message."""
        return self.log_chat("assistant", content)

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

    def get_agent_tokens(self) -> dict:
        """Get per-agent token breakdown from ACP (v1.0.3)."""
        status = self.get_status()
        return status.get("agent_tokens", {})

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

    def get_duration_stats(self) -> dict:
        """Get activity duration statistics (v1.0.3)."""
        return self._request("/api/stats/duration")

    # ------------------------------------------------------------------ #
    #  Batch Operations (v1.0.3)                                          #
    # ------------------------------------------------------------------ #

    def batch_start(
        self,
        activities: list[dict],
    ) -> dict:
        """
        Start multiple activities in a single atomic request.

        This is more efficient than individual /api/action calls when
        reading multiple files or starting several operations at once.

        Parameters
        ----------
        activities : list[dict]
            List of activity dicts, each with:
            - action: Action type (READ, WRITE, etc.)
            - target: Target string (file path, command, etc.)
            - details: Optional description
            - content_size: Optional character count for token tracking
            - priority: Optional priority (high, medium, low)

        Returns
        -------
        dict
            Response with 'results' array containing activity_id for each

        Example
        -------
        >>> result = acp.batch_start([
        ...     {"action": "READ", "target": "/file1.py", "content_size": 5000},
        ...     {"action": "READ", "target": "/file2.py", "content_size": 3000},
        ... ])
        >>> activity_ids = [r["activity_id"] for r in result["results"]]
        """
        if not self.enabled:
            return {"success": False, "error": "Plugin disabled"}

        # Build operations array for /api/activity/batch
        operations = []
        for act in activities:
            op = {
                "type": "start",
                "action": act.get("action", "READ"),
                "target": act.get("target", ""),
                "details": act.get("details", ""),
                "content_size": act.get("content_size", 0),
                "priority": act.get("priority", "medium"),
                "metadata": self._build_metadata(act.get("tool")),
            }
            if act.get("details"):
                op["details"] = act["details"]
            operations.append(op)

        resp = self._request("/api/activity/batch", "POST", {
            "operations": operations,
        })

        # Process response fields
        self._process_response_fields(resp)

        # Track activity IDs
        if resp.get("success"):
            for result in resp.get("results", []):
                if result.get("success") and result.get("activity_id"):
                    self._activity_stack.append(result["activity_id"])

        return resp

    def batch_complete(
        self,
        completions: list[dict],
    ) -> dict:
        """
        Complete multiple activities in a single atomic request.

        Parameters
        ----------
        completions : list[dict]
            List of completion dicts, each with:
            - activity_id: ID of activity to complete
            - result: Optional result summary
            - error: Optional error message
            - content_size: Optional character count for token tracking

        Returns
        -------
        dict
            Response with 'results' array for each completion

        Example
        -------
        >>> result = acp.batch_complete([
        ...     {"activity_id": "id1", "result": "File read successfully"},
        ...     {"activity_id": "id2", "result": "File read successfully"},
        ... ])
        """
        if not self.enabled:
            return {"success": False, "error": "Plugin disabled"}

        # Build operations array
        operations = []
        for comp in completions:
            op = {
                "type": "complete",
                "activity_id": comp.get("activity_id"),
                "result": comp.get("result", ""),
                "content_size": comp.get("content_size", 0),
            }
            if comp.get("error"):
                op["error"] = comp["error"]
            operations.append(op)

        resp = self._request("/api/activity/batch", "POST", {
            "operations": operations,
        })

        # Remove from activity stack
        if resp.get("success"):
            completed_ids = {c.get("activity_id") for c in completions}
            self._activity_stack = [
                aid for aid in self._activity_stack if aid not in completed_ids
            ]

        return resp

    def batch_action(
        self,
        operations: list[dict],
    ) -> dict:
        """
        Execute mixed batch of start and complete operations.

        This is the most flexible batch method - combine starts and
        completions in a single atomic request.

        Parameters
        ----------
        operations : list[dict]
            List of operations, each with:
            - type: "start" or "complete"
            - For start: action, target, details, content_size, priority
            - For complete: activity_id, result, error, content_size

        Returns
        -------
        dict
            Response with 'results' array for each operation

        Example
        -------
        >>> # Complete previous reads and start new ones
        >>> result = acp.batch_action([
        ...     {"type": "complete", "activity_id": "prev1", "result": "Done"},
        ...     {"type": "complete", "activity_id": "prev2", "result": "Done"},
        ...     {"type": "start", "action": "READ", "target": "/newfile.py"},
        ... ])
        """
        if not self.enabled:
            return {"success": False, "error": "Plugin disabled"}

        # Add metadata to start operations
        for op in operations:
            if op.get("type") == "start":
                op["metadata"] = self._build_metadata(op.get("tool"))

        resp = self._request("/api/activity/batch", "POST", {
            "operations": operations,
        })

        self._process_response_fields(resp)

        # Track/cleanup activity IDs
        if resp.get("success"):
            for result in resp.get("results", []):
                if result.get("operation") == "start" and result.get("activity_id"):
                    self._activity_stack.append(result["activity_id"])
                elif result.get("operation") == "complete":
                    # Remove from stack if present
                    completed_id = result.get("activity_id")
                    if completed_id in self._activity_stack:
                        self._activity_stack.remove(completed_id)

        return resp

    # ------------------------------------------------------------------ #
    #  Shutdown Support (v1.0.2)                                          #
    # ------------------------------------------------------------------ #

    def shutdown(
        self,
        reason: str = "Session ended by LocalClaw",
        export_summary: bool = True,
    ) -> dict:
        """
        Gracefully end the ACP session.

        This triggers:
        1. Session summary export for context recovery
        2. Cancellation of all running activities
        3. Shutdown nudge sent to any connected agents
        4. Server stops after brief delay

        Parameters
        ----------
        reason : str
            Human-readable reason for shutdown
        export_summary : bool
            Whether to export session summary (default: True)

        Returns
        -------
        dict
            Response with shutdown status and summary path

        Example
        -------
        >>> # End session gracefully
        >>> result = acp.shutdown("Work complete, ending session")
        >>> print(f"Summary saved to: {result.get('summary_path')}")
        """
        if not self.enabled:
            return {"success": False, "error": "Plugin disabled"}

        resp = self._request("/api/shutdown", "POST", {
            "reason": reason,
            "export_summary": export_summary,
        })

        self._log(f"Shutdown requested: {reason}")

        # Clear local state
        if resp.get("success"):
            self._activity_stack.clear()
            self._current_activity_id = None

        return resp

    def is_shutdown_nudge(self, nudge: dict) -> bool:
        """
        Check if a nudge is a shutdown notification.

        Parameters
        ----------
        nudge : dict
            Nudge dict from ACP response

        Returns
        -------
        bool
            True if this is a shutdown nudge
        """
        return nudge and nudge.get("type") == "shutdown"

    def get_todos(self) -> list[dict]:
        """
        Get current TODO list from ACP.

        Use this to recover TODOs from a previous session or to check
        current task state.

        Returns
        -------
        list[dict]
            List of TODO objects, each with id, content, status, priority
        """
        resp = self._request("/api/todos")
        return resp.get("todos", [])

    def bootstrap(self, claim_primary: bool = True) -> dict:
        """
        Bootstrap ACP session - check status, establish identity, claim primary.

        Call this at the start of a session to:
        1. Check if STOP flag is set
        2. Establish agent identity via /api/whoami
        3. Optionally claim primary agent status

        Per ACP spec §5, this should be the first ACP call in a session.

        Parameters
        ----------
        claim_primary : bool
            Whether to claim primary agent status (default: True)
            If False, will only check status and establish identity

        Returns
        -------
        dict
            Bootstrap result with status, identity, and primary_claimed fields
        """
        result = {
            "status": None,
            "identity": None,
            "primary_claimed": False,
            "stop_flag": False,
            "warnings": [],
        }

        # 1. Check status
        status = self.get_status()
        result["status"] = status

        if status.get("stop_flag"):
            self._stop_flag = True
            self._stop_reason = status.get("stop_reason", "No reason given")
            result["stop_flag"] = True
            result["warnings"].append(f"STOP flag is set: {self._stop_reason}")
            self._log(f"Bootstrap: STOP flag detected - {self._stop_reason}")

        # 2. Establish identity
        whoami = self._request("/api/whoami")
        result["identity"] = whoami.get("identity", {})
        self._log(f"Bootstrap: Identity established as {self.agent_name}")

        # 3. Log bootstrap activity (always, regardless of primary claim)
        if not result["stop_flag"]:
            resp = self._request("/api/action", "POST", {
                "action": "CHAT",
                "target": f"{self.agent_name}: Session bootstrap",
                "details": f"Connecting to ACP session" + ("(claiming primary)" if claim_primary else "(secondary agent)"),
                "metadata": self._build_metadata(),
            })
            self._process_response_fields(resp)
            if resp.get("success") and resp.get("activity_id"):
                # Complete immediately
                self._request("/api/complete", "POST", {
                    "activity_id": resp["activity_id"],
                    "result": "Bootstrap complete",
                })
                self._log(f"Bootstrap: Logged bootstrap activity")

        # 4. Handle primary agent claim
        if claim_primary and not result["stop_flag"]:
            current_primary = status.get("primary_agent")
            if current_primary is None:
                # Try to claim primary via bootstrap activity
                result["primary_claimed"] = True  # We were first to log
                self._log(f"Bootstrap: Claimed primary agent status")
            elif current_primary == self.agent_name:
                result["primary_claimed"] = True
                self._log(f"Bootstrap: Already primary agent")
            else:
                result["warnings"].append(f"Primary agent is {current_primary}")
                self._log(f"Bootstrap: Primary agent is {current_primary}")

        return result

    def reset(self):
        """Reset plugin state (for new session)."""
        self._activity_stack.clear()
        self._current_activity_id = None
        self._step_count = 0
        self._stop_flag = False
        self._stop_reason = None
        self._pending_nudge = None


# ------------------------------------------------------------------ #
#  Convenience Factory                                                 #
# ------------------------------------------------------------------ #

def create_acp_agent(
    model: str,
    tools: Any = None,
    acp_url: str | None = None,
    agent_name: str = "LocalClaw",
    on_hint: Callable[[dict], None] | None = None,
    on_nudge: Callable[[dict], None] | None = None,
    on_orphan: Callable[[list], None] | None = None,
    **agent_kwargs,
) -> tuple["Agent", ACPPlugin]:
    """
    Create a LocalClaw Agent pre-configured with ACP plugin.

    Returns both the agent and plugin for additional control.

    v1.0.3: Full spec compliance with hints, nudge, orphan support.

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

    plugin = ACPPlugin(
        base_url=acp_url,
        agent_name=agent_name,
        model_name=model,
        on_hint=on_hint,
        on_nudge=on_nudge,
        on_orphan=on_orphan,
    )
    agent = Agent(
        model=model,
        tools=tools,
        on_step=plugin.on_step,
        **agent_kwargs,
    )
    return agent, plugin
