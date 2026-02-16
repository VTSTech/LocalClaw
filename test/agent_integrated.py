# -*- coding: utf-8 -*-
"""
VTSBot R6 - Multi-Agent System with Agent Skills Integration

Combines the original multi-agent architecture with the Agent Skills specification:
- Dispatcher: Routes to skills or tags
- Skills: Provide task-specific instructions
- DevOps: Executes using skill guidance
- Auditor: Verifies results

Architecture:
User Input ? Dispatcher ? [SKILL] ? DevOps ? Auditor ? Worker
                   ?
              [CHAT/LOCAL] ? Direct response
"""

import json
import re
import os
import platform
import getpass
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# Import original components
from tools import run_shell
from state import AgentState, goal_satisfied
from ollama import chat_api
from prompts import WORKER_PROMPT, DEVOPS_EXPERT_PROMPT, AUDITOR_PROMPT, TEST_PROMPTS
from cli import handle_command

# Import Agent Skills
import sys
sys.path.insert(0, str(Path(__file__).parent))
from agent_skills.core.skill import SkillRegistry, Skill, SkillMetadata
from agent_skills.core.skill import parse_skill_md, load_skill, validate_skill


# =============================================================================
# INTEGRATED PROMPTS
# =============================================================================

# Dispatcher now considers skills
SKILL_DISPATCHER_PROMPT = """# DISPATCHER: SKILL-AWARE ROUTING

Analyze the user request and route to the appropriate handler.
Output EXACTLY this format: [TAG] payload

# AVAILABLE HANDLERS:

## Skills (preferred for domain-specific tasks):
{skills_list}

## Tags (for general operations):
[CHAT] - Questions, explanations, conversations
[LOCAL] - Simple system info (user, host, cwd)
[DIRECT] - Single simple commands (ls, pwd, date)
[SCRIPT] - Shell commands needing execution

# ROUTING RULES:

1. Check skills FIRST - if request matches a skill's description, use [SKILL:name]
2. For PDFs, documents, forms ? [SKILL:pdf-processing]
3. For web search, current info ? [SKILL:web-search]
4. For code review, analysis ? [SKILL:code-analysis]
5. For file operations ? [SKILL:file-operations]
6. For shell commands ? [DIRECT] or [SCRIPT]
7. For questions ? [CHAT]
8. For system info ? [LOCAL]

# OUTPUT FORMAT:

[SKILL:skill-name] original request
[CHAT] question here
[LOCAL] user host
[DIRECT] ls -la
[SCRIPT] command here

# EXAMPLES:
Query: "Extract text from report.pdf"
Output: [SKILL:pdf-processing] Extract text from report.pdf

Query: "What's the latest AI news?"
Output: [SKILL:web-search] What's the latest AI news?

Query: "Review my Python code"
Output: [SKILL:code-analysis] Review my Python code

Query: "List files in current directory"
Output: [DIRECT] ls -la

Query: "What is machine learning?"
Output: [CHAT] What is machine learning?
"""

# Skill execution prompt
SKILL_EXECUTION_PROMPT = """# ACTIVE SKILL: {skill_name}

{skill_instructions}

---

# TASK

User Request: {user_request}

Using the skill instructions above, determine the appropriate commands or actions.
Output the shell command(s) needed to accomplish this task.

# RULES:
1. Follow the skill's step-by-step process
2. Use the skill's recommended commands
3. Apply error handling patterns from the skill
4. Make commands safe and idempotent

# OUTPUT:
Output the command(s) to execute. For multiple commands, use && to chain.
"""


# =============================================================================
# AGENT CLASS
# =============================================================================

class SkillAwareMultiAgent:
    """
    Multi-agent system integrated with Agent Skills.
    
    Agent Flow:
    1. Dispatcher ? Routes to skill or tag
    2. Skill Handler ? Provides instructions and commands
    3. DevOps ? Executes commands with skill guidance
    4. Auditor ? Verifies results
    5. Worker ? Reports status
    """
    
    def __init__(
        self,
        refiner_model: str = "qwen2.5:1.5b-instruct-q4_k_m",
        worker_model: str = "qwen2.5-coder:0.5b-instruct-q4_k_m",
        skills_dirs: List[str] = None,
    ):
        self.refiner_model = refiner_model
        self.worker_model = worker_model
        
        # Initialize skill registry
        self.registry = SkillRegistry()
        
        # Load built-in skills
        builtin_dir = Path(__file__).parent / "agent_skills" / "builtin"
        if builtin_dir.exists():
            loaded = self.registry.load_directory(builtin_dir)
            print(f"  [Skills] Loaded {len(loaded)} built-in skills")
        
        # Load additional skill directories
        if skills_dirs:
            for dir_path in skills_dirs:
                loaded = self.registry.load_directory(Path(dir_path))
                print(f"  [Skills] Loaded {len(loaded)} skills from {dir_path}")
        
        # State
        self.state = AgentState(goal="Session Start")
        self.messages: List[Dict] = []
        self.trace: List[Dict] = []
        self.sys_context = self._bootstrap_environment()
    
    def _bootstrap_environment(self) -> str:
        """Collect environment information"""
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
        
        self.state.collected["environment"] = True
        return (
            f"SYSTEM:\n"
            f"ARCH: {info['arch']}\n"
            f"OS: {info['os']}\n"
            f"TIME: {info['now']}\n"
            f"CWD: {info['cwd']}\n"
            f"USER: {info['user']}\n"
            f"HOST: {info['host']}\n"
        )
    
    def _call_llm(self, system: str, user: str) -> str:
        """Call the LLM"""
        try:
            response = chat_api(
                self.refiner_model,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                [],
            )
            return response.get("message", {}).get("content", "")
        except Exception as e:
            return f"[ERROR] LLM call failed: {e}"
    
    def dispatch(self, user_request: str) -> Tuple[str, str, Optional[Skill]]:
        """
        Dispatcher agent: Route to appropriate handler.
        
        Returns:
            (tag, payload, skill) where skill is loaded if [SKILL:xxx]
        """
        self.state.active_agent = "Dispatcher"
        
        # Get skills context
        skills_list = self.registry.get_skills_context()
        
        # Call dispatcher LLM
        system = SKILL_DISPATCHER_PROMPT.format(skills_list=skills_list)
        response = self._call_llm(system, user_request)
        
        # Parse response
        # Check for [SKILL:name]
        skill_match = re.search(r'\[SKILL:([a-z0-9-]+)\]\s*(.*)', response, re.IGNORECASE)
        if skill_match:
            skill_name = skill_match.group(1).lower()
            payload = skill_match.group(2).strip()
            skill = self.registry.get(skill_name)
            if skill:
                return ("SKILL", payload, skill)
            else:
                # Skill not found, fall back to SCRIPT
                return ("SCRIPT", payload, None)
        
        # Check for standard tags
        tag_match = re.search(r'\[(CHAT|LOCAL|DIRECT|SCRIPT)\]\s*(.*)', response, re.DOTALL | re.IGNORECASE)
        if tag_match:
            tag = tag_match.group(1).upper()
            payload = tag_match.group(2).strip()
            return (tag, payload, None)
        
        # Fallback
        return ("CHAT", user_request, None)
    
    def handle_local(self, payload: str) -> str:
        """Handle LOCAL queries from system context"""
        keywords = payload.lower().split()
        found = []
        for line in self.sys_context.split('\n'):
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in keywords):
                found.append(line)
        
        if found:
            return "\n".join(found)
        return "No matching system info found"
    
    def handle_chat(self, user_request: str) -> str:
        """Handle CHAT queries with worker model"""
        self.state.active_agent = "Worker"
        return self._call_llm(WORKER_PROMPT, user_request)
    
    def handle_skill(self, skill: Skill, user_request: str) -> Tuple[str, str]:
        """
        Handle a skill-based request.
        
        Returns:
            (command, skill_instructions)
        """
        self.state.active_agent = f"Skill:{skill.name}"
        
        # Load skill instructions
        instructions = skill.load_instructions()
        
        # Get command from LLM using skill context
        system = SKILL_EXECUTION_PROMPT.format(
            skill_name=skill.name,
            skill_instructions=instructions,
            user_request=user_request,
        )
        
        command = self._call_llm(system, user_request)
        
        # Clean up command
        command = re.sub(r'```(?:bash|shell)?\s*', '', command)
        command = re.sub(r'\s*```\s*', '', command)
        command = command.strip()
        
        return command, instructions
    
    def execute_command(self, command: str, tag: str) -> str:
        """Execute a command via DevOps agent"""
        self.state.active_agent = "DevOps"
        
        print(f"  [DevOps] Executing: {command[:60]}{'...' if len(command) > 60 else ''}")
        
        if tag == "DIRECT":
            result = run_shell(command)
        else:
            # Execute as script
            try:
                script_content = f"#!/bin/bash\nset -e\n{command}"
                with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                    f.write(script_content)
                    script_path = f.name
                
                os.chmod(script_path, 0o700)
                result = run_shell(f"bash {script_path}")
                os.unlink(script_path)
            except Exception as e:
                result = f"Script execution error: {e}"
        
        return result
    
    def audit(self, user_request: str, command: str, result: str) -> bool:
        """
        Auditor agent: Verify command result.
        
        Returns:
            True if PASS, False if FAIL
        """
        self.state.active_agent = "Auditor"
        
        audit_input = f"Goal: {user_request}\nCommand: {command}\nOutput: {result[:500]}"
        response = self._call_llm(AUDITOR_PROMPT, audit_input)
        
        return "PASS" in response.upper()
    
    def get_fix(self, user_request: str, command: str, error: str) -> str:
        """Get a fix for a failed command from DevOps Expert"""
        fix_input = f"Failed Command: {command}\nError Output: {error}\nUser Goal: {user_request}"
        fixed = self._call_llm(DEVOPS_EXPERT_PROMPT, fix_input)
        
        # Clean up
        fixed = re.sub(r'```(?:bash|shell)?\s*', '', fixed)
        fixed = re.sub(r'\s*```\s*', '', fixed)
        return fixed.strip()
    
    def report(self, user_request: str, success: bool, result: str) -> str:
        """Worker reports the final status"""
        self.state.active_agent = "Worker"
        
        if success:
            prompt = f"Task completed successfully: {user_request}. Summarize what was done."
        else:
            prompt = f"Task failed: {user_request}. Error: {result[:200]}"
        
        return self._call_llm(WORKER_PROMPT, prompt)
    
    def run(self, user_request: str) -> str:
        """
        Main execution flow.
        
        Returns:
            Final response string
        """
        # Step 1: Dispatch
        tag, payload, skill = self.dispatch(user_request)
        
        print(f"  [Dispatcher] Tag: {tag}" + (f", Skill: {skill.name}" if skill else ""))
        
        # Step 2: Handle based on tag
        if tag == "LOCAL":
            result = self.handle_local(payload)
            return f"[Local Info]\n{result}"
        
        if tag == "CHAT":
            result = self.handle_chat(payload)
            return result
        
        # Step 3: Get command (from skill or payload)
        if tag == "SKILL" and skill:
            command, skill_instructions = self.handle_skill(skill, user_request)
            tag = "SCRIPT"  # Treat as script execution
        else:
            command = payload
            skill_instructions = None
        
        # Step 4: Execute with retry loop
        max_attempts = 2
        for attempt in range(max_attempts):
            self.state.step += 1
            
            # Execute
            result = self.execute_command(command, tag)
            
            # Record trace
            self.trace.append({
                "agent": self.state.active_agent,
                "command": command[:100],
                "result": result[:200],
            })
            self.state.last_result = result
            
            print(f"  [Output] {result[:150]}{'...' if len(result) > 150 else ''}")
            
            # Audit
            passed = self.audit(user_request, command, result)
            print(f"  [Auditor] {'PASS' if passed else 'FAIL'}")
            
            if passed:
                # Success
                report = self.report(user_request, True, result)
                return report
            else:
                # Failed - try to fix
                if attempt < max_attempts - 1:
                    print(f"  [Retry {attempt + 1}/{max_attempts}] Getting fix...")
                    fixed = self.get_fix(user_request, command, result)
                    if fixed and fixed != command:
                        command = fixed
                        print(f"  [Fix] {fixed[:60]}...")
                    else:
                        print(f"  [Fix] No valid fix, retrying...")
        
        # All attempts failed
        report = self.report(user_request, False, result)
        return report


# =============================================================================
# CLI RUNNER
# =============================================================================

def banner(refiner_model: str, worker_model: str, skill_count: int):
    print(f"\n{'='*70}")
    print(f"VTSBot R6 - Multi-Agent with Agent Skills")
    print(f"{'='*70}")
    print(f"Dispatcher: {refiner_model:<25} Worker: {worker_model}")
    print(f"Skills: {skill_count}")
    print(f"{'='*70}\n")


def run_integrated_agent(
    refiner_model: str = "qwen2.5:1.5b-instruct-q4_k_m",
    worker_model: str = "qwen2.5-coder:0.5b-instruct-q4_k_m",
    skills_dirs: List[str] = None,
    test_queue: List[str] = None,
):
    """
    Run the integrated multi-agent with skills.
    """
    agent = SkillAwareMultiAgent(
        refiner_model=refiner_model,
        worker_model=worker_model,
        skills_dirs=skills_dirs,
    )
    
    banner(refiner_model, worker_model, len(agent.registry))
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
        
        # Handle slash commands
        if user.startswith('/'):
            if user == "/skills":
                print("\n" + agent.registry.get_skills_context())
                continue
            elif user == "/status":
                print(f"\nSteps: {agent.state.step}")
                print(f"Skills available: {agent.registry.list_skills()}")
                continue
            elif user == "/help":
                print("\nCommands: /skills /status /help /exit")
                continue
            else:
                # Try original CLI handler
                if handle_command(user, {
                    "messages": agent.messages,
                    "state": agent.state,
                    "trace": agent.trace,
                    "model": worker_model
                }):
                    continue
        
        # Run the agent
        response = agent.run(user)
        print(f"\n{response}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="VTSBot R6 - Multi-Agent with Skills")
    parser.add_argument("--refiner", default="qwen2.5:1.5b-instruct-q4_k_m")
    parser.add_argument("--worker", default="qwen2.5-coder:0.5b-instruct-q4_k_m")
    parser.add_argument("--skills", nargs="*", default=[], help="Skill directories")
    parser.add_argument("--test", action="store_true", help="Run test prompts")
    
    args = parser.parse_args()
    
    test_queue = None
    if args.test:
        test_queue = [p.strip() for p in TEST_PROMPTS.strip().split('\n') if p.strip()]
    
    run_integrated_agent(
        refiner_model=args.refiner,
        worker_model=args.worker,
        skills_dirs=args.skills,
        test_queue=test_queue,
    )
