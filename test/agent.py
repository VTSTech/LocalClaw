from tools import run_shell, read_file, write_file
from state import AgentState, goal_satisfied, goal_requires_environment
from ollama import chat_api
from prompts import SYSTEM_PROMPT
from cli import handle_command

TOOLS = [
    {"type": "function", "function": {
        "name": "run_shell",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"}
        }, "required": ["command"]}
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "parameters": {"type": "object", "properties": {
            "filename": {"type": "string"}
        }, "required": ["filename"]}
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "parameters": {"type": "object", "properties": {
            "filename": {"type": "string"}
        }, "required": ["filename"]}
    }},
]

def run_agent(model):
    print(f"--- Agent Online (Model: {model}) ---")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    state = None
    trace = []

    while True:
        user = input("\nUser> ").strip()
        if not user:
            continue
        if user.lower() in ["/exit", "/quit"]:
            break

        if handle_command(user.lower(), {
            "messages": messages,
            "state": state,
            "trace": trace,
            "model": model
        }):
            continue

        state = AgentState(goal=user)
        trace.clear()
        messages.append({"role": "user", "content": user})

        for _ in range(6):
            state.step += 1
            res = chat_api(model, messages, TOOLS)
            msg = res["message"]
            messages.append(msg)

            if msg.get("tool_calls"):
                for call in msg["tool_calls"]:
                    name = call["function"]["name"]
                    args = call["function"]["arguments"]

                    if name == "run_shell":
                        obs = run_shell(args["command"])
                        state.collected["environment"] = True
                    elif name == "read_file":
                        obs = read_file(args["filename"])
                    elif name == "write_file":
                        obs = write_file(args["filename"], state.last_result)
                        state.files_written.append(args["filename"])

                    state.last_result = obs
                    trace.append({"tool": name, "args": args, "result": obs})
                    messages.append({"role": "tool", "content": obs})
                    print(f"\nAgent (tool:{name})>\n{obs}")

            if goal_satisfied(state):
                print("\nAgent> Task completed.")
                break
