"""
examples/01_basic_agent_acp.py
-------------------------------
The simplest possible LocalClaw agent — with ACP integration.
Uses dynamic model discovery.

Demonstrates:
- ACP bootstrap sequence
- Logging chat messages to ACP
- Graceful shutdown
- Dynamic model discovery
- Backend-agnostic (Ollama or BitNet)

Run from the project root:   python examples/01_basic_agent_acp.py
Or from the examples folder: python 01_basic_agent_acp.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import (
    Agent,
    get_default_client,
    get_available_models,
    DEFAULT_MODEL,
    LOCALCLAW_BACKEND,
    ACPPlugin,
)
from localclaw.model_discovery import pick_best_model

BACKEND_NAME = LOCALCLAW_BACKEND.upper()

# ── 1. Verify backend is running ────────────────────────────────────
client = get_default_client()
if not client.is_running():
    print(f"❌  {BACKEND_NAME} is not running.")
    if LOCALCLAW_BACKEND == "bitnet":
        print("   Start llama-server from bitnet.cpp directory")
    else:
        print("   Start it with: ollama serve")
    sys.exit(1)

print(f"✓  {BACKEND_NAME} is running")
models = get_available_models(client)
print(f"   Available models: {models}\n")

# ── 2. Create ACP plugin and bootstrap ─────────────────────────────
# Dynamically pick model
preferred = os.environ.get("LOCALCLAW_MODEL")
MODEL = pick_best_model(preferred=preferred, client=client)

if not MODEL:
    if models:
        MODEL = models[0]
    else:
        print(f"❌  No models available.")
        sys.exit(1)

acp = ACPPlugin(
    agent_name="LocalClaw-Basic",
    model_name=MODEL,
    debug=os.environ.get("ACP_DEBUG", "").lower() in ("1", "true"),
)

print(f"   ACP URL: {acp.base_url}")

# Bootstrap - MANDATORY first ACP call
bootstrap = acp.bootstrap(claim_primary=False)
if bootstrap.get("stop_flag"):
    print(f"   ⚠️ ACP STOP flag is set: {bootstrap.get('stop_reason')}")
print(f"   ACP Status: {'connected' if bootstrap.get('status') else 'unavailable'}")
if bootstrap.get("warnings"):
    for w in bootstrap["warnings"]:
        print(f"   ⚠️ {w}")

# ── 3. Create an agent ─────────────────────────────────────────────
agent = Agent(
    model=MODEL,
    client=client,  # Pass the backend-aware client!
    system_prompt="You are a concise and helpful assistant. Keep answers brief.",
    model_options={
        "temperature": 0.7,
        "num_ctx": 1024,
        "num_predict": 256,
    },
)
print(f"   Using model: {agent.model}\n")

# ── 4. Single-turn chat ────────────────────────────────────────────
prompt = "What is the capital of France, and why is it historically significant?"
acp.log_user_message(prompt)

answer = agent.chat(prompt)
print("Answer:", answer)

acp.log_assistant_message(answer)

# ── 5. Multi-turn conversation (memory is retained) ────────────────
print("\n--- Multi-turn conversation ---")
prompt2 = "My name is Alex."
acp.log_user_message(prompt2)
agent.chat(prompt2)
acp.log_assistant_message("Name noted")

prompt3 = "What's my name?"
acp.log_user_message(prompt3)
response = agent.chat(prompt3)
acp.log_assistant_message(response)
print("Agent remembers:", response)

# ── 6. Streaming ───────────────────────────────────────────────────
print("\n--- Streaming response ---")
prompt4 = "Tell me a one-sentence joke about programming."
acp.log_user_message(prompt4)

print("Agent: ", end="", flush=True)
full_response = ""
for token in agent.stream(prompt4):
    print(token, end="", flush=True)
    full_response += token
print()

acp.log_assistant_message(full_response)

# ── 7. Graceful shutdown ───────────────────────────────────────────
print("\n--- Session complete ---")
tokens = acp.get_session_tokens()
print(f"   Session tokens: {tokens}")
print("   ACP session left active for other agents")
