# -*- coding: utf-8 -*-
"""
VTSBot R7 - Function Calling Agent with chain_tools support
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
    """Agent using text-based JSON tool calling with chain_tools support."""
    
    def __init__(
        self,
        model: str = "qwen2.5:3b",
        skills_dirs: List[str] = None,
        verbose: bool = True,
    ):
        self.model = model
        self.verbose = verbose
        self.registry = SkillRegistry()
        
        builtin_dir = Path(__file__).parent / "agent_skills" / "builtin"
        if builtin_dir.exists():
            loaded = self.registry.load_directory(builtin_dir)
            self._log(f"  [Skills] Loaded {len(loaded)} skills: {', '.join(loaded)}")
        
        if skills_dirs:
            for dir_path in skills_dirs:
                loaded = self.registry.load_directory(Path(dir_path))
                self._log(f"  [Skills] Loaded {len(loaded)} skills from {dir_path}")
        
        self.state = AgentState(goal="Session Start")
        self.messages: List[Dict] = []
        self.trace: List[Dict] = []
        self._last_result = None
    
    def _log(self, msg: str):
        if self.verbose:
            print(msg)
    
    def _parse_tool_call(self, text: str) -> Optional[Dict]:
        """Parse a tool call from JSON text."""
        json_match = re.search(r'\{[^{}]*"name"[^{}]*"arguments"[^{}]*\}', text, re.DOTALL)
        
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                if "name" in parsed and "arguments" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass
        
        try:
            parsed = json.loads(text)
            if "name" in parsed and "arguments" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _execute_single_tool(self, name: str, args: Dict) -> Dict:
        """Execute a single tool and return result."""
        
        # Handle $previous reference
        if self._last_result is not None:
            for key, value in args.items():
                if isinstance(value, str) and "$previous" in value:
                    # Replace $previous with actual result
                    if value == "$previous":
                        args[key] = json.dumps(self._last_result, indent=2)
                    else:
                        args[key] = value.replace("$previous", json.dumps(self._last_result))
        
        self.trace.append({
            "tool": name,
            "args": args,
            "timestamp": datetime.now().isoformat()
        })
        
        self.state.step += 1
        
        if name == "run_shell_command":
            command = args.get("command", "")
            self._log(f"    [Shell] {command}")
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
            self._log(f"    [Write] {path} ({len(content)} bytes)")
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
    
    def _execute_chain_tools(self, steps: List[Dict]) -> Dict:
        """Execute multiple tools in sequence."""
        
        self._log(f"  [Chain] Executing {len(steps)} steps...")
        
        results = []
        self._last_result = None
        
        for i, step in enumerate(steps):
            tool_name = step.get("tool")
            tool_args = step.get("args", {})
            
            self._log(f"    [Step {i+1}/{len(steps)}] {tool_name}")
            
            result = self._execute_single_tool(tool_name, tool_args)
            results.append(result)
            self._last_result = result
            
            self._log(f"    [Result] {json.dumps(result)[:100]}...")
            
            # Stop on error
            if "error" in result:
                return {"results": results, "error": f"Step {i+1} failed: {result['error']}"}
        
        return {"results": results, "success": True}
    
    def _execute_tool(self, name: str, args: Dict) -> Dict:
        """Execute a tool (handles chain_tools specially)."""
        
        self._log(f"  [Tool] {name}({json.dumps(args)[:100]}...)")
        
        if name == "chain_tools":
            steps = args.get("steps", [])
            return self._execute_chain_tools(steps)
        
        return self._execute_single_tool(name, args)
    
    def _execute_skill(self, skill: Skill, args: Dict) -> Dict:
        """Execute a skill."""
        query = args.get("query", "")
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
        """Main execution with tool calling."""
        
        self._log(f"  [Input] {user_input}")
        
        # Build messages
        messages = [{"role": "system", "content": TOOL_SYSTEM_PROMPT}]
        messages.extend(TOOL_FEW_SHOT)
        messages.append({"role": "user", "content": user_input})
        
        # Get response
        self._log("  [LLM] Generating response...")
        response = chat_api(self.model, messages, [])
        content = response.get("message", {}).get("content", "")
        
        self._log(f"  [LLM Output] {content[:200]}{'...' if len(content) > 200 else ''}")
        
        # Parse tool call
        tool_call = self._parse_tool_call(content)
        
        if tool_call:
            name = tool_call["name"]
            args = tool_call["arguments"]
            result = self._execute_tool(name, args)
            
            self._log(f"  [Tool Result] {json.dumps(result)[:200]}")
            
            # Generate natural response
            summary_prompt = RESULT_SUMMARY_PROMPT.format(
                question=user_input,
                result=json.dumps(result)
            )
            
            self._log("  [LLM] Generating natural response...")
            final_response = chat_api(
                self.model,
                [{"role": "user", "content": summary_prompt}],
                []
            )
            final_content = final_response.get("message", {}).get("content", str(result))
            
            self._log(f"  [Response] {final_content}")
            return final_content
        
        # No tool call
        self._log("  [Direct Response] (no tool used)")
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
    verbose: bool = True,
):
    agent = FunctionCallingAgent(
        model=model, 
        skills_dirs=skills_dirs,
        verbose=verbose
    )
    banner(model, len(agent.registry))
    
    if test_queue:
        print(f"  [TEST MODE] {len(test_queue)} tests queued\n")
    
    while True:
        if test_queue is not None:
            if not test_queue:
                print(f"\n  [TEST COMPLETE]")
                break
            user = test_queue.pop(0)
            print(f"\n{'='*50}")
            print(f"[TEST] >>> {user}")
            print(f"{'='*50}")
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
                print("\n--- Tool Call Trace ---")
                for t in agent.trace[-10:]:
                    print(f"  {t}")
                continue
        
        response = agent.run(user)
        print(f"\n>>> {response}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="VTSBot R7")
    parser.add_argument("--model", default="qwen2.5:3b", help="LLM model")
    parser.add_argument("--skills", nargs="*", default=[], help="Skill directories")
    parser.add_argument("--test", action="store_true", help="Run test prompts")
    parser.add_argument("--quiet", action="store_true", help="Reduce output verbosity")
    
    args = parser.parse_args()
    
    test_queue = None
    if args.test:
        test_queue = [p.strip() for p in TEST_PROMPTS.strip().split('\n') if p.strip()]
    
    run_agent(
        model=args.model,
        skills_dirs=args.skills if args.skills else None,
        test_queue=test_queue,
        verbose=not args.quiet,
    )