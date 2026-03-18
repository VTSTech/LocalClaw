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

# Config exports
from .config import (
    OLLAMA_BASE_URL,
    BITNET_BASE_URL,
    ACP_BASE_URL,
    ACP_USER,
    ACP_PASS,
    DEFAULT_MODEL,
    LOCALCLAW_BACKEND,
)

# R03: BitNet backend support
try:
    from .bitnet_client import BitnetClient, KNOWN_MODELS
    _BITNET_AVAILABLE = True
except ImportError:
    _BITNET_AVAILABLE = False
    BitnetClient = None
    KNOWN_MODELS = []


def get_default_client():
    """
    Get the default client based on LOCALCLAW_BACKEND setting.
    
    Returns
    -------
    OllamaClient or BitnetClient
        The appropriate client for the configured backend.
    
    Examples
    --------
    >>> # With LOCALCLAW_BACKEND=ollama (default)
    >>> client = get_default_client()  # Returns OllamaClient
    
    >>> # With LOCALCLAW_BACKEND=bitnet
    >>> client = get_default_client()  # Returns BitnetClient
    """
    if LOCALCLAW_BACKEND == "bitnet":
        if not _BITNET_AVAILABLE:
            raise ImportError("BitNet backend requested but bitnet_client not available")
        return BitnetClient()
    else:
        return OllamaClient()


def get_available_models(client=None):
    """
    Get list of available models from the configured backend.
    
    Parameters
    ----------
    client : OllamaClient or BitnetClient, optional
        Client to use. Creates one via get_default_client() if not provided.
    
    Returns
    -------
    list[str]
        List of model names available on the backend.
    """
    if client is None:
        client = get_default_client()
    
    if not client.is_running():
        return []
    
    return client.list_models() or []

# R03 Enhancements
from .core.orchestrator_enhanced import Orchestrator as EnhancedOrchestrator, AgentCard as EnhancedAgentCard

__all__ = [
    # Core
    "Agent", "AgentRun", "StepResult",
    "Memory", "Tool", "ToolRegistry", "ToolParam",
    "OllamaClient", "Orchestrator", "AgentCard",
    # Skills
    "SkillLoader", "Skill", "SkillRegistry",
    # R03 Enhancements
    "EnhancedOrchestrator", "EnhancedAgentCard",
    "ACPPlugin",
    # R03: Backend-agnostic helpers
    "get_default_client",
    "get_available_models",
    "model_discovery",
    # Config exports
    "OLLAMA_BASE_URL",
    "BITNET_BASE_URL", 
    "ACP_BASE_URL",
    "ACP_USER",
    "ACP_PASS",
    "DEFAULT_MODEL",
    "LOCALCLAW_BACKEND",
]

# Conditionally export BitNet
if _BITNET_AVAILABLE:
    __all__.extend(["BitnetClient", "KNOWN_MODELS"])

__version__ = "0.3.0.4"
__author__ = "VTSTech"
__author_email__ = "contact@vts-tech.org"
__url__ = "https://github.com/VTSTech/LocalClaw"
__website__ = "https://www.vts-tech.org"