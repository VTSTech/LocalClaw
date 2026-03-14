"""
🦞 LocalClaw R02 - A minimal, hackable agentic framework for Ollama

Written by VTSTech
https://www.vts-tech.org
https://github.com/VTSTech/LocalClaw
"""

from .core.agent import Agent, AgentRun, StepResult
from .core.memory import Memory
from .core.tools import Tool, ToolRegistry, ToolParam
from .core.ollama_client import OllamaClient
from .core.orchestrator import Orchestrator, AgentCard
from .skills import SkillLoader, Skill, SkillRegistry
from .acp_plugin import ACPPlugin, create_acp_agent

# Import centralized config
from .config import (
    OLLAMA_BASE_URL,
    ACP_BASE_URL,
    ACP_USER,
    ACP_PASS,
    DEFAULT_MODEL,
)

__all__ = [
    "Agent", "AgentRun", "StepResult",
    "Memory", "Tool", "ToolRegistry", "ToolParam",
    "OllamaClient", "Orchestrator", "AgentCard",
    "SkillLoader", "Skill", "SkillRegistry",
    # Config
    "OLLAMA_BASE_URL", "ACP_BASE_URL", "ACP_USER", "ACP_PASS", "DEFAULT_MODEL",
]

__version__ = "0.2.0"
__author__ = "VTSTech"
__author_email__ = "veritas@vts-tech.org"
__url__ = "https://github.com/VTSTech/LocalClaw"
__website__ = "https://www.vts-tech.org"