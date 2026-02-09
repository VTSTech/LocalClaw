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
        os_data["PRETTY_NAME"] = platform.system()
    return os_data

def bootstrap_environment(state):
    """Gathers system facts using Python for the local context."""
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
    state.last_result = f"System initialized at {info['now']}"
    
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

        # --- STAGE 1: REFINER (Intent Classifier) ---
        refiner_system = f"{REFINER_PROMPT}\n\n{sys_context}"
        refined = chat_api(refiner_model, [{"role": "system", "content": refiner_system}, {"role": "user", "content": user}], [])
        refined_query = refined["message"]["content"].strip()
        
        # Regex to capture [TAG] and Payload
        tag_match = re.search(r'\[(CHAT|LOCAL|DIRECT|SCRIPT)\]\s*(.*)', refined_query, re.DOTALL | re.IGNORECASE)
        
        if not tag_match:
            # Fallback if the model ignores the tag format
            if any(k in refined_query.lower() for k in ["rm ", "ls ", "mkdir ", "mv ", "grep "]):
                tag = "SCRIPT" if "\n" in refined_query else "DIRECT"
            else:
                tag = "CHAT"
            payload = refined_query
        else:
            tag = tag_match.group(1).upper()
            payload = tag_match.group(2).strip()

        # --- HEURISTIC OVERRIDE ---
        # Prevent technical commands from being treated as chat yapping
        tech_keywords = ["rm ", "cat ", "ls ", "mkdir ", "mv ", "grep ", "touch ", "find "]
        if tag == "CHAT" and any(k in user.lower() for k in tech_keywords):
            tag = "DIRECT"
            payload = user

        # --- ROUTING ---
        
        # 1. LOCAL (Context-Based Lookup)
        if tag == "LOCAL":
            found_info = []
            p_low = payload.lower()
            lines = sys_context.split('\n')
            
            # Key Mapping for context lookup
            mapping = {
                "date": ["DATE", "now", "time"],
                "cwd": ["CWD", "dir", "path", "working directory"],
                "arch": ["ARCH", "architecture", "cpu"],
                "os": ["OS", "distro", "ubuntu", "linux"],
                "user": ["USER", "whoami", "username"],
                "host": ["HOST", "hostname", "machine"]
            }

            for line in lines:
                if not line.strip() or ":" not in line: continue
                for key, synonyms in mapping.items():
                    if any(s in p_low for s in synonyms) and line.split(':')[0].strip('- ').strip() == key.upper():
                        if line not in found_info: found_info.append(line)
            
            res = "\n".join(found_info) if found_info else f"Info not found in context for query: {payload}"
            print(f"  VTSBot (Local Lookup):\n    {res}")
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": res})
            continue

        # 2. CHAT (Conversational Assistant)
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
            exec_cmd = payload if (payload and payload.upper() != "DIRECT") else user
            print(f"  [DIRECT EXEC] {exec_cmd}")
            obs = run_shell(exec_cmd)
            print(f"  Worker (Direct)> {obs[:100]}...")
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": obs})
            state.last_result = obs
            state.step += 1
            continue

        # 4. SCRIPT BUNDLE (Multi-Step)
        if tag == "SCRIPT":
            # Sanity check: if it looks like English sentences instead of code, pivot to CHAT
            if payload.count(' ') > payload.count('\n') * 10 and not any(k in payload for k in tech_keywords):
                tag = "CHAT"
                # Fallthrough to logic handled above or just re-run chat logic here
                worker_system = f"{WORKER_PROMPT}\n\n{sys_context}"
                chat_res = chat_api(worker_model, [{"role": "system", "content": worker_system}, {"role": "user", "content": user}], [])
                vts_reply = chat_res['message']['content'].strip()
                print(f"  VTSBot (Script-to-Chat Pivot): {vts_reply}")
                continue

            lines = [l.strip() for l in payload.split('\n') if l.strip()]
            if not lines: lines = [user]
                
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