import json
from tools import run_shell, read_file, write_file
from state import AgentState, goal_satisfied
from ollama import chat_api
from prompts import COORDINATOR_PROMPT, WORKER_PROMPT
from cli import handle_command

TOOLS = [
    {"type": "function", "function": {
        "name": "run_shell",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "parameters": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]}
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "parameters": {"type": "object", "properties": {
            "filename": {"type": "string"},
            "content": {"type": "string"}
        }, "required": ["filename", "content"]}
    }},
]

def run_agent(coord_model, worker_model):
    print(f"--- MAS Online ---")
    print(f"Coordinator: {coord_model} | Worker: {worker_model}")
    
    messages = []
    state = None
    trace = []

    while True:
        user = input("\nUser> ").strip()
        if not user or handle_command(user.lower(), {"messages": messages, "state": state, "trace": trace, "model": worker_model}):
            continue

        state = AgentState(goal=user)
        
        # STEP 1: COORDINATOR PLANS
        plan_msg = [{"role": "system", "content": COORDINATOR_PROMPT}, {"role": "user", "content": user}]
        plan_res = chat_api(coord_model, plan_msg, [])
        try:
            # Simple 0.5b models often fail to output clean JSON, so we strip backticks
            raw_plan = plan_res["message"]["content"].replace("```json", "").replace("```", "").strip()
            state.plan = json.loads(raw_plan)
            print(f"  [PLAN] {state.plan}")
        except:
            print("  [ERR] Coordinator failed to generate valid plan.")
            continue

        # STEP 2: WORKER EXECUTES
        worker_msgs = [{"role": "system", "content": WORKER_PROMPT}]
        
        while state.plan:
            current_task = state.plan.pop(0)
            worker_msgs.append({"role": "user", "content": f"Task: {current_task}"})
            
            state.step += 1
            res = chat_api(worker_model, worker_msgs, TOOLS)
            msg = res["message"]
            worker_msgs.append(msg)

            if msg.get("tool_calls"):
                for call in msg["tool_calls"]:
                    name, args = call["function"]["name"], call["function"]["arguments"]
                    
                    if name == "run_shell":
                        obs = run_shell(args["command"])
                    elif name == "read_file":
                        obs = read_file(args["filename"])
                    elif name == "write_file":
                        # Grounding logic to pass previous output into the file
                        content = args.get("content", state.last_result or "")
                        obs = write_file(args["filename"], content)
                    
                    state.last_result = obs
                    trace.append({"tool": name, "args": args, "result": obs})
                    worker_msgs.append({"role": "tool", "content": obs})
                    print(f"  Worker (tool:{name})> {obs[:30]}...")

        if goal_satisfied(state):
            print("\nAgent> MAS Goal Completed.")