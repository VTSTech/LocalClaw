"""
examples/04_comprehensive_test_acp.py
--------------------------------------
Comprehensive test suite for LocalClaw with ACP logging.
Tests multiple capabilities: Q&A, reasoning, tools, code generation.

Run from the project root:   python examples/04_comprehensive_test_acp.py
Or from the examples folder: python 04_comprehensive_test_acp.py

Prerequisites:
- ACP server running (python VTSTech-GLMACP.py)
- Ollama running with a model pulled

Environment variables:
- LOCALCLAW_MODEL: Model name (default: qwen2.5-coder:0.5b-instruct-q4_k_m)
- ACP_HOST: ACP server address (default: 127.0.0.1:8766)
  Can be: "127.0.0.1:8766" or "http://127.0.0.1:8766" or "hostname:8766"

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


# ═══════════════════════════════════════════════════════════════════════════════
# COMBINED CALLBACK: Verbose Print + ACP Logging
# ═══════════════════════════════════════════════════════════════════════════════

def make_on_step_callback(acp_plugin):
    """Create a combined callback: verbose print + ACP logging."""
    def on_step(step: StepResult):
        # Print to console (verbose)
        if step.type == "tool_call":
            args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
            print(f"    🔧  Tool: {step.tool_name}({args})")
        elif step.type == "tool_result":
            preview = step.content[:80] + "..." if len(step.content) > 80 else step.content
            print(f"    📦  Result: {preview}")
        elif step.type == "final":
            preview = step.content[:60] + "..." if len(step.content) > 60 else step.content
            print(f"    ✨  Final: {preview}")
        
        # Log to ACP
        if acp_plugin:
            acp_plugin.on_step(step)
    
    return on_step


def run_tests():
    """Run all test categories with ACP logging."""
    
    # Check Ollama
    client = OllamaClient()
    if not client.is_running():
        print("❌  Ollama is not running.")
        print("   Start with: ollama serve")
        return
    
    models = client.list_models()
    if MODEL not in models:
        print(f"❌  Model '{MODEL}' not found. Available: {models}")
        print(f"   Pull with: ollama pull {MODEL}")
        return
    
    # Check ACP
    print(f"Connecting to ACP at {ACP_HOST}:{ACP_PORT}...")
    acp = ACPPlugin(host=ACP_HOST, port=ACP_PORT)
    status = acp.get_status()
    
    if "error" in status:
        print(f"⚠️  ACP not available: {status['error']}")
        print("   Tests will run without ACP logging.")
        print("   Start ACP with: python VTSTech-GLMACP.py")
        acp = None
    else:
        print(f"✅  Connected to ACP")
        print(f"   Session tokens: {status.get('session_tokens', 0):,}")
    
    print(f"\n{'='*60}")
    print(f"🧪
    
    # Sync TODOs to ACP
    if acp:
        test_todos = []
        for category, tests in TESTS.items():
            for i, test in enumerate(tests):
                test_todos.append({
                    "id": f"{category}_{i}",
                    "content": f"{category}: {test['name']}",
                    "status": "pending",
                    "priority": "medium"
                })
        acp.sync_todos(test_todos)
    
    total_passed = 0
    total_tests = 0
    total_time = 0
    
    for category, tests in TESTS.items():
        print(f"\n📋
        # Create combined callback
        on_step = make_on_step_callback(acp)
        
        # Create agent for this category
        agent = Agent(
            model=MODEL,
            client=client,
            system_prompt="You are a helpful assistant. Be concise and accurate.",
            max_steps=6,
            on_step=on_step,
            model_options={
                "temperature": 0.0,     # Deterministic for tests
                "num_ctx": 1024,        # Moderate context
                "num_predict": 128,     # Short test answers
            },
        )
        
        for i, test in enumerate(tests):
            total_tests += 1
            print(f"\n  🔮  {test['name']}")
            
            # Update TODO status
            if acp:
                acp._request("/api/todos/update", "POST", {
                    "id": f"{category}_{i}",
                    "status": "in_progress"
                })
            
            t0 = time.time()
            try:
                response = agent.chat(test["prompt"])
                elapsed = time.time() - t0
                total_time += elapsed
                
                passed = test["check"](response)
                total_passed += int(passed)
                
                status = "✅ PASS" if passed else "❌   FAIL"
                preview = response[:60].replace("\n", " ")
                print(f"  {status} ({elapsed:.1f}s): {preview}...")
                
                if not passed:
                    print(f"       Full response: {response}")
                
                # Update TODO with result
                if acp:
                    acp._request("/api/todos/update", "POST", {
                        "id": f"{category}_{i}",
                        "status": "completed" if passed else "pending",
                        "content": f"{category}: {test['name']} - {'PASS' if passed else 'FAIL'}"
                    })
                    
            except Exception as e:
                total_time += 60
                print(f"  ❌  ERROR: {e}")
                
                if acp:
                    acp.add_note("error", f"{test['name']}: {e}", "high")
    
    # Summary
    print(f"\n{'='*60}")
    print("📊  SUMMARY")
    print(f"{'='*60}")
    pass_rate = total_passed / total_tests * 100 if total_tests > 0 else 0
    print(f"  Tests: {total_passed}/{total_tests} passed ({pass_rate:.0f}%)")
    print(f"  Time: {total_time:.1f}s total, {total_time/total_tests:.1f}s avg")
    
    # ACP session summary
    if acp:
        tokens = acp.get_session_tokens()
        print(f"  ACP Tokens: {tokens:,}")
        acp.add_note("summary", f"Test run complete: {total_passed}/{total_tests} passed ({pass_rate:.0f}%)", "high")
    
    if pass_rate >= 70:
        print(f"\n✅  Model '{MODEL}' is working well!")
    elif pass_rate >= 50:
        print(f"\n⚠️  Model '{MODEL}' has some issues but usable.")
    else:
        print(f"\n❌
if __name__ == "__main__":
    run_tests()