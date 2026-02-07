import json
from tools import run_shell, read_file, write_file
from state import AgentState, goal_satisfied
from ollama import chat_api
from prompts import REFINER_PROMPT, COORDINATOR_PROMPT, WORKER_PROMPT
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

def run_agent(refiner_model, coord_model, worker_model):
    print(f"--- VTSBot Online ---")
    messages = []
    state = None
    trace = []

    while True:
        user = input("\nUser> ").strip()
        if not user: continue
        
        # 1. Check for Hard Exit
        if user.lower() in ["/exit", "/quit"]:
            break
            
        if not user or handle_command(user.lower(), {"messages": messages, "state": state, "trace": trace, "model": worker_model}):
            continue

        # STAGE 1: REFINER (Sanitizer)
        refine_msg = [{"role": "system", "content": REFINER_PROMPT}, {"role": "user", "content": user}]
        refined_res = chat_api(refiner_model, refine_msg, [])
        refined_goal = refined_res["message"]["content"].strip()
        print(f"  [REFINED] {refined_goal}")

        state = AgentState(goal=refined_goal)
        trace.clear()
        
        # STAGE 2: COORDINATOR (Planner)
        plan_msg = [{"role": "system", "content": COORDINATOR_PROMPT}, {"role": "user", "content": refined_goal}]
        plan_res = chat_api(coord_model, plan_msg, [])
        try:
            raw_content = plan_res["message"]["content"].replace("```json", "").replace("```", "").strip()
            state.plan = json.loads(raw_content)
            print(f"  [PLAN] {state.plan}")
        except Exception as e:
            print(f"  [ERR] Planning failed: {e}")
            continue

        # STAGE 3: WORKER (Executor)
        worker_msgs = [{"role": "system", "content": WORKER_PROMPT}]
        while state.plan:
            current_task = state.plan.pop(0)
            
            # Variable Grounding (Memory Bridge)
            if state.last_result:
                current_task = current_task.replace("$PREV", state.last_result)

            worker_msgs.append({"role": "user", "content": f"Task: {current_task}"})
            state.step += 1
            
            res = chat_api(worker_model, worker_msgs, [
                {"type": "function", "function": {"name": "run_shell", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
                {"type": "function", "function": {"name": "read_file", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]}}},
                {"type": "function", "function": {"name": "write_file", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}, "content": {"type": "string"}}, "required": ["filename", "content"]}}},
            ])
            msg = res["message"]
            worker_msgs.append(msg)

            if msg.get("tool_calls"):
                for call in msg["tool_calls"]:
                    name, args = call["function"]["name"], call["function"]["arguments"]
                    
                    # Handle arg extraction
                    if name == "run_shell":
                        obs = run_shell(args.get("command", current_task))
                    elif name == "write_file":
                        obs = write_file(args.get("filename", "output.txt"), args.get("content", state.last_result or ""))

                    state.last_result = obs
                    trace.append({"tool": name, "args": args, "result": obs})
                    worker_msgs.append({"role": "tool", "content": obs})
                    print(f"  Worker (tool:{name})> {obs[:30]}...")

        if goal_satisfied(state):
            print("\nAgent> VTSBot Task Completed.")