#!/usr/bin/env python3
"""
GSM8K Agent Benchmark with ACP - Using LocalClaw Agent System

This benchmark uses the full Agent system with:
  • Calculator tool for accurate arithmetic
  • Chain-of-thought prompting
  • Better output parsing
  • Math-specific system prompts
  • Dynamic model discovery
  • ACP integration for activity tracking

Uses centralized config from localclaw/config.py
"""

import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw.core.ollama_client import get_default_client
from localclaw.core.tools import ToolRegistry, Tool, ToolParam
from localclaw.core.agent import Agent, StepResult
from localclaw.core.math_prompts import (
    MATH_SYSTEM_PROMPT,
    MATH_SYSTEM_PROMPT_COMPACT,
    extract_number,
    calculator_tool,
)
from localclaw.model_discovery import pick_models_for_benchmark
from localclaw.acp_plugin import ACPPlugin
from localclaw import LOCALCLAW_BACKEND

BACKEND_NAME = LOCALCLAW_BACKEND.upper()

RESULTS_FILE = "/home/z/my-project/download/gsm8k_agent_acp_results.jsonl"
LOG_FILE = "/home/z/my-project/download/gsm8k_agent_acp_progress.log"

# 50 GSM8K-style questions
QUESTIONS = [
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
    ("Janet has 8 apples. She buys 12 more. How many apples does she have now?", "20"),
    ("A book costs $15. If you pay with $20, how much change do you get?", "5"),
    ("There are 24 students in a class. If 6 are absent, how many are present?", "18"),
    ("A pizza has 8 slices. If 3 people share it equally, how many slices does each person get?", "3"),
    ("Tom has 45 marbles. He gives 18 to his friend. How many does he have left?", "27"),
    ("A train travels 60 miles per hour. How far does it travel in 2 hours?", "120"),
    ("What is 999 minus 777?", "222"),
    ("If 5 pens cost $10, how much does 1 pen cost?", "2"),
    ("What is 15% of 80?", "12"),
    ("A rectangle is 8 feet long and 5 feet wide. What is the area in square feet?", "40"),
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


def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def create_calculator_tool():
    registry = ToolRegistry()
    
    @registry.tool(
        description="Evaluate a mathematical expression. Use this for ALL arithmetic operations.",
        param_descriptions={"expression": "Math expression to evaluate"}
    )
    def calculator(expression: str) -> str:
        return calculator_tool(expression)
    
    return registry


def test_model_with_agent(model: str, question: str, expected: str, client, acp: ACPPlugin) -> dict:
    try:
        is_small = any(x in model.lower() for x in ["270m", "135m", "350m", "0.5b", "tiny", "1b"])
        system_prompt = MATH_SYSTEM_PROMPT_COMPACT if is_small else MATH_SYSTEM_PROMPT
        
        agent = Agent(
            model=model,
            tools=create_calculator_tool(),
            system_prompt=system_prompt,
            max_steps=5,
            client=client,
            model_options={"num_predict": 150},
            on_step=acp.on_step,
        )
        
        start = time.time()
        result = agent.run(question)
        elapsed = time.time() - start
        
        final_answer = result.final_answer or ""
        extracted = extract_number(final_answer)
        
        correct = False
        if extracted:
            try:
                correct = abs(float(extracted) - float(expected)) < 0.01
            except ValueError:
                correct = extracted == expected
        
        return {
            "model": model,
            "question": question,
            "expected": expected,
            "response": final_answer[:200],
            "extracted": extracted,
            "correct": correct,
            "time": round(elapsed, 1),
            "steps": len(result.steps),
        }
        
    except Exception as e:
        return {
            "model": model,
            "question": question,
            "expected": expected,
            "error": str(e)[:100],
            "correct": False,
            "time": 0,
        }


def main():
    open(RESULTS_FILE, "w").close()
    open(LOG_FILE, "w").close()
    
    client = get_default_client()
    
    if not client.is_running():
        log(f"ERROR: {BACKEND_NAME} is not running!")
        if LOCALCLAW_BACKEND == "bitnet":
            log("Start llama-server from bitnet.cpp directory")
        else:
            log("Start with: ollama serve")
        sys.exit(1)
    
    # Setup ACP
    acp = ACPPlugin(
        agent_name="LocalClaw-GSM8K",
        debug=os.environ.get("ACP_DEBUG", "").lower() in ("1", "true"),
    )
    
    log(f"ACP URL: {acp.base_url}")
    bootstrap = acp.bootstrap(claim_primary=False)
    if bootstrap.get("stop_flag"):
        log(f"ACP STOP flag set: {bootstrap.get('stop_reason')}")
        sys.exit(0)
    
    # Discover models
    log("Discovering available models...")
    MODELS = pick_models_for_benchmark(max_models=6, prefer_small=True, client=client)
    
    if not MODELS:
        log("ERROR: No models found!")
        sys.exit(1)
    
    log(f"Found {len(MODELS)} models: {MODELS}")
    
    results = []
    total_tests = len(MODELS) * len(QUESTIONS)
    
    log(f"\nStarting GSM8K Agent Benchmark (ACP)")
    log(f"Models: {len(MODELS)}, Questions: {len(QUESTIONS)}, Total: {total_tests}")
    log("=" * 50)
    
    overall_start = time.time()
    
    for model in MODELS:
        log(f"\nTesting: {model}")
        correct_count = 0
        model_start = time.time()
        
        for i, (question, expected) in enumerate(QUESTIONS):
            result = test_model_with_agent(model, question, expected, client, acp)
            results.append(result)
            
            status = "✓" if result["correct"] else "✗"
            elapsed = result.get("time", 0)
            steps = result.get("steps", 0)
            extracted = result.get("extracted", "?")
            log(f"  Q{i+1:2d}: {status} ({elapsed}s, {steps} steps) - Expected: {expected}, Got: {extracted}")
            
            if result["correct"]:
                correct_count += 1
            
            time.sleep(0.3)
        
        model_time = time.time() - model_start
        accuracy = (correct_count / len(QUESTIONS)) * 100
        log(f"  Score: {correct_count}/{len(QUESTIONS)} = {accuracy:.1f}% (Time: {model_time:.1f}s)")
        
        with open(RESULTS_FILE, "a") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")
            results = []
    
    total_time = time.time() - overall_start
    
    log("\n" + "=" * 50)
    log(f"COMPLETED: {total_tests} tests in {total_time:.1f}s")
    log(f"Results saved to: {RESULTS_FILE}")
    
    summarize_results(MODELS)


def summarize_results(models: list[str]):
    try:
        results = []
        with open(RESULTS_FILE, "r") as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
        
        print("\n" + "=" * 70)
        print("GSM8K AGENT BENCHMARK RESULTS (with calculator tool + ACP)")
        print("=" * 70)
        print(f"{'Model':<40} | {'Score':^7} | {'Accuracy':^8} | {'Avg Time':^8}")
        print("-" * 70)
        
        for model in models:
            model_results = [r for r in results if r["model"] == model]
            correct = sum(1 for r in model_results if r.get("correct", False))
            total = len(model_results)
            if total > 0:
                pct = (correct / total) * 100
                avg_time = sum(r.get("time", 0) for r in model_results) / total
                print(f"{model:<40} | {correct:2d}/50  | {pct:6.1f}% | {avg_time:.1f}s")
        
        print("=" * 70)
        
    except Exception as e:
        print(f"Error summarizing: {e}")


if __name__ == "__main__":
    main()
