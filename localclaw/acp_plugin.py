"""
🦞 LocalClaw ACP Plugin - Bridge to Agent Control Panel

This plugin connects LocalClaw agents to an ACP (Agent Control Panel) server,
enabling real-time monitoring, token tracking, and STOP/Resume control.

ACP Specification: v1.0.4 (A2A Compliance)
Compliance: Full (mandatory requirements, hints, orphan handling, nudge support, batch ops, shutdown, A2A, JSON-RPC 2.0)

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
- A2A Agent Registry and Messaging (v1.0.4)
- JSON-RPC 2.0 support for A2A compliance (1.0.4)
- Agent Card discovery via well-known URI (1.0.4)
- AgentSkill registration support (1.0.4)
- contextId tracking for session continuity (1.0.4)

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
    on_a2a_message : Callable[[dict], None] | None
        Callback when A2A messages are pending (v1.0.4)
        Receives dict with pending_count, senders, and preview
    debug : bool
        Print debug info (default: False)
    agent_name : str
        Name to use for activity attribution (default: "LocalClaw")
        v1.0.3: Helps identify which agent performed each action in multi-agent scenarios
    model_name : str | None
        Model identifier to display (e.g., "qwen2.5-coder:0.5b")
        v1.0.3: Shows agent_name · model_name format in ACP UI
    capabilities : list[str]
        List of agent capabilities for A2A registry (v1.0.4)
        Examples: ["code", "research"], ["testing"], ["a2a"]
    endpoint : str | None
        Optional HTTP endpoint for A2A messaging (v1.0.4)
        Other agents can use this to send direct messages
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
        on_a2a_message: Callable[[dict], None] | None = None,
        debug: bool = False,
        agent_name: str = "LocalClaw",
        model_name: str | None = None,
        capabilities: list[str] | None = None,
        endpoint: str | None = None,
    ):
        self.base_url = base_url if base_url else DEFAULT_ACP_URL
        self.auth = base64.b64encode(f"{user or DEFAULT_ACP_USER}:{password or DEFAULT_ACP_PASS}".encode()).decode()
        self.enabled = enabled
        self.on_stop = on_stop
        self.on_hint = on_hint          # v1.0.3: Hints callback
        self.on_nudge = on_nudge        # v1.0.3: Nudge callback
        self.on_orphan = on_orphan      # v1.0.3: Orphan callback
        self.on_a2a_message = on_a2a_message  # v1.0.4: A2A message notification callback
        self.debug = debug
        self.agent_name = agent_name
        self.model_name = model_name
        self.capabilities = capabilities or ["code", "research"]  # v1.0.4: A2A capabilities
        self.endpoint = endpoint  # v1.0.4: A2A endpoint

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

        # 1.0.4: A2A compliance - context tracking
        self._context_id: str | None = None
        self._jsonrpc_id: int = 0  # Incrementing ID for JSON-RPC requests

        # 1.0.4: AgentSkills for A2A Agent Card
        self._skills: list[dict] | None = None

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

        # 1.0.4: Auto-generate AgentSkills from tools for A2A discovery
        # This allows other agents to know what actions this agent supports
        self._auto_skills = self._generate_skills_from_tools()

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

    # ------------------------------------------------------------------ #
    #  JSON-RPC 2.0 Support (1.0.4 - A2A Compliance)                          #
    # ------------------------------------------------------------------ #

    def _jsonrpc_request(
        self,
        method: str,
        params: dict | None = None,
        timeout: float = 5.0,
    ) -> dict:
        """
        Make a JSON-RPC 2.0 request to ACP server.

        This is the A2A-compliant way to communicate with ACP.

        Parameters
        ----------
        method : str
            JSON-RPC method name (e.g., "SendMessage", "GetTask", "RegisterAgent")
        params : dict | None
            Method parameters
        timeout : float
            Request timeout in seconds

        Returns
        -------
        dict
            JSON-RPC response with 'result' or 'error'
        """
        if not self.enabled:
            return {"error": {"code": -32603, "message": "Plugin disabled"}}

        # Build JSON-RPC 2.0 request
        self._jsonrpc_id += 1
        request_body = {
            "jsonrpc": "2.0",
            "id": self._jsonrpc_id,
            "method": method,
            "params": params or {}
        }

        headers = {
            "Authorization": f"Basic {self.auth}",
            "Content-Type": "application/json",
            "X-Agent-Name": self.agent_name,  # 1.0.4: Agent identification header
        }

        url = f"{self.base_url}/jsonrpc"
        body = json.dumps(request_body).encode()

        req = urllib.request.Request(
            url,
            headers=headers,
            method="POST",
            data=body,
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                response = json.loads(resp.read().decode())

                # Check for JSON-RPC error
                if "error" in response:
                    return {"error": response["error"]}

                # Return result
                return response.get("result", {})

        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            return {"error": {"code": e.code, "message": error_body}}
        except urllib.error.URLError as e:
            return {"error": {"code": -32300, "message": f"Connection error: {e.reason}"}}
        except json.JSONDecodeError as e:
            return {"error": {"code": -32700, "message": f"Parse error: {e}"}}
        except Exception as e:
            return {"error": {"code": -32603, "message": str(e)}}

    def get_agent_card(self) -> dict:
        """
        Get ACP server's Agent Card from well-known URI.

        Returns
        -------
        dict
            Agent Card with name, description, skills, capabilities
        """
        if not self.enabled:
            return {"error": "Plugin disabled"}

        headers = {
            "Authorization": f"Basic {self.auth}",
        }

        url = f"{self.base_url}/.well-known/agent-card.json"

        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": str(e)}

    def _generate_skills_from_tools(self) -> list[dict]:
        """
        Auto-generate AgentSkill objects from LocalClaw's tool mapping.

        Per ACP-Spec 1.0.4 §3.10, AgentSkill objects describe specific capabilities
        an agent can perform. This method creates them automatically from the
        _action_map so other agents can discover what actions this agent supports.

        Returns
        -------
        list[dict]
            List of AgentSkill objects for A2A registration
        """
        # Define skill templates for each tool type
        skill_templates = {
            "read_file": {
                "id": "read_file",
                "name": "Read File",
                "description": "Read the contents of a file from the filesystem",
                "tags": ["file", "read", "filesystem"],
                "examples": ["Read /etc/passwd", "Read the contents of config.py"],
                "inputModes": ["text/plain", "application/json"],
                "outputModes": ["text/plain"],
            },
            "write_file": {
                "id": "write_file",
                "name": "Write File",
                "description": "Create or overwrite a file with new content",
                "tags": ["file", "write", "create", "filesystem"],
                "examples": ["Create a new Python script", "Write config to file"],
                "inputModes": ["text/plain", "application/json"],
                "outputModes": ["text/plain"],
            },
            "edit_file": {
                "id": "edit_file",
                "name": "Edit File",
                "description": "Modify an existing file with targeted edits",
                "tags": ["file", "edit", "modify", "filesystem"],
                "examples": ["Edit the config file", "Fix a bug in the code"],
                "inputModes": ["text/plain", "application/json"],
                "outputModes": ["text/plain"],
            },
            "shell": {
                "id": "shell",
                "name": "Execute Shell Command",
                "description": "Run a bash/shell command and return the output",
                "tags": ["bash", "shell", "command", "execute"],
                "examples": ["Run ls -la", "Execute npm install", "Run pytest"],
                "inputModes": ["text/plain", "application/json"],
                "outputModes": ["text/plain"],
            },
            "web_search": {
                "id": "web_search",
                "name": "Web Search",
                "description": "Search the web for information",
                "tags": ["web", "search", "internet", "query"],
                "examples": ["Search for Python tutorials", "Find documentation for FastAPI"],
                "inputModes": ["text/plain", "application/json"],
                "outputModes": ["text/plain", "application/json"],
            },
            "http_get": {
                "id": "http_get",
                "name": "HTTP GET Request",
                "description": "Make an HTTP GET request to a URL",
                "tags": ["http", "api", "request", "get"],
                "examples": ["GET https://api.example.com/data", "Fetch data from API"],
                "inputModes": ["text/plain", "application/json"],
                "outputModes": ["text/plain", "application/json"],
            },
            "http_post": {
                "id": "http_post",
                "name": "HTTP POST Request",
                "description": "Make an HTTP POST request to a URL",
                "tags": ["http", "api", "request", "post"],
                "examples": ["POST data to API", "Submit form data"],
                "inputModes": ["text/plain", "application/json"],
                "outputModes": ["text/plain", "application/json"],
            },
            "calculator": {
                "id": "calculator",
                "name": "Calculator",
                "description": "Evaluate mathematical expressions",
                "tags": ["math", "calculate", "expression"],
                "examples": ["Calculate 2^20", "Evaluate sqrt(144)"],
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain"],
            },
            "python_repl": {
                "id": "python_repl",
                "name": "Python REPL",
                "description": "Execute Python code and return the result",
                "tags": ["python", "code", "execute", "repl"],
                "examples": ["Run Python script", "Execute Python expression"],
                "inputModes": ["text/plain", "application/json"],
                "outputModes": ["text/plain"],
            },
            "list_directory": {
                "id": "list_directory",
                "name": "List Directory",
                "description": "List contents of a directory",
                "tags": ["directory", "list", "files", "filesystem"],
                "examples": ["List files in /home", "Show directory contents"],
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain", "application/json"],
            },
        }

        # Generate skills for tools in our action map
        skills = []
        for tool_name in self._action_map.keys():
            if tool_name in skill_templates:
                skills.append(skill_templates[tool_name])

        return skills

    def set_skills(self, skills: list[dict]) -> None:
        """
        Set agent skills for A2A Agent Card (overrides auto-generated skills).

        Skills define what this agent can do for other agents.

        Parameters
        ----------
        skills : list[dict]
            List of skill objects, each with:
            - id: Unique skill identifier
            - name: Human-readable name
            - description: What this skill does
            - tags: Keywords for discovery
            - examples: Example prompts
            - inputModes: Supported input MIME types (default: ["text/plain"])
            - outputModes: Supported output MIME types (default: ["text/plain"])

        Example
        -------
        >>> acp.set_skills([
        ...     {
        ...         "id": "code_generation",
        ...         "name": "Code Generation",
        ...         "description": "Generate code from specifications",
        ...         "tags": ["code", "generation", "programming"],
        ...         "examples": ["Create a REST API", "Write a Python function"]
        ...     }
        ... ])
        """
        self._skills = skills

    def get_skills(self) -> list[dict]:
        """
        Get the agent's skills for A2A discovery.

        Returns custom skills if set via set_skills(), otherwise returns
        auto-generated skills from LocalClaw's tool mapping.

        Returns
        -------
        list[dict]
            List of AgentSkill objects
        """
        return self._skills if self._skills else self._auto_skills

    def get_context_id(self, create: bool = True) -> str | None:
        """
        Get current contextId for A2A session continuity.

        Parameters
        ----------
        create : bool
            If True and no context exists, create one

        Returns
        -------
        str | None
            Current contextId or None
        """
        if self._context_id is None and create:
            import uuid
            self._context_id = f"ctx-{uuid.uuid4().hex[:12]}"
            self._log(f"Created contextId: {self._context_id}")
        return self._context_id

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
        Process ACP response fields: hints, orphan_warning, nudge, a2a.
        
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
            
            # v1.0.4: Process A2A hints (pending messages notification)
            a2a_hints = hints.get("a2a")
            if a2a_hints:
                pending = a2a_hints.get("pending_count", 0)
                if pending > 0:
                    senders = a2a_hints.get("senders", [])
                    preview = a2a_hints.get("preview", {})
                    self._log(f"📨 A2A: {pending} pending message(s) from {senders}")
                    if preview:
                        self._log(f"   Preview: {preview.get('from')} - {preview.get('action')}")
                    # Call A2A callback if registered
                    if self.on_a2a_message:
                        self.on_a2a_message(a2a_hints)

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

        # Unregister from A2A first (v1.0.4)
        self.a2a_unregister()

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

        # 5. Register with A2A Agent Registry (v1.0.4)
        if not result["stop_flag"]:
            a2a_result = self.a2a_register()
            result["a2a_registered"] = a2a_result.get("success", False)
            if a2a_result.get("success"):
                self._log(f"Bootstrap: Registered with A2A")

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
    #  A2A Methods (v1.0.4, 1.0.4 - JSON-RPC 2.0)                            #
    # ------------------------------------------------------------------ #

    def a2a_register(self, use_jsonrpc: bool = True) -> dict:
        """
        Register this agent with the A2A Agent Registry.

        Call this after bootstrap to make the agent discoverable by other agents.
        Registration includes capabilities, model name, skills, and optional endpoint.

        1.0.4: Supports JSON-RPC 2.0 for A2A compliance.

        Parameters
        ----------
        use_jsonrpc : bool
            Use JSON-RPC 2.0 if True (default), REST API otherwise

        Returns
        -------
        dict
            Registration response with success status and agent_card
        """
        if not self.enabled:
            return {"success": False, "error": "Plugin disabled"}

        # Get skills (custom or auto-generated)
        skills = self.get_skills()
        
        params = {
            "agent_name": self.agent_name,
            "capabilities": self.capabilities,
            "model_name": self.model_name,
            "endpoint": self.endpoint,
            "skills": skills,
        }

        if use_jsonrpc:
            resp = self._jsonrpc_request("RegisterAgent", params)
            if "error" in resp:
                # Fallback to REST
                self._log(f"JSON-RPC failed, falling back to REST: {resp.get('error')}")
                resp = self._request("/api/agents/register", "POST", params)
            elif "agent_card" in resp:
                self._log(f"A2A: Registered via JSON-RPC as {self.agent_name}")
                return {"success": True, "agent_card": resp["agent_card"]}
        else:
            resp = self._request("/api/agents/register", "POST", params)

        if resp.get("success"):
            self._log(f"A2A: Registered as {self.agent_name}")

        return resp

    def a2a_unregister(self) -> dict:
        """
        Unregister this agent from the A2A Agent Registry.

        Call this before shutdown to cleanly remove the agent from the registry.

        Returns
        -------
        dict
            Unregistration response
        """
        if not self.enabled:
            return {"success": False, "error": "Plugin disabled"}

        resp = self._request("/api/agents/unregister", "POST", {
            "agent_name": self.agent_name,
        })

        if resp.get("success"):
            self._log(f"A2A: Unregistered {self.agent_name}")

        return resp

    def a2a_heartbeat(self) -> dict:
        """
        Send heartbeat to update agent's last_seen timestamp.

        Call this periodically (every 30-60 seconds) to maintain online status.

        Returns
        -------
        dict
            Heartbeat response with success status
        """
        if not self.enabled:
            return {"success": False, "error": "Plugin disabled"}

        return self._request("/api/agents/heartbeat", "POST", {
            "agent_name": self.agent_name,
        })

    def a2a_get_agents(self, use_jsonrpc: bool = False) -> list[dict]:
        """
        Get list of all registered agents with their Agent Cards.

        Parameters
        ----------
        use_jsonrpc : bool
            Use JSON-RPC 2.0 for A2A compliance

        Returns
        -------
        list[dict]
            List of agent cards with name, skills, capabilities, status
        """
        if not self.enabled:
            return []

        if use_jsonrpc:
            resp = self._jsonrpc_request("GetAgents", {})
            if "error" not in resp:
                return resp.get("agents", [])

        resp = self._request("/api/agents")
        return resp.get("agents", [])

    def a2a_get_agent(self, agent_name: str) -> dict | None:
        """
        Get details for a specific agent.

        Parameters
        ----------
        agent_name : str
            Name of the agent to look up

        Returns
        -------
        dict | None
            Agent details or None if not found
        """
        if not self.enabled:
            return None

        resp = self._request(f"/api/agents/{agent_name}")
        return resp.get("agent") if resp.get("success") else None

    def a2a_send(
        self,
        to_agent: str,
        action: str,
        payload: dict | None = None,
        message_type: str = "notification",
        subject: str | None = None,
        priority: int = 5,
        ttl: int = 3600,
        reply_to: str | None = None,
        use_jsonrpc: bool = True,
    ) -> dict:
        """
        Send an A2A message to another agent.

        1.0.4: Supports JSON-RPC 2.0 SendMessage for A2A compliance.

        Parameters
        ----------
        to_agent : str
            Name of the target agent
        action : str
            Action type (e.g., "run_tests", "status_check", "collaborate")
        payload : dict | None
            Message payload/data
        message_type : str
            "request" (expects response), "response" (reply), or "notification"
        subject : str | None
            Human-readable subject line
        priority : int
            Message priority 1-10 (default: 5)
        ttl : int
            Time-to-live in seconds (default: 3600 = 1 hour)
        reply_to : str | None
            Message ID this is a reply to
        use_jsonrpc : bool
            Use JSON-RPC 2.0 SendMessage if True (default)

        Returns
        -------
        dict
            Response with success status and message_id or task
        """
        if not self.enabled:
            return {"success": False, "error": "Plugin disabled"}

        # 1.0.4: Use JSON-RPC SendMessage for A2A compliance
        if use_jsonrpc:
            # Build A2A-format message
            parts = []
            if payload:
                if isinstance(payload, dict):
                    parts.append({"data": payload})
                else:
                    parts.append({"text": str(payload)})
            else:
                parts.append({"text": action})

            message = {
                "contextId": self._context_id,
                "messageId": f"msg-{time.time_ns()}",
                "parts": parts,
                "metadata": {
                    "action": action,
                    "target_agent": to_agent,
                    "priority": priority,
                }
            }

            resp = self._jsonrpc_request("SendMessage", {"message": message})
            if "error" not in resp:
                task = resp.get("task", {})
                self._log(f"A2A: Sent via JSON-RPC to {to_agent}: {action}")
                return {
                    "success": True,
                    "message_id": task.get("id"),
                    "task": task,
                    "context_id": task.get("contextId"),
                }
            else:
                self._log(f"JSON-RPC failed, falling back to REST: {resp.get('error')}")

        # Fallback to REST API
        data = {
            "from_agent": self.agent_name,
            "to_agent": to_agent,
            "action": action,
            "payload": payload or {},
            "type": message_type,
            "priority": priority,
            "ttl": ttl,
        }
        if subject:
            data["subject"] = subject
        if reply_to:
            data["reply_to"] = reply_to

        resp = self._request("/api/a2a/send", "POST", data)

        if resp.get("success"):
            self._log(f"A2A: Sent message to {to_agent} ({action})")

        return resp

    def a2a_get_inbox(self, since: float | None = None) -> list[dict]:
        """
        Get messages for this agent.

        Parameters
        ----------
        since : float | None
            Optional timestamp to only get messages after this time

        Returns
        -------
        list[dict]
            List of messages for this agent
        """
        if not self.enabled:
            return []

        data = {"agent_name": self.agent_name}
        if since:
            data["since"] = since

        resp = self._request("/api/a2a/inbox", "POST", data)

        messages = resp.get("messages", [])
        if messages:
            self._log(f"A2A: Received {len(messages)} message(s)")

        return messages

    def a2a_clear(self, older_than_hours: int = 24) -> dict:
        """
        Clear old messages (optional cleanup).

        Parameters
        ----------
        older_than_hours : int
            Clear messages older than this many hours (default: 24)

        Returns
        -------
        dict
            Response with cleared count
        """
        if not self.enabled:
            return {"success": False, "error": "Plugin disabled"}

        return self._request("/api/a2a/clear", "POST", {
            "older_than_hours": older_than_hours,
        })

    def a2a_acknowledge(self, msg_ids: str | list[str]) -> dict:
        """
        Acknowledge (remove) messages after processing.

        Parameters
        ----------
        msg_ids : str | list[str]
            Message ID or list of message IDs to acknowledge

        Returns
        -------
        dict
            Response with removed count
        """
        if not self.enabled:
            return {"success": False, "error": "Plugin disabled"}

        if isinstance(msg_ids, str):
            msg_ids = [msg_ids]

        return self._request("/api/a2a/acknowledge", "POST", {
            "msg_ids": msg_ids,
        })

    def a2a_get_history(
        self,
        from_agent: str | None = None,
        to_agent: str | None = None,
        msg_type: str | None = None,
    ) -> list[dict]:
        """
        Get A2A message history with optional filters.

        Parameters
        ----------
        from_agent : str | None
            Filter by sender
        to_agent : str | None
            Filter by recipient
        msg_type : str | None
            Filter by message type

        Returns
        -------
        list[dict]
            List of messages matching filters
        """
        if not self.enabled:
            return []

        params = []
        if from_agent:
            params.append(f"from={from_agent}")
        if to_agent:
            params.append(f"to={to_agent}")
        if msg_type:
            params.append(f"type={msg_type}")

        query = "?" + "&".join(params) if params else ""
        resp = self._request(f"/api/a2a/history{query}")

        return resp.get("messages", [])

    def a2a_broadcast(
        self,
        action: str,
        payload: dict | None = None,
        capabilities_filter: list[str] | None = None,
        exclude_self: bool = True,
    ) -> list[dict]:
        """
        Broadcast a message to all agents (optionally filtered by capability).

        Parameters
        ----------
        action : str
            Action type for the broadcast
        payload : dict | None
            Message payload
        capabilities_filter : list[str] | None
            Only send to agents with these capabilities
        exclude_self : bool
            Exclude this agent from broadcast (default: True)

        Returns
        -------
        list[dict]
            List of send responses for each recipient
        """
        agents = self.a2a_get_agents()
        results = []

        for agent in agents:
            agent_name = agent.get("name")

            # Skip self
            if exclude_self and agent_name == self.agent_name:
                continue

            # Check capability filter
            if capabilities_filter:
                agent_caps = set(agent.get("capabilities", []))
                if not any(cap in agent_caps for cap in capabilities_filter):
                    continue

            # Send message
            result = self.a2a_send(
                to_agent=agent_name,
                action=action,
                payload=payload,
                message_type="notification",
            )
            results.append({"agent": agent_name, "result": result})

        self._log(f"A2A: Broadcast {action} to {len(results)} agent(s)")
        return results

    def a2a_map_action_to_tool(self, action: str) -> str | None:
        """
        Map an incoming A2A action to a LocalClaw tool name.

        ACP-Spec 1.0.4: Other agents send actions like "read_file", "shell", etc.
        This method maps those actions to LocalClaw tool names.

        Parameters
        ----------
        action : str
            Action name from incoming A2A message

        Returns
        -------
        str | None
            LocalClaw tool name or None if not supported
        """
        # Direct mapping for standard tool names
        tool_map = {
            "read_file": "read_file",
            "read": "read_file",
            "write_file": "write_file",
            "write": "write_file",
            "edit_file": "edit_file",
            "edit": "edit_file",
            "shell": "shell",
            "bash": "shell",
            "execute": "shell",
            "web_search": "web_search",
            "search": "web_search",
            "http_get": "http_get",
            "get": "http_get",
            "http_post": "http_post",
            "post": "http_post",
            "calculator": "calculator",
            "calculate": "calculator",
            "python_repl": "python_repl",
            "python": "python_repl",
            "list_directory": "list_directory",
            "ls": "list_directory",
        }
        return tool_map.get(action.lower())

    def a2a_process_inbox(
        self,
        tool_executor: Callable[[str, dict], Any] | None = None,
        auto_respond: bool = True,
    ) -> list[dict]:
        """
        Process pending A2A messages and optionally respond.

        This method fetches pending messages from the inbox and processes
        each request-type message by executing the requested action.

        Parameters
        ----------
        tool_executor : Callable | None
            Optional custom tool executor. If None, returns messages without
            processing. Signature: (action: str, payload: dict) -> result
        auto_respond : bool
            Whether to automatically send responses (default: True)

        Returns
        -------
        list[dict]
            List of processed messages with results

        Example
        -------
        >>> # Process with custom executor
        >>> results = acp.a2a_process_inbox(
        ...     tool_executor=lambda action, payload: my_tools.run(action, payload)
        ... )
        """
        messages = self.a2a_get_inbox()
        if not messages:
            return []

        processed = []
        for msg in messages:
            msg_id = msg.get("id")
            msg_type = msg.get("type", "notification")
            action = msg.get("action", "")
            payload = msg.get("payload", {})
            from_agent = msg.get("from_agent", "unknown")

            self._log(f"A2A: Processing {msg_type} from {from_agent}: {action}")

            # Map action to LocalClaw tool
            tool_name = self.a2a_map_action_to_tool(action)
            supported = tool_name is not None

            result = {
                "msg_id": msg_id,
                "from_agent": from_agent,
                "action": action,
                "type": msg_type,
                "status": "processed",
                "result": None,
                "error": None,
                "tool_name": tool_name,
                "supported": supported,
            }

            # Check if action is supported
            if msg_type == "request" and not supported:
                result["status"] = "unsupported"
                result["error"] = f"Tool not found: {action}"
                self._log(f"A2A: Unsupported action: {action}")
                
                # Send error response
                if auto_respond:
                    self.a2a_send(
                        to_agent=from_agent,
                        action=f"{action}_result",
                        payload={
                            "text": "",
                            "success": True,
                            "result": {"error": f"Tool not found: {action} (action: {action})"},
                            "original_msg_id": msg_id,
                        },
                        message_type="request",
                        reply_to=msg_id,
                    )

            # Only process request-type messages with supported actions
            elif msg_type == "request" and tool_executor:
                try:
                    exec_result = tool_executor(action, payload)
                    result["result"] = exec_result
                    self._log(f"A2A: Executed {action} -> {str(exec_result)[:100]}")

                    # Send response
                    if auto_respond:
                        self.a2a_send(
                            to_agent=from_agent,
                            action=f"{action}_result",
                            payload={
                                "success": True,
                                "result": exec_result,
                                "original_msg_id": msg_id,
                            },
                            message_type="response",
                            reply_to=msg_id,
                        )
                        self._log(f"A2A: Sent response to {from_agent}")

                except Exception as e:
                    result["status"] = "error"
                    result["error"] = str(e)
                    self._log(f"A2A: Error executing {action}: {e}")

                    # Send error response
                    if auto_respond:
                        self.a2a_send(
                            to_agent=from_agent,
                            action=f"{action}_error",
                            payload={
                                "success": False,
                                "error": str(e),
                                "original_msg_id": msg_id,
                            },
                            message_type="response",
                            reply_to=msg_id,
                        )

            elif msg_type == "notification":
                # Notifications don't need responses
                result["status"] = "acknowledged"

            elif msg_type == "response":
                # Responses are just informational
                result["status"] = "received"

            processed.append(result)

        # Acknowledge (remove) all processed messages
        if processed:
            msg_ids = [p["msg_id"] for p in processed]
            ack_result = self.a2a_acknowledge(msg_ids)
            if ack_result.get("success"):
                self._log(f"A2A: Acknowledged {len(msg_ids)} message(s)")

        return processed

    def a2a_process_with_tools(
        self,
        tools_registry: dict[str, Callable] | None = None,
    ) -> list[dict]:
        """
        Process A2A inbox using a tools registry.

        This is a convenience method that creates a tool executor from
        a registry of tool functions.

        Parameters
        ----------
        tools_registry : dict | None
            Dict mapping action names to callables.
            If None, uses built-in mapping.

        Returns
        -------
        list[dict]
            List of processed messages with results

        Example
        -------
        >>> tools = {
        ...     "read_file": lambda p: open(p["path"]).read(),
        ...     "execute_python": lambda p: exec(p["code"]),
        ... }
        >>> results = acp.a2a_process_with_tools(tools)
        """
        if tools_registry is None:
            # Default tools mapping
            tools_registry = {}

        def executor(action: str, payload: dict) -> Any:
            if action in tools_registry:
                return tools_registry[action](payload)
            else:
                return {"error": f"Unknown action: {action}"}

        return self.a2a_process_inbox(tool_executor=executor)


# ------------------------------------------------------------------ #
#  Convenience Factory                                                 #
# ------------------------------------------------------------------ #

def create_acp_agent(
    model: str,
    tools: Any = None,
    acp_url: str | None = None,
    agent_name: str = "LocalClaw",
    capabilities: list[str] | None = None,
    endpoint: str | None = None,
    on_hint: Callable[[dict], None] | None = None,
    on_nudge: Callable[[dict], None] | None = None,
    on_orphan: Callable[[list], None] | None = None,
    **agent_kwargs,
) -> tuple["Agent", ACPPlugin]:
    """
    Create a LocalClaw Agent pre-configured with ACP plugin.

    Returns both the agent and plugin for additional control.

    v1.0.4: Full spec compliance with hints, nudge, orphan support, and A2A.

    Usage:
        from localclaw.acp_plugin import create_acp_agent
        from localclaw.tools.builtins import BUILTIN_REGISTRY

        agent, acp = create_acp_agent(
            model="qwen2.5-coder:0.5b",
            tools=BUILTIN_REGISTRY,
            capabilities=["code", "research"],
        )

        # Bootstrap to register with ACP and A2A
        acp.bootstrap()

        result = agent.run("Calculate 2^20")
        print(f"Tokens used: {acp.get_session_tokens()}")

        # Send A2A message to another agent
        acp.a2a_send("Super-Z", "help_request", {"task": "debug code"})
    """
    # Import here to avoid circular imports
    from . import Agent

    plugin = ACPPlugin(
        base_url=acp_url,
        agent_name=agent_name,
        model_name=model,
        capabilities=capabilities,
        endpoint=endpoint,
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