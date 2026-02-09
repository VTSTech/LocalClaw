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

def read_os_release():
    os_data = {}
    with open('/etc/os-release') as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                os_data[key] = value.strip('"')  # Remove surrounding quotes
    return os_data

def bootstrap_environment(state):
    try:
        username = getpass.getuser()
        system_info = os.uname()
    except:
        username = os.environ.get("USER", os.environ.get("USERNAME", "unknown"))
        system_info = os.uname()
    os_info = read_os_release()
    info = {
        "os": system_info.sysname,
        "os_release": system_info.release,
        "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cwd": os.getcwd(),
        "arch": system_info.machine,
        "hostname": system_info.nodename,
        "user": username
    }
    
    state.collected["environment"] = True
    state.collected["time"] = True
    state.last_result = f"System initialized at {info['now']}"
    
    #print(os_info)
    return (
        f"CURRENT_SYSTEM_INFO:\n"
        f"- ARCH: {info['arch']}\n"
        f"- OS: {os_info['NAME']} {os_info['VERSION']} {info['os']} {info['os_release']}\n"
        f"- DATE: {info['now']}\n"
        f"- CWD: {info['cwd']}\n"
        f"- USER: {info['user']}\n"
        f"- HOST: {info['hostname']}\n"
    )

def run_agent(refiner_model, coord_model, worker_model, test_queue=None):
    banner(worker_model, coord_model)
    messages, trace = [], []
    state = AgentState(goal="System Initialization")
    sys_context = bootstrap_environment(state)
    print(f"\n\n[SYSTEM] Environment and Date synchronized.\n\n{sys_context}")
    
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

        # --- STAGE 1: REFINER (Intent Classifier) ---
        refiner_system = f"{REFINER_PROMPT}\n\n{sys_context}"
        refined = chat_api(refiner_model, [{"role": "system", "content": refiner_system}, {"role": "user", "content": user}], [])
        refined_query = refined["message"]["content"].strip()
        
        # Regex to capture [TAG] and Payload
        tag_match = re.search(r'\[(CHAT|LOCAL|DIRECT|SCRIPT)\]\s*(.*)', refined_query, re.DOTALL | re.IGNORECASE)
        
        if not tag_match:
            # Smart fallback for small model tagging failure
            tag = "SCRIPT" if "\n" in refined_query else "DIRECT"
            payload = refined_query
        else:
            tag = tag_match.group(1).upper()
            payload = tag_match.group(2).strip()

        # --- ROUTING ---
        
        # 1. LOCAL (Context-Based)
        if tag == "LOCAL":
            found_info = []
            p_low = payload.lower()
            for line in sys_context.split('\n'):
                if not line.strip(): continue
                if any(k in p_low for k in ["time", "date"]) and "DATE" in line: found_info.append(line)
                if any(k in p_low for k in ["cwd", "dir", "path"]) and "CWD" in line: found_info.append(line)
                if any(k in p_low for k in ["os", "arch", "distro", "host"]) and any(x in line for x in ["OS:", "ARCH:", "HOST:"]): found_info.append(line)
                if any(k in p_low for k in ["user", "whoami"]) and "USER" in line: found_info.append(line)
            
            res = "\n".join(found_info) if found_info else f"Info not found in context: {payload}"
            print(f"  VTSBot (Local Lookup):\n    {res}")
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": res})
            continue

        # 2. CHAT (Conversational)
        if tag == "CHAT":
            worker_system = f"{WORKER_PROMPT}\n\n{sys_context}"
            chat_res = chat_api(worker_model, [{"role": "system", "content": worker_system}, {"role": "user", "content": user}], [])
            vts_reply = chat_res['message']['content'].strip()
            print(f"  VTSBot: {vts_reply}")
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": vts_reply})
            continue

        # 3. DIRECT (Immediate Exec)
        if tag == "DIRECT":
            # Sanity check: Ensure payload isn't empty or just a tag
            if not payload or payload.upper() == "DIRECT": payload = user 
            print(f"  [DIRECT EXEC] {payload}")
            obs = run_shell(payload)
            print(f"  Worker (Direct)> {obs[:100]}...")
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": obs})
            state.last_result = obs
            state.step += 1
            continue

        # 4. SCRIPT (Bundled Exec)
        if tag == "SCRIPT":
            lines = [l.strip() for l in payload.split('\n') if l.strip()]
            if not lines:
                print("  [ERROR] Empty script payload.")
                continue
            
            script_name = f"vts_task_{uuid.uuid4().hex[:8]}.sh"
            script_content = "#!/bin/bash\n" + "\n".join(lines)
            print(f"  [SCRIPT BUNDLE] Executing {len(lines)} steps via {script_name}")
            
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