#!/usr/bin/env python3
"""
🦞 LocalClaw R03 — Backend-Agnostic Example

This example works with EITHER Ollama OR BitNet backend.
Set LOCALCLAW_BACKEND environment variable to switch:

    # Use Ollama (default)
    export LOCALCLAW_BACKEND=ollama
    python 00_backend_demo.py

    # Use BitNet
    export LOCALCLAW_BACKEND=bitnet
    export BITNET_BASE_URL=http://localhost:8765
    python 00_backend_demo.py

Written by VTSTech — https://www.vts-tech.org
"""

import sys
import os

# Add LocalClaw package to path (parent directory)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import (
    Agent,
    get_default_client,
    get_available_models,
    DEFAULT_MODEL,
    LOCALCLAW_BACKEND,
    OLLAMA_BASE_URL,
    BITNET_BASE_URL,
)
from localclaw.tools.builtins import make_builtin_registry


def main():
    print(f"""
╔═══════════════════════════════════════════════════════════════════╗
║     🦞 LocalClaw R03 — Backend-Agnostic Demo                      ║
╠═══════════════════════════════════════════════════════════════════╣""")
    
    # Show current configuration
    print(f"║  Backend: {LOCALCLAW_BACKEND:<53} ║")
    print(f"║  Default Model: {DEFAULT_MODEL:<49} ║")
    
    if LOCALCLAW_BACKEND == "bitnet":
        print(f"║  BitNet URL: {BITNET_BASE_URL:<51} ║")
    else:
        print(f"║  Ollama URL: {OLLAMA_BASE_URL:<51} ║")
    
    print(f"╚═══════════════════════════════════════════════════════════════════╝")
    
    # Get client for configured backend
    print("\n📡 Connecting to backend...")
    client = get_default_client()
    
    if not client.is_running():
        print(f"❌ {LOCALCLAW_BACKEND.upper()} is not running!")
        if LOCALCLAW_BACKEND == "bitnet":
            print("   Start llama-server from bitnet.cpp directory")
        else:
            print("   Run: ollama serve")
        sys.exit(1)
    
    print(f"✅ Connected to {LOCALCLAW_BACKEND.upper()}")
    
    # List available models
    print("\n📋 Available models:")
    models = get_available_models(client)
    if models:
        for m in models:
            marker = " ← default" if m == DEFAULT_MODEL or DEFAULT_MODEL in m else ""
            print(f"   • {m}{marker}")
    else:
        print("   (no models found)")
        sys.exit(1)
    
    # Determine which model to use
    model = DEFAULT_MODEL
    if model not in models:
        # Try partial match
        for m in models:
            if model.split(":")[0] in m or m.split(":")[0] in model:
                model = m
                break
        else:
            # Use first available
            model = models[0]
    
    print(f"\n🤖 Using model: {model}")
    
    # Create agent with tools
    # Note: BitNet models don't support native tool calling,
    # so Agent will automatically use ReAct fallback
    tools = make_builtin_registry().subset(["calculator"])
    
    agent = Agent(
        model=model,
        tools=tools,
        system_prompt="You are a helpful math assistant. Use the calculator tool for arithmetic.",
        client=client,
        debug=True,  # Show tool calls
    )
    
    print("\n" + "=" * 60)
    print("🧪 Test: Calculate 15 * 8")
    print("=" * 60)
    
    result = agent.run("What is 15 times 8?")
    print(f"\n📝 Answer: {result.final_answer}")
    
    if result.steps:
        print("\n📊 Steps:")
        for step in result.steps:
            print(f"   {step}")
    
    print("\n" + "=" * 60)
    print("✅ Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
