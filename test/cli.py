import json
import time
from ollama import get_model_info

def handle_command(cmd, context):
    messages = context["messages"]
    model = context["model"]
    state = context.get("state")
    trace = context["trace"]

    if cmd == "/status":
        print("\n" + "=" * 60)
        print(f"Model:        {model}")
        print(f"Messages:     {len(messages)}")
        print(f"Last Step:    {state.step if state else 'N/A'}")
        print("=" * 60)
        return True

    if cmd == "/context":
        print("\n" + "-" * 60)
        for i, m in enumerate(messages):
            role = m["role"].upper()
            text = m.get("content", "").replace("\n", " ")
            if len(text) > 80:
                text = text[:77] + "..."
            print(f"{i:02d} | {role:9} | {text}")
        print("-" * 60)
        return True

    if cmd == "/trace":
        print("\n--- TOOL TRACE ---")
        for i, t in enumerate(trace):
            print(f"{i+1}. {t['tool']}({t['args']})")
            print(f"   ? {t['result']}")
        if not trace:
            print("(empty)")
        print("------------------")
        return True

    if cmd == "/template":
        print(get_model_info(model, "template"))
        return True

    if cmd == "/save":
        fname = f"agent_save_{int(time.time())}.json"
        with open(fname, "w") as f:
            json.dump(context, f, indent=2, default=str)
        print(f"Saved to {fname}")
        return True

    if cmd == "/clear":
        messages[:] = [messages[0]]
        print("Context cleared.")
        return True

    return False
