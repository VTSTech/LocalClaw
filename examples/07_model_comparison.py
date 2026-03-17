"""
examples/07_model_comparison.py
-------------------------------
Compare all available small models (<=1B parameters) on standard tests.

Run from the project root:   python examples/07_model_comparison.py
Or from the examples folder: python 07_model_comparison.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import sys
import os
import time
import re
import json
import unicodedata
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, get_default_client, LOCALCLAW_BACKEND
from localclaw.tools.builtins import make_builtin_registry
from localclaw.model_discovery import get_available_models

BACKEND_NAME = LOCALCLAW_BACKEND.upper()


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, remove accents, strip whitespace."""
    # Normalize unicode (NFD splits accents from base chars)
    normalized = unicodedata.normalize('NFD', text.lower())
    # Remove combining characters (accents)
    without_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return without_accents.strip()


# Verbosity level: 0=minimal, 1=show failures, 2=show all responses
VERBOSITY = 2

# Models discovered dynamically at runtime
# Will be populated from available models (no hardcoded list)
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
# Prompts optimized for small models (≤1.5B parameters)
TESTS = [
    # === SIMPLE MATH (3 tests) ===
    ("Math: Multiply", "What is 7 * 8? Answer with just the number.", None, "56"),
    ("Math: Add", "What is 25 + 17? Answer with just the number.", None, "42"),
    ("Math: Divide", "What is 144 / 12? Answer with just the number.", None, "12"),

    # === REASONING (3 tests) - multi-step thinking ===
    ("Reasoning: Apples", "I have 10 apples. I give 3 to Bob and 2 to Alice. How many apples do I have left? Answer with just the number.", None, "5"),
    ("Reasoning: Sequence", "What comes next in this sequence: 2, 4, 6, 8, ? Answer with just the number.", None, "10"),
    ("Reasoning: Logic", "All cats are animals. Fluffy is a cat. What category does Fluffy belong to? Answer with one word.", None, "animal"),

    # === KNOWLEDGE (3 tests) ===
    ("Knowledge: Japan", "What is the capital of Japan? Answer with one word.", None, "tokyo"),
    ("Knowledge: France", "What is the capital of France? Answer with one word.", None, "paris"),
    ("Knowledge: Brazil", "What is the capital of Brazil? Answer with one word.", None, "brasilia"),

    # === CALC TOOL (3 tests) - tool usage ===
    ("Calc: Multiply", "Use the calculator tool to compute 15 times 8.", ["calculator"], "120"),
    ("Calc: Divide", "Use the calculator tool to compute 100 divided by 4.", ["calculator"], "25"),
    ("Calc: Power", "Use the calculator tool to compute 2 to the power of 10.", ["calculator"], "1024"),

    # === CODE (3 tests) - code generation ===
    ("Code: is_even", "Write a Python function called is_even(n) that returns True if n is even.", None, "def"),
    ("Code: reverse", "Write a Python function called reverse_string(s) that returns the reversed string.", None, "def"),
    ("Code: max_num", "Write a Python function called find_max(numbers) that returns the largest number in a list.", None, "def"),
]


def test_model(client, model: str) -> dict:
    """Test a single model and return results."""
    print(f"\n{'='*60}")
    print(f"🧪 Testing: {model}")
    print(f"{'='*60}")
    
    results = {"model": model, "passed": 0, "total": len(TESTS), "time": 0, "tests": {}, "categories": {}}
    current_category = None
    category_passed = 0
    category_total = 0
    
    for test_name, prompt, tools, expected in TESTS:
        # Extract category from test name
        category = test_name.split(":")[0]
        
        # Print category header when entering new category
        if category != current_category:
            if current_category is not None:
                # Save previous category score
                results["categories"][current_category] = {"passed": category_passed, "total": category_total}
            current_category = category
            category_passed = 0
            category_total = 0
            print(f"\n  📁 {category}")
        
        print(f"    • {test_name.split(': ')[1]}...", end=" ", flush=True)
        category_total += 1
        
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
                    "temperature": 0.0,      # Deterministic
                    "num_ctx": 512,        # Small context for short answers
                    "num_predict": 64,     # Most answers are 1-10 tokens
                },
            )
            
            t0 = time.time()
            response = agent.chat(prompt)
            elapsed = time.time() - t0
            results["time"] += elapsed
            
            response_norm = normalize_text(response)
            expected_norm = normalize_text(expected)
            passed = expected_norm in response_norm
            
            # Check for near-misses (correct number but with extra text)
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
                "response": response,  # Full response
                "response_norm": response_norm,
                "expected": expected,
                "expected_norm": expected_norm
            }
            
            if passed:
                print(f"✅ ({elapsed:.1f}s)")
                if VERBOSITY >= 2:
                    print(f"      📝 Found '{expected}' in: {response[:100].replace(chr(10), ' ')}")
            elif near_miss:
                print(f"⚠️ NEAR-MISS ({elapsed:.1f}s)")
                print(f"      ⚠️ Expected '{expected}' found in numbers: {numbers}")
                print(f"      📝 RESPONSE: {response[:100].replace(chr(10), ' ')}")
            else:
                print(f"❌ ({elapsed:.1f}s)")
                if VERBOSITY >= 1:
                    print(f"      ❌ EXPECTED: '{expected}' (norm: '{expected_norm}')")
                    print(f"      📝 RESPONSE: {response[:100].replace(chr(10), ' ')}")
                    print(f"      📝 NORMALIZED: '{response_norm}''")
                
        except Exception as e:
            results["time"] += 60  # penalty for errors
            results["tests"][test_name] = {"passed": False, "error": str(e)[:100]}
            print(f"❌ ERROR: {str(e)[:50]}")
    
    # Save last category
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
    
    return results


def main():
    client = get_default_client()
    
    if not client.is_running():
        print(f"❌ {BACKEND_NAME} is not running.")
        if LOCALCLAW_BACKEND == "bitnet":
            print("   Start llama-server from bitnet.cpp directory")
        else:
            print("   Start it with: ollama serve")
        return
    
    available = get_available_models(client)
    print(f"\n🦞 LocalClaw Model Comparison")
    print(f"   Backend: {BACKEND_NAME}")
    print(f"   Available models: {', '.join(available)}")
    
    # Use all available models if MODELS not specified
    if MODELS is None:
        models_to_test = available
    else:
        # Filter to available models
        models_to_test = [m for m in MODELS if any(m.split(':')[0] in a for a in available)]
    
    if not models_to_test:
        print("   ⚠️ No models to test!")
        return
    
    print(f"   Testing: {', '.join(models_to_test)}")
    
    # Clear old results - start fresh
    all_results = []
    
    for model in models_to_test:
        # Find the exact model name from available
        exact_name = next((a for a in available if model.split(':')[0] in a), model)
        result = test_model(client, exact_name)
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
    print(f"✨ BEST MODEL (<=1B): {winner['model']}")
    print(f"   Passed {winner['passed']}/{winner['total']} tests in {winner['time']:.1f}s")
    
    # Category breakdown for winner
    if winner.get("categories"):
        print(f"\n   📊 Category breakdown:")
        for cat, stats in winner["categories"].items():
            cat_rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
            bar = "█" * int(cat_rate / 10) + "░" * (10 - int(cat_rate / 10))
            print(f"      {cat:<12} [{bar}] {stats['passed']}/{stats['total']}")
    
    # Category champions
    print(f"\n{'='*60}")
    print("🏅 CATEGORY CHAMPIONS")
    print(f"{'='*60}")
    
    categories = ["Math", "Reasoning", "Knowledge", "Calc", "Code"]
    for cat in categories:
        best_for_cat = None
        best_score = -1
        for r in all_results:
            if cat in r.get("categories", {}):
                score = r["categories"][cat]["passed"]
                if score > best_score or (score == best_score and (best_for_cat is None or r["time"] < best_for_cat["time"])):
                    best_score = score
                    best_for_cat = r
        if best_for_cat:
            print(f"   {cat:<12} 🏆 {best_for_cat['model']} ({best_score}/3)")
    
    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "model_comparison_results.json")
    import json
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n📄 Results saved to: {output_path}")


if __name__ == "__main__":
    main()
