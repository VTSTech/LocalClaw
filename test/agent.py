import json, re
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

        # 1. REFINER: Mapping casual language to tech specs
        refined = chat_api(refiner_model, [{"role": "system", "content": REFINER_PROMPT}, {"role": "user", "content": user}], [])
        refined_query = refined["message"]["content"].strip()
        print(f"  [REFINED] {refined_query}")

        # 2. COORDINATOR: Planning the command sequence
        plan_res = chat_api(coord_model, [{"role": "system", "content": COORDINATOR_PROMPT}, {"role": "user", "content": refined_query}], [])
        try:
            plan_text = plan_res["message"]["content"]
            plan = json.loads(plan_text)
        except:
            plan = [refined_query]
        print(f"  [PLAN] {plan}")

        state = AgentState(goal=user, plan=plan)
        total_steps = len(plan)

        # 3. WORKER: Verbose execution loop
        step_count = 0
        while state.plan:
            step_count += 1
            current_task = state.plan.pop(0)
            
            # VERBOSITY: Explicit progress tracking before tool call
            print(f"  [STEP {step_count}/{total_steps}] Executing: {current_task}")
            
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
                        # ARG FLATTENING: Handles 0.5b hallucinating nested dicts or JSON strings
                        cmd_string = args.get("command", current_task)
                        if isinstance(cmd_string, dict):
                            cmd_string = cmd_string.get("command", str(cmd_string))
                        
                        # REDIRECTION TRACKER: Detect if the shell is writing a file
                        write_match = re.search(r'>>?\s*([a-zA-Z0-9_\-\.]+)', cmd_string)
                        if write_match:
                            filename = write_match.group(1)
                            if filename not in state.files_written:
                                state.files_written.append(filename)

                        obs = run_shell(cmd_string)
                        # Print the actual output from the tool
                        preview = obs.replace('\n', ' ')[:60]
                        print(f"  Worker (tool:run_shell)> {preview}...")
            else:
                # If no tool was called, print the error so the user knows why it skipped
                print(f"  Worker (error)> {obs}")

            state.last_result = obs
            state.step = step_count
            trace.append({"tool": "run_shell", "args": {"command": current_task}, "result": obs})

        if goal_satisfied(state):
            print(f"  [GOAL SATISFIED]")