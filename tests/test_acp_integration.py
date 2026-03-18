#!/usr/bin/env python3
"""
LocalClaw R03 + ACP Integration Test
====================================

Tests sub-agent orchestration with ACP monitoring.

Uses centralized config from localclaw/config.py

Written for VTSTech LocalClaw R03 + ACP v1.0.2
"""

import sys
import os
import time

# Add LocalClaw package to path (parent directory)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import (
    Agent, Orchestrator, AgentCard,
    ACPPlugin, create_acp_agent,
    ACP_BASE_URL, DEFAULT_MODEL
)
from localclaw.tools.builtins import BUILTIN_REGISTRY

print(f"""
╔═══════════════════════════════════════════════════════════════════╗
║     🦞 LocalClaw R03 + ACP Integration Test                        ║
╠═══════════════════════════════════════════════════════════════════╣
║  Using centralized config from localclaw/config.py                ║
║  Model:  {DEFAULT_MODEL:<48} ║
╚═══════════════════════════════════════════════════════════════════╝
""")

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: Basic Agent with ACP Plugin
# ═══════════════════════════════════════════════════════════════════════════════

def test_basic_agent():
    print("\n" + "="*60)
    print("TEST 1: Basic Agent with ACP Plugin")
    print("="*60)
    
    # Create ACP plugin (uses config defaults)
    acp = ACPPlugin(debug=True, agent_name="LocalClaw-Basic")
    
    status = acp.get_status()
    if "error" in status:
        print(f"WARNING: ACP not reachable: {status['error']}")
        return False
    
    print(f"ACP Connected: {status.get('session_tokens', 0)} tokens used")
    
    agent = Agent(
        model=DEFAULT_MODEL,
        system_prompt="You are a helpful assistant. Be concise.",
        on_step=acp.on_step,
        model_options={"num_ctx": 2048, "num_predict": 128}
    )
    
    print("\nSending: 'What is 2+2? Answer briefly.'")
    start = time.time()
    
    try:
        response = agent.chat("What is 2+2? Answer briefly.")
        elapsed = time.time() - start
        print(f"\nResponse ({elapsed:.1f}s): {response}")
        
        status = acp.get_status()
        print(f"ACP Tokens: {status.get('session_tokens', 0):,}")
        return True
        
    except StopIteration as e:
        print(f"STOPPED by ACP: {e}")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: Agent with Tools + ACP
# ═══════════════════════════════════════════════════════════════════════════════

def test_tool_agent():
    print("\n" + "="*60)
    print("TEST 2: Agent with Tools + ACP Monitoring")
    print("="*60)
    
    acp = ACPPlugin(debug=True, agent_name="LocalClaw-Tool")
    
    tools = BUILTIN_REGISTRY.subset(["calculator"])
    
    agent = Agent(
        model=DEFAULT_MODEL,
        tools=tools,
        system_prompt="You have a calculator tool. Use it for math questions.",
        on_step=acp.on_step,
        max_steps=5,
        model_options={"num_ctx": 2048}
    )
    
    print("\nSending: 'What is 25 times 17? Use the calculator.'")
    start = time.time()
    
    try:
        run = agent.run("What is 25 times 17? Use the calculator.")
        elapsed = time.time() - start
        
        print(f"\nAnswer ({elapsed:.1f}s): {run.final_answer}")
        run.print_trace()
        
        status = acp.get_status()
        print(f"ACP Tokens: {status.get('session_tokens', 0):,}")
        return True
        
    except StopIteration as e:
        print(f"STOPPED by ACP: {e}")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3: Multi-Agent Orchestrator + ACP
# ═══════════════════════════════════════════════════════════════════════════════

def test_orchestrator():
    print("\n" + "="*60)
    print("TEST 3: Multi-Agent Orchestrator + ACP")
    print("="*60)
    
    acp = ACPPlugin(debug=True, agent_name="LocalClaw-Orchestrator")
    
    coder = Agent(
        model=DEFAULT_MODEL,
        system_prompt="You write Python code. Be concise.",
        on_step=acp.on_step,
        model_options={"num_ctx": 2048, "num_predict": 256}
    )
    
    math_agent = Agent(
        model=DEFAULT_MODEL,
        system_prompt="You solve math problems. Be accurate.",
        on_step=acp.on_step,
        model_options={"num_ctx": 2048, "num_predict": 128}
    )
    
    orch = Orchestrator(
        agents=[
            AgentCard("coder", coder, "Writing Python code"),
            AgentCard("math", math_agent, "Solving math problems"),
        ],
        router_model=DEFAULT_MODEL,
        mode="router"
    )
    
    print("\nSending: 'Write a Python function to check if a number is even'")
    start = time.time()
    
    try:
        result = orch.run("Write a Python function to check if a number is even. Just the code.")
        elapsed = time.time() - start
        
        print(f"\nChosen Agent: {result.chosen_agent}")
        print(f"Time: {elapsed:.1f}s")
        print(f"Answer:\n{result.final_answer}")
        
        acp.add_note("insight", f"Orchestrator routed to {result.chosen_agent} agent")
        
        status = acp.get_status()
        print(f"ACP Tokens: {status.get('session_tokens', 0):,}")
        return True
        
    except StopIteration as e:
        print(f"STOPPED by ACP: {e}")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    results = []
    
    results.append(("Basic Agent", test_basic_agent()))
    results.append(("Tool Agent", test_tool_agent()))
    results.append(("Orchestrator", test_orchestrator()))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")

if __name__ == "__main__":
    main()
