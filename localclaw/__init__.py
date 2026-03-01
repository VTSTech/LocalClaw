"""LocalClaw Local agentic framework for Ollama"""

from .core.agent import Agent, AgentRun, StepResult
from .core.memory import Memory
from .core.tools import Tool, ToolRegistry, ToolParam
from .core.ollama_client import OllamaClient
from .core.orchestrator import Orchestrator, AgentCard

__all__ = [
    "Agent", "AgentRun", "StepResult",
    "Memory", "Tool", "ToolRegistry", "ToolParam",
    "OllamaClient", "Orchestrator", "AgentCard",
]

__version__ = "0.1.0"