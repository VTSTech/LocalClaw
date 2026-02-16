# -*- coding: utf-8 -*-
"""
VTSBot R7 - Function Calling Agent

Uses text-based JSON tool calling (proven 82% success with 0.5B models)
"""

import json
import re
import os
import platform
import getpass
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from tools import run_shell
from state import AgentState
from ollama import chat_api
from prompts import (
    TOOL_SYSTEM_PROMPT, 
    TOOL_FEW_SHOT, 
    RESULT_SUMMARY_PROMPT,
    TEST_PROMPTS
)
from agent_skills.core.skill import SkillRegistry, Skill


class FunctionCallingAgent:
    """
    Agent using text-based JSON tool calling.
    
    Flow:
    1. User input ? LLM generates JSON tool call
    2. Parse JSON and execute tool
    3. Send result back ? LLM generates natural language response
    """
    
    def __init__(
        self,
        model: str = "qwen2.5:3b",
        skills_dirs: List[str] = None,
    ):
        self.model = model
        self.registry = SkillRegistry()
        
        # Load built-in skills
        builtin_dir = Path(__file__).parent / "agent_skills" / "builtin"
        if builtin_dir.exists():
            loaded = self.registry.load_directory(builtin_dir)
            print(f"  [Skills] Loaded {len(loaded)} skills: {', '.join(loaded)}")
        
        # Load additional skill directories
        if skills_dirs:
            for dir_path in skills_dirs:
                loaded = self.registry.load_directory(Path(dir_path))
                print(f"  [Skills] Loaded {len(loaded)} skills from {dir_path}")
        
        self.state = AgentState(goal="Session Start")
        self.messages: List[Dict] = []
        self.trace: List[Dict] = []
    
    def _parse_tool_call(self, text: str) -> Optional[Dict]:
        """Parse a tool call from JSON text."""
        # Try to find JSON in the response
        json_match = re.search(r'\{[^{}]*"name"[^{}]*"arguments"[^{}]*\}', text, re.DOTALL)
        
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                if "name" in parsed and "arguments" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass
        
        # Try parsing entire text as JSON
        try:
            parsed = json.loads(text)
            if "name" in parsed and "arguments" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _execute_tool(self, name: str, args: Dict) -> Dict:
        """Execute a tool and return result."""
        
        print(f"  [Tool] {name}({args})")
        
        self.trace.append({
            "tool": name,
            "args": args,
            "timestamp": datetime.now().isoformat()
        })
        
        self.state.step += 1
        
        # Built-in tools
        if name == "run_shell_command":
            command = args.get("command", "")
            result = run_shell(command)
            self.state.last_result = result
            return {"output": result, "command": command}
        
        elif name == "get_system_info":
            info_type = args.get("info_type", "all")
            
            try:
                username = getpass.getuser()
                uname = os.uname()
            except Exception:
                username = os.environ.get("USER", "unknown")
                uname = type('obj', (object,), {'machine': 'unknown'})
            
            info = {
                "user": username,
                "hostname": platform.node(),
                "os": platform.system(),
                "arch": uname.machine,
                "cwd": os.getcwd(),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "time": datetime.now().strftime("%H:%M:%S"),
            }
            
            if info_type == "all":
                return {"info": info}
            return {"info": info.get(info_type, f"Unknown: {info_type}")}
        
        elif name == "read_file":
            path = args.get("path", "")
            try:
                if not os.path.exists(path):
                    return {"error": f"File not found: {path}"}
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return {"content": content[:5000], "path": path}
            except Exception as e:
                return {"error": str(e)}
        
        elif name == "write_file":
            path = args.get("path", "")
            content = args.get("content", "")
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.state.files_written.append(path)
                return {"status": "written", "path": path, "bytes": len(content)}
            except Exception as e:
                return {"error": str(e)}
        
        elif name == "list_directory":
            path = args.get("path", ".")
            try:
                files = os.listdir(path)
                return {"files": files, "path": path, "count": len(files)}
            except Exception as e:
                return {"error": str(e)}
        
        # Skills
        skill = self.registry.get(name)
        if skill:
            return self._execute_skill(skill, args)
        
        return {"error": f"Unknown tool: {name}"}
    
    def _execute_skill(self, skill: Skill, args: Dict) -> Dict:
        """Execute a skill."""
        query = args.get("query", "")
        print(f"  [Skill] {skill.name}")
        
        instructions = skill.get_full_context()
        
        response = chat_api(
            self.model,
            [
                {"role": "system", "content": f"# Skill: {skill.name}\n\n{instructions}"},
                {"role": "user", "content": query}
            ],
            []
        )
        
        return {"skill": skill.name, "response": response.get("message", {}).get("content", "")}
    
    def run(self, user_input: str) -> str:
        """Main execution with two-step tool calling."""
        
        # Build messages with few-shot examples
        messages = [{"role": "system", "content": TOOL_SYSTEM_PROMPT}]
        messages.extend(TOOL_FEW_SHOT)
        messages.append({"role": "user", "content": user_input})
        
        # Step 1: Get tool call from model
        response = chat_api(self.model, messages, [])
        content = response.get("message", {}).get("content", "")
        
        # Try to parse as tool call
        tool_call = self._parse_tool_call(content)
        
        if tool_call:
            # Execute tool
            name = tool_call["name"]
            args = tool_call["arguments"]
            result = self._execute_tool(name, args)
            
            # Step 2: Get natural language response
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": f"[Tool returns: {json.dumps(result)}]"})
            
            final_response = chat_api(self.model, messages, [])
            return final_response.get("message", {}).get("content", str(result))
        
        # No tool call - return direct response
        return content
    
    def get_status(self) -> Dict:
        return {
            "model": self.model,
            "skills": self.registry.list_skills(),
            "steps": self.state.step,
            "files_written": self.state.files_written,
            "trace_count": len(self.trace),
        }


# =============================================================================
# CLI RUNNER
# =============================================================================

def banner(model: str, skill_count: int):
    print(f"\n{'='*60}")
    print(f"VTSBot R7 - Function Calling Agent")
    print(f"{'='*60}")
    print(f"Model: {model}")
    print(f"Skills: {skill_count}")
    print(f"{'='*60}\n")


def run_agent(
    model: str = "qwen2.5:3b",
    skills_dirs: List[str] = None,
    test_queue: List[str] = None,
):
    agent = FunctionCallingAgent(model=model, skills_dirs=skills_dirs)
    banner(model, len(agent.registry))
    
    if test_queue:
        print(f"  [TEST MODE] {len(test_queue)} tests queued\n")
    
    while True:
        if test_queue is not None:
            if not test_queue:
                print(f"\n  [TEST COMPLETE]")
                break
            user = test_queue.pop(0)
            print(f"\n[TEST] >>> {user}")
        else:
            try:
                user = input("\nVTS> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[SYSTEM] Session ended.")
                break
            
            if not user:
                continue
        
        if user.lower() in ["/exit", "/quit", "exit", "quit"]:
            print("[SYSTEM] Goodbye!")
            break
        
        if user.startswith('/'):
            if user == "/skills":
                print("\n" + agent.registry.get_skills_context())
                continue
            elif user == "/status":
                print("\n" + json.dumps(agent.get_status(), indent=2))
                continue
            elif user == "/help":
                print("\nCommands: /skills /status /trace /help /exit")
                continue
            elif user == "/trace":
                print("\n--- Tool Calls ---")
                for t in agent.trace[-10:]:
                    print(f"  {t}")
                continue
        
        response = agent.run(user)
        print(f"\n{response}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="VTSBot R7")
    parser.add_argument("--model", default="qwen2.5:3b", help="LLM model")
    parser.add_argument("--skills", nargs="*", default=[], help="Skill directories")
    parser.add_argument("--test", action="store_true", help="Run test prompts")
    
    args = parser.parse_args()
    
    test_queue = None
    if args.test:
        test_queue = [p.strip() for p in TEST_PROMPTS.strip().split('\n') if p.strip()]
    
    run_agent(
        model=args.model,
        skills_dirs=args.skills if args.skills else None,
        test_queue=test_queue,
    )