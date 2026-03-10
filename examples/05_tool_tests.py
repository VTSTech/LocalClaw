"""
examples/05_tool_tests.py
-------------------------
Test suite focused on tool usage with calculator, shell, and Python REPL.

Note: For small models, prompts include explicit instructions:
- Calculator: Full expressions in parentheses
- Python REPL: print() statements required for output

Run from the project root:   python examples/05_tool_tests.py
Or from the examples folder: python 05_tool_tests.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import sys
import os
import time
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, OllamaClient, StepResult
from localclaw.tools.builtins import make_builtin_registry


MODEL = os.environ.get("LOCALCLAW_MODEL", "qwen2.5-coder:0.5b-instruct-q4_k_m")
VERBOSE = os.environ.get("LOCALCLAW_VERBOSE", "1") == "1"
TIMEOUT = int(os.environ.get("LOCALCLAW_TIMEOUT", "120"))  # seconds per test


def print_step(step: StepResult):
    """Print step information."""
    if step.type == "tool_call":
        args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
        print(f"    🔧 {step.tool_name}({args})")
    elif step.type == "tool_result":
        preview = step.content[:80] + "..." if len(step.content) > 80 else step.content
        print(f"    📦 → {preview}")


def check_tool_used(run, tool_name: str) -> bool:
    """Verify that a specific tool was actually called during the run."""
    for step in run.steps:
        if step.type == "tool_call" and step.tool_name == tool_name:
            return True
    return False


def normalize_number(text: str) -> str:
    """Extract first number from text for comparison."""
    match = re.search(r'-?\d+\.?\d*', text.replace(',', ''))
    return match.group(0) if match else ""


def run_test(agent, prompt: str, timeout: int = TIMEOUT):
    """Run agent with timeout and return (run, error)."""
    import signal
    
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Test timed out after {timeout}s")
    
    # Set alarm for timeout (Unix only)
    old_handler = None
    try:
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
    except (AttributeError, ValueError):
        pass  # Windows doesn't have SIGALRM
    
    try:
        run = agent.run(prompt)
        try:
            signal.alarm(0)
            if old_handler:
                signal.signal(signal.SIGALRM, old_handler)
        except:
            pass
        return run, None
    except TimeoutError as e:
        return None, str(e)
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:100]}"


def test_calculator():
    """Test calculator tool with various expressions."""
    client = OllamaClient()
    
    print(f"\n{'='*60}")
    print(f"🧮 Calculator Tool Tests")
    print(f"   Model: {MODEL}")
    print(f"   Timeout: {TIMEOUT}s per test")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["calculator"])
    
    tests = [
        ("Basic multiplication", "Use the calculator to compute 15 * 8", "120"),
        ("Power", "Use the calculator to compute 2 ** 10", "1024"),
        ("Square root", "Use the calculator to compute sqrt(144)", "12"),
        ("Complex expression", "Use the calculator to compute (10 + 5) * 3. Pass the ENTIRE expression: '(10 + 5) * 3'", "45"),
        ("Division", "Use the calculator to compute 100 / 4", "25"),
    ]
    
    results = []
    
    for name, prompt, expected in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt[:60]}...")
        
        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Use the calculator tool for math. Then explain the result briefly.",
            max_steps=5,
            on_step=print_step if VERBOSE else None,
            model_options={"temperature": 0.1},
        )
        
        t0 = time.time()
        run, error = run_test(agent, prompt)
        elapsed = time.time() - t0
        
        if error:
            results.append(False)
            print(f"  ❌ Error: {error}")
            continue
        
        # Check if tool was actually used
        tool_used = check_tool_used(run, "calculator")
        if not tool_used:
            print(f"  ⚠️ WARNING: Calculator tool was NOT called - model may have hallucinated!")
        
        # Check answer - use normalized number matching
        expected_num = normalize_number(expected)
        actual_num = normalize_number(run.final_answer)
        passed = expected_num == actual_num and expected_num != ""
        
        if not passed and expected in run.final_answer:
            passed = True  # Fallback to string match
        
        results.append(passed)
        
        status = "✅" if passed else "❌"
        print(f"  {status} Expected '{expected}' (normalized: {expected_num})")
        print(f"  📝 Got: {actual_num} | Answer: {run.final_answer[:80].replace(chr(10), ' ')}...")
        print(f"  ⏱️  {elapsed:.1f}s, {len(run.steps)} steps, tool_used={tool_used}")
    
    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"📊 Calculator: {passed}/{total} tests passed ({100*passed//total}%)")
    print(f"{'='*60}")
    return passed, total


def test_shell():
    """Test shell tool with proper expected values."""
    client = OllamaClient()
    
    print(f"\n{'='*60}")
    print(f"🖥️  Shell Tool Tests")
    print(f"   Model: {MODEL}")
    print(f"   Note: Tests adapted for both Unix and Windows")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["shell"])
    
    tests = [
        ("Echo test", "Use shell to run: echo 'Hello LocalClaw'", "Hello LocalClaw", "shell"),
        ("Current directory", "Use shell to print working directory with pwd or cd", None, "shell"),  # Just check tool used
        ("Environment", "Use shell to echo the HOME or USERPROFILE variable", None, "shell"),  # Just check tool used
    ]
    
    results = []
    
    for name, prompt, expected, required_tool in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt[:60]}...")
        
        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Use shell tool when asked. Report the output briefly.",
            max_steps=5,
            on_step=print_step if VERBOSE else None,
            model_options={"temperature": 0.1},
        )
        
        t0 = time.time()
        run, error = run_test(agent, prompt)
        elapsed = time.time() - t0
        
        if error:
            results.append(False)
            print(f"  ❌ Error: {error}")
            continue
        
        # Verify tool was used
        tool_used = check_tool_used(run, required_tool)
        if not tool_used:
            print(f"  ⚠️ WARNING: Shell tool was NOT called!")
            results.append(False)
            print(f"  ❌ FAILED: Tool not used")
            print(f"  📝 Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
            continue
        
        # Check expected value if provided
        if expected:
            passed = expected.lower() in run.final_answer.lower()
            results.append(passed)
            status = "✅" if passed else "❌"
            print(f"  {status} Expected '{expected}' in response")
        else:
            # No expected value - just verify tool was used
            results.append(True)
            print(f"  ✅ Tool was used correctly")
        
        print(f"  📝 Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
        print(f"  ⏱️  {elapsed:.1f}s, {len(run.steps)} steps")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Shell: {passed}/{total} tests passed ({100*passed//total}%)")
    return passed, total


def test_python_repl():
    """Test Python REPL tool."""
    client = OllamaClient()
    
    print(f"\n{'='*60}")
    print(f"🐍 Python REPL Tool Tests")
    print(f"   Model: {MODEL}")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["python_repl"])
    
    tests = [
        ("Simple calculation", "Use Python to calculate and print 2 ** 20. Use: print(2 ** 20)", "1048576", "python_repl"),
        ("List comprehension", "Use Python to create and print a list of squares from 1 to 5. Use: print([i**2 for i in range(1,6)])", "1, 4, 9, 16, 25", "python_repl"),
        ("String manipulation", "Use Python to print 'Hello' repeated 3 times. Use: print('Hello' * 3)", "HelloHelloHello", "python_repl"),
    ]
    
    results = []
    
    for name, prompt, expected, required_tool in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt[:60]}...")
        
        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Use Python REPL for calculations. Always use print() to show results.",
            max_steps=5,
            on_step=print_step if VERBOSE else None,
            model_options={"temperature": 0.1},
        )
        
        t0 = time.time()
        run, error = run_test(agent, prompt)
        elapsed = time.time() - t0
        
        if error:
            results.append(False)
            print(f"  ❌ Error: {error}")
            continue
        
        # Verify tool was used
        tool_used = check_tool_used(run, required_tool)
        if not tool_used:
            print(f"  ⚠️ WARNING: Python REPL tool was NOT called!")
            results.append(False)
            print(f"  ❌ FAILED: Tool not used")
            print(f"  📝 Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
            continue
        
        # Check answer with flexible matching (handles different list formats)
        passed = False
        if expected in run.final_answer:
            passed = True
        else:
            # Normalize and compare (handles [1, 4, 9, 16, 25] vs 1, 4, 9, 16, 25)
            expected_clean = expected.replace("[", "").replace("]", "").replace(" ", "")
            answer_clean = run.final_answer.replace("[", "").replace("]", "").replace(" ", "")
            if expected_clean in answer_clean:
                passed = True
        
        results.append(passed)
        status = "✅" if passed else "❌"
        print(f"  {status} Expected '{expected}' in response")
        print(f"  📝 Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
        print(f"  ⏱️  {elapsed:.1f}s, {len(run.steps)} steps, tool_used={tool_used}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Python REPL: {passed}/{total} tests passed ({100*passed//total}%)")
    return passed, total


def main():
    print(f"\n{'='*60}")
    print(f"🔧 LocalClaw Tool Tests")
    print(f"   Model: {MODEL}")
    print(f"   Verbose: {VERBOSE}")
    print(f"   Timeout: {TIMEOUT}s")
    print(f"{'='*60}")
    
    total_passed = 0
    total_tests = 0
    
    p, t = test_calculator()
    total_passed += p
    total_tests += t
    
    p, t = test_shell()
    total_passed += p
    total_tests += t
    
    p, t = test_python_repl()
    total_passed += p
    total_tests += t
    
    print(f"\n{'='*60}")
    print(f"📊 TOTAL: {total_passed}/{total_tests} tests passed ({100*total_passed//total_tests}%)")
    print(f"{'='*60}\n")
    
    return total_passed == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
