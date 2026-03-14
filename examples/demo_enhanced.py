#!/usr/bin/env python3
"""
🦞 LocalClaw R02 — Enhanced Features Demo

Demonstrates:
  • Extended tools (JSON, text processing, etc.)
  • Enhanced orchestrator with parallel mode
  • Streaming ACP plugin with cost tracking
  • Session health monitoring

Uses centralized config from localclaw/config.py

Run with: python demo_enhanced.py
"""

import sys
import os
import time

# Add LocalClaw package to path (parent directory)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import (
    Agent, Orchestrator, AgentCard, ToolRegistry,
    ACP_BASE_URL, DEFAULT_MODEL
)
from localclaw.tools.builtins import BUILTIN_REGISTRY
from localclaw.tools.extended import EXTENDED_TOOLS
from localclaw.core.orchestrator_enhanced import Orchestrator as EnhancedOrchestrator, AgentCard as EnhancedAgentCard
from localclaw.acp_streaming import ACPStreamingPlugin

print(f"""
╔═══════════════════════════════════════════════════════════════════╗
║     🦞 LocalClaw R02 — Enhanced Features Demo                     ║
╠═══════════════════════════════════════════════════════════════════╣
║  • Extended Tools: JSON, text processing, regex, templates        ║
║  • Enhanced Orchestrator: Router, Pipeline, Parallel modes        ║
║  • ACP Streaming Plugin: Cost tracking, health monitoring         ║
║                                                                   ║
║  Using centralized config - Model: {DEFAULT_MODEL:<27} ║
╚═══════════════════════════════════════════════════════════════════╝
""")


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO 1: Extended Tools
# ═══════════════════════════════════════════════════════════════════════════════

def demo_extended_tools():
    print("\n" + "="*60)
    print("DEMO 1: Extended Tools")
    print("="*60)
    
    # Combine built-in + extended tools
    registry = ToolRegistry()
    registry._tools.update(BUILTIN_REGISTRY._tools)
    registry._tools.update(EXTENDED_TOOLS._tools)
    
    agent = Agent(
        model=DEFAULT_MODEL,
        tools=registry,
        system_prompt="You have many tools. Use json_extract to parse JSON.",
        model_options={"num_ctx": 2048}
    )
    
    print("\nTest: Parse JSON and extract a value")
    
    test_json = '{"users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]}'
    
    run = agent.run(f"Parse this JSON and tell me Alice's age: {test_json}")
    print(f"Answer: {run.final_answer}")
    run.print_trace()
    
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO 2: Parallel Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

def demo_parallel_orchestrator():
    print("\n" + "="*60)
    print("DEMO 2: Parallel Orchestrator")
    print("="*60)
    
    analyzer = Agent(
        model=DEFAULT_MODEL,
        system_prompt="Analyze the problem. Be brief.",
        model_options={"num_ctx": 2048, "num_predict": 128}
    )
    
    solver = Agent(
        model=DEFAULT_MODEL,
        system_prompt="Solve the problem. Show the answer.",
        model_options={"num_ctx": 2048, "num_predict": 128}
    )
    
    reviewer = Agent(
        model=DEFAULT_MODEL,
        system_prompt="Review the answer. Confirm if correct.",
        model_options={"num_ctx": 2048, "num_predict": 128}
    )
    
    orch = EnhancedOrchestrator(
        agents=[
            EnhancedAgentCard("analyzer", analyzer, "Problem analysis", timeout=30),
            EnhancedAgentCard("solver", solver, "Problem solving", timeout=30),
            EnhancedAgentCard("reviewer", reviewer, "Answer review", timeout=30),
        ],
        mode="parallel",
        merge_strategy="concat",
        timeout=60
    )
    
    print("\nRunning agents in parallel on: 'What is 15 squared?'")
    start = time.time()
    
    result = orch.run("What is 15 squared?")
    
    print(f"\nTotal time: {time.time() - start:.1f}s")
    result.print_summary()
    
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO 3: ACP Streaming with Cost Tracking
# ═══════════════════════════════════════════════════════════════════════════════

def demo_acp_streaming():
    print("\n" + "="*60)
    print("DEMO 3: ACP Streaming with Cost Tracking")
    print("="*60)
    
    # Create streaming plugin (uses config defaults)
    plugin = ACPStreamingPlugin(
        agent_name="LocalClaw-Demo",
        model="local",  # Local model = free
        token_budget=50000,
        debug=True,
        enabled=True
    )
    
    status = plugin.get_status()
    if "error" in status:
        print(f"ACP not connected: {status['error']}")
        print("Skipping ACP demo...")
        return False
    
    print(f"ACP connected: {status.get('session_tokens', 0)} tokens used")
    print(f"Health score: {plugin.health.health_score:.1%}")
    
    tools = BUILTIN_REGISTRY.subset(["calculator"])
    
    agent = Agent(
        model=DEFAULT_MODEL,
        tools=tools,
        on_step=plugin.on_step,
        system_prompt="Use calculator for math.",
        model_options={"num_ctx": 2048}
    )
    
    print("\nSending: 'Calculate 7 to the power of 8'")
    
    try:
        run = agent.run("What is 7 to the power of 8? Use calculator.")
        print(f"\nAnswer: {run.final_answer}")
        
        print(f"\nPlugin Summary:")
        for k, v in plugin.summary.items():
            print(f"  {k}: {v}")
        
        return True
        
    except StopIteration as e:
        print(f"STOPPED: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    results = []
    
    results.append(("Extended Tools", demo_extended_tools()))
    results.append(("Parallel Orchestrator", demo_parallel_orchestrator()))
    results.append(("ACP Streaming", demo_acp_streaming()))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} demos passed")


if __name__ == "__main__":
    main()
