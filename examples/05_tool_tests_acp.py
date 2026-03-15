"""
examples/05_tool_tests_acp.py
----------------------------
Test suite focused on tool usage — with ACP integration.

Demonstrates:
- Tool calls automatically logged to ACP
- Shell command logging
- Per-tool token tracking

Run from the project root:   python examples/05_tool_tests_acp.py
Or from the examples folder: python 05_tool_tests_acp.py

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import sys
import os
import time
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, OllamaClient, StepResult
from localclaw.tools.builtins import make_builtin_registry
from localclaw.acp_plugin import ACPPlugin


MODEL = os.environ.get("LOCALCLAW_MODEL", "qwen2.5-coder:0.5b-instruct-q4_k_m")
VERBOSE = os.environ.get("LOCALCLAW_VERBOSE", "1") == "1"
TIMEOUT = int(os.environ.get("LOCALCLAW_TIMEOUT", "120"))


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


def test_calculator(acp: ACPPlugin):
    """Test calculator tool with ACP logging."""
    client = OllamaClient()
    
    print(f"\n{'='*60}")
    print(f"🧮 Calculator Tool Tests (ACP)")
    print(f"   Model: {MODEL}")
    print(f"   Timeout: {TIMEOUT}s per test")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["calculator"])
    
    tests = [
        ("Basic multiplication", "What is 15 times 8?", "120"),
        ("Power", "What is 2 to the power of 10?", "1024"),
        ("Square root", "What is the square root of 144?", "12"),
        ("Complex expression", "What is (10 + 5) times 3?", "45"),
        ("Division", "What is 100 divided by 4?", "25"),
    ]
    
    results = []
    
    for name, prompt, expected in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt}")
        
        # Log to ACP
        acp.log_user_message(f"[Calculator Test] {name}: {prompt}")
        
        # Combined step callback
        def print_step(step: StepResult):
            acp.on_step(step)
            if VERBOSE:
                if step.type == "tool_call":
                    args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
                    print(f"    🔧 {step.tool_name}({args})")
                elif step.type == "tool_result":
                    preview = step.content[:80] + "..." if len(step.content) > 80 else step.content
                    print(f"    📦 → {preview}")
        
        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Answer math questions using the calculator tool. Call the calculator with the expression.",
            max_steps=5,
            on_step=print_step,
            model_options={
                "temperature": 0.0,
                "num_ctx": 1024,
                "num_predict": 128,
            },
        )
        
        t0 = time.time()
        run, error = run_test(agent, prompt)
        elapsed = time.time() - t0
        
        if error:
            results.append(False)
            print(f"  ❌ Error: {error}")
            acp.log_assistant_message(f"[ERROR] {error}")
            continue
        
        tool_used = check_tool_used(run, "calculator")
        if not tool_used:
            print(f"  ⚠️ WARNING: Calculator tool was NOT called!")
        
        expected_num = normalize_number(expected)
        actual_num = normalize_number(run.final_answer)
        passed = expected_num == actual_num and expected_num != ""
        
        if not passed and expected in run.final_answer:
            passed = True
        
        results.append(passed)
        
        # Log result to ACP
        acp.log_assistant_message(f"[{'PASS' if passed else 'FAIL'}] Expected {expected}, got {run.final_answer[:100]}")
        
        status = "✅" if passed else "❌"
        print(f"  {status} Expected '{expected}' (normalized: {expected_num})")
        print(f"  📝 Got: {actual_num} | Answer: {run.final_answer[:80].replace(chr(10), ' ')}...")
        print(f"  ⏱️  {elapsed:.1f}s, {len(run.steps)} steps, tool_used={tool_used}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"📊 Calculator: {passed}/{total} tests passed ({100*passed//total}%)")
    print(f"{'='*60}")
    return passed, total


def test_shell(acp: ACPPlugin):
    """Test shell tool with ACP logging (shell commands logged to /api/shell/add)."""
    client = OllamaClient()
    
    print(f"\n{'='*60}")
    print(f"🖥️  Shell Tool Tests (ACP)")
    print(f"   Model: {MODEL}")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["shell"])
    
    tests = [
        ("Echo test", "Use shell to echo the text 'Hello LocalClaw'", "Hello LocalClaw", "shell"),
        ("Current directory", "What is the current working directory?", None, "shell"),
        ("Date", "What is today's date? Use shell to find out.", None, "shell"),
    ]
    
    results = []
    
    for name, prompt, expected, required_tool in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt}")
        
        acp.log_user_message(f"[Shell Test] {name}: {prompt}")
        
        def print_step(step: StepResult):
            acp.on_step(step)
            if VERBOSE:
                if step.type == "tool_call":
                    args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
                    print(f"    🔧 {step.tool_name}({args})")
                elif step.type == "tool_result":
                    preview = step.content[:80].replace("\n", " ")
                    if len(step.content) > 80:
                        preview += "..."
                    print(f"    📦 → {preview}")
        
        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Use the shell tool to run commands when asked.",
            max_steps=5,
            on_step=print_step,
            model_options={
                "temperature": 0.0,
                "num_ctx": 1024,
                "num_predict": 128,
            },
        )
        
        t0 = time.time()
        run, error = run_test(agent, prompt)
        elapsed = time.time() - t0
        
        if error:
            results.append(False)
            print(f"  ❌ Error: {error}")
            acp.log_assistant_message(f"[ERROR] {error}")
            continue
        
        tool_used = check_tool_used(run, required_tool)
        if not tool_used:
            print(f"  ⚠️ WARNING: Shell tool was NOT called!")
            results.append(False)
            acp.log_assistant_message(f"[FAIL] Tool not used")
            print(f"  ❌ FAILED: Tool not used")
            print(f"  📝 Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
            continue
        
        if expected:
            passed = expected.lower() in run.final_answer.lower()
            results.append(passed)
            status = "✅" if passed else "❌"
            print(f"  {status} Expected '{expected}' in response")
            acp.log_assistant_message(f"[{'PASS' if passed else 'FAIL'}] {run.final_answer[:100]}")
        else:
            results.append(True)
            print(f"  ✅ Tool was used correctly")
            acp.log_assistant_message(f"[PASS] Tool used correctly: {run.final_answer[:100]}")
        
        print(f"  📝 Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
        print(f"  ⏱️  {elapsed:.1f}s, {len(run.steps)} steps")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Shell: {passed}/{total} tests passed ({100*passed//total}%)")
    return passed, total


def test_python_repl(acp: ACPPlugin):
    """Test Python REPL tool with ACP logging."""
    client = OllamaClient()
    
    print(f"\n{'='*60}")
    print(f"🐍 Python REPL Tool Tests (ACP)")
    print(f"   Model: {MODEL}")
    print(f"{'='*60}")
    
    tools = make_builtin_registry().subset(["python_repl"])
    
    tests = [
        ("Power calculation", "What is 2 to the power of 20?", "1048576", "python_repl"),
        ("List squares", "Generate a list of squares from 1 to 5. What are they?", "1, 4, 9, 16, 25", "python_repl"),
        ("String repeat", "What is 'Hello' repeated 3 times?", "HelloHelloHello", "python_repl"),
    ]
    
    results = []
    
    for name, prompt, expected, required_tool in tests:
        print(f"\n📋 {name}")
        print(f"   Prompt: {prompt}")
        
        acp.log_user_message(f"[Python REPL Test] {name}: {prompt}")
        
        def print_step(step: StepResult):
            acp.on_step(step)
            if VERBOSE:
                if step.type == "tool_call":
                    args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
                    print(f"    🔧 {step.tool_name}({args})")
                elif step.type == "tool_result":
                    preview = step.content[:80].replace("\n", " ")
                    if len(step.content) > 80:
                        preview += "..."
                    print(f"    📦 → {preview}")
        
        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Use Python REPL for calculations. Use print() to show results in your code.",
            max_steps=5,
            on_step=print_step,
            model_options={
                "temperature": 0.0,
                "num_ctx": 1024,
                "num_predict": 128,
            },
        )
        
        t0 = time.time()
        run, error = run_test(agent, prompt)
        elapsed = time.time() - t0
        
        if error:
            results.append(False)
            print(f"  ❌ Error: {error}")
            acp.log_assistant_message(f"[ERROR] {error}")
            continue
        
        tool_used = check_tool_used(run, required_tool)
        if not tool_used:
            print(f"  ⚠️ WARNING: Python REPL tool was NOT called!")
            results.append(False)
            acp.log_assistant_message(f"[FAIL] Tool not used")
            print(f"  ❌ FAILED: Tool not used")
            print(f"  📝 Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
            continue
        
        passed = False
        if expected in run.final_answer:
            passed = True
        else:
            expected_clean = expected.replace("[", "").replace("]", "").replace(" ", "")
            answer_clean = run.final_answer.replace("[", "").replace("]", "").replace(" ", "")
            if expected_clean in answer_clean:
                passed = True
        
        results.append(passed)
        status = "✅" if passed else "❌"
        print(f"  {status} Expected '{expected}' in response")
        print(f"  📝 Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
        print(f"  ⏱️  {elapsed:.1f}s, {len(run.steps)} steps, tool_used={tool_used}")
        
        acp.log_assistant_message(f"[{'PASS' if passed else 'FAIL'}] {run.final_answer[:100]}")
    
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Python REPL: {passed}/{total} tests passed ({100*passed//total}%)")
    return passed, total


def main():
    print(f"\n{'='*60}")
    print(f"🔧 LocalClaw Tool Tests (ACP Enabled)")
    print(f"   Model: {MODEL}")
    print(f"   Verbose: {VERBOSE}")
    print(f"   Timeout: {TIMEOUT}s")
    print(f"{'='*60}")
    
    # ── Create and bootstrap ACP ─────────────────────────────────
    acp = ACPPlugin(
        agent_name="LocalClaw-ToolTester",
        model_name=MODEL,
        debug=os.environ.get("ACP_DEBUG", "").lower() in ("1", "true"),
    )
    
    bootstrap = acp.bootstrap(claim_primary=False)
    acp_connected = bootstrap.get("status") is not None
    print(f"ACP: {'connected' if acp_connected else 'unavailable'}")
    
    total_passed = 0
    total_tests = 0
    
    p, t = test_calculator(acp)
    total_passed += p
    total_tests += t
    
    p, t = test_shell(acp)
    total_passed += p
    total_tests += t
    
    p, t = test_python_repl(acp)
    total_passed += p
    total_tests += t
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 TOTAL: {total_passed}/{total_tests} tests passed ({100*total_passed//total_tests}%)")
    
    if acp_connected:
        status = acp.get_status()
        print(f"\nACP Summary:")
        print(f"   Session tokens: {status.get('session_tokens', 0)}")
        print(f"   Agent tokens: {acp.get_agent_tokens()}")
    
    print(f"{'='*60}\n")
    
    return total_passed == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
