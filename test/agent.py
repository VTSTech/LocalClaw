import json
import re
import os
import platform
import getpass
from datetime import datetime
from tools import run_shell
from state import AgentState, goal_satisfied
from ollama import chat_api
from prompts import REFINER_PROMPT, COORDINATOR_PROMPT, WORKER_PROMPT
from cli import handle_command

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

def bootstrap_environment(state):
    """
    Directly gather system facts using Python instead of AI tools.
    Returns a string context for the LLM.
    """
    try:
        username = getpass.getuser()
    except:
        username = os.environ.get("USER", os.environ.get("USERNAME", "unknown"))

    info = {
        "os": platform.system(),
        "os_release": platform.release(),
        "distro": platform.platform(),
        "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cwd": os.getcwd(),
        "user": username
    }
    
    state.collected["environment"] = True
    state.collected["time"] = True
    state.last_result = f"System initialized at {info['now']}"
    
    return (
        f"CURRENT_SYSTEM_INFO:\n"
        f"- OS: {info['os']} ({info['distro']})\n"
        f"- DATE/TIME: {info['now']}\n"
        f"- CWD: {info['cwd']}\n"
        f"- USER: {info['user']}\n"
    )

def run_agent(refiner_model, coord_model, worker_model, test_queue=None):
    banner(worker_model, coord_model)
    messages, trace = [], []

    state = AgentState(goal="System Initialization")
    sys_context = bootstrap_environment(state)
    print(f"  [SYSTEM] Environment and Date synchronized.\n{sys_context}")
    
    while True:
        if test_queue is not None:
            if not test_queue: break
            user = test_queue.pop(0)
            print(f"\n[TEST] User Query: {user}")
        else:
            user = input("\nUser> ").strip()
            if not user: continue
        
        if user.lower() in ["/exit", "/quit"]:
            break            

        if user.startswith('/') and handle_command(user, {"messages": messages, "state": state, "trace": trace, "model": worker_model}):
            continue

        # --- INTERNAL INTENT HANDLER (Static/Common) ---
        query_lower = user.lower()
        handled_locally = False
        lookup_output = []

        system_keywords = ["what is your os", "what os", "current time", "who am i", "current dir", "distro", "distribution", "release", "current date"]
        if any(keyword in query_lower for keyword in system_keywords):
            for line in sys_context.split('\n'):
                if not line.strip(): continue
                if any(x in query_lower for x in ["os", "distro", "distribution", "release"]) and "OS:" in line: 
                    label = "Distro" if "distro" in query_lower or "distribution" in query_lower else "OS"
                    clean_line = line.replace("- OS:", f"- {label}:")
                    lookup_output.append(clean_line)
                    handled_locally = True
                if any(x in query_lower for x in ["time", "date"]) and "DATE" in line: 
                    lookup_output.append(line)
                    handled_locally = True
                if any(x in query_lower for x in ["dir", "cwd", "folder"]) and "CWD" in line: 
                    lookup_output.append(line)
                    handled_locally = True
                if any(x in query_lower for x in ["user", "who am i", "username"]) and "USER" in line:
                    lookup_output.append(line)
                    handled_locally = True

        if handled_locally:
            print(f"  VTSBot (Local Lookup):")
            for out in lookup_output: print(f"    {out}")
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": "\n".join(lookup_output)})
            continue

        messages.append({"role": "user", "content": user})

        # --- STAGE 1: REFINER ---
        refiner_system = f"{REFINER_PROMPT}\n\n{sys_context}\nIf the query requires a system action, output ONLY the bash command(s). For multi-step tasks, output each command on a new line."
        refined = chat_api(refiner_model, [{"role": "system", "content": refiner_system}, {"role": "user", "content": user}], [])
        refined_query = refined["message"]["content"].strip()
        
        # Check if Refiner gave us code/commands directly
        # We assume if it's not "CHAT" and contains common shell indicators, it's a direct command
        shell_indicators = ['ls', 'cat', 'rm', 'mkdir', 'find', 'grep', 'echo', 'cd', 'python']
        is_direct_cmd = any(refined_query.split()[0] == cmd for cmd in shell_indicators if refined_query.split())

        if is_direct_cmd:
            lines = [l.strip() for l in refined_query.split('\n') if l.strip()]
            
            if len(lines) == 1:
                # Direct single execution
                print(f"  [DIRECT EXEC] {lines[0]}")
                obs = run_shell(lines[0])
            else:
                # Multi-step: Create a script and run it
                script_name = f"vts_task_{uuid.uuid4().hex[:8]}.sh"
                script_content = "#!/bin/bash\n" + "\n".join(lines)
                print(f"  [SCRIPT BUNDLE] Executing {len(lines)} steps via {script_name}")
                
                # Write script via run_shell redirection
                run_shell(f"cat << 'EOF' > {script_name}\n{script_content}\nEOF")
                obs = run_shell(f"bash {script_name} && rm {script_name}")

            print(f"  Worker (Direct)> {obs[:100]}...")
            messages.append({"role": "assistant", "content": f"Executed: {refined_query}\nResult: {obs}"})
            state.last_result = obs
            continue

        # --- FALLBACK: COORDINATOR/WORKER (For complex reasoning) ---
        if "CHAT" in refined_query.upper() and len(refined_query) < 10:
            worker_system = f"{WORKER_PROMPT}\n\n{sys_context}"
            chat_res = chat_api(worker_model, [{"role": "system", "content": worker_system}, {"role": "user", "content": user}], [])
            vts_reply = chat_res['message']['content'].strip()
            print(f"  VTSBot: {vts_reply}")
            messages.append({"role": "assistant", "content": vts_reply})
            continue

        print(f"  [REFINED] {refined_query}")

        # 2. COORDINATOR
        plan_res = chat_api(coord_model, [{"role": "system", "content": COORDINATOR_PROMPT}, {"role": "user", "content": refined_query}], [])
        try:
            plan_content = plan_res["message"]["content"]
            json_match = re.search(r'\[.*\]', plan_content, re.DOTALL)
            plan = json.loads(json_match.group(0)) if json_match else json.loads(plan_content)
        except:
            plan = [cmd.strip() for cmd in refined_query.split(';') if cmd.strip()]
        
        plan = [re.sub(r"^echo ['\"](.+)['\"]$", r"\1", p).strip() for p in plan if p.strip()]
        if not plan: continue
            
        print(f"  [PLAN] {plan}")

        state.goal = user
        state.plan = plan
        total_steps = len(plan)
        step_count = 0

        while state.plan:
            step_count += 1
            current_task = state.plan.pop(0)
            print(f"  [STEP {step_count}/{total_steps}] Executing: {current_task}")
            
            worker_system = f"{WORKER_PROMPT}\n\n{sys_context}"
            worker_msgs = [{"role": "system", "content": worker_system}, {"role": "user", "content": f"Task: {current_task}"}]
            res = chat_api(worker_model, worker_msgs, TOOLS)
            msg = res["message"]
            
            obs = None
            cmd_to_run = current_task

            if msg.get("tool_calls"):
                for call in msg["tool_calls"]:
                    args = call["function"]["arguments"]
                    cmd_to_run = args.get("command", current_task)
                    if isinstance(cmd_to_run, dict):
                        cmd_to_run = cmd_to_run.get("command", str(cmd_to_run))
                    
                    obs = run_shell(cmd_to_run)
                    messages.append({"role": "assistant", "tool_calls": msg["tool_calls"]})
            
            if not obs:
                obs = run_shell(cmd_to_run)
                print(f"  Worker (fallback:force_exec)> Running...")

            # --- STATE OBSERVER ---
            write_match = re.search(r'>>?\s*([a-zA-Z0-9_\-\.\/]+)', cmd_to_run)
            if write_match:
                fname = write_match.group(1)
                if fname not in state.files_written: state.files_written.append(fname)
            
            is_env_cmd = any(x in cmd_to_run for x in ["printenv", "echo $PATH", "env"])
            if is_env_cmd and obs and "Error" not in obs:
                state.collected["environment"] = True
            
            if "date" in cmd_to_run or re.search(r'\d{4}-\d{2}-\d{2}', obs):
                state.collected["time"] = True

            if obs:
                preview = obs.replace('\n', ' ')[:60]
                print(f"  Worker (tool:run_shell)> {preview}...")
                messages.append({"role": "tool", "content": obs})

            state.last_result = obs
            state.step = step_count
            trace.append({"tool": "run_shell", "args": {"command": cmd_to_run}, "result": obs})

        if goal_satisfied(state):
            print(f"  [GOAL SATISFIED]")