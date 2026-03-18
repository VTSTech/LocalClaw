"""
examples/08_robust_comparison_acp.py
------------------------------------
Robust model comparison with ACP logging and progress resumption.

Demonstrates:
- Incremental result saving with ACP tracking
- Multi-model benchmarking with resumability
- Per-model agent registration
- Detailed category breakdown

Run: python examples/08_robust_comparison_acp.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import sys
import os
import time
import json
import re
import unicodedata
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, get_default_client, LOCALCLAW_BACKEND
from localclaw.tools.builtins import make_builtin_registry
from localclaw.model_discovery import get_available_models
from localclaw.acp_plugin import ACPPlugin

BACKEND_NAME = LOCALCLAW_BACKEND.upper()


def normalize_text(text: str) -> str:
    """Normalize text: lowercase, remove accents."""
    normalized = unicodedata.normalize('NFD', text.lower())
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')


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


# Models discovered dynamically at runtime
SMALL_MODEL_INDICATORS = ["0.5b", "270m", "135m", "350m", "0.6b", "1b", "1.5b", "2b", "tiny", "mini", "micro", "small", "moe", "bitnet"]


def get_small_models(client) -> list[str]:
    """Get list of small models, or all available if none match."""
    available = get_available_models(client)
    small_models = []
    for model in available:
        model_lower = model.lower()
        if any(ind in model_lower for ind in SMALL_MODEL_INDICATORS):
            small_models.append(model)
    
    if not small_models:
        print("   ⚠️ No small models found by indicators, using all available")
        small_models = available
    
    return small_models


MODELS = []  # Will be populated dynamically in main()

# Verbosity level: 0=minimal, 1=show failures, 2=show all responses
VERBOSITY = 2

# 15 tests: 3 per category
TESTS = [
    # Math - basic arithmetic
    ('Math', 'Multiply', 'What is 7 times 8? Answer with just the number.', None, '56'),
    ('Math', 'Add', 'What is 25 plus 17? Answer with just the number.', None, '42'),
    ('Math', 'Divide', 'What is 144 divided by 12? Answer with just the number.', None, '12'),
    # Reasoning - multi-step thinking
    ('Reason', 'Apples', 'I have 10 apples. I give 3 to Bob and 2 to Alice. How many apples do I have left? Answer with just the number.', None, '5'),
    ('Reason', 'Sequence', 'What comes next in this sequence: 2, 4, 6, 8, ? Answer with just the number.', None, '10'),
    ('Reason', 'Logic', 'All cats are animals. Fluffy is a cat. What category does Fluffy belong to? Answer with one word.', None, 'animal'),
    # Knowledge - world facts
    ('Know', 'Japan', 'What is the capital of Japan? Answer with one word.', None, 'tokyo'),
    ('Know', 'France', 'What is the capital of France? Answer with one word.', None, 'paris'),
    ('Know', 'Brazil', 'What is the capital of Brazil? Answer with one word.', None, 'brasilia'),
    # Calc (with tools) - tool usage
    ('Calc', 'Multiply', 'Use the calculator tool to compute 15 times 8.', ['calculator'], '120'),
    ('Calc', 'Divide', 'Use the calculator tool to compute 100 divided by 4.', ['calculator'], '25'),
    ('Calc', 'Power', 'Use the calculator tool to compute 2 to the power of 10.', ['calculator'], '1024'),
    # Code - code generation
    ('Code', 'is_even', 'Write a Python function called is_even(n) that returns True if n is even.', None, 'def'),
    ('Code', 'reverse', 'Write a Python function called reverse_string(s) that returns the reversed string.', None, 'def'),
    ('Code', 'max_num', 'Write a Python function called find_max(numbers) that returns the largest number in a list.', None, 'def'),
]

RESULTS_FILE = os.path.join(os.path.dirname(__file__), 'model_comparison_results.json')


def save_results(results):
    """Save results to JSON."""
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)


def test_model(client, model: str, results: dict) -> dict:
    """Test a single model, saving progress after each test with ACP logging."""
    
    # Create model-specific agent name
    # For paths like "Falcon3-1B-Instruct-1.58bit/ggml-model-i2_s.gguf", use the directory name
    if '/' in model:
        model_short = model.split('/')[0]  # "Falcon3-1B-Instruct-1.58bit"
    else:
        model_short = model.split(':')[0]  # For Ollama-style "model:tag"
    model_short = model_short[:25]  # Truncate if needed
    
    # Create a new ACP instance for this model (like 02_tool_agent_acp.py does)
    acp = ACPPlugin(
        agent_name=f"LocalClaw",
        model_name=model,
        debug=os.environ.get("ACP_DEBUG", "").lower() in ("1", "true"),
    )
    acp.bootstrap(claim_primary=False)
    
    if model not in results:
        results[model] = {
            'model': model,
            'tests': {},
            'total': len(TESTS),
            'time': 0
        }

    model_results = results[model]

    for cat, test_name, prompt, tools, expected in TESTS:
        full_name = f"{cat}:{test_name}"

        # Skip already tested
        if full_name in model_results['tests']:
            continue

        print(f"  Testing {full_name}...", end=' ', flush=True)

        # Log test start - no prefix
        acp.log_user_message(f"Test: {full_name}")

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

            response_norm = normalize_text(response)
            expected_norm = normalize_text(expected)
            passed = expected_norm in response_norm
            
            # Check for near-misses
            near_miss = False
            if not passed:
                numbers = re.findall(r'-?\d+\.?\d*', response_norm)
                if numbers and expected_norm.replace('.', '').replace('-', '').isdigit():
                    near_miss = expected_norm in numbers
            
            model_results['tests'][full_name] = {
                'passed': passed,
                'near_miss': near_miss,
                'time': elapsed,
                'response': response,
                'response_norm': response_norm,
                'expected': expected,
                'expected_norm': expected_norm
            }

            model_results['time'] += elapsed

            result_status = "PASS" if passed else ("NEAR-MISS" if near_miss else "FAIL")
            acp.log_assistant_message(f"[{result_status}] {full_name}")

            if passed:
                print(f"✅ ({elapsed:.1f}s)")
                if VERBOSITY >= 2:
                    print(f"    📝 Found '{expected}' in: {response[:150]}")
            elif near_miss:
                print(f"⚠️ NEAR-MISS ({elapsed:.1f}s)")
                print(f"    ⚠️ Expected '{expected}' found in numbers: {numbers}")
                print(f"    📝 RESPONSE: {response}")
            else:
                print(f"❌ ({elapsed:.1f}s)")
                if VERBOSITY >= 1:
                    print(f"    ❌ EXPECTED: '{expected}'")
                    print(f"    📝 RESPONSE: {response}")

        except Exception as e:
            model_results['tests'][full_name] = {
                'passed': False,
                'error': str(e)[:100]
            }
            model_results['time'] += 30
            acp.log_assistant_message(f"[ERROR] {full_name}: {str(e)[:30]}")
            print(f"❌ ERROR: {str(e)[:50]}")

        # Save after each test
        save_results(results)

    model_results['total'] = len(TESTS)
    return model_results


def main():
    print("🦞 LocalClaw Robust Model Comparison (ACP)")
    print("=" * 60)
    
    # Main ACP for session-level tracking
    # Individual models create their own ACP instances
    main_acp = ACPPlugin(
        agent_name="LocalClaw",
        model_name="robust-comparison",
        debug=os.environ.get("ACP_DEBUG", "").lower() in ("1", "true"),
    )
    
    bootstrap = main_acp.bootstrap(claim_primary=False)
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
    print(f"   Available: {', '.join(available)}")

    # Load existing results for resumability
    results = {}
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE) as f:
                results = json.load(f)
            completed_models = list(results.keys())
            print(f"   📁 Loaded existing results: {len(completed_models)} models already tested")
            print(f"   Resuming from where we left off...")
        except Exception as e:
            print(f"   ⚠️ Could not load existing results: {e}")
            results = {}

    # Get small models dynamically
    models_to_test = get_small_models(client)
    
    if not models_to_test:
        print(f"   ⚠️ No small models found by name indicators, using all available")
        models_to_test = available
    
    print(f"   Models to test: {', '.join(models_to_test)}")
    
    if acp_connected:
        main_acp.log_chat("system", f"Benchmark started: {len(models_to_test)} models", complete=True)

    for model in models_to_test:
        print(f"\n{'='*50}")
        print(f"🧪 Testing: {model}")
        print(f"{'='*50}")

        test_model(client, model, results)

    # Print rankings
    print(f"\n{'='*50}")
    print("🏆 RANKINGS")
    print(f"{'='*50}")

    # Calculate passed count from tests dict
    for model_name, model_data in results.items():
        if 'tests' in model_data:
            model_data['passed'] = sum(1 for t in model_data['tests'].values() if t.get('passed', False))
            model_data['total'] = len(TESTS)

    sorted_results = sorted(
        results.values(),
        key=lambda x: (-x.get('passed', 0), x.get('time', 9999))
    )

    for i, r in enumerate(sorted_results, 1):
        if 'tests' not in r or len(r.get('tests', {})) == 0:
            continue
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        passed = r.get('passed', 0)
        total = r.get('total', len(TESTS))
        rate = passed / total * 100 if total > 0 else 0
        
        near_misses = sum(1 for t in r.get('tests', {}).values() if t.get('near_miss', False))
        nm_str = f" (+{near_misses}⚠️)" if near_misses else ""
        
        print(f"{medal} {r['model']:<40} {passed}/{total} ({rate:.0f}%) - {r.get('time', 0):.1f}s{nm_str}")

    # Print category breakdown
    print(f"\n{'='*50}")
    print("📊 CATEGORY BREAKDOWN")
    print(f"{'='*50}")
    
    categories = ['Math', 'Reason', 'Know', 'Calc', 'Code']
    cat_labels = {'Math': 'Math', 'Reason': 'Reasoning', 'Know': 'Knowledge', 'Calc': 'Calc', 'Code': 'Code'}
    
    for cat in categories:
        print(f"\n  {cat_labels[cat]}:")
        cat_results = []
        for model_name, model_data in results.items():
            if 'tests' not in model_data:
                continue
            cat_tests = [t for k, t in model_data['tests'].items() if k.startswith(f"{cat}:")]
            if cat_tests:
                passed = sum(1 for t in cat_tests if t.get('passed', False))
                cat_results.append((model_name, passed, len(cat_tests)))
        
        cat_results.sort(key=lambda x: (-x[1], x[0]))
        for model, passed, total in cat_results:
            bar = "█" * passed + "░" * (total - passed)
            print(f"    {model:<35} {bar} {passed}/{total}")

    if acp_connected:
        winner = sorted_results[0] if sorted_results else None
        if winner:
            main_acp.log_chat("system", f"Benchmark complete. Winner: {winner['model']} ({winner.get('passed', 0)}/{len(TESTS)})", 
                        complete=True)

    # Show session stats
    status = main_acp.get_status()
    print(f"\n📊 Session tokens: {status.get('session_tokens', 0)}")
    agent_tokens = main_acp.get_agent_tokens()
    if agent_tokens:
        print("   Agent tokens:")
        for name, tokens in sorted(agent_tokens.items(), key=lambda x: -x[1]):
            print(f"      {name}: {tokens}")
    
    print(f"\n📄 Results saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
