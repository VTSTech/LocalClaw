import json
import time

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
            print(f"{i+1}. {t['tool']}({t['args']})")
            print(f"   -> {t['result']}")
        if not trace:
            print("(empty)")
        return True

    if cmd == "/context":
        for i, m in enumerate(messages):
            print(f"{i:02d} | {m['role']} | {m.get('content','')[:80]}")
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
