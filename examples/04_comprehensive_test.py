"""
examples/04_comprehensive_test.py
---------------------------------
Comprehensive test suite for LocalClaw with detailed output.
Tests multiple capabilities: Q&A, reasoning, tools, code generation.

Run from the project root:   python examples/04_comprehensive_test.py
Or from the examples folder: python 04_comprehensive_test.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, OllamaClient, StepResult
from localclaw.tools.builtins import make_builtin_registry


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Model to test (set via environment or default)
MODEL = os.environ.get("LOCALCLAW_MODEL", "qwen2.5-coder:0.5b-instruct-q4_k_m")

# Test categories
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


def print_step(step: StepResult):
    """Print step information for verbose mode."""
    if step.type == "tool_call":
        args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
        print(f"    🔧 Tool: {step.tool_name}({args})")
    elif step.type == "tool_result":
        preview = step.content[:80] + "..." if len(step.content) > 80 else step.content
        print(f"    📦 Result: {preview}")


def run_tests():
    """Run all test categories."""
    client = OllamaClient()
    
    if not client.is_running():
        print("❌ Ollama is not running.")
        return
    
    models = client.list_models()
    if MODEL not in models:
        print(f"❌ Model '{MODEL}' not found. Available: {models}")
        return
    
    print(f"\n{'='*60}")
    print(f"🧪 LocalClaw Comprehensive Test Suite")
    print(f"   Model: {MODEL}")
    print(f"{'='*60}")
    
    total_passed = 0
    total_tests = 0
    total_time = 0
    
    for category, tests in TESTS.items():
        print(f"\n📋 {category.upper()} TESTS")
        print("-" * 40)
        
        # Create agent for this category
        agent = Agent(
            model=MODEL,
            client=client,
            system_prompt="You are a helpful assistant. Be concise and accurate.",
            max_steps=6,
            on_step=print_step,
            model_options={
                "temperature": 0.0,     # Deterministic for tests
                "num_ctx": 1024,        # Moderate context
                "num_predict": 128,     # Short test answers
            },
        )
        
        for test in tests:
            total_tests += 1
            print(f"\n  🔮 {test['name']}")
            
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
                
                if not passed:
                    print(f"       Full response: {response}")
            except Exception as e:
                total_time += 60
                print(f"  ❌ ERROR: {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}")
    pass_rate = total_passed / total_tests * 100 if total_tests > 0 else 0
    print(f"  Tests: {total_passed}/{total_tests} passed ({pass_rate:.0f}%)")
    print(f"  Time: {total_time:.1f}s total, {total_time/total_tests:.1f}s avg")
    
    if pass_rate >= 70:
        print(f"\n✅ Model '{MODEL}' is working well!")
    elif pass_rate >= 50:
        print(f"\n⚠️  Model '{MODEL}' has some issues but usable.")
    else:
        print(f"\n❌ Model '{MODEL}' needs improvement or replacement.")


if __name__ == "__main__":
    run_tests()
