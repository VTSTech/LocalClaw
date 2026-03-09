"""
examples/09_expanded_benchmark.py
---------------------------------
Expanded benchmark with 25 tests across 8 categories.
Includes multi-step reasoning, comparison, and tool chaining.

Run: python examples/09_expanded_benchmark.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import sys
import os
import time
import re
import json
import unicodedata
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, OllamaClient
from localclaw.tools.builtins import make_builtin_registry


def normalize_text(text: str) -> str:
    """Normalize text: lowercase, remove accents."""
    normalized = unicodedata.normalize('NFD', text.lower())
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')


# System prompts
SYSTEM_PROMPT_NO_TOOLS = """You are a helpful assistant. Answer concisely and directly."""

SYSTEM_PROMPT_WITH_TOOLS = """You are a helpful assistant with access to tools. Use tools when needed."""


# 25 tests: 8 categories
# Prompts heavily optimized for small models (≤1.5B parameters)
TESTS = [
    # === MATH (3 tests) - Basic arithmetic ===
    ('Math', 'Multiply', 'What is 7 * 8? Answer with just the number.', None, '56'),
    ('Math', 'Add', 'What is 25 + 17? Answer with just the number.', None, '42'),
    ('Math', 'Divide', 'What is 144 / 12? Answer with just the number.', None, '12'),

    # === REASONING (4 tests) - Multi-step thinking ===
    ('Reason', 'Apples', 'Starting with 10 apples, I give away 3 apples to Bob and 2 apples to Alice. Calculate: 10 minus 3 minus 2 equals? Answer with just the final number.', None, '5'),
    ('Reason', 'Sequence', 'This is an arithmetic sequence where each number increases by 2. The sequence is: 2, 4, 6, 8. What is the NEXT number after 8? Answer with just the number.', None, '10'),
    ('Reason', 'Logic', 'All cats belong to the category called animals. Fluffy is a cat. So Fluffy is a member of what category? Answer: animals (one word).', None, 'animal'),
    ('Reason', 'Marbles', 'I have 100 marbles total. I remove 20 marbles and then remove 15 more marbles. Calculate: 100 minus 20 minus 15 equals? Answer with just the final number.', None, '65'),

    # === KNOWLEDGE (3 tests) - World facts ===
    ('Know', 'Japan', 'What is the capital of Japan? One word.', None, 'tokyo'),
    ('Know', 'France', 'What is the capital of France? One word.', None, 'paris'),
    ('Know', 'Brazil', 'The capital of Brazil is Brasilia. What is the capital of Brazil? One word.', None, 'brasilia'),

    # === CALC TOOL (3 tests) - Calculator tool usage ===
    ('Calc', 'Multiply', 'Use the calculator tool. Pass the expression 15 * 8 to the calculator. What is the result?', ['calculator'], '120'),
    ('Calc', 'Divide', 'Use the calculator tool. Pass the expression 100 / 4 to the calculator. What is the result?', ['calculator'], '25'),
    ('Calc', 'Power', 'Use the calculator tool. Pass the expression 2 ** 10 to the calculator. What is the result?', ['calculator'], '1024'),

    # === CODE (3 tests) - Python code generation ===
    ('Code', 'is_even', 'Write Python code. Define a function called is_even(n) that returns True if n is even. Start with: def is_even', None, 'def'),
    ('Code', 'reverse', 'Write Python code. Define a function called reverse_string(s) that returns the reversed string. Start with: def reverse_string', None, 'def'),
    ('Code', 'max_num', 'Write Python code. Define a function called find_max(numbers) that returns the largest number. Start with: def find_max', None, 'def'),

    # === COMPARISON (3 tests) - Compare values ===
    ('Compare', 'Larger', 'Which is larger: 100 or 99? Answer with the larger number.', None, '100'),
    ('Compare', 'Smaller', 'Which is smaller: 5 or 3? Answer with the smaller number.', None, '3'),
    ('Compare', 'Power', '2 to the power of 10 equals 1024. 3 to the power of 5 equals 243. Which result is larger: 1024 or 243? Answer with the larger number.', None, '1024'),

    # === MULTI-STEP (3 tests) - Requires multiple operations ===
    ('Multi', 'SquareSum', 'First calculate 3 squared (which is 9). Then calculate 4 squared (which is 16). Then add them together: 9 + 16 equals? Answer with just the final number.', None, '25'),
    ('Multi', 'Perimeter', 'A rectangle has width 5 and length 8. The perimeter is calculated as 2 times width plus 2 times length. Calculate: 2*5 + 2*8 equals? Answer with just the number.', None, '26'),
    ('Multi', 'Average', 'To find the average of 10, 20, and 30: first add them to get 60, then divide by 3. Calculate: 60 / 3 equals? Answer with just the number.', None, '20'),

    # === PYTHON REPL (3 tests) - Code execution with tool ===
    ('Repl', 'List', 'Use the python_repl tool. Pass the code: print(list(range(5))). What does it print?', ['python_repl'], '0, 1, 2, 3, 4'),
    ('Repl', 'Sum', 'Use the python_repl tool. Pass the code: print(sum([1,2,3,4,5])). What does it print?', ['python_repl'], '15'),
    ('Repl', 'Squares', 'Use the python_repl tool. Pass the code: print([x**2 for x in range(4)]). What list does it print?', ['python_repl'], '0, 1, 4, 9'),
]

RESULTS_FILE = os.path.join(os.path.dirname(__file__), 'expanded_benchmark_results.json')


def save_results(results):
    """Save results to JSON."""
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)


def test_model(client: OllamaClient, model: str, results: dict) -> dict:
    """Test a single model, saving progress after each test."""
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

        try:
            registry = make_builtin_registry().subset(tools) if tools else None
            system_prompt = SYSTEM_PROMPT_WITH_TOOLS if tools else SYSTEM_PROMPT_NO_TOOLS

            agent = Agent(
                model=model,
                tools=registry,
                system_prompt=system_prompt,
                max_steps=5,
                client=client,
                model_options={"temperature": 0.1},
            )

            t0 = time.time()
            response = agent.chat(prompt)
            elapsed = time.time() - t0

            response_norm = normalize_text(response)
            expected_norm = normalize_text(expected)
            passed = expected_norm in response_norm

            # Check for near-misses (correct number in response)
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
                'expected': expected,
            }

            model_results['time'] += elapsed

            if passed:
                print(f"✅ ({elapsed:.1f}s)")
            elif near_miss:
                print(f"⚠️ NEAR-MISS ({elapsed:.1f}s)")
            else:
                print(f"❌ ({elapsed:.1f}s)")
                print(f"    Expected '{expected}' in: {response[:80]}...")

        except Exception as e:
            model_results['tests'][full_name] = {
                'passed': False,
                'error': str(e)[:100]
            }
            model_results['time'] += 30  # Penalty
            print(f"❌ ERROR: {str(e)[:50]}")

        # Save after each test
        save_results(results)

    # Calculate final score
    model_results['total'] = len(TESTS)
    return model_results


def main():
    client = OllamaClient()

    if not client.is_running():
        print("❌ Ollama is not running.")
        return

    available = client.list_models()
    print(f"🦞 LocalClaw Expanded Benchmark (25 tests)")
    print(f"   Available: {', '.join(available)}")

    # Clear old results
    results = {}
    if os.path.exists(RESULTS_FILE):
        os.remove(RESULTS_FILE)

    # Models to test (in order)
    models_to_test = ['qwen2.5-coder:0.5b-instruct-q4_k_m', 'llama3.2:1b', 'gemma3:270m']
    models_to_test = [m for m in models_to_test if any(m.split(':')[0] in a for a in available)]
    print(f"   Testing: {', '.join(models_to_test)}")

    for model in models_to_test:
        exact_name = next((a for a in available if model.split(':')[0] in a), model)

        print(f"\n{'='*50}")
        print(f"🧪 Testing: {exact_name}")
        print(f"{'='*50}")

        test_model(client, exact_name, results)

    # Print rankings
    print(f"\n{'='*50}")
    print("🏆 RANKINGS")
    print(f"{'='*50}")

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
        print(f"{medal} {r['model']:<40} {passed}/{total} ({rate:.0f}%) - {r.get('time', 0):.1f}s")

    # Category breakdown
    categories = ['Math', 'Reason', 'Know', 'Calc', 'Code', 'Compare', 'Multi', 'Repl']
    print(f"\n{'='*50}")
    print("📊 CATEGORY BREAKDOWN")
    print(f"{'='*50}")

    for cat in categories:
        print(f"\n  {cat}:")
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

    print(f"\n📄 Results saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
