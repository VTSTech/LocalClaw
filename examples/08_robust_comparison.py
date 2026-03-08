"""
examples/08_robust_comparison.py
--------------------------------
Robust model comparison that saves progress incrementally.
Run: python examples/08_robust_comparison.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import sys
import os
import time
import json
import unicodedata
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, OllamaClient
from localclaw.tools.builtins import make_builtin_registry


def normalize_text(text: str) -> str:
    """Normalize text: lowercase, remove accents."""
    normalized = unicodedata.normalize('NFD', text.lower())
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')


# Models to test
MODELS = [
    'qwen2.5-coder:0.5b-instruct-q4_k_m',
    'granite3.1-moe:1b',
    'qwen3:0.6b',
    'llama3.2:1b',
    'gemma3:270m',
]

# 15 tests: 3 per category
TESTS = [
    # Math
    ('Math', 'Multiply', 'What is 7 * 8? Answer with just the number.', None, '56'),
    ('Math', 'Add', 'What is 25 + 17? Answer with just the number.', None, '42'),
    ('Math', 'Divide', 'What is 144 / 12? Answer with just the number.', None, '12'),
    # Reasoning
    ('Reason', 'Apples', 'I have 10 apples, give 3 to Bob and 2 to Alice. How many left? Just number.', None, '5'),
    ('Reason', 'Sequence', 'What comes next in the sequence: 2, 4, 6, 8? Just the number.', None, '10'),
    ('Reason', 'Logic', 'All cats are animals. Fluffy is a cat. What category is Fluffy? One word.', None, 'animal'),
    # Knowledge
    ('Know', 'Japan', 'What is the capital of Japan? One word.', None, 'tokyo'),
    ('Know', 'France', 'What is the capital of France? One word.', None, 'paris'),
    ('Know', 'Brazil', 'What is the capital of Brazil? One word.', None, 'brasilia'),
    # Calc (with tools)
    ('Calc', 'Multiply', 'Use calculator to compute 15 * 8', ['calculator'], '120'),
    ('Calc', 'Divide', 'Use calculator to compute 100 / 4', ['calculator'], '25'),
    ('Calc', 'Power', 'Use calculator to compute 2 ** 10', ['calculator'], '1024'),
    # Code
    ('Code', 'is_even', 'Write a Python function is_even(n) that returns True if n is even.', None, 'def'),
    ('Code', 'reverse', 'Write a Python function reverse_string(s) that returns the reversed string.', None, 'def'),
    ('Code', 'max_num', 'Write a Python function find_max(numbers) that returns the largest number.', None, 'def'),
]

RESULTS_FILE = os.path.join(os.path.dirname(__file__), 'model_comparison_results.json')


def load_results():
    """Load existing results if any."""
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r') as f:
            data = json.load(f)
            # Convert list to dict keyed by model name
            if isinstance(data, list):
                return {r['model']: r for r in data if 'model' in r}
            return data
    return {}


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
            'passed': 0,
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

            passed = normalize_text(expected) in normalize_text(response)
            model_results['tests'][full_name] = {
                'passed': passed,
                'time': elapsed,
                'response': response[:100]
            }

            if passed:
                model_results['passed'] += 1
            model_results['time'] += elapsed

            status = "✅" if passed else "❌"
            print(f"{status} ({elapsed:.1f}s)")
            if not passed:
                print(f"    Expected '{expected}' in: {response[:60]}...")

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
    print(f"🦞 LocalClaw Robust Model Comparison")
    print(f"   Available: {', '.join(available)}")

    # Load existing results
    results = load_results()

    # Filter to available models
    models_to_test = [m for m in MODELS if any(m.split(':')[0] in a or m.split('-')[0] in a for a in available)]
    print(f"   Testing: {', '.join(models_to_test)}")

    for model in models_to_test:
        # Find exact name
        exact_name = next((a for a in available if model.split(':')[0] in a), model)

        print(f"\n{'='*50}")
        print(f"🧪 Testing: {exact_name}")
        print(f"{'='*50}")

        test_model(client, exact_name, results)

    # Print rankings
    print(f"\n{'='*50}")
    print("🏆 RANKINGS")
    print(f"{'='*50}")

    sorted_results = sorted(
        results.values(),
        key=lambda x: (-x.get('passed', 0), x.get('time', 9999))
    )

    for i, r in enumerate(sorted_results, 1):
        if 'passed' not in r:
            continue
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        rate = r['passed'] / r['total'] * 100 if r['total'] > 0 else 0
        print(f"{medal} {r['model']:<40} {r['passed']}/{r['total']} ({rate:.0f}%) - {r.get('time', 0):.1f}s")

    print(f"\n📄 Results saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
