"""
examples/01_basic_agent.py
--------------------------
The simplest possible LocalClaw agent — no tools, just conversation.
Uses dynamic model discovery to find available models.

Works with either Ollama or BitNet backend (set LOCALCLAW_BACKEND env var).
Use --acp flag or LOCALCLAW_ACP=1 to enable ACP integration.

Run from the project root:   python examples/01_basic_agent.py
Or from the examples folder: python 01_basic_agent.py

With CLI:
  localclaw test 01
  localclaw test 01 --acp
  localclaw test 01 --use-mf-sys --model qwen2.5-coder:0.5b
"""

import sys
import os

# Ensure the project root (which contains the localclaw/ package) is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import (
    Agent,
    get_default_client,
    get_available_models,
    get_system_prompt,
    DEFAULT_MODEL,
    LOCALCLAW_BACKEND,
)

# Check for optional ACP support
USE_ACP = os.environ.get("LOCALCLAW_ACP", "0") == "1"
if USE_ACP:
    try:
        from localclaw import ACPPlugin
    except ImportError:
        print("⚠️ ACP requested but ACPPlugin not available")
        USE_ACP = False

# Check for debug mode
DEBUG = os.environ.get("LOCALCLAW_DEBUG", "0") == "1"

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

# ── 2. Create ACP plugin if requested ─────────────────────────────
# Use model from env var or default
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

acp = None
if USE_ACP:
    acp = ACPPlugin(
        agent_name="LocalClaw-Basic",
        model_name=MODEL,
        debug=DEBUG,
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
    system_prompt=get_system_prompt(
        MODEL, 
        client=client,
        default_prompt="You are a concise and helpful assistant. Keep answers brief."
    ),
    model_options={
        "temperature": 0.7,
        "num_ctx": 1024,
        "num_predict": 256,
    },
    debug=DEBUG,
)
print(f"   Using model: {agent.model}\n")

# ── 4. Single-turn chat ────────────────────────────────────────────
prompt = "What is the capital of France, and why is it historically significant?"
if acp:
    acp.log_user_message(prompt)

answer = agent.chat(prompt)
print("Answer:", answer)

if acp:
    acp.log_assistant_message(answer)

# ── 5. Multi-turn conversation (memory is retained) ────────────────
print("\n--- Multi-turn conversation ---")
prompt2 = "My name is Alex."
if acp:
    acp.log_user_message(prompt2)
agent.chat(prompt2)
if acp:
    acp.log_assistant_message("Name noted")

prompt3 = "What's my name?"
if acp:
    acp.log_user_message(prompt3)
response = agent.chat(prompt3)
if acp:
    acp.log_assistant_message(response)
print("Agent remembers:", response)

# ── 6. Streaming ───────────────────────────────────────────────────
print("\n--- Streaming response ---")
prompt4 = "Tell me a one-sentence joke about programming."
if acp:
    acp.log_user_message(prompt4)

print("Agent: ", end="", flush=True)
full_response = ""
for token in agent.stream(prompt4):
    print(token, end="", flush=True)
    full_response += token
print()

if acp:
    acp.log_assistant_message(full_response)

# ── 7. Session summary ───────────────────────────────────────────
if acp:
    print("\n--- Session complete ---")
    tokens = acp.get_session_tokens()
    print(f"   Session tokens: {tokens}")
    print("   ACP session left active for other agents")
