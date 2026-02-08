import json
import time
from tools import run_shell

def handle_command(cmd, context):
    messages = context["messages"]
    state = context.get("state")
    trace = context["trace"]
    model = context["model"]

    if cmd == "/help":
        print("/status /context /trace /env /last /files /clear /reset /exit")
        return True

    if cmd == "/status":
        print(f"\nModel: {model}")
        print(f"Messages: {len(messages)}")
        print(f"Last step: {state.step if state else 'N/A'}")
        return True

    if cmd == "/template":
        from ollama import get_model_info
        template = get_model_info(model, "template")
        print(f"\n--- TEMPLATE for {model} ---")
        print(template)
        return True

    if cmd == "/clean":
        if not state or not state.files_written:
            print("No files to clean.")
        else:
            print("\nCleaning sandbox...")
            for file in state.files_written:
                # Bypass safety for the cleanup command specifically
                import os
                try:
                    if os.path.exists(file):
                        os.remove(file)
                        print(f"  Removed: {file}")
                except Exception as e:
                    print(f"  Failed to remove {file}: {e}")
            state.files_written.clear()
            print("Cleanup complete.")
        return True
    if cmd == "/last" and state:
        print(state.last_result or "(none)")
        return True

    if cmd == "/files" and state:
        print("\n".join(state.files_written) or "(none)")
        return True

    if cmd == "/env" and state:
        print(state.collected)
        return True

    if cmd == "/trace":
        print("\n--- TOOL TRACE ---")
        for i, t in enumerate(trace):
            # FIXED: Defensive check for 'args' key to prevent KeyError
            tool_name = t.get('tool', 'unknown')
            tool_args = t.get('args', t.get('command', 'N/A'))
            result = t.get('result', 'No output')
            
            print(f"{i+1}. {tool_name}({tool_args})")
            print(f"   -> {result[:100]}...") # Truncate for readability
            
        if not trace:
            print("(empty)")
        return True

    if cmd == "/context":
        print("\n--- MESSAGE CONTEXT ---")
        for i, m in enumerate(messages):
            role = m['role']
            content = m.get('content', '')
            if m.get('tool_calls'):
                content = f"[TOOL CALLS: {len(m['tool_calls'])}]"
            print(f"{i:02d} | {role:9} | {content[:80]}")
        return True

    if cmd == "/verify" and state:
        last_file = state.files_written[-1] if state.files_written else None
        if last_file:
            actual = run_shell(f"cat {last_file}")
            print(f"\n[VERIFY] File: {last_file}")
            print(f"  Expected (Memory): {state.last_result}")
            print(f"  Actual (Disk):     {actual}")
            if state.last_result.strip() == actual.strip():
                print("  STATUS: MATCH ?")
            else:
                print("  STATUS: MISMATCH ? (Hallucination Detected)")
        else:
            print("No files written yet.")
        return True

    if cmd == "/clear":
        messages[:] = messages[:1]
        print("Context cleared.")
        return True

    if cmd == "/reset":
        messages[:] = messages[:1]
        trace.clear()
        print("Agent reset.")
        return True

    return False
