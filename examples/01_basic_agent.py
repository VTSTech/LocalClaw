"""
examples/01_basic_agent.py
--------------------------
The simplest possible LocalClaw agent — no tools, just conversation.

Run from the project root:   python examples/01_basic_agent.py
Or from the examples folder: python 01_basic_agent.py
"""

import sys
import os

# Ensure the project root (which contains the localclaw/ package) is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, OllamaClient

# ── 1. Verify Ollama is running ────────────────────────────────────
client = OllamaClient()
if not client.is_running():
    print("❌  Ollama is not running. Start it with: ollama serve")
    sys.exit(1)

print("✓  Ollama is running")
print(f"   Available models: {client.list_models()}\n")

# ── 2. Create an agent ─────────────────────────────────────────────
agent = Agent(
    model="qwen2.5-coder:0.5b-instruct-q4_k_m",          # change to any model you have pulled
    system_prompt="You are a concise and helpful assistant. Keep answers brief.",
    model_options={"temperature": 0.7},
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