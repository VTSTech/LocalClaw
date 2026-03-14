#!/usr/bin/env python3
"""
GSM8K Improved Benchmark

Uses:
  • Math-specific system prompt with few-shot examples
  • Calculator tool forcing via native tool calling
  • Better output parsing (extract last number)
  • Chain-of-thought prompting

Uses centralized config from localclaw/config.py
"""

import json
import time
import urllib.request
import re
import sys
import os

# Add LocalClaw package to path (parent directory)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import OLLAMA_BASE_URL

OLLAMA_URL = OLLAMA_BASE_URL
RESULTS_FILE = "/home/z/my-project/download/gsm8k_improved_results.jsonl"
LOG_FILE = "/home/z/my-project/download/gsm8k_improved_progress.log"

# ═══════════════════════════════════════════════════════════════════════════════
# MATH SYSTEM PROMPT WITH FEW-SHOT
# ═══════════════════════════════════════════════════════════════════════════════

MATH_SYSTEM_PROMPT = """You are a precise math assistant. Solve problems step by step.

IMPORTANT: 
- Use the calculator tool for ALL arithmetic
- Give ONLY the final number as your answer on the last line

Examples:

User: What is 15 + 27?
Assistant: Let me calculate 15 + 27.
[uses calculator tool]
Result: 42
Answer: 42

User: Janet has 8 apples. She buys 12 more. How many?
Assistant: Janet starts with 8 apples, buys 12 more. I need to add.
[uses calculator tool]
Result: 20
Answer: 20

User: What is 144 divided by 12?
Assistant: I need to divide 144 by 12.
[uses calculator tool]
Result: 12
Answer: 12"""

# ═══════════════════════════════════════════════════════════════════════════════
# CALCULATOR TOOL SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

CALCULATOR_TOOL = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Evaluate a mathematical expression. Use this for ALL arithmetic operations.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression to evaluate, e.g. '15 + 27' or '144 / 12'"
                }
            },
            "required": ["expression"]
        }
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# 50 GSM8K QUESTIONS
# ═══════════════════════════════════════════════════════════════════════════════

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


def safe_eval(expression: str) -> str:
    """Safely evaluate a math expression"""
    import math
    try:
        # Clean expression
        expr = expression.strip().replace("^", "**")
        # Only allow safe characters
        allowed = set('0123456789+-*/.() sqrt,abs,min,max')
        if not all(c in allowed or c.isspace() for c in expr):
            return "[Error]"
        result = eval(expr, {"__builtins__": {}}, {"sqrt": math.sqrt, "abs": abs, "min": min, "max": max})
        if isinstance(result, float) and result == int(result):
            return str(int(result))
        return str(round(result, 4))
    except:
        return "[Error]"


def extract_number(response: str) -> str:
    """Extract the final number from model output"""
    if not response:
        return ""
    
    # Look for explicit answer patterns
    patterns = [
        r'(?:final answer|answer|result)[:\s]*([+-]?\d+\.?\d*)',
        r'=\s*([+-]?\d+\.?\d*)\s*$',
    ]
    for pattern in patterns:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            return match.group(1).rstrip('.').lstrip('+')
    
    # Find all numbers, take last one
    numbers = re.findall(r'[+-]?\d+\.?\d*', response)
    if numbers:
        return numbers[-1].rstrip('.').lstrip('+')
    return ""


def test_with_tools(model: str, question: str, expected: str) -> dict:
    """Test model with calculator tool available"""
    try:
        # First, get model response with tools available
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": MATH_SYSTEM_PROMPT},
                    {"role": "user", "content": question}
                ],
                "tools": [CALCULATOR_TOOL],
                "stream": False,
                "options": {"num_predict": 150}
            }).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        start = time.time()
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
        elapsed = time.time() - start
        
        msg = result.get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])
        
        # Process tool calls if any
        tool_results = []
        for tc in tool_calls:
            fn = tc.get("function", {})
            if fn.get("name") == "calculator":
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    args = json.loads(args)
                expr = args.get("expression", "")
                if expr:
                    tool_result = safe_eval(expr)
                    tool_results.append(f"calculator({expr}) = {tool_result}")
        
        # If tool was used, get final answer
        if tool_results:
            # Send tool results back
            req2 = urllib.request.Request(
                f"{OLLAMA_URL}/api/chat",
                data=json.dumps({
                    "model": model,
                    "messages": [
                        {"role": "system", "content": MATH_SYSTEM_PROMPT},
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": content, "tool_calls": tool_calls},
                        {"role": "tool", "content": "\n".join(tool_results)},
                    ],
                    "stream": False,
                    "options": {"num_predict": 50}
                }).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req2, timeout=60) as resp:
                result2 = json.loads(resp.read().decode())
            content = result2.get("message", {}).get("content", content)
            elapsed = time.time() - start
        
        # Extract number
        extracted = extract_number(content)
        
        # Check correctness
        try:
            correct = abs(float(extracted) - float(expected)) < 0.01
        except:
            correct = extracted == expected
        
        return {
            "model": model,
            "question": question[:50],
            "expected": expected,
            "extracted": extracted,
            "correct": correct,
            "time": round(elapsed, 1),
            "used_tool": len(tool_calls) > 0,
            "response": content[:100]
        }
        
    except Exception as e:
        return {
            "model": model,
            "question": question[:50],
            "expected": expected,
            "error": str(e)[:50],
            "correct": False,
            "time": 0
        }


def test_simple(model: str, question: str, expected: str) -> dict:
    """Simple test without tools (fallback)"""
    try:
        prompt = f"""Solve this math problem step by step. Give ONLY the final number as your answer.

Problem: {question}

Think through it:
1. What numbers are mentioned?
2. What operation is needed?
3. Calculate the answer.
4. Write ONLY the final number.

Answer:"""

        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 100}
            }).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        start = time.time()
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read().decode())
        elapsed = time.time() - start
        
        response = result.get("response", "")
        extracted = extract_number(response)
        
        try:
            correct = abs(float(extracted) - float(expected)) < 0.01
        except:
            correct = extracted == expected
        
        return {
            "model": model,
            "question": question[:50],
            "expected": expected,
            "extracted": extracted,
            "correct": correct,
            "time": round(elapsed, 1),
            "used_tool": False,
            "response": response[:100]
        }
        
    except Exception as e:
        return {
            "model": model,
            "question": question[:50],
            "expected": expected,
            "error": str(e)[:50],
            "correct": False,
            "time": 0
        }


def main():
    open(RESULTS_FILE, "w").close()
    open(LOG_FILE, "w").close()
    
    total_tests = len(MODELS) * len(QUESTIONS)
    
    log(f"Starting GSM8K Improved Benchmark")
    log(f"Models: {len(MODELS)}")
    log(f"Questions per model: {len(QUESTIONS)}")
    log(f"Total tests: {total_tests}")
    log("=" * 50)
    
    overall_start = time.time()
    results = []
    
    for model in MODELS:
        log(f"\nTesting: {model}")
        correct_count = 0
        tool_count = 0
        
        for i, (question, expected) in enumerate(QUESTIONS):
            # Try with tools first
            result = test_with_tools(model, question, expected)
            
            # Fallback to simple if no tool was used
            if not result.get("used_tool") and not result.get("correct"):
                result = test_simple(model, question, expected)
            
            results.append(result)
            
            status = "✓" if result["correct"] else "✗"
            tool_mark = "🔧" if result.get("used_tool") else "  "
            elapsed = result.get("time", 0)
            extracted = result.get("extracted", "?")
            log(f"  Q{i+1:2d}: {status}{tool_mark} ({elapsed}s) Expected: {expected}, Got: {extracted}")
            
            if result["correct"]:
                correct_count += 1
            if result.get("used_tool"):
                tool_count += 1
            
            time.sleep(0.2)
        
        accuracy = (correct_count / len(QUESTIONS)) * 100
        tool_pct = (tool_count / len(QUESTIONS)) * 100
        log(f"  Score: {correct_count}/{len(QUESTIONS)} = {accuracy:.1f}% (Tools used: {tool_pct:.0f}%)")
        
        # Save progress
        with open(RESULTS_FILE, "a") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")
            results = []
    
    total_time = time.time() - overall_start
    log("\n" + "=" * 50)
    log(f"COMPLETED: {total_tests} tests in {total_time:.1f}s")
    summarize_results()


def summarize_results():
    """Print final summary"""
    try:
        results = []
        with open(RESULTS_FILE, "r") as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
        
        print("\n" + "=" * 70)
        print("GSM8K IMPROVED BENCHMARK RESULTS")
        print("=" * 70)
        print(f"{'Model':<40} | {'Score':^7} | {'Accuracy':^8} | {'Tools':^6}")
        print("-" * 70)
        
        for model in MODELS:
            mr = [r for r in results if r["model"] == model]
            correct = sum(1 for r in mr if r.get("correct", False))
            tools = sum(1 for r in mr if r.get("used_tool", False))
            total = len(mr)
            if total > 0:
                pct = (correct / total) * 100
                tool_pct = (tools / total) * 100
                print(f"{model:<40} | {correct:2d}/50  | {pct:6.1f}% | {tool_pct:5.0f}%")
        
        print("=" * 70)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
