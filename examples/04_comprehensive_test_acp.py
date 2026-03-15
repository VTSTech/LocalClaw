"""
examples/04_comprehensive_test_acp.py
------------------------------------
Comprehensive test suite with ACP integration.

Demonstrates:
- ACP activity logging during tests
- Token tracking per test category
- Batch operations for efficiency

Run from the project root:   python examples/04_comprehensive_test_acp.py
Or from the examples folder: python 04_comprehensive_test_acp.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, OllamaClient, StepResult
from localclaw.tools.builtins import make_builtin_registry
from localclaw.acp_plugin import ACPPlugin


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

MODEL = os.environ.get("LOCALCLAW_MODEL", "qwen2.5-coder:0.5b-instruct-q4_k_m")

TESTS = {
    "basic": [
        {
            "name": "Simple Addition",
            "prompt": "What is 2 + 2? Answer with just the number.",
            "check": lambda r: "4" in r,
        },
        {
            "name": "Multiplication",
            "prompt": "What is 7 times 8? Answer with just the number.",
            "check": lambda r: "56" in r,
        },
        {
            "name": "Capital City",
            "prompt": "What is the capital of Japan? Answer in one word.",
            "check": lambda r: "tokyo" in r.lower(),
        },
    ],
    "reasoning": [
        {
            "name": "Simple Reasoning",
            "prompt": "I have 10 apples. I eat 3 and give 2 to a friend. How many do I have left? Just the number.",
            "check": lambda r: "5" in r,
        },
        {
            "name": "Age Problem",
            "prompt": "Tom is 5 years older than Mary. Mary is 12. How old is Tom? Just the number.",
            "check": lambda r: "17" in r,
        },
    ],
    "code": [
        {
            "name": "Even Function",
            "prompt": "Write a Python function called is_even that takes a number and returns True if it's even.",
            "check": lambda r: "def is_even" in r and "return" in r,
        },
        {
            "name": "Add Function",
            "prompt": "Write a Python function called add that takes two numbers and returns their sum.",
            "check": lambda r: "def add" in r and "return" in r,
        },
    ],
}


def run_tests():
    """Run all test categories with ACP tracking."""
    client = OllamaClient()
    
    if not client.is_running():
        print("❌ Ollama is not running.")
        return
    
    models = client.list_models()
    if MODEL not in models:
        print(f"❌ Model '{MODEL}' not found. Available: {models}")
        return
    
    # ── Create ACP plugin and bootstrap ─────────────────────────────
    acp = ACPPlugin(
        agent_name="LocalClaw-TestRunner",
        model_name=MODEL,
        debug=os.environ.get("ACP_DEBUG", "").lower() in ("1", "true"),
    )
    
    bootstrap = acp.bootstrap(claim_primary=False)
    acp_connected = bootstrap.get("status") is not None
    
    print(f"\n{'='*60}")
    print(f"🧪 LocalClaw Comprehensive Test Suite (ACP)")
    print(f"   Model: {MODEL}")
    print(f"   ACP: {'connected' if acp_connected else 'unavailable'}")
    print(f"{'='*60}")
    
    # Log test session start
    if acp_connected:
        acp.log_chat("system", f"Test suite started with model {MODEL}", complete=True)
    
    total_passed = 0
    total_tests = 0
    total_time = 0
    
    for category, tests in TESTS.items():
        print(f"\n📋 {category.upper()} TESTS")
        print("-" * 40)
        
        # Log category start
        if acp_connected:
            acp.add_note("context", f"Starting {category} tests ({len(tests)} tests)")
        
        # Create agent for this category
        agent = Agent(
            model=MODEL,
            client=client,
            system_prompt="You are a helpful assistant. Be concise and accurate.",
            max_steps=6,
            model_options={
                "temperature": 0.0,
                "num_ctx": 1024,
                "num_predict": 128,
            },
        )
        
        for test in tests:
            total_tests += 1
            print(f"\n  🔮 {test['name']}")
            
            # Log test to ACP
            if acp_connected:
                acp.log_user_message(f"[TEST] {test['name']}: {test['prompt']}")
            
            t0 = time.time()
            try:
                response = agent.chat(test["prompt"])
                elapsed = time.time() - t0
                total_time += elapsed
                
                passed = test["check"](response)
                total_passed += int(passed)
                
                status = "✅ PASS" if passed else "❌ FAIL"
                preview = response[:60].replace("\n", " ")
                print(f"  {status} ({elapsed:.1f}s): {preview}...")
                
                # Log result to ACP
                if acp_connected:
                    acp.log_assistant_message(f"[{'PASS' if passed else 'FAIL'}] {response[:200]}")
                
                if not passed:
                    print(f"       Full response: {response}")
            except Exception as e:
                total_time += 60
                print(f"  ❌ ERROR: {e}")
                if acp_connected:
                    acp.log_assistant_message(f"[ERROR] {str(e)[:200]}")
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}")
    pass_rate = total_passed / total_tests * 100 if total_tests > 0 else 0
    print(f"  Tests: {total_passed}/{total_tests} passed ({pass_rate:.0f}%)")
    print(f"  Time: {total_time:.1f}s total, {total_time/total_tests:.1f}s avg")
    
    # ACP token summary
    if acp_connected:
        agent_tokens = acp.get_agent_tokens()
        status = acp.get_status()
        print(f"\n  ACP Session Tokens: {status.get('session_tokens', 0)}")
        print(f"  This Agent Tokens: {agent_tokens}")
        
        # Add summary note
        acp.add_note("context", f"Test suite complete: {total_passed}/{total_tests} passed ({pass_rate:.0f}%)")
    
    if pass_rate >= 70:
        print(f"\n✅ Model '{MODEL}' is working well!")
    elif pass_rate >= 50:
        print(f"\n⚠️  Model '{MODEL}' has some issues but usable.")
    else:
        print(f"\n❌ Model '{MODEL}' needs improvement or replacement.")


if __name__ == "__main__":
    run_tests()
