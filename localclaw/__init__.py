"""
🦞 LocalClaw R01 - A minimal, hackable agentic framework for Ollama

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

__all__ = [
    "Agent", "AgentRun", "StepResult",
    "Memory", "Tool", "ToolRegistry", "ToolParam",
    "OllamaClient", "Orchestrator", "AgentCard",
    "SkillLoader", "Skill", "SkillRegistry",
]

__version__ = "0.1.0"
__author__ = "VTSTech"
__author_email__ = "contact@vts-tech.org"
__url__ = "https://github.com/VTSTech/LocalClaw"
__website__ = "https://www.vts-tech.org"