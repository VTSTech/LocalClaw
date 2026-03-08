"""
examples/05_tool_tests.py
-------------------------
Test suite focused on tool usage with the calculator.

Run from the project root:   python examples/05_tool_tests.py
Or from the examples folder: python 05_tool_tests.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, OllamaClient, StepResult
from localclaw.tools.builtins import make_builtin_registry


MODEL = os.environ.get("LOCALCLAW_MODEL", "qwen2.5-coder:0.5b-instruct-q4_k_m")


def print_step(step: StepResult):
    """Print step information."""
    if step.type == "tool_call":
        args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
        print(f"    🔧 {step.tool_name}({args})")
    elif step.type == "tool_result":
        preview = step.content[:60] + "..." if len(step.content) > 60 else step.content
        print(f"    📦 → {preview}")


def test_calculator():
    """Test calculator tool with various expressions."""
    client = OllamaClient()
    
    print(f"\n{'='*60}")
    print(f"🧮 Calculator Tool Tests")
    print(f"   Model: {MODEL}")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["calculator"])
    
    tests = [
        ("Basic multiplication", "Use the calculator to compute 15 * 8", "120"),
        ("Power", "Use the calculator to compute 2 ** 10", "1024"),
        ("Square root", "Use the calculator to compute sqrt(144)", "12"),
        ("Complex expression", "Use the calculator to compute (10 + 5) * 3", "45"),
    ]
    
    results = []
    
    for name, prompt, expected in tests:
        print(f"\n📋 {name}")
        
        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Use the calculator tool for math. Then explain the result briefly.",
            max_steps=5,
            on_step=print_step,
            model_options={"temperature": 0.1},
        )
        
        t0 = time.time()
        try:
            run = agent.run(prompt)
            elapsed = time.time() - t0
            
            passed = expected in run.final_answer
            results.append(passed)
            
            status = "✅" if passed else "❌"
            print(f"  {status} Expected '{expected}' in response")
            print(f"  📝 Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
            print(f"  ⏱️  {elapsed:.1f}s, {len(run.steps)} steps")
            
        except Exception as e:
            results.append(False)
            print(f"  ❌ Error: {e}")
    
    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"📊 Calculator: {passed}/{total} tests passed")
    print(f"{'='*60}")


def test_shell():
    """Test shell tool (if available)."""
    client = OllamaClient()
    
    print(f"\n{'='*60}")
    print(f"🖥️  Shell Tool Tests")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["shell"])
    
    tests = [
        ("List files", "Use shell to list files in /tmp directory"),
        ("Echo test", "Use shell to echo 'Hello LocalClaw'"),
    ]
    
    for name, prompt in tests:
        print(f"\n📋 {name}")
        
        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Use shell tool when asked. Report the output.",
            max_steps=5,
            on_step=print_step,
            model_options={"temperature": 0.1},
        )
        
        try:
            run = agent.run(prompt)
            print(f"  📝 Answer: {run.final_answer[:150].replace(chr(10), ' ')}...")
        except Exception as e:
            print(f"  ❌ Error: {e}")


def test_python_repl():
    """Test Python REPL tool."""
    client = OllamaClient()
    
    print(f"\n{'='*60}")
    print(f"🐍 Python REPL Tool Tests")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["python_repl"])
    
    tests = [
        ("Simple calculation", "Use Python to calculate 2 ** 20"),
        ("List comprehension", "Use Python to create a list of squares from 1 to 5"),
    ]
    
    for name, prompt in tests:
        print(f"\n📋 {name}")
        
        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Use Python REPL for calculations. Show the result.",
            max_steps=5,
            on_step=print_step,
            model_options={"temperature": 0.1},
        )
        
        try:
            run = agent.run(prompt)
            print(f"  📝 Answer: {run.final_answer[:150].replace(chr(10), ' ')}...")
        except Exception as e:
            print(f"  ❌ Error: {e}")


def main():
    test_calculator()
    test_shell()
    test_python_repl()
    
    print(f"\n{'='*60}")
    print("✅ Tool tests complete!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
