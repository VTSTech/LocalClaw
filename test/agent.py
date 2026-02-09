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
from prompts import (
    REFINER_PROMPT, 
    WORKER_PROMPT, 
    DEVOPS_EXPERT_PROMPT,
    TEST_PROMPTS
)
from cli import handle_command

# R3: Tools are handled via shell-only architecture
TOOLS = [] 

def banner(worker_model, refiner_model):
    print(f"-- VTSBot LocalClaw R3 AI (Models: {refiner_model} / {worker_model})")
    print(f"-- Written by VTSTech https://www.vts-tech.org https://github.com/VTSTech --")
    print(f"-- Multi-Agent Orchestration: Enabled --")

def read_os_release():
    os_data = {}
    try:
        if os.path.exists('/etc/os-release'):
            with open('/etc/os-release') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        os_data[key] = value.strip('"')
        else:
            os_data["PRETTY_NAME"] = platform.system()
    except Exception:
        os_data["PRETTY_NAME"] = "Linux/Unknown"
    return os_data

def bootstrap_environment(state):
    """Gathers system facts for the local context."""
    try:
        username = getpass.getuser()
        uname = os.uname()
    except Exception:
        username = os.environ.get("USER", "unknown")
        uname = type('obj', (object,), {'machine': 'unknown', 'release': 'unknown'})
        
    os_info = read_os_release()
    info = {
        "arch": uname.machine,
        "os": os_info.get("PRETTY_NAME", "Linux"),
        "kernel": uname.release,
        "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cwd": os.getcwd(),
        "user": username,
        "host": platform.node()
    }
    
    state.collected["environment"] = True
    state.collected["time"] = True
    
    return (
        f"CURRENT_SYSTEM_INFO:\n"
        f"- ARCH: {info['arch']}\n"
        f"- OS: {info['os']} Linux {info['kernel']}\n"
        f"- DATE: {info['now']}\n"
        f"- CWD: {info['cwd']}\n"
        f"- USER: {info['user']}\n"
        f"- HOST: {info['host']}\n"
    )

def run_agent(refiner_model, coord_model, worker_model, test_queue=None):
    banner(worker_model, refiner_model)
    messages, trace = [], []
    state = AgentState(goal="Session Start")
    sys_context = bootstrap_environment(state)
    print(f"  [SYSTEM] R3 State Initialized.\n{sys_context}")
    
    while True:
        if test_queue is not None:
            if not test_queue: break
            user = test_queue.pop(0)
            print(f"\n[R3-TEST] Query: {user}")
        else:
            user = input("\nVTS> ").strip()
            if not user: continue
        
        if user.lower() in ["/exit", "/quit"]: break            
        if user.startswith('/') and handle_command(user, {"messages": messages, "state": state, "trace": trace, "model": worker_model}):
            continue

        # --- DISPATCHER: Intent Classification ---
        refiner_system = f"{REFINER_PROMPT}\n\n{sys_context}"
        refined = chat_api(refiner_model, [{"role": "system", "content": refiner_system}, {"role": "user", "content": user}], [])
        refined_query = refined["message"]["content"].strip()
        
        tag_match = re.search(r'\[(CHAT|LOCAL|DIRECT|SCRIPT)\]\s*(.*)', refined_query, re.DOTALL | re.IGNORECASE)
        tag = tag_match.group(1).upper() if tag_match else "CHAT"
        payload = tag_match.group(2).strip() if tag_match else refined_query

        # --- ROUTING LOGIC ---
        
        # 1. LOCAL CONTEXT LOOKUP
        if tag == "LOCAL":
            found_info = []
            p_low = payload.lower()
            mapping = {"date": "DATE", "time": "DATE", "cwd": "CWD", "arch": "ARCH", "os": "OS", "user": "USER", "host": "HOST"}
            for line in sys_context.split('\n'):
                for key, marker in mapping.items():
                    if key in p_low and marker in line:
                        found_info.append(line)
            
            res = "\n".join(list(set(found_info))) if found_info else "No local data matched."
            print(f"  VTSBot (Local): {res}")
            continue

        # 2. CHAT / EXPLANATION
        if tag == "CHAT":
            worker_system = f"{WORKER_PROMPT}\n\n{sys_context}"
            chat_res = chat_api(worker_model, [{"role": "system", "content": worker_system}, {"role": "user", "content": user}], [])
            vts_reply = chat_res['message']['content'].strip()
            print(f"  VTSBot: {vts_reply}")
            continue

        # 3. DIRECT / SCRIPT EXECUTION
        if tag in ["DIRECT", "SCRIPT"]:
            state.active_agent = "DevOps Expert" if tag == "SCRIPT" else "Dispatcher"
            attempts = 0
            max_attempts = 2
            current_payload = payload
            
            while attempts < max_attempts:
                # Use DEVOPS_EXPERT for SCRIPT refinement if it fails
                if tag == "DIRECT":
                    print(f"  [EXEC] {current_payload}")
                    obs = run_shell(current_payload)
                else:
                    s_name = f"vts_r3_{uuid.uuid4().hex[:6]}.sh"
                    print(f"  [SCRIPT] {s_name}")
                    # Write script without backticks
                    run_shell(f"cat << 'EOF' > {s_name}\n#!/bin/bash\n{current_payload}\nEOF")
                    obs = run_shell(f"bash {s_name} && rm {s_name}")
                
                state.last_result = obs
                state.step += 1
                trace.append({"tool": tag, "command": current_payload, "result": obs, "agent": state.active_agent})
                
                if goal_satisfied(state):
                    # Use Worker to confirm success briefly
                    confirm_sys = f"{WORKER_PROMPT}\n\n{sys_context}"
                    confirm_prompt = f"The user command '{current_payload}' resulted in: {obs}. Confirm status."
                    confirm_res = chat_api(worker_model, [{"role": "system", "content": confirm_sys}, {"role": "user", "content": confirm_prompt}], [])
                    print(f"  Worker> {confirm_res['message']['content'].strip()}")
                    break
                else:
                    attempts += 1
                    state.retries += 1
                    if attempts < max_attempts:
                        print(f"  [RETRY] Error detected: {obs[:50]}. Consulting Systems Engineer...")
                        # Consult DevOps Expert for the fix
                        state.active_agent = "DevOps Expert"
                        fix_sys = f"{DEVOPS_EXPERT_PROMPT}\n\n{sys_context}"
                        fix_prompt = f"Command failed: {obs}. Original: {current_payload}. Provide a corrected bash command."
                        fix_res = chat_api(refiner_model, [{"role": "system", "content": fix_sys}, {"role": "user", "content": fix_prompt}], [])
                        
                        # Extract raw bash (expert prompt enforces no backticks)
                        new_payload = fix_res["message"]["content"].strip()
                        # Clean any leftover backticks
                        current_payload = new_payload.replace("```bash", "").replace("```", "").strip()
                    else:
                        print(f"  Worker> FAILED: {obs[:100]}")
            continue