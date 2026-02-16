import json
from tools import run_shell

def handle_command(cmd, context):
    messages = context.get("messages", [])
    state = context.get("state")
    trace = context.get("trace", [])
    model = context.get("model", "unknown")

    if cmd == "/help":
        print("/status /trace /last /files /skills /exit")
        return True

    if cmd == "/status":
        print(f"\n--- VTSBOT R7 STATUS ---")
        print(f"Model: {model}")
        print(f"Active Agent: {state.active_agent if state else 'None'}")
        print(f"Steps Taken:  {state.step if state else 0}")
        print(f"Memory:       {len(messages)} messages")
        return True

    if cmd == "/last" and state:
        print(state.last_result or "(none)")
        return True

    if cmd == "/files" and state:
        print("\n".join(state.files_written) or "(none)")
        return True

    if cmd == "/trace":
        print("\n--- TOOL CALL TRACE ---")
        for i, t in enumerate(trace):
            tool = t.get('tool', 'unknown')
            args = t.get('args', {})
            print(f"{i+1}. {tool}({args})")
        if not trace:
            print("(empty)")
        return True

    if cmd == "/clear":
        messages[:] = messages[:1]
        print("Context cleared.")
        return True

    if cmd == "/reset":
        messages.clear()
        trace.clear()
        if state:
            state.step = 0
            state.retries = 0
            state.last_result = None
        print("Session reset.")
        return True

    return False