#!/usr/bin/env python3
"""
GSM8K One-Shot Test Runner V3
- 50 questions per model
- GSM8K-style math problems

Uses centralized config from localclaw/config.py
"""

import json
import time
import urllib.request
import sys
import os

# Add LocalClaw package to path (parent directory)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import OLLAMA_BASE_URL

OLLAMA_URL = OLLAMA_BASE_URL
RESULTS_FILE = "/home/z/my-project/download/gsm8k_results_v3.jsonl"
LOG_FILE = "/home/z/my-project/download/gsm8k_progress_v3.log"

# 50 GSM8K-style questions (math word problems and arithmetic)
QUESTIONS = [
    # Basic arithmetic (1-10)
    ("What is 15 + 27?", "42"),
    ("What is 8 times 7?", "56"),
    ("What is 100 minus 37?", "63"),
    ("What is 144 divided by 12?", "12"),
    ("What is 25 times 4?", "100"),
    ("What is 17 + 18 + 19?", "54"),
    ("What is 200 - 50 - 30?", "120"),
    ("What is 6 times 9?", "54"),
    ("What is 81 divided by 9?", "9"),
    ("What is 35 + 65?", "100"),
    # Word problems basic (11-20)
    ("Janet has 8 apples. She buys 12 more. How many apples does she have now?", "20"),
    ("A book costs $15. If you pay with $20, how much change do you get?", "5"),
    ("There are 24 students in a class. If 6 are absent, how many are present?", "18"),
    ("A pizza has 8 slices. If 3 people share it equally, how many slices does each person get?", "8"),
    ("Tom has 45 marbles. He gives 18 to his friend. How many does he have left?", "27"),
    ("A train travels 60 miles per hour. How far does it travel in 2 hours?", "120"),
    ("What is 999 minus 777?", "222"),
    ("If 5 pens cost $10, how much does 1 pen cost?", "2"),
    ("What is 15% of 80?", "12"),
    ("A rectangle is 8 feet long and 5 feet wide. What is the area in square feet?", "40"),
    # Intermediate arithmetic (21-30)
    ("What is 12 times 11?", "132"),
    ("What is 3 squared plus 4 squared?", "25"),
    ("A store has 156 items. They sell 89. How many remain?", "67"),
    ("What is half of 150?", "75"),
    ("What is 7 times 8?", "56"),
    ("What is 225 divided by 15?", "15"),
    ("What is 33 + 44 + 55?", "132"),
    ("What is 1000 minus 777?", "223"),
    ("What is 9 times 8?", "72"),
    ("What is 18 divided by 3?", "6"),
    # Word problems intermediate (31-40)
    ("Mary reads 12 pages per day. How many pages in 5 days?", "60"),
    ("A box contains 48 eggs. If 12 eggs are broken, how many are good?", "36"),
    ("John earns $15 per hour. How much for 6 hours of work?", "90"),
    ("A cake has 12 slices. If 4 friends share equally, how many slices each?", "3"),
    ("What is 20% of 200?", "40"),
    ("A car travels 50 miles on 2 gallons. How many miles per gallon?", "25"),
    ("A dozen eggs costs $3. How much for 4 dozen?", "12"),
    ("What is 50 minus 17?", "33"),
    ("A garden has 15 rows with 8 plants each. How many plants total?", "120"),
    ("What is 11 times 11?", "121"),
    # Advanced (41-50)
    ("What is 16 times 5?", "80"),
    ("A shirt costs $25. If it is 20% off, how much do you save?", "5"),
    ("What is 360 divided by 6?", "60"),
    ("A pool holds 500 gallons. 125 gallons evaporate. How many remain?", "375"),
    ("What is 14 plus 28 plus 42?", "84"),
    ("A recipe needs 3 cups of flour for 12 cookies. How many cups for 24 cookies?", "6"),
    ("What is 45 minus 19?", "26"),
    ("A train has 8 cars with 15 passengers each. How many passengers total?", "120"),
    ("What is 7 times 9?", "63"),
    ("A store opens at 9am and closes at 5pm. How many hours is it open?", "8"),
]

MODELS = [
    "gemma3:270m",
    "qwen2.5:0.5b", 
    "tinyllama:latest",
    "granite4:350m",
    "smollm:135m",
    "qwen2.5-coder:0.5b-instruct-q4_k_m",
]

def log(msg):
    """Write to log file and print"""
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def test_model(model, question, expected):
    """Single API call to Ollama"""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=json.dumps({
                "model": model,
                "prompt": f"{question} Say just the number.",
                "stream": False,
                "options": {"num_predict": 15}
            }).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        start = time.time()
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read().decode())
        elapsed = time.time() - start
        
        response = result.get("response", "").strip()[:50]
        correct = expected in response
        
        return {
            "model": model,
            "question": question,
            "expected": expected,
            "response": response,
            "correct": correct,
            "time": round(elapsed, 1)
        }
    except Exception as e:
        return {
            "model": model,
            "question": question,
            "expected": expected,
            "error": str(e)[:80],
            "correct": False,
            "time": 0
        }

def main():
    # Clear previous results
    open(RESULTS_FILE, "w").close()
    open(LOG_FILE, "w").close()
    
    results = []
    total_tests = len(MODELS) * len(QUESTIONS)
    completed = 0
    
    log(f"Starting GSM8K One-Shot Test V3")
    log(f"Models: {len(MODELS)}")
    log(f"Questions per model: {len(QUESTIONS)}")
    log(f"Total tests: {total_tests}")
    log("=" * 50)
    
    overall_start = time.time()
    
    for model in MODELS:
        log(f"\nTesting: {model}")
        correct_count = 0
        model_start = time.time()
        
        for i, (question, expected) in enumerate(QUESTIONS):
            result = test_model(model, question, expected)
            results.append(result)
            completed += 1
            
            status = "✓" if result["correct"] else "✗"
            elapsed = result.get("time", 0)
            log(f"  Q{i+1:2d}: {status} ({elapsed}s) - Expected: {expected}")
            
            if result["correct"]:
                correct_count += 1
            
            # Brief pause between tests
            time.sleep(0.3)
        
        model_time = time.time() - model_start
        accuracy = (correct_count / len(QUESTIONS)) * 100
        log(f"  Score: {correct_count}/{len(QUESTIONS)} = {accuracy:.1f}% (Time: {model_time:.1f}s)")
        
        # Save progress after each model
        with open(RESULTS_FILE, "a") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")
            results = []  # Clear for next batch
    
    total_time = time.time() - overall_start
    
    log("\n" + "=" * 50)
    log(f"COMPLETED: {total_tests} tests in {total_time:.1f}s")
    log(f"Results saved to: {RESULTS_FILE}")
    
    # Print summary
    log("\nFinal Summary:")
    summarize_results()

def summarize_results():
    """Read results and print summary table"""
    try:
        results = []
        with open(RESULTS_FILE, "r") as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
        
        print("\n" + "=" * 70)
        print("GSM8K ONE-SHOT ACCURACY RESULTS (50 questions per model)")
        print("=" * 70)
        
        for model in MODELS:
            model_results = [r for r in results if r["model"] == model]
            correct = sum(1 for r in model_results if r.get("correct", False))
            total = len(model_results)
            if total > 0:
                pct = (correct / total) * 100
                avg_time = sum(r.get("time", 0) for r in model_results) / total
                print(f"{model:40s} | {correct:2d}/50 | {pct:5.1f}% | {avg_time:.1f}s avg")
        
        print("=" * 70)
        
    except Exception as e:
        print(f"Error summarizing: {e}")

if __name__ == "__main__":
    main()
