import json
import re
import os
import platform
import getpass
import uuid
import tempfile
from datetime import datetime
from tools import run_shell
from state import AgentState, goal_satisfied
from ollama import chat_api
from prompts import (
    REFINER_PROMPT, 
    WORKER_PROMPT, 
    DEVOPS_EXPERT_PROMPT,
    AUDITOR_PROMPT,
    TEST_PROMPTS
)
from cli import handle_command

def banner(worker_model, refiner_model):
    print(f"\n{'='*70}")
    print(f"VTSBot R4 LocalClaw - Multi-Agent Orchestration System")
    print(f"{'='*70}")
    print(f"Dispatcher: {refiner_model:<25} Worker: {worker_model}")
    print(f"{'='*70}\n")

def bootstrap_environment(state):
    try:
        username = getpass.getuser()
        uname = os.uname()
    except Exception:
        username = os.environ.get("USER", "unknown")
        uname = type('obj', (object,), {'machine': 'unknown', 'release': 'unknown'})
    
    info = {
        "arch": uname.machine,
        "os": platform.system(),
        "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cwd": os.getcwd(),
        "user": username,
        "host": platform.node()
    }
    
    state.collected["environment"] = True
    return (
        f"SYSTEM:\n"
        f"ARCH: {info['arch']}\n"
        f"OS: {info['os']}\n"
        f"TIME: {info['now']}\n"
        f"CWD: {info['cwd']}\n"
        f"USER: {info['user']}\n"
        f"HOST: {info['host']}\n"
    )

def clean_dispatcher_output(text):
    """Clean dispatcher output to extract [TAG] payload"""
    if not text:
        return "CHAT", ""
    
    # Remove all markdown code blocks
    text = re.sub(r'```[a-z]*\s*', '', text)
    text = re.sub(r'\s*```\s*', '', text)
    
    # Look for [TAG] pattern
    match = re.search(r'\[(CHAT|LOCAL|DIRECT|SCRIPT)\]\s*(.*)', text, re.DOTALL | re.IGNORECASE)
    
    if match:
        tag = match.group(1).upper()
        payload = match.group(2).strip()
        
        # Clean up payload
        payload = re.sub(r'^\s*-\s*', '', payload)  # Remove bullet points
        payload = re.sub(r'\s*\n\s*', ' ', payload)  # Collapse newlines
        payload = payload.strip()
        
        return tag, payload
    else:
        # If no tag found, check if it's a local info request
        text_lower = text.lower()
        local_keywords = ['user', 'host', 'cwd', 'arch', 'os', 'time', 'date', 'path', 'directory']
        if any(keyword in text_lower for keyword in local_keywords):
            return "LOCAL", text
        # Check if it looks like a command
        elif any(cmd in text_lower for cmd in ['ls', 'echo', 'cat', 'mkdir', 'rm', 'mv', 'cp', 'gcc']):
            if '|' in text or '&&' in text or '>' in text:
                return "SCRIPT", text
            else:
                return "DIRECT", text
        else:
            return "CHAT", text

def run_agent(refiner_model, coord_model, worker_model, test_queue=None):
    banner(worker_model, refiner_model)
    messages, trace = [], []
    state = AgentState(goal="Session Start")
    sys_context = bootstrap_environment(state)
    print(f"  [SYSTEM] Environment synchronized. Safety protocols active.\n")
    
    if test_queue:
        print(f"  [TEST MODE] {len(test_queue)} tests queued\n")
    
    while True:
        if test_queue is not None:
            if not test_queue:
                print(f"\n  [TEST COMPLETE] All tests executed")
                break
            user = test_queue.pop(0)
            print(f"\n[TEST] >>> {user}")
        else:
            try:
                user = input("\nVTS> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n[SYSTEM] Session terminated.")
                break
                
            if not user:
                continue
        
        if user.lower() in ["/exit", "/quit", "exit", "quit"]:
            print("[SYSTEM] Terminating VTSBot session.")
            break
            
        if user.startswith('/'):
            if handle_command(user, {"messages": messages, "state": state, "trace": trace, "model": worker_model}):
                continue
        
        # --- AGENT 1: DISPATCHER ---
        state.active_agent = "Dispatcher"
        
        refiner_system = f"{REFINER_PROMPT}\n\n{sys_context}"
        try:
            refined = chat_api(
                refiner_model, 
                [
                    {"role": "system", "content": refiner_system},
                    {"role": "user", "content": user}
                ], 
                []
            )
            refined_query = refined["message"]["content"].strip()
            
            # Parse the dispatcher output
            tag, payload = clean_dispatcher_output(refined_query)
            
            # Validate
            if not payload:
                print(f"  [ERROR] Empty payload from dispatcher. Using CHAT.")
                tag = "CHAT"
                payload = user
                
        except Exception as e:
            print(f"  [ERROR] Dispatcher failed: {e}")
            tag = "CHAT"
            payload = user
        
        print(f"  [Dispatcher] Tag: {tag}")
        
        if tag == "LOCAL":
            # Search in system context
            keywords = [k.strip() for k in payload.lower().split() if k.strip()]
            found = []
            
            for line in sys_context.split('\n'):
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in keywords):
                    found.append(line)
            
            if found:
                print(f"  [Local Info]")
                for line in found[:3]:  # Limit output
                    print(f"    {line}")
            else:
                print(f"  [Local Info] No matching information.")
            continue

        if tag == "CHAT":
            worker_system = f"{WORKER_PROMPT}\n\n{sys_context}"
            try:
                chat_res = chat_api(
                    worker_model, 
                    [
                        {"role": "system", "content": worker_system},
                        {"role": "user", "content": user}
                    ], 
                    []
                )
                response = chat_res['message']['content'].strip()
                
                # Clean markdown from response
                response = re.sub(r'```[a-z]*\s*', '', response)
                response = re.sub(r'\s*```\s*', '', response)
                
                print(f"  VTSBot: {response}")
                
                messages.append({"role": "user", "content": user})
                messages.append({"role": "assistant", "content": response})
                
            except Exception as e:
                print(f"  [ERROR] Worker failed: {e}")
            continue

        # --- COMMAND EXECUTION (DIRECT/SCRIPT) ---
        if tag in ["DIRECT", "SCRIPT"]:
            current_cmd = payload
            max_attempts = 2
            
            for attempt in range(max_attempts):
                state.active_agent = "DevOps"
                
                print(f"  [DevOps] Attempt {attempt+1}/{max_attempts}")
                
                # Execute command
                if tag == "DIRECT":
                    print(f"  [EXEC] $ {current_cmd[:80]}{'...' if len(current_cmd) > 80 else ''}")
                    obs = run_shell(current_cmd)
                else:
                    # Create temporary script
                    try:
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                            f.write("#!/bin/bash\n")
                            f.write("# VTSBot script\n")
                            f.write(f"{current_cmd}\n")
                            script_path = f.name
                        
                        os.chmod(script_path, 0o700)
                        print(f"  [SCRIPT] Executing script...")
                        obs = run_shell(f"bash {script_path}")
                        os.unlink(script_path)
                    except Exception as e:
                        obs = f"Script error: {e}"
                
                state.last_result = obs
                state.step += 1
                
                print(f"  [Output] {obs[:150]}{'...' if len(obs) > 150 else ''}")
                
                # --- AGENT 4: AUDITOR ---
                state.active_agent = "Auditor"
                
                audit_sys = f"{AUDITOR_PROMPT}"
                audit_res = chat_api(
                    refiner_model, 
                    [
                        {"role": "system", "content": audit_sys},
                        {"role": "user", "content": f"Goal: {user}\nCommand Output: {obs[:500]}"}
                    ], 
                    []
                )
                
                audit_result = audit_res['message']['content'].strip().upper()
                print(f"  [Auditor] Result: {audit_result}")
                
                if "PASS" in audit_result:
                    # Success - get final report
                    confirm_sys = f"{WORKER_PROMPT}\n\n{sys_context}"
                    confirm_res = chat_api(
                        worker_model, 
                        [
                            {"role": "system", "content": confirm_sys},
                            {"role": "user", "content": f"Task completed with output: {obs[:200]}"}
                        ], 
                        []
                    )
                    report = confirm_res['message']['content'].strip()
                    print(f"  [Worker] {report}")
                    break
                else:
                    # Auditor says FAIL
                    if attempt < max_attempts - 1:
                        print(f"  [RETRY] Auditor rejected output. Fixing command...")
                        # Get fixed command from DevOps expert
                        fix_sys = f"{DEVOPS_EXPERT_PROMPT}"
                        fix_res = chat_api(
                            refiner_model, 
                            [
                                {"role": "system", "content": fix_sys},
                                {"role": "user", "content": f"Fix command: {current_cmd}\nError: {obs}"}
                            ], 
                            []
                        )
                        current_cmd = fix_res['message']['content'].strip()
                        current_cmd = re.sub(r'```[a-z]*\s*', '', current_cmd)
                        current_cmd = re.sub(r'\s*```\s*', '', current_cmd)
                    else:
                        print(f"  [FAILED] Max retries reached.")
                        break
            
            continue