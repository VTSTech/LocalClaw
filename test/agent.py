import json
import re
import os
import platform
import getpass
import uuid
from datetime import datetime
from tools import run_shell
from state import AgentState, goal_satisfied
from ollama import chat_api
from prompts import REFINER_PROMPT, COORDINATOR_PROMPT, WORKER_PROMPT
from cli import handle_command

# In R2, tools are handled as raw strings/scripts; no JSON schema needed for AI.
TOOLS = [] 

def banner(worker_model, coord_model):
    print(f"-- VTSBot AI Online (Models: {worker_model}, {coord_model})")
    print(f"-- Written by VTSTech https://www.vts-tech.org https://github.com/VTSTech --")

def bootstrap_environment(state):
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

        # --- STAGE 1: REFINER (The Intent Classifier) ---
        refiner_system = f"{REFINER_PROMPT}\n\n{sys_context}"
        refined = chat_api(refiner_model, [{"role": "system", "content": refiner_system}, {"role": "user", "content": user}], [])
        refined_query = refined["message"]["content"].strip()
        
        # Extract Tag and Payload
        # Pattern looks for [TAG] then captures the rest of the string
        tag_match = re.search(r'\[(CHAT|LOCAL|DIRECT|SCRIPT)\]\s*(.*)', refined_query, re.DOTALL | re.IGNORECASE)
        
        if not tag_match:
            # Fallback if the model misses the tag but gives a command
            tag = "SCRIPT" if "\n" in refined_query else "DIRECT"
            payload = refined_query
        else:
            tag = tag_match.group(1).upper()
            payload = tag_match.group(2).strip()

        # --- ROUTING LOGIC ---

        # 1. LOCAL LOOKUP (Fastest)
        if tag == "LOCAL":
            found_info = []
            payload_lower = payload.lower()
            for line in sys_context.split('\n'):
                if not line.strip(): continue
                # Match keywords like 'time', 'cwd', 'user', 'os'
                if any(kw in payload_lower for kw in ["time", "date", "now"]) and "DATE" in line: found_info.append(line)
                if any(kw in payload_lower for kw in ["cwd", "dir", "path", "folder"]) and "CWD" in line: found_info.append(line)
                if any(kw in payload_lower for kw in ["os", "distro", "system", "version"]) and "OS" in line: found_info.append(line)
                if any(kw in payload_lower for kw in ["user", "whoami", "name"]) and "USER" in line: found_info.append(line)
            
            out = "\n".join(found_info) if found_info else "No local info found for: " + payload
            print(f"  VTSBot (Local Lookup):\n    {out}")
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": out})
            continue

        # 2. CHAT (Social)
        if tag == "CHAT":
            worker_system = f"{WORKER_PROMPT}\n\n{sys_context}"
            chat_res = chat_api(worker_model, [{"role": "system", "content": worker_system}, {"role": "user", "content": user}], [])
            vts_reply = chat_res['message']['content'].strip()
            print(f"  VTSBot: {vts_reply}")
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": vts_reply})
            continue

        # 3. DIRECT EXEC (Single Command)
        if tag == "DIRECT":
            print(f"  [DIRECT EXEC] {payload}")
            obs = run_shell(payload)
            print(f"  Worker (Direct)> {obs[:100]}...")
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": obs})
            state.last_result = obs
            state.step += 1
            continue

        # 4. SCRIPT BUNDLE (Multi-Step)
        if tag == "SCRIPT":
            lines = [l.strip() for l in payload.split('\n') if l.strip()]
            if len(lines) == 0:
                print("  [ERROR] Script tag received but no payload.")
                continue
                
            script_name = f"vts_task_{uuid.uuid4().hex[:8]}.sh"
            script_content = "#!/bin/bash\n" + "\n".join(lines)
            print(f"  [SCRIPT BUNDLE] Executing {len(lines)} steps via {script_name}")
            
            # Write and execute
            run_shell(f"cat << 'EOF' > {script_name}\n{script_content}\nEOF")
            obs = run_shell(f"bash {script_name} && rm {script_name}")
            
            print(f"  Worker (Script)> {obs[:100]}...")
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": obs})
            state.last_result = obs
            state.step += 1
            continue

        if goal_satisfied(state):
            print(f"  [GOAL SATISFIED]")