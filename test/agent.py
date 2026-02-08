import json
from tools import run_shell#, read_file, write_file
from state import AgentState, goal_satisfied
from ollama import chat_api
from prompts import REFINER_PROMPT, COORDINATOR_PROMPT, WORKER_PROMPT
from cli import handle_command

#TOOLS = [
#    {"type": "function", "function": {
#        "name": "run_shell",
#        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}
#    }},
#    {"type": "function", "function": {
#        "name": "read_file",
#        "parameters": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]}
#    }},
#    {"type": "function", "function": {
#        "name": "write_file",
#        "parameters": {"type": "object", "properties": {
#            "filename": {"type": "string"},
#            "content": {"type": "string"}
#        }, "required": ["filename", "content"]}
#    }},
#]

TOOLS = [
    {"type": "function", "function": {
        "name": "run_shell",
        "description": "Execute a bash command in the Linux terminal",
        "parameters": {
            "type": "object", 
            "properties": {
                "command": {"type": "string"}
            }, 
            "required": ["command"]
        }
    }}
]

def banner(worker_model, coord_model):
    print(f"-- VTSBot AI Online (Models: {worker_model}, {coord_model})")
    print(f"-- Written by VTSTech https://www.vts-tech.org https://github.com/VTSTech --")
    
def run_agent(refiner_model, coord_model, worker_model, test_queue=None):
    banner(worker_model, coord_model)
    messages = []
    state = None
    trace = []

    while True:
        # Support for automated testing    
        if test_queue is not None:
            if not test_queue: break
            user = test_queue.pop(0)
            print(f"\n[TEST] User Query: {user}")
        else:
            user = input("\nUser> ").strip()
            if not user: continue
        if user.lower() in ["/exit", "/quit"]:
            break            
        if handle_command(user, {"messages": messages, "state": state, "trace": trace, "model": worker_model}):
            continue

        # 1. Refiner Stage
        refined = chat_api(refiner_model, [{"role": "system", "content": REFINER_PROMPT}, {"role": "user", "content": user}], [])
        refined_query = refined["message"]["content"].strip()
        print(f"  [REFINED] {refined_query}")

        # 2. Coordinator Stage
        plan_res = chat_api(coord_model, [{"role": "system", "content": COORDINATOR_PROMPT}, {"role": "user", "content": refined_query}], [])
        try:
            plan = json.loads(plan_res["message"]["content"])
        except:
            plan = [refined_query]
        print(f"  [PLAN] {plan}")

        state = AgentState(goal=user, plan=plan)

        # 3. Worker Stage (Shell-Only)
        while state.plan:
            current_task = state.plan.pop(0)
            obs = "Error: Tool not called"
            
            worker_msgs = [
                {"role": "system", "content": WORKER_PROMPT},
                {"role": "user", "content": f"Task: {current_task}"}
            ]
            
            res = chat_api(worker_model, worker_msgs, TOOLS)
            msg = res["message"]

            if msg.get("tool_calls"):
                for call in msg["tool_calls"]:
                    name, args = call["function"]["name"], call["function"]["arguments"]
                    
                    if name == "run_shell":
                        # Handle potential dict-nesting hallucination
                        cmd_string = args.get("command", current_task)
                        if isinstance(cmd_string, dict):
                            cmd_string = cmd_string.get("command", str(cmd_string))
                        
                        obs = run_shell(cmd_string)
                        print(f"  Worker (tool:run_shell)> {obs[:40]}...")

            state.last_result = obs
            trace.append({"tool": "run_shell", "command": current_task, "result": obs})

        if goal_satisfied(state):
            print(f"  [GOAL SATISFIED]")