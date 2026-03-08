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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, OllamaClient
from localclaw.tools.builtins import make_builtin_registry


# Models to test (1B parameters or less)
MODELS = [
    "smollm:135m",
    "qwen2.5:0.5b", 
    "qwen2.5-coder:0.5b-instruct-q4_k_m",
    "tinyllama:latest",
    "llama3.2:1b",
]

# Test cases
TESTS = [
    ("Simple Math", "What is 7 * 8? Answer with just the number.", None, "56"),
    ("Reasoning", "I have 10 apples, give 3 to Bob and 2 to Alice. How many left? Just number.", None, "5"),
    ("Capital", "What is the capital of Japan? One word.", None, "tokyo"),
    ("Calc Tool", "Use calculator to compute 15 * 8", ["calculator"], "120"),
    ("Code", "Write a Python function is_even(n) that returns True if n is even.", None, "def"),
]


def test_model(client: OllamaClient, model: str) -> dict:
    """Test a single model and return results."""
    print(f"\n{'='*60}")
    print(f"🧪 Testing: {model}")
    print(f"{'='*60}")
    
    results = {"model": model, "passed": 0, "total": len(TESTS), "time": 0, "tests": {}}
    
    for test_name, prompt, tools, expected in TESTS:
        print(f"  📋 {test_name}...", end=" ", flush=True)
        
        try:
            registry = make_builtin_registry().subset(tools) if tools else None
            
            agent = Agent(
                model=model,
                client=client,
                tools=registry,
                system_prompt="Be concise and accurate.",
                max_steps=5,
                model_options={"temperature": 0.1},
            )
            
            t0 = time.time()
            response = agent.chat(prompt)
            elapsed = time.time() - t0
            results["time"] += elapsed
            
            passed = expected.lower() in response.lower()
            results["passed"] += int(passed)
            results["tests"][test_name] = {"passed": passed, "time": elapsed, "response": response[:100]}
            
            status = "✅" if passed else "❌"
            print(f"{status} ({elapsed:.1f}s)")
            
            if not passed:
                print(f"      Expected '{expected}' in: {response[:80].replace(chr(10), ' ')}...")
                
        except Exception as e:
            results["time"] += 60  # penalty for errors
            results["tests"][test_name] = {"passed": False, "error": str(e)[:100]}
            print(f"❌ ERROR: {str(e)[:50]}")
    
    pass_rate = results["passed"] / results["total"] * 100
    print(f"\n  📊 Score: {results['passed']}/{results['total']} ({pass_rate:.0f}%) in {results['time']:.1f}s")
    
    return results


def main():
    client = OllamaClient()
    
    if not client.is_running():
        print("❌ Ollama is not running.")
        return
    
    available = client.list_models()
    print(f"\\n🦞 LocalClaw Model Comparison")
    print(f"   Available models: {', '.join(available)}")
    
    # Filter to available models
    models_to_test = [m for m in MODELS if any(m.split(':')[0] in a for a in available)]
    print(f"   Testing: {', '.join(models_to_test)}")
    
    all_results = []
    
    for model in models_to_test:
        # Find the exact model name from available
        exact_name = next((a for a in available if model.split(':')[0] in a), model)
        result = test_model(client, exact_name)
        all_results.append(result)
    
    # Rankings
    print(f"\\n{'='*60}")
    print("🏆 RANKINGS (by pass rate, then speed)")
    print(f"{'='*60}")
    
    sorted_results = sorted(all_results, key=lambda x: (-x["passed"], x["time"]))
    
    for i, r in enumerate(sorted_results, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        pass_rate = r["passed"] / r["total"] * 100
        print(f"{medal} {r['model']:<40} {r['passed']}/{r['total']} ({pass_rate:.0f}%) - {r['time']:.1f}s")
    
    # Winner
    winner = sorted_results[0]
    print(f"\\n✨ BEST MODEL (<=1B): {winner['model']}")
    print(f"   Passed {winner['passed']}/{winner['total']} tests in {winner['time']:.1f}s")
    
    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "model_comparison_results.json")
    import json
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\\n📄 Results saved to: {output_path}")


if __name__ == "__main__":
    main()
