"""
examples/07_model_comparison_acp.py
-----------------------------------
Compare all available models on standard tests with ACP logging.

Demonstrates:
- Multi-model benchmarking with ACP tracking
- Per-model activity logging
- Token tracking per agent/model
- Results aggregation

Run: python examples/07_model_comparison_acp.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import os
import sys
import time
import re
import unicodedata
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, get_default_client, LOCALCLAW_BACKEND
from localclaw.tools.builtins import make_builtin_registry
from localclaw.model_discovery import get_available_models
from localclaw.acp_plugin import ACPPlugin

BACKEND_NAME = LOCALCLAW_BACKEND.upper()


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, remove accents, strip whitespace."""
    normalized = unicodedata.normalize('NFD', text.lower())
    without_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return without_accents.strip()


# Verbosity level: 0=minimal, 1=show failures, 2=show all responses
VERBOSITY = 2

# Models discovered dynamically at runtime
MODELS = None  # None means "use all available"

# System prompts for different test types
SYSTEM_PROMPT_NO_TOOLS = """You are a helpful assistant. Follow these rules:
- Answer directly and concisely
- For math questions, provide only the numerical answer
- For knowledge questions, provide one-word answers when asked
- For reasoning, think step-by-step but give the final answer clearly
- For code requests, write clean, working Python functions"""

SYSTEM_PROMPT_WITH_TOOLS = """You are a helpful assistant with access to tools.
- Use tools when they can help answer the question
- For calculator requests, pass the complete mathematical expression to the calculator tool
- After using tools, report the results clearly and concisely
- Always execute tools rather than describing how to use them"""


# Test cases - 3 tests per category (15 total)
TESTS = [
    # === SIMPLE MATH (3 tests) ===
    ("Math: Multiply", "What is 7 * 8? Answer with just the number.", None, "56"),
    ("Math: Add", "What is 25 + 17? Answer with just the number.", None, "42"),
    ("Math: Divide", "What is 144 / 12? Answer with just the number.", None, "12"),

    # === REASONING (3 tests) ===
    ("Reasoning: Apples", "I have 10 apples. I give 3 to Bob and 2 to Alice. How many apples do I have left? Answer with just the number.", None, "5"),
    ("Reasoning: Sequence", "What comes next in this sequence: 2, 4, 6, 8, ? Answer with just the number.", None, "10"),
    ("Reasoning: Logic", "All cats are animals. Fluffy is a cat. What category does Fluffy belong to? Answer with one word.", None, "animal"),

    # === KNOWLEDGE (3 tests) ===
    ("Knowledge: Japan", "What is the capital of Japan? Answer with one word.", None, "tokyo"),
    ("Knowledge: France", "What is the capital of France? Answer with one word.", None, "paris"),
    ("Knowledge: Brazil", "What is the capital of Brazil? Answer with one word.", None, "brasilia"),

    # === CALC TOOL (3 tests) ===
    ("Calc: Multiply", "Use the calculator tool to compute 15 times 8.", ["calculator"], "120"),
    ("Calc: Divide", "Use the calculator tool to compute 100 divided by 4.", ["calculator"], "25"),
    ("Calc: Power", "Use the calculator tool to compute 2 to the power of 10.", ["calculator"], "1024"),

    # === CODE (3 tests) ===
    ("Code: is_even", "Write a Python function called is_even(n) that returns True if n is even.", None, "def"),
    ("Code: reverse", "Write a Python function called reverse_string(s) that returns the reversed string.", None, "def"),
    ("Code: max_num", "Write a Python function called find_max(numbers) that returns the largest number in a list.", None, "def"),
]


def test_model(client, model: str, acp: ACPPlugin) -> dict:
    """Test a single model and return results with ACP logging."""
    print(f"\n{'='*60}")
    print(f"🧪 Testing: {model}")
    print(f"{'='*60}")
    
    # Create model-specific ACP agent name
    # For paths like "Falcon3-1B-Instruct-1.58bit/ggml-model-i2_s.gguf", use the directory name
    if '/' in model:
        model_short = model.split('/')[0]  # "Falcon3-1B-Instruct-1.58bit"
    else:
        model_short = model.split(':')[0]  # For Ollama-style "model:tag"
    model_short = model_short[:25]  # Truncate if needed
    model_agent_name = f"LocalClaw-{model_short}"
    
    # Note: We log activities with agent_name in metadata - ACP will track per-agent tokens
    # No separate registration needed - activities are attributed by metadata.agent_name
    
    results = {"model": model, "passed": 0, "total": len(TESTS), "time": 0, "tests": {}, "categories": {}}
    current_category = None
    category_passed = 0
    category_total = 0
    
    for test_name, prompt, tools, expected in TESTS:
        category = test_name.split(":")[0]
        
        if category != current_category:
            if current_category is not None:
                results["categories"][current_category] = {"passed": category_passed, "total": category_total}
            current_category = category
            category_passed = 0
            category_total = 0
            print(f"\n  📁 {category}")
        
        print(f"    • {test_name.split(': ')[1]}...", end=" ", flush=True)
        category_total += 1
        
        # Log test start
        acp.log_user_message(f"[{model_short}] Test: {test_name}")
        
        try:
            registry = make_builtin_registry().subset(tools) if tools else None
            system_prompt = SYSTEM_PROMPT_WITH_TOOLS if tools else SYSTEM_PROMPT_NO_TOOLS
            
            agent = Agent(
                model=model,
                tools=registry,
                system_prompt=system_prompt,
                max_steps=5,
                client=client,
                model_options={
                    "temperature": 0.0,
                    "num_ctx": 512,
                    "num_predict": 64,
                },
            )
            
            t0 = time.time()
            response = agent.chat(prompt)
            elapsed = time.time() - t0
            results["time"] += elapsed
            
            response_norm = normalize_text(response)
            expected_norm = normalize_text(expected)
            passed = expected_norm in response_norm
            
            near_miss = False
            if not passed:
                numbers = re.findall(r'-?\d+\.?\d*', response_norm)
                if numbers and expected_norm.replace('.', '').replace('-', '').isdigit():
                    near_miss = expected_norm in numbers
            
            results["passed"] += int(passed)
            if passed:
                category_passed += 1
            results["tests"][test_name] = {
                "passed": passed,
                "near_miss": near_miss,
                "time": elapsed,
                "response": response,
            }
            
            # Log test result
            result_status = "PASS" if passed else ("NEAR-MISS" if near_miss else "FAIL")
            acp.log_assistant_message(f"[{model_short}] [{result_status}] {test_name}: {response[:50]}")
            
            if passed:
                print(f"✅ ({elapsed:.1f}s)")
                if VERBOSITY >= 2:
                    print(f"      📝 Found '{expected}' in: {response[:100].replace(chr(10), ' ')}")
            elif near_miss:
                print(f"⚠️ NEAR-MISS ({elapsed:.1f}s)")
                if VERBOSITY >= 1:
                    print(f"      ⚠️ Expected '{expected}' found in numbers: {numbers}")
            else:
                print(f"❌ ({elapsed:.1f}s)")
                if VERBOSITY >= 1:
                    print(f"      ❌ EXPECTED: '{expected}'")
                    print(f"      📝 RESPONSE: {response[:100].replace(chr(10), ' ')}")
                
        except Exception as e:
            results["time"] += 60
            results["tests"][test_name] = {"passed": False, "error": str(e)[:100]}
            acp.log_assistant_message(f"[{model_short}] [ERROR] {test_name}: {str(e)[:50]}")
            print(f"❌ ERROR: {str(e)[:50]}")
    
    if current_category is not None:
        results["categories"][current_category] = {"passed": category_passed, "total": category_total}
    
    pass_rate = results["passed"] / results["total"] * 100
    
    # Print category summary
    print(f"\n  📊 Categories:")
    for cat, stats in results["categories"].items():
        cat_rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
        bar = "█" * int(cat_rate / 10) + "░" * (10 - int(cat_rate / 10))
        print(f"     {cat:<12} [{bar}] {stats['passed']}/{stats['total']} ({cat_rate:.0f}%)")
    
    print(f"\n  📈 Total: {results['passed']}/{results['total']} ({pass_rate:.0f}%) in {results['time']:.1f}s")
    
    # Log final result for this model
    acp.add_note("context", f"{model_short}: {results['passed']}/{results['total']} ({pass_rate:.0f}%)", 
                importance="high")
    
    return results


def main():
    print("🦞 LocalClaw Model Comparison (ACP)")
    print("=" * 60)
    
    # ── Create and bootstrap ACP ─────────────────────────────────
    acp = ACPPlugin(
        agent_name="LocalClaw-Benchmark",
        model_name="comparison",
        debug=os.environ.get("ACP_DEBUG", "").lower() in ("1", "true"),
    )
    
    bootstrap = acp.bootstrap(claim_primary=False)
    acp_connected = bootstrap.get("status") is not None
    print(f"ACP: {'connected' if acp_connected else 'unavailable'}\n")
    
    client = get_default_client()
    
    if not client.is_running():
        print(f"❌ {BACKEND_NAME} is not running.")
        if LOCALCLAW_BACKEND == "bitnet":
            print("   Start llama-server from bitnet.cpp directory")
        else:
            print("   Start it with: ollama serve")
        return
    
    available = get_available_models(client)
    print(f"   Backend: {BACKEND_NAME}")
    print(f"   Available models: {', '.join(available)}")
    
    # Use all available models if MODELS not specified
    if MODELS is None:
        models_to_test = available
    else:
        models_to_test = [m for m in MODELS if any(m.split(':')[0] in a for a in available)]
    
    if not models_to_test:
        print("   ⚠️ No models to test!")
        return
    
    print(f"   Testing: {', '.join(models_to_test)}")
    
    if acp_connected:
        acp.log_chat("system", f"Benchmark started: {len(models_to_test)} models", complete=True)
    
    all_results = []
    
    for model in models_to_test:
        exact_name = next((a for a in available if model.split(':')[0] in a), model)
        result = test_model(client, exact_name, acp)
        all_results.append(result)
    
    # Rankings
    print(f"\n{'='*60}")
    print("🏆 RANKINGS (by pass rate, then speed)")
    print(f"{'='*60}")
    
    sorted_results = sorted(all_results, key=lambda x: (-x["passed"], x["time"]))
    
    for i, r in enumerate(sorted_results, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        pass_rate = r["passed"] / r["total"] * 100
        print(f"{medal} {r['model']:<40} {r['passed']}/{r['total']} ({pass_rate:.0f}%) - {r['time']:.1f}s")
    
    # Winner
    winner = sorted_results[0]
    print(f"\n{'='*60}")
    print(f"✨ BEST MODEL: {winner['model']}")
    print(f"   Passed {winner['passed']}/{winner['total']} tests in {winner['time']:.1f}s")
    
    if acp_connected:
        acp.log_chat("system", f"Benchmark complete. Winner: {winner['model']} ({winner['passed']}/{winner['total']})", 
                    complete=True)
    
    # Show session token usage
    status = acp.get_status()
    print(f"\n📊 Session tokens: {status.get('session_tokens', 0)}")
    agent_tokens = acp.get_agent_tokens()
    if agent_tokens:
        print("   Agent tokens:")
        for name, tokens in sorted(agent_tokens.items(), key=lambda x: -x[1]):
            print(f"      {name}: {tokens}")


if __name__ == "__main__":
    main()