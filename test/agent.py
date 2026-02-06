from tools import run_shell, read_file, write_file
from state import AgentState, goal_satisfied, goal_requires_environment
from ollama import chat_api
from prompts import SYSTEM_PROMPT
from cli import handle_command

TOOLS = [
    {"type": "function", "function": {"name": "run_shell", "parameters": {"type": "object","properties": {"command": {"type": "string"}},"required": ["command"]}}},
    {"type": "function", "function": {"name": "read_file", "parameters": {"type": "object","properties": {"filename": {"type": "string"}},"required": ["filename"]}}},
    {"type": "function", "function": {"name": "write_file", "parameters": {"type": "object","properties": {"filename": {"type": "string"}},"required": ["filename"]}}},
]

def goal_satisfied(state):
    # Never complete without doing at least one action
    if state.step == 0:
        return False

    # If a tool was required, ensure it was actually used
    if goal_requires_environment(state.goal):
        return state.collected["environment"]

    # Otherwise require some observable result
    return state.last_result is not None
    
def run_agent(model):
    print(f"--- Agent Online (Model: {model}) ---")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    last_goal = None
    last_state = None
    trace = []

    while True:
        user_input = input("\nUser> ").strip()
        if not user_input:
            continue

        if user_input.lower() in ["/exit", "/quit"]:
            break

        context = {
            "messages": messages,
            "model": model,
            "state": last_state,
            "trace": trace
        }

        if handle_command(user_input.lower(), context):
            continue

        last_goal = user_input
        state = AgentState(goal=user_input)
        last_state = state
        trace.clear()

        messages.append({"role": "user", "content": user_input})

        for _ in range(8):
            state.step += 1

            if goal_requires_environment(state.goal) and not state.collected["environment"]:
                messages.append({
                    "role": "system",
                    "content": "The goal requires operating system environment details."
                })

            res = chat_api(model, messages, TOOLS)
            msg = res["message"]
            messages.append(msg)

            if msg.get("tool_calls"):
                for call in msg["tool_calls"]:
                    name = call["function"]["name"]
                    args = call["function"]["arguments"]

                    if name == "run_shell":
                        obs = run_shell(args.get("command"))
                        cmd = args.get("command", "").lower()
                        if any(x in cmd for x in ["env", "printenv", "uname", "os-release", "lsb_release"]):
                            state.collected["environment"] = True
                        if "date" in cmd:
                            state.collected["time"] = True

                    elif name == "read_file":
                        obs = read_file(args.get("filename"))

                    elif name == "write_file":
                        obs = write_file(args.get("filename"), state.last_result)
                        state.files_written.append(args.get("filename"))

                    trace.append({"tool": name, "args": args, "result": obs})
                    state.last_result = obs
                    messages.append({"role": "tool", "content": obs})

                if goal_satisfied(state):
                    state.completed = True
                    print("\nAgent> Task completed.")
                    break

            elif msg.get("content"):
                print(f"\nAgent> {msg['content']}")
                break
