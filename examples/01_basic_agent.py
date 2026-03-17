"""
examples/01_basic_agent.py
--------------------------
The simplest possible LocalClaw agent — no tools, just conversation.
Uses dynamic model discovery to find available models.

Works with either Ollama or BitNet backend (set LOCALCLAW_BACKEND env var).

Run from the project root:   python examples/01_basic_agent.py
Or from the examples folder: python 01_basic_agent.py
"""

import sys
import os

# Ensure the project root (which contains the localclaw/ package) is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import (
    Agent,
    get_default_client,
    get_available_models,
    DEFAULT_MODEL,
    LOCALCLAW_BACKEND,
)

# ── 1. Verify backend is running ────────────────────────────────────
client = get_default_client()
BACKEND_NAME = LOCALCLAW_BACKEND.upper()

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

# ── 2. Create an agent ─────────────────────────────────────────────
# Use default model from config (respects LOCALCLAW_BACKEND)
# Set LOCALCLAW_MODEL env var to override
MODEL = os.environ.get("LOCALCLAW_MODEL", DEFAULT_MODEL)

# If default model not found, use first available
if MODEL not in models:
    for m in models:
        if MODEL.split(":")[0] in m or m.split(":")[0] in MODEL:
            MODEL = m
            break
    else:
        if models:
            MODEL = models[0]
        else:
            print(f"❌  No models available.")
            sys.exit(1)

agent = Agent(
    model=MODEL,
    system_prompt="You are a concise and helpful assistant. Keep answers brief.",
    model_options={
        "temperature": 0.7,
        "num_ctx": 1024,
        "num_predict": 256,
    },
)
print(f"   Using model: {agent.model}\n")

# ── 3. Single-turn chat ────────────────────────────────────────────
answer = agent.chat("What is the capital of France, and why is it historically significant?")
print("Answer:", answer)

# ── 4. Multi-turn conversation (memory is retained) ────────────────
print("\n--- Multi-turn conversation ---")
agent.chat("My name is Alex.")
response = agent.chat("What's my name?")
print("Agent remembers:", response)

# ── 5. Streaming ───────────────────────────────────────────────────
print("\n--- Streaming response ---")
print("Agent: ", end="", flush=True)
for token in agent.stream("Tell me a one-sentence joke about programming."):
    print(token, end="", flush=True)
print()
