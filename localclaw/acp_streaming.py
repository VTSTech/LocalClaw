"""
🦞 LocalClaw R02 — Enhanced ACP Streaming Plugin

Features:
  • Real-time streaming output capture
  • Better step attribution for multi-agent scenarios
  • Cost estimation (approximate token costs)
  • Session health monitoring
  • Graceful degradation when ACP unavailable

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import base64
import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator
from contextlib import contextmanager

# Import centralized config
from .config import ACP_BASE_URL, ACP_USER, ACP_PASS, DEFAULT_MODEL


# ═══════════════════════════════════════════════════════════════════════════════
# COST ESTIMATION (Approximate)
# ═══════════════════════════════════════════════════════════════════════════════

# Approximate costs per 1M tokens (as of 2024, will vary)
MODEL_COSTS = {
    # OpenAI
    "gpt-4": {"input": 30.0, "output": 60.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    # Anthropic
    "claude-3-opus": {"input": 15.0, "output": 75.0},
    "claude-3-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    # Local (free)
    "local": {"input": 0.0, "output": 0.0},
    # Default for unknown
    "default": {"input": 0.0, "output": 0.0},
}


@dataclass
class CostTracker:
    """Track approximate costs for API calls."""
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = "local"
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
    
    @property
    def estimated_cost(self) -> float:
        """Return estimated cost in USD."""
        costs = MODEL_COSTS.get(self.model, MODEL_COSTS["default"])
        input_cost = (self.input_tokens / 1_000_000) * costs["input"]
        output_cost = (self.output_tokens / 1_000_000) * costs["output"]
        return input_cost + output_cost
    
    def add(self, input_tokens: int, output_tokens: int):
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION HEALTH
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SessionHealth:
    """Track session health metrics."""
    acp_connected: bool = True
    last_successful_heartbeat: float = 0.0
    failed_requests: int = 0
    total_requests: int = 0
    last_error: str | None = None
    
    @property
    def health_score(self) -> float:
        """Return 0.0-1.0 health score."""
        if self.total_requests == 0:
            return 1.0
        success_rate = 1.0 - (self.failed_requests / self.total_requests)
        return success_rate
    
    @property
    def is_healthy(self) -> bool:
        return self.health_score > 0.8 and self.acp_connected


# ═══════════════════════════════════════════════════════════════════════════════
# ENHANCED ACP PLUGIN
# ═══════════════════════════════════════════════════════════════════════════════

class ACPStreamingPlugin:
    """
    Enhanced ACP plugin with streaming support and health monitoring.
    
    Features:
    - Real-time streaming capture
    - Cost estimation
    - Session health monitoring
    - Graceful degradation
    - Multi-agent attribution
    - Token budget tracking
    
    Parameters
    ----------
    base_url : str | None
        ACP server URL. Uses config.ACP_BASE_URL if None.
    user : str
        ACP username (default: from config)
    password : str
        ACP password (default: from config)
    agent_name : str
        Name for activity attribution
    model : str
        Model name for cost estimation
    token_budget : int
        Maximum tokens for this session (0 = unlimited)
    on_budget_exceeded : Callable | None
        Callback when budget exceeded
    enabled : bool
        Whether plugin is active
    debug : bool
        Enable debug output
    """
    
    def __init__(
        self,
        base_url: str | None = None,
        user: str | None = None,
        password: str | None = None,
        agent_name: str = "LocalClaw",
        model: str = "local",
        token_budget: int = 0,
        on_budget_exceeded: Callable | None = None,
        enabled: bool = True,
        debug: bool = False,
    ):
        self.base_url = (base_url or ACP_BASE_URL).rstrip("/")
        self.auth = base64.b64encode(f"{user or ACP_USER}:{password or ACP_PASS}".encode()).decode()
        self.agent_name = agent_name
        self.enabled = enabled
        self.debug = debug
        
        # Tracking
        self.costs = CostTracker(model=model)
        self.health = SessionHealth()
        self.token_budget = token_budget
        self.on_budget_exceeded = on_budget_exceeded
        
        # State
        self._activity_stack: list[str] = []
        self._step_count = 0
        self._last_stop_check = 0.0
        self._stop_flag = False
        self._stop_reason: str | None = None
        self._stream_buffer: list[str] = []
        
        # Tool name mapping
        self._action_map = {
            "read_file": "READ",
            "write_file": "WRITE",
            "shell": "BASH",
            "web_search": "SEARCH",
            "http_get": "API",
            "calculator": "SKILL",
            "python_repl": "SKILL",
            "json_extract": "SKILL",
            "text_process": "SKILL",
            "diff_compare": "SKILL",
            "template_fill": "SKILL",
            "data_transform": "SKILL",
        }
    
    # ------------------------------------------------------------------ #
    #  HTTP Methods                                                       #
    # ------------------------------------------------------------------ #
    
    def _log(self, msg: str):
        if self.debug:
            print(f"  [ACP] {msg}")
    
    def _request(self, endpoint: str, method: str = "GET", data: dict | None = None, timeout: float = 10.0) -> dict:
        """Make HTTP request with error handling."""
        if not self.enabled:
            return {"success": False, "error": "Plugin disabled"}
        
        self.health.total_requests += 1
        
        headers = {
            "Authorization": f"Basic {self.auth}",
            "Content-Type": "application/json",
        }
        
        url = f"{self.base_url}{endpoint}"
        body = json.dumps(data).encode() if data else None
        
        req = urllib.request.Request(url, headers=headers, method=method, data=body)
        
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode())
                self.health.last_successful_heartbeat = time.time()
                self.health.acp_connected = True
                return result
        except urllib.error.HTTPError as e:
            self.health.failed_requests += 1
            self.health.last_error = f"HTTP {e.code}"
            return {"success": False, "error": f"HTTP {e.code}"}
        except urllib.error.URLError as e:
            self.health.failed_requests += 1
            self.health.acp_connected = False
            self.health.last_error = str(e.reason)
            return {"success": False, "error": f"Connection: {e.reason}"}
        except Exception as e:
            self.health.failed_requests += 1
            self.health.last_error = str(e)
            return {"success": False, "error": str(e)}
    
    def _check_budget(self) -> bool:
        """Check if we're within token budget."""
        if self.token_budget <= 0:
            return True
        
        status = self._request("/api/status")
        if "error" in status:
            return True  # Assume OK if can't check
        
        current = status.get("session_tokens", 0)
        if current >= self.token_budget:
            if self.on_budget_exceeded:
                self.on_budget_exceeded(current, self.token_budget)
            return False
        return True
    
    def _check_stop_flag(self) -> bool:
        """Check if STOP was requested."""
        now = time.time()
        if (now - self._last_stop_check) < 2.0:
            return self._stop_flag
        
        self._last_stop_check = now
        status = self._request("/api/status")
        
        if status.get("stop_flag"):
            self._stop_flag = True
            self._stop_reason = status.get("stop_reason", "Stop requested")
            return True
        
        return False
    
    # ------------------------------------------------------------------ #
    #  Activity Logging                                                   #
    # ------------------------------------------------------------------ #
    
    def start_activity(self, action: str, target: str, details: str = "", priority: str = "medium") -> str | None:
        """Start a new activity and return its ID."""
        if not self.enabled or not self.health.acp_connected:
            return None
        
        resp = self._request("/api/action", "POST", {
            "action": action,
            "target": target[:200],  # Truncate
            "details": details[:500],
            "priority": priority,
            "metadata": {"agent_name": self.agent_name}
        })
        
        activity_id = resp.get("activity_id")
        if activity_id:
            self._activity_stack.append(activity_id)
            self._log(f"Started: {activity_id} ({action})")
        
        return activity_id
    
    def complete_activity(self, activity_id: str | None, result: str = "", content_size: int = 0):
        """Complete an activity."""
        if not activity_id or not self.enabled:
            return
        
        # Estimate output tokens
        if content_size:
            self.costs.add(0, content_size // 4)
        elif result:
            self.costs.add(0, len(result) // 4)
        
        self._request("/api/complete", "POST", {
            "activity_id": activity_id,
            "result": result[:500],
            "content_size": content_size
        })
        
        self._log(f"Completed: {activity_id}")
        
        # Remove from stack
        if activity_id in self._activity_stack:
            self._activity_stack.remove(activity_id)
    
    # ------------------------------------------------------------------ #
    #  Agent Callback (Main Integration)                                  #
    # ------------------------------------------------------------------ #
    
    def on_step(self, step) -> None:
        """
        Callback for LocalClaw Agent.
        
        Pass this to Agent(on_step=plugin.on_step)
        """
        if not self.enabled:
            return
        
        self._step_count += 1
        
        # Check stop
        if self._check_stop_flag():
            raise StopIteration(f"ACP STOP: {self._stop_reason}")
        
        # Check budget
        if not self._check_budget():
            raise StopIteration("Token budget exceeded")
        
        step_type = getattr(step, "type", None)
        
        if step_type == "tool_call":
            self._handle_tool_call(step)
        elif step_type == "tool_result":
            self._handle_tool_result(step)
        elif step_type == "final":
            self._handle_final(step)
    
    def _handle_tool_call(self, step):
        """Log tool call as activity."""
        tool_name = getattr(step, "tool_name", "unknown")
        tool_args = getattr(step, "tool_args", {}) or {}
        
        action = self._action_map.get(tool_name.lower(), tool_name.upper())
        target = self._format_target(tool_name, tool_args)
        
        activity_id = self.start_activity(action, target, f"Tool: {tool_name}")
        
        # Track input tokens
        if tool_args:
            args_str = json.dumps(tool_args)
            self.costs.add(len(args_str) // 4, 0)
    
    def _handle_tool_result(self, step):
        """Complete activity with result."""
        content = getattr(step, "content", "") or ""
        
        if self._activity_stack:
            activity_id = self._activity_stack.pop()
            self.complete_activity(activity_id, content[:500], len(content))
    
    def _handle_final(self, step):
        """Log final answer and clean up."""
        content = getattr(step, "content", "") or ""
        
        self._log(f"Final: {content[:100]}...")
        
        # Add as note
        if self.health.acp_connected:
            self._request("/api/notes/add", "POST", {
                "category": "context",
                "content": f"{self.agent_name}: {content[:400]}",
                "importance": "normal"
            })
        
        # Clean up orphaned activities
        while self._activity_stack:
            orphan_id = self._activity_stack.pop()
            self.complete_activity(orphan_id, "[Completed by final handler]")
    
    def _format_target(self, tool_name: str, args: dict) -> str:
        """Format tool args as target string."""
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
        elif tool_name == "python_repl":
            code = args.get("code", "")
            return code.split("\n")[0][:100]
        else:
            if args:
                return str(list(args.values())[0])[:100]
            return tool_name
    
    # ------------------------------------------------------------------ #
    #  Context Manager                                                    #
    # ------------------------------------------------------------------ #
    
    @contextmanager
    def track_operation(self, action: str, target: str):
        """Context manager for tracking an operation."""
        activity_id = self.start_activity(action, target)
        start_time = time.time()
        
        try:
            yield activity_id
        except Exception as e:
            if activity_id:
                self.complete_activity(activity_id, f"Error: {e}")
            raise
        finally:
            if activity_id and activity_id in self._activity_stack:
                elapsed = time.time() - start_time
                self.complete_activity(activity_id, f"Completed in {elapsed:.1f}s")
    
    # ------------------------------------------------------------------ #
    #  Utility Methods                                                    #
    # ------------------------------------------------------------------ #
    
    def get_status(self) -> dict:
        """Get ACP status."""
        return self._request("/api/status")
    
    def get_session_tokens(self) -> int:
        """Get current session token count."""
        status = self.get_status()
        return status.get("session_tokens", 0)
    
    def get_remaining_budget(self) -> int:
        """Get remaining tokens in budget."""
        if self.token_budget <= 0:
            return -1  # Unlimited
        current = self.get_session_tokens()
        return max(0, self.token_budget - current)
    
    def add_note(self, category: str, content: str, importance: str = "normal"):
        """Add a note to ACP."""
        self._request("/api/notes/add", "POST", {
            "category": category,
            "content": content,
            "importance": importance
        })
    
    def sync_todos(self, todos: list[dict]):
        """Sync TODO list to ACP."""
        for todo in todos:
            if "metadata" not in todo:
                todo["metadata"] = {}
            todo["metadata"]["agent_name"] = self.agent_name
        
        self._request("/api/todos/update", "POST", {"todos": todos})
    
    def reset(self):
        """Reset plugin state."""
        self._activity_stack.clear()
        self._step_count = 0
        self._stop_flag = False
        self._stop_reason = None
        self._stream_buffer.clear()
    
    @property
    def summary(self) -> dict:
        """Get plugin summary."""
        return {
            "agent_name": self.agent_name,
            "enabled": self.enabled,
            "health_score": self.health.health_score,
            "is_healthy": self.health.is_healthy,
            "total_tokens": self.costs.total_tokens,
            "estimated_cost_usd": self.costs.estimated_cost,
            "steps_logged": self._step_count,
            "pending_activities": len(self._activity_stack),
        }
