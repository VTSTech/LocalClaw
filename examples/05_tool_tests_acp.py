#!/usr/bin/env python3
"""
examples/05_tool_tests_acp.py
-----------------------------
Test suite focused on tool usage with ACP logging.
Tests calculator, shell, and Python REPL tools.

All tool calls are logged to ACP for monitoring.

Run from the project root:   python examples/05_tool_tests_acp.py
Or from the examples folder: python 05_tool_tests_acp.py

Environment variables:
- LOCALCLAW_MODEL: Model name (default: qwen2.5-coder:0.5b-instruct-q4_k_m)
- ACP_HOST: ACP server address (default: 127.0.0.1:8766)
- LOCALCLAW_VERBOSE: Show step output (default: 1)
- LOCALCLAW_TIMEOUT: Timeout per test in seconds (default: 120)

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/LocalClaw
"""

import sys
import os
import time
import re

# Ensure the parent directory is in the path so localclaw can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localclaw import Agent, OllamaClient, StepResult
from localclaw.tools.builtins import make_builtin_registry
from localclaw.acp_plugin import ACPPlugin

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

MODEL = os.environ.get("LOCALCLAW_MODEL", "qwen2.5-coder:0.5b-instruct-q4_k_m")
VERBOSE = os.environ.get("LOCALCLAW_VERBOSE", "1") == "1"
TIMEOUT = int(os.environ.get("LOCALCLAW_TIMEOUT", "120"))

# ACP configuration
ACP_URL = os.environ.get("ACP_HOST", "127.0.0.1:8766")
ACP_USER = os.environ.get("ACP_USER", "admin")
ACP_PASS = os.environ.get("ACP_PASS", "changeme")
# Global ACP plugin (initialized in main)
acp = None


# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════

def make_on_step_callback():
    """Create combined callback: verbose print + ACP logging."""
    def on_step(step: StepResult):
        # Print to console (verbose)
        if VERBOSE:
            if step.type == "tool_call":
                args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
                print(f"    🔧  {step.tool_name}({args})")
            elif step.type == "tool_result":
                preview = step.content[:80] + "..." if len(step.content) > 80 else step.content
                print(f"    📦 →  {preview}")

        # Log to ACP
        if acp:
            acp.on_step(step)

    return on_step


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_number(s: str) -> str:
    """Extract and normalize a number from a string (removes commas, etc.)."""
    if not s:
        return ""
    # Remove everything except digits, decimal point, and minus sign
    cleaned = re.sub(r"[^\d\-.]", "", s)
    # Handle simple cases
    try:
        # Convert to float then to int if it's a whole number
        num = float(cleaned)
        if num.is_integer():
            return str(int(num))
        else:
            return str(num)
    except ValueError:
        return cleaned


def check_tool_used(run, tool_name: str) -> bool:
    """Return True if the tool was called at least once in the run."""
    if not run or not hasattr(run, 'steps'):
        return False
    for step in run.steps:
        if step.type == "tool_call" and step.tool_name == tool_name:
            return True
    return False


def run_test(agent, prompt, timeout=TIMEOUT):
    """
    Run the agent with a timeout.
    Returns (run, error). If timeout or exception, run is None and error is a string.
    """
    import signal

    # Set up alarm for timeout (Unix only)
    old_handler = None
    try:
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Test timed out after {timeout} seconds")

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
    except (AttributeError, ValueError):
        # Windows or unsupported platform – skip alarm
        pass

    try:
        run = agent.run(prompt)
        # Cancel alarm
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


# ═══════════════════════════════════════════════════════════════════════════════
# TEST SUITES
# ═══════════════════════════════════════════════════════════════════════════════

def test_calculator():
    """Test calculator tool - models must figure out how to use it."""
    client = OllamaClient()

    print(f"\n{'='*60}")
    print(f"🧮  Calculator Tool Tests (ACP Enabled)")
    print(f"   Model: {MODEL}")
    print(f"   Timeout: {TIMEOUT}s per test")
    print(f"{'='*60}")

    tools = make_builtin_registry().subset(["calculator"])
    on_step = make_on_step_callback()

    # Ask questions - model must use calculator tool
    tests = [
        ("Basic multiplication", "What is 15 times 8?", "120"),
        ("Power", "What is 2 to the power of 10?", "1024"),
        ("Square root", "What is the square root of 144?", "12"),
        ("Complex expression", "What is (10 + 5) times 3?", "45"),
        ("Division", "What is 100 divided by 4?", "25"),
    ]

    # Sync TODOs to ACP
    if acp:
        acp.sync_todos([
            {"id": f"calc_{i}", "content": f"Calculator: {t[0]}", "status": "pending", "priority": "medium"}
            for i, t in enumerate(tests)
        ])

    results = []

    for i, (name, prompt, expected) in enumerate(tests):
        print(f"\n📋  {name}")
        print(f"   Prompt: {prompt}")

        if acp:
            acp._request("/api/todos/update", "POST", {"id": f"calc_{i}", "status": "in_progress"})

        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Answer math questions using the calculator tool. Call the calculator with the expression.",
            max_steps=5,
            on_step=on_step,
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
            print(f"  ❌  Error: {error}")
            if acp:
                acp._request("/api/todos/update", "POST", {"id": f"calc_{i}", "status": "pending"})
                acp.add_note("error", f"Calculator test '{name}' failed: {error}", "high")
            continue

        # Check if tool was actually used
        tool_used = check_tool_used(run, "calculator")
        if not tool_used:
            print(f"  ⚠️  WARNING: Calculator tool was NOT called!")

        # Check answer
        expected_num = normalize_number(expected)
        actual_num = normalize_number(run.final_answer)
        passed = expected_num == actual_num and expected_num != ""

        if not passed and expected in run.final_answer:
            passed = True

        results.append(passed)

        # Update TODO with result
        if acp:
            acp._request("/api/todos/update", "POST", {
                "id": f"calc_{i}",
                "status": "completed" if passed else "pending",
                "content": f"Calculator: {name} - {'PASS' if passed else 'FAIL'}"
            })

        status = "✅" if passed else "❌"
        print(f"  {status} Expected '{expected}' (normalized: {expected_num})")
        print(f"  📝  Got: {actual_num} | Answer: {run.final_answer[:80].replace(chr(10), ' ')}...")
        print(f"  ⏱️  {elapsed:.1f}s, {len(run.steps)} steps, tool_used={tool_used}")

    passed = sum(results)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"📊  Calculator: {passed}/{total} tests passed ({100*passed//total}%)")
    print(f"{'='*60}")
    return passed, total


def test_shell():
    """Test shell tool - models must figure out how to use it."""
    client = OllamaClient()

    print(f"\n{'='*60}")
    print(f"🖥️  Shell Tool Tests (ACP Enabled)")
    print(f"   Model: {MODEL}")
    print(f"   Timeout: {TIMEOUT}s per test")
    print(f"{'='*60}")

    tools = make_builtin_registry().subset(["shell"])
    on_step = make_on_step_callback()

    tests = [
        ("Echo test", "Use shell to echo the text 'Hello LocalClaw'", "Hello LocalClaw", "shell"),
        ("Current directory", "What is the current working directory?", None, "shell"),
        ("Date", "What is today's date? Use shell to find out.", None, "shell"),
    ]

    # Sync TODOs to ACP
    if acp:
        acp.sync_todos([
            {"id": f"shell_{i}", "content": f"Shell: {t[0]}", "status": "pending", "priority": "medium"}
            for i, t in enumerate(tests)
        ])

    results = []

    for i, (name, prompt, expected, required_tool) in enumerate(tests):
        print(f"\n📋  {name}")
        print(f"   Prompt: {prompt}")

        if acp:
            acp._request("/api/todos/update", "POST", {"id": f"shell_{i}", "status": "in_progress"})

        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Use the shell tool to run commands when asked.",
            max_steps=5,
            on_step=on_step,
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
            print(f"  ❌  Error: {error}")
            if acp:
                acp._request("/api/todos/update", "POST", {"id": f"shell_{i}", "status": "pending"})
            continue

        # Verify tool was used
        tool_used = check_tool_used(run, required_tool)
        if not tool_used:
            print(f"  ⚠️ WARNING: Shell tool was NOT called!")
            results.append(False)
            print(f"  ❌  FAILED: Tool not used")
            print(f"  📝  Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
            if acp:
                acp._request("/api/todos/update", "POST", {"id": f"shell_{i}", "status": "pending"})
            continue

        # Check expected value if provided
        if expected:
            passed = expected.lower() in run.final_answer.lower()
            results.append(passed)
            status = "✅" if passed else "❌"
            print(f"  {status} Expected '{expected}' in response")
        else:
            results.append(True)
            print(f"  ✅  Tool was used correctly")

        if acp:
            acp._request("/api/todos/update", "POST", {
                "id": f"shell_{i}",
                "status": "completed" if results[-1] else "pending"
            })

        print(f"  📝  Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
        print(f"  ⏱️  {elapsed:.1f}s, {len(run.steps)} steps")

    passed = sum(results)
    total = len(results)
    print(f"\n📊  Shell: {passed}/{total} tests passed ({100*passed//total}%)")
    return passed, total


def test_python_repl():
    """Test Python REPL tool - models must figure out how to use it."""
    client = OllamaClient()

    print(f"\n{'='*60}")
    print(f"🐍  Python REPL Tool Tests (ACP Enabled)")
    print(f"   Model: {MODEL}")
    print(f"   Timeout: {TIMEOUT}s per test")
    print(f"{'='*60}")

    tools = make_builtin_registry().subset(["python_repl"])
    on_step = make_on_step_callback()

    tests = [
        ("Power calculation", "What is 2 to the power of 20?", "1048576", "python_repl"),
        ("List squares", "Generate a list of squares from 1 to 5. What are they?", "1, 4, 9, 16, 25", "python_repl"),
        ("String repeat", "What is 'Hello' repeated 3 times?", "HelloHelloHello", "python_repl"),
    ]

    # Sync TODOs to ACP
    if acp:
        acp.sync_todos([
            {"id": f"pyrepl_{i}", "content": f"Python REPL: {t[0]}", "status": "pending", "priority": "medium"}
            for i, t in enumerate(tests)
        ])

    results = []

    for i, (name, prompt, expected, required_tool) in enumerate(tests):
        print(f"\n📋  {name}")
        print(f"   Prompt: {prompt}")

        if acp:
            acp._request("/api/todos/update", "POST", {"id": f"pyrepl_{i}", "status": "in_progress"})

        agent = Agent(
            model=MODEL,
            client=client,
            tools=tools,
            system_prompt="Use Python REPL for calculations. Use print() to show results in your code.",
            max_steps=5,
            on_step=on_step,
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
            print(f"  ❌  Error: {error}")
            if acp:
                acp._request("/api/todos/update", "POST", {"id": f"pyrepl_{i}", "status": "pending"})
            continue

        # Verify tool was used
        tool_used = check_tool_used(run, required_tool)
        if not tool_used:
            print(f"  ⚠️ WARNING: Python REPL tool was NOT called!")
            results.append(False)
            print(f"  ❌  FAILED: Tool not used")
            print(f"  📝  Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
            if acp:
                acp._request("/api/todos/update", "POST", {"id": f"pyrepl_{i}", "status": "pending"})
            continue

        # Check answer with flexible matching
        passed = False
        if expected in run.final_answer:
            passed = True
        else:
            expected_clean = expected.replace("[", "").replace("]", "").replace(" ", "")
            answer_clean = run.final_answer.replace("[", "").replace("]", "").replace(" ", "")
            if expected_clean in answer_clean:
                passed = True

        results.append(passed)

        if acp:
            acp._request("/api/todos/update", "POST", {
                "id": f"pyrepl_{i}",
                "status": "completed" if passed else "pending"
            })

        status = "✅" if passed else "❌"
        print(f"  {status} Expected '{expected}' in response")
        print(f"  📝  Answer: {run.final_answer[:100].replace(chr(10), ' ')}...")
        print(f"  ⏱️  {elapsed:.1f}s, {len(run.steps)} steps, tool_used={tool_used}")

    passed = sum(results)
    total = len(results)
    print(f"\n📊  Python REPL: {passed}/{total} tests passed ({100*passed//total}%)")
    return passed, total


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    global acp

    # Parse ACP URL
    acp_host = ACP_URL
    acp_port = 8766
    if "://" in acp_host:
        acp_host = acp_host.split("://", 1)[1]
    if ":" in acp_host:
        acp_host, port_str = acp_host.rsplit(":", 1)
        acp_port = int(port_str)

    # Connect to ACP
    print(f"Connecting to ACP at {acp_host}:{acp_port}...")
    acp = ACPPlugin(host=acp_host, port=acp_port)
    status = acp.get_status()

    if "error" in status:
        print(f"⚠️  ACP not available: {status['error']}")
        print("   Tests will run without ACP logging.")
        print("   Start ACP with: python VTSTech-GLMACP.py")
        acp = None
    else:
        print(f"✅  Connected to ACP")
        print(f"   Session tokens: {status.get('session_tokens', 0):,}")

    print(f"\n{'='*60}")
    print(f"🔧  Starting tool tests with model {MODEL}")
    print(f"{'='*60}")

    if acp:
        acp.add_note("context", f"Tool tests started with model {MODEL}", "normal")

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

    # Summary
    print(f"\n{'='*60}")
    print(f"📊  TOTAL: {total_passed}/{total_tests} tests passed ({100*total_passed//total_tests}%)")
    print(f"{'='*60}")

    # ACP session summary
    if acp:
        tokens = acp.get_session_tokens()
        print(f"   ACP Session Tokens: {tokens:,}")
        acp.add_note("summary", f"Tool tests complete: {total_passed}/{total_tests} passed", "high")

    return total_passed == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)