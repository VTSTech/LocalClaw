# -*- coding: utf-8 -*-
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
    TEST_PROMPTS,
    TEST_ORCHESTRATOR_PROMPT  # New import
)
from cli import handle_command

def banner(worker_model, refiner_model):
    print(f"\n{'='*70}")
    print(f"VTSBot R3 LocalClaw - Multi-Agent Orchestration System")
    print(f"{'='*70}")
    print(f"Dispatcher: {refiner_model:<25} Worker: {worker_model}")
    print(f"Agents: Dispatcher ? Worker/DevOps ? Auditor ? Coordinator")
    print(f"{'='*70}\n")

def bootstrap_environment(state):
    """Enhanced environment bootstrap with more system details"""
    try:
        username = getpass.getuser()
        uname = os.uname()
    except Exception:
        username = os.environ.get("USER", "unknown")
        uname = type('obj', (object,), {'machine': 'unknown', 'release': 'unknown'})
    
    # Get more system info
    try:
        cpu_info = platform.processor() or "Unknown"
        python_version = platform.python_version()
    except:
        cpu_info = "Unknown"
        python_version = "Unknown"
    
    info = {
        "arch": uname.machine,
        "os": platform.system(),
        "os_release": platform.release(),
        "cpu": cpu_info,
        "python": python_version,
        "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cwd": os.getcwd(),
        "home": os.path.expanduser("~"),
        "user": username,
        "host": platform.node(),
        "shell": os.environ.get("SHELL", "Unknown"),
    }
    
    state.collected["environment"] = True
    state.collected["system_info"] = info
    
    return (
        f"SYSTEM CONTEXT:\n"
        f"- ARCHITECTURE: {info['arch']}\n"
        f"- OS: {info['os']} {info['os_release']}\n"
        f"- CPU: {info['cpu']}\n"
        f"- PYTHON: {info['python']}\n"
        f"- TIME: {info['now']}\n"
        f"- WORKDIR: {info['cwd']}\n"
        f"- HOME: {info['home']}\n"
        f"- USER: {info['user']}@{info['host']}\n"
        f"- SHELL: {info['shell']}\n"
        f"- SAFETY: Restricted command execution active\n"
    )

def validate_tag(tag, payload):
    """Validate dispatcher tag and payload for safety"""
    valid_tags = {"CHAT", "LOCAL", "DIRECT", "SCRIPT"}
    
    if tag not in valid_tags:
        return False, f"Invalid tag: {tag}. Must be one of {valid_tags}"
    
    # Additional validation for command tags
    if tag in ["DIRECT", "SCRIPT"]:
        if not payload or payload.strip() == "":
            return False, "Empty command payload"
        
        # Block potentially dangerous patterns even before tools.py
        dangerous_patterns = [
            r"rm\s+(-\w*[rf]|--(recursive|force))",
            r"chmod\s+[0-7]{3,4}\s+.*/",
            r"dd\s+.*if=.*of=.*",
            r"mkfs\.?\w*\s+",
            r">\s*/dev/(sda|hda|nvme)",
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, payload, re.IGNORECASE):
                return False, f"Command blocked by safety pattern: {pattern}"
    
    return True, "Valid"

def create_secure_script(content):
    """Create temporary script with security checks"""
    import tempfile
    import re
    
    try:
        # Clean the content
        clean_content = str(content)
        
        # Remove markdown code blocks
        if '```' in clean_content:
            # Extract content between first and last backticks
            parts = clean_content.split('```')
            if len(parts) >= 3:
                # Take the middle part (inside code block)
                clean_content = parts[1].strip()
                # Remove language specifier if present
                if clean_content.startswith('bash') or clean_content.startswith('shell'):
                    clean_content = clean_content[4:].strip()
        
        # Remove any remaining backticks
        clean_content = clean_content.replace('```', '').strip()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("#!/bin/bash\n")
            f.write("# VTSBot Temporary Script\n")
            f.write("set -e\n")  # Exit on error
            f.write(f"{clean_content}\n")
            script_path = f.name
        
        # Make executable
        os.chmod(script_path, 700)
        return script_path
        
    except Exception as e:
        return None

def run_agent(refiner_model, coord_model, worker_model, test_queue=None):
    banner(worker_model, refiner_model)
    messages, trace = [], []
    state = AgentState(goal="Session Start")
    sys_context = bootstrap_environment(state)
    print(f"  [SYSTEM] Environment synchronized. Safety protocols active.\n")
    
    # Test mode initialization
    if test_queue:
        print(f"  [TEST MODE] {len(test_queue)} tests queued\n")
    
    while True:
        if test_queue is not None:
            if not test_queue:
                print(f"\n  [TEST COMPLETE] All tests executed")
                break
            user = test_queue.pop(0)
            print(f"\n[R3-TEST] >>> {user}")
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
        
        # --- AGENT 1: DISPATCHER (Refiner) ---
        state.active_agent = "Dispatcher"
        print(f"  [Dispatcher] Analyzing request...")
        
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
            
            # Extract tag and payload
            tag_match = re.search(r'\[(CHAT|LOCAL|DIRECT|SCRIPT)\]\s*(.*)', refined_query, re.DOTALL)
            if not tag_match:
                print(f"  [ERROR] Dispatcher output invalid format: {refined_query[:50]}...")
                # Fallback to CHAT
                tag = "CHAT"
                payload = user
            else:
                tag = tag_match.group(1).upper()
                payload = tag_match.group(2).strip()
            
            # Validate tag
            is_valid, validation_msg = validate_tag(tag, payload)
            if not is_valid:
                print(f"  [SAFETY] {validation_msg}. Falling back to CHAT.")
                tag = "CHAT"
                payload = user
                
        except Exception as e:
            print(f"  [ERROR] Dispatcher failed: {e}")
            tag = "CHAT"
            payload = user
        
        print(f"  [Dispatcher] Tag: {tag}, Payload: {payload[:50]}...")
        
        if tag == "LOCAL":
            # Enhanced local info lookup
            keywords = payload.lower().split()
            found_info = []
            for line in sys_context.split('\n'):
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in keywords):
                    found_info.append(line)
            
            if found_info:
                print(f"  [Local Info]")
                for info in found_info[:5]:  # Limit output
                    print(f"    {info}")
                if len(found_info) > 5:
                    print(f"    ... and {len(found_info) - 5} more lines")
            else:
                print(f"  [Local Info] No matching system information found.")
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
                print(f"  VTSBot: {response}")
                
                # Store in message history
                messages.append({"role": "user", "content": user})
                messages.append({"role": "assistant", "content": response})
                
            except Exception as e:
                print(f"  [ERROR] Worker failed: {e}")
            continue

        # --- AGENT 2 & 3: DEVOPS ENGINEER ---
        if tag in ["DIRECT", "SCRIPT"]:
            current_cmd = payload
            attempts = 0
            max_attempts = 2
            
            print(f"  [DevOps] Executing {'script' if tag == 'SCRIPT' else 'command'}...")
            
            while attempts < max_attempts:
                state.active_agent = "DevOps"
                
                try:
                    if tag == "DIRECT":
                        print(f"  [EXEC] $ {current_cmd}")
                        obs = run_shell(current_cmd)
                    else:
                        # Secure script handling
                        script_path = create_secure_script(current_cmd)
                        if isinstance(script_path, tuple):  # Error case
                            obs = script_path[1]
                        else:
                            print(f"  [EXEC-SCRIPT] $ cat script.sh")
                            print(f"    # Content: {current_cmd[:60]}...")
                            obs = run_shell(f"bash {script_path}")
                            # Cleanup
                            try:
                                os.unlink(script_path)
                            except:
                                pass
                    
                    state.last_result = obs
                    state.step += 1
                    
                    # Enhanced tracing
                    trace_entry = {
                        "agent": state.active_agent,
                        "tag": tag,
                        "cmd": current_cmd,
                        "result": obs[:200] + "..." if len(obs) > 200 else obs,
                        "timestamp": datetime.now().isoformat(),
                        "attempt": attempts + 1
                    }
                    trace.append(trace_entry)
                    
                    print(f"  [Output] {obs[:100]}{'...' if len(obs) > 100 else ''}")
                    
                    # --- AGENT 4: AUDITOR ---
                    state.active_agent = "Auditor"
                    print(f"  [Auditor] Analyzing output...")
                    
                    audit_sys = f"{AUDITOR_PROMPT}\n\nCommand: {current_cmd}\nOutput: {obs[:500]}"
                    audit_res = chat_api(
                        refiner_model, 
                        [
                            {"role": "system", "content": audit_sys},
                            {"role": "user", "content": f"User Goal: {user}"}
                        ], 
                        []
                    )
                    
                    audit_result = audit_res['message']['content'].strip().upper()
                    print(f"  [Auditor] Result: {audit_result}")
                    
                    if "PASS" in audit_result:
                        # Task successful - get final confirmation
                        confirm_sys = f"{WORKER_PROMPT}\n\n{sys_context}\nTask executed with result: {obs[:200]}"
                        confirm_res = chat_api(
                            worker_model, 
                            [
                                {"role": "system", "content": confirm_sys},
                                {"role": "user", "content": f"Task completed. Provide final status report."}
                            ], 
                            []
                        )
                        final_report = confirm_res['message']['content'].strip()
                        print(f"  [Worker] {final_report}")
                        
                        # Update state
                        state.completed = True
                        break
                    else:
                        # Auditor flagged issue
                        attempts += 1
                        if attempts < max_attempts:
                            print(f"  [RETRY {attempts}/{max_attempts}] Auditor flagged issues. Consulting Engineer...")
                            
                            fix_sys = f"{DEVOPS_EXPERT_PROMPT}\n\n{sys_context}\nOriginal Command: {current_cmd}\nError Output: {obs}"
                            fix_res = chat_api(
                                refiner_model, 
                                [
                                    {"role": "system", "content": fix_sys},
                                    {"role": "user", "content": f"Fix this command to achieve: {user}"}
                                ], 
                                []
                            )
                            
                            # Clean up command
                            fixed_cmd = fix_res['message']['content'].strip()
                            # Remove code blocks if present
                            fixed_cmd = re.sub(r'```(bash|shell)?\s*', '', fixed_cmd)
                            fixed_cmd = re.sub(r'\s*```\s*', '', fixed_cmd)
                            fixed_cmd = fixed_cmd.strip()
                            
                            print(f"  [Engineer] Suggested fix: {fixed_cmd[:80]}...")
                            current_cmd = fixed_cmd
                        else:
                            print(f"  [FAILURE] Maximum retries ({max_attempts}) reached.")
                            print(f"  [Status] Technical failure. Last output: {obs[:100]}...")
                            state.retries = attempts
                            break
                            
                except Exception as e:
                    print(f"  [ERROR] Execution failed: {e}")
                    attempts = max_attempts  # Break out of retry loop
                    break
            
            continue