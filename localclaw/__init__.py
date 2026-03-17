"""
🦞 LocalClaw R03 - A minimal, hackable agentic framework for Ollama and BitNet

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

# R03: BitNet backend support
try:
    from .bitnet_client import BitnetClient, KNOWN_MODELS
    _BITNET_AVAILABLE = True
except ImportError:
    _BITNET_AVAILABLE = False

# R02/R03 Enhancements
from .core.orchestrator_enhanced import Orchestrator as EnhancedOrchestrator, AgentCard as EnhancedAgentCard

__all__ = [
    "Agent", "AgentRun", "StepResult",
    "Memory", "Tool", "ToolRegistry", "ToolParam",
    "OllamaClient", "Orchestrator", "AgentCard",
    "SkillLoader", "Skill", "SkillRegistry",
    # R02/R03 Enhancements
    "EnhancedOrchestrator", "EnhancedAgentCard",
    "ACPPlugin",
    # R03: Model discovery
    "model_discovery",
]

# Conditionally export BitNet
if _BITNET_AVAILABLE:
    __all__.extend(["BitnetClient", "KNOWN_MODELS"])

__version__ = "0.3.0"
__author__ = "VTSTech"
__author_email__ = "contact@vts-tech.org"
__url__ = "https://github.com/VTSTech/LocalClaw"
__website__ = "https://www.vts-tech.org"