"""
🦞 LocalClaw R02 — Central Configuration

Single source of truth for Ollama and ACP server URLs.
Change these values once to update all tests and examples.

Written by VTSTech — https://www.vts-tech.org
"""

import os

# ═══════════════════════════════════════════════════════════════════════════════
# OLLAMA CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
# Uncomment ONE of the following to switch between local and remote Ollama:

# LOCAL OLLAMA:
# OLLAMA_BASE_URL = "http://localhost:11434"

# REMOTE OLLAMA (cloudflare tunnel):
OLLAMA_BASE_URL = "https://ooo.trycloudflare.com/"

# Override via environment variable (takes precedence if set)
_ollama_env = os.environ.get("OLLAMA_BASE_URL")
if _ollama_env:
    OLLAMA_BASE_URL = _ollama_env

# ═══════════════════════════════════════════════════════════════════════════════
# BITNET CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
# Default for local bitnet.cpp llama-server
BITNET_BASE_URL = "http://localhost:8765"

# Override via environment variable (useful for Colab/ngrok)
_bitnet_env = os.environ.get("BITNET_BASE_URL")
if _bitnet_env:
    BITNET_BASE_URL = _bitnet_env
    
# ═══════════════════════════════════════════════════════════════════════════════
# ACP CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
# Uncomment ONE of the following to switch between local and remote ACP:

# LOCAL ACP:
# ACP_BASE_URL = "http://localhost:8766"

# REMOTE ACP (cloudflare tunnel):
ACP_BASE_URL = "https://aaa.trycloudflare.com/"

# Override via environment variable (takes precedence if set)
_acp_env = os.environ.get("ACP_BASE_URL")
if _acp_env:
    ACP_BASE_URL = _acp_env

# ACP Credentials
ACP_USER = os.environ.get("ACP_USER", "admin")
ACP_PASS = os.environ.get("ACP_PASS", "secret")


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT MODEL
# ═══════════════════════════════════════════════════════════════════════════════
# Default model for tests and examples
DEFAULT_MODEL = os.environ.get("LOCALCLAW_MODEL", "qwen2.5-coder:0.5b-instruct-q4_k_m")


# ═══════════════════════════════════════════════════════════════════════════════
# TUNNEL URL REFERENCE (for documentation/comments)
# ═══════════════════════════════════════════════════════════════════════════════
# Current tunnels:
#   Ollama Colab: https://ooo.trycloudflare.com
#   ACP Tunnel:    https://aaa.trycloudflare.com
#
# To update: Just change OLLAMA_BASE_URL and ACP_BASE_URL above
# ═══════════════════════════════════════════════════════════════════════════════
