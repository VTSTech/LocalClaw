# -*- coding: utf-8 -*-
"""
VTSBot R7 - Function Calling Agent with skills that can use tools
"""

import json
import re
import os
import sys
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
        
        self._log(f"  [Skills] Initializing skill registry...")
        
        builtin_dir = Path(__file__).parent / "agent_skills" / "builtin"
        if builtin_dir.exists():
            self._log(f"  [Skills] Loading builtin skills from: {builtin_dir}")
            loaded = self.registry.load_directory(builtin_dir)
            self._log(f"  [Skills] Loaded {len(loaded)} builtin skills: {', '.join(loaded)}")
            for skill_name in loaded:
                skill = self.registry.get(skill_name)
                if skill:
                    desc_preview = skill.description[:80] + "..." if len(skill.description) > 80 else skill.description
                    self._log(f"    - {skill_name}: {desc_preview}")
        
        if skills_dirs:
            for dir_path in skills_dirs:
                self._log(f"  [Skills] Loading custom skills from: {dir_path}")
                loaded = self.registry.load_directory(Path(dir_path))
                self._log(f"  [Skills] Loaded {len(loaded)} custom skills: {', '.join(loaded)}")
        
        self._log(f"  [Skills] Total skills available: {len(self.registry)}")
        
        self.state = AgentState(goal="Session Start")
        self.messages: List[Dict] = []
        self.trace: List[Dict] = []
        self._last_result = None
    
    def _log(self, msg: str):
        if self.verbose:
            print(msg)
    
    def _parse_tool_call(self, text: str) -> Optional[Dict]:
        """Parse a tool call from JSON text, handling various formats."""
        
        cleaned = text.strip()
        
        # Remove markdown code blocks
        if cleaned.startswith('```'):
            lines = cleaned.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            cleaned = '\n'.join(lines).strip()
        
        # Extract JSON with balanced braces
        start_idx = cleaned.find('{')
        if start_idx != -1:
            brace_count = 0
            end_idx = None
            for i, char in enumerate(cleaned[start_idx:]):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = start_idx + i + 1
                        break
            
            if end_idx:
                json_str = cleaned[start_idx:end_idx]
                try:
                    parsed = json.loads(json_str)
                    if isinstance(parsed, dict):
                        # Normalize "tool" -> "name"
                        if "tool" in parsed and "name" not in parsed:
                            parsed["name"] = parsed.pop("tool")
                        
                        # Normalize arguments
                        if "arguments" in parsed and isinstance(parsed["arguments"], list):
                            parsed["arguments"] = {"args": parsed["arguments"]}
                        
                        if "name" in parsed:
                            if "arguments" not in parsed:
                                parsed["arguments"] = {}
                            return parsed
                except json.JSONDecodeError:
                    pass
        
        return None
    
    def _execute_single_tool(self, name: str, args: Dict) -> Dict:
        """Execute a single tool and return result."""
        
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
            return {"info": info}
        
        elif name == "read_file":
            path = args.get("path", "")
            self._log(f"    [Read] {path}")
            try:
                if not os.path.exists(path):
                    return {"error": f"File not found: {path}"}
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return {"content": content[:8000], "path": path, "size": len(content)}
            except Exception as e:
                return {"error": str(e)}
        
        elif name == "write_file":
            path = args.get("path", "")
            content = args.get("content", "")
            self._log(f"    [Write] {path}")
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.state.files_written.append(path)
                return {"status": "written", "path": path}
            except Exception as e:
                return {"error": str(e)}
        
        elif name == "delete_file":
            path = args.get("path", "")
            self._log(f"    [Delete] {path}")
            try:
                if os.path.exists(path):
                    os.remove(path)
                return {"status": "deleted", "path": path}
            except Exception as e:
                return {"error": str(e)}
        
        elif name == "list_directory":
            path = args.get("path", ".")
            self._log(f"    [List] {path}")
            try:
                files = [{"name": f, "type": "dir" if os.path.isdir(os.path.join(path, f)) else "file"} 
                        for f in os.listdir(path)]
                return {"files": files, "path": path}
            except Exception as e:
                return {"error": str(e)}
        
        return {"error": f"Unknown tool: {name}"}
    
    def _execute_chain_tools(self, steps: List[Dict]) -> Dict:
        """Execute multiple tools in sequence."""
        results = []
        for i, step in enumerate(steps):
            tool_name = step.get("tool")
            tool_args = step.get("args", {})
            result = self._execute_single_tool(tool_name, tool_args)
            results.append(result)
            if "error" in result:
                return {"results": results, "error": f"Step {i+1} failed"}
        return {"results": results, "success": True}
    
    def _detect_initial_action(self, skill_name: str, query: str) -> Optional[Dict]:
        """Detect the first action needed based on query patterns."""
        query_lower = query.lower()
        
        # Code analysis patterns
        if skill_name == "code-analysis":
            # Extract filename from query
            file_match = re.search(r'[\w_-]+\.(py|js|ts|java|go|rs|c|cpp|h)', query_lower)
            if file_match:
                filename = file_match.group(0)
                # Check if file exists with various paths
                for path in [filename, f"./{filename}", f"/content/LocalClaw/test/{filename}"]:
                    if os.path.exists(path):
                        return {"name": "read_file", "arguments": {"path": path}}
                # Try to find in current directory
                if os.path.exists(filename):
                    return {"name": "read_file", "arguments": {"path": filename}}
        
        # Web search patterns
        elif skill_name == "web-search":
            if "python version" in query_lower or "latest python" in query_lower:
                return {"name": "run_shell_command", "arguments": {
                    "command": "curl -s https://www.python.org/downloads/ | grep -oP 'Python [0-9]+\\.[0-9]+' | head -1"
                }}
            elif "search" in query_lower:
                # Extract search term
                return {"name": "run_shell_command", "arguments": {
                    "command": f"curl -s 'https://api.duckduckgo.com/?q={query}&format=json' 2>/dev/null | head -c 2000"
                }}
        
        # File operations patterns
        elif skill_name == "file-operations":
            if "list" in query_lower:
                return {"name": "list_directory", "arguments": {"path": "."}}
            file_match = re.search(r'[\w_-]+\.\w+', query)
            if file_match and "read" in query_lower:
                return {"name": "read_file", "arguments": {"path": file_match.group(0)}}
        
        return None
    
    def _execute_skill(self, skill: Skill, args: Dict) -> Dict:
        """Execute a skill with deterministic first action when possible."""
        query = args.get("query", "")
        
        self._log(f"    [Skill] ========== SKILL: {skill.name} ==========")
        self._log(f"    [Skill] Query: {query}")
        
        # Load instructions
        instructions = skill.load_instructions() if hasattr(skill, 'load_instructions') else ""
        if not instructions:
            instructions = skill.get_full_context() if hasattr(skill, 'get_full_context') else ""
        
        # Try to detect first action automatically
        initial_action = self._detect_initial_action(skill.name, query)
        
        if initial_action:
            self._log(f"    [Skill] Auto-detected action: {initial_action}")
            tool_result = self._execute_single_tool(initial_action["name"], initial_action["arguments"])
            self._log(f"    [Skill] Auto-executed, result: {str(tool_result)[:100]}...")
            
            # Now ask LLM to analyze the result
            result_text = tool_result.get("content", tool_result.get("output", str(tool_result)))
            
            analysis_prompt = f"""# Task: {query}

# Data Retrieved:
{str(result_text)[:3000]}

# Instructions:
Based on the data above, provide a clear and helpful answer to the task.
Be concise but informative.

Answer:"""

            response = chat_api(self.model, [{"role": "user", "content": analysis_prompt}], [])
            content = response.get("message", {}).get("content", "")
            
            self._log(f"    [Skill] Analysis: {content[:200]}...")
            self._log(f"    [Skill] ========== SKILL COMPLETE ==========")
            
            return {"skill": skill.name, "response": content, "auto_action": initial_action}
        
        # No auto-detection - use LLM to decide
        self._log(f"    [Skill] No auto-detection, using LLM...")
        
        skill_prompt = f"""# Skill: {skill.name}

{instructions[:2000]}

# Task: {query}

# Available Tools (output as JSON):
- read_file: {{"name": "read_file", "arguments": {{"path": "filename"}}}}
- run_shell_command: {{"name": "run_shell_command", "arguments": {{"command": "cmd"}}}}
- write_file: {{"name": "write_file", "arguments": {{"path": "filename", "content": "text"}}}}

Output JSON only. No markdown."""

        response = chat_api(self.model, [{"role": "user", "content": skill_prompt}], [])
        content = response.get("message", {}).get("content", ""
        )
        tool_call = self._parse_tool_call(content)
        
        # Execute tools in loop
        max_loops = 3
        for loop_idx in range(max_loops):
            if not tool_call:
                self._log(f"    [Skill] ========== SKILL COMPLETE ==========")
                return {"skill": skill.name, "response": content}
            
            tool_name = tool_call["name"]
            tool_args = tool_call["arguments"]
            
            self._log(f"    [Skill] Tool: {tool_name}({tool_args})")
            tool_result = self._execute_single_tool(tool_name, tool_args)
            
            result_text = tool_result.get("content", tool_result.get("output", str(tool_result)))
            
            next_prompt = f"""# Result:
{str(result_text)[:2000]}

# Task: {query}

If done, answer in text. If need another tool, output JSON.
Valid tools: read_file, run_shell_command, write_file"""

            response = chat_api(self.model, [{"role": "user", "content": next_prompt}], [])
            content = response.get("message", {}).get("content", "")
            tool_call = self._parse_tool_call(content)
        
        self._log(f"    [Skill] ========== SKILL COMPLETE ==========")
        return {"skill": skill.name, "response": content}
    
    def _execute_tool(self, name: str, args: Dict) -> Dict:
        """Execute a tool or skill."""
        
        self._log(f"  [Tool] {name}({json.dumps(args)[:200]})")
        
        if name == "chain_tools":
            return self._execute_chain_tools(args.get("steps", []))
        
        skill = self.registry.get(name)
        if skill:
            return self._execute_skill(skill, args)
        
        return self._execute_single_tool(name, args)
    
    def run(self, user_input: str) -> str:
        """Main execution."""
        
        self._log(f"  [Input] {user_input}")
        
        messages = [{"role": "system", "content": TOOL_SYSTEM_PROMPT}]
        messages.extend(TOOL_FEW_SHOT)
        messages.append({"role": "user", "content": user_input})
        
        self._log("  [LLM] Generating response...")
        response = chat_api(self.model, messages, [])
        content = response.get("message", {}).get("content", "")
        
        self._log(f"  [LLM Output] {content[:500]}...")
        
        tool_call = self._parse_tool_call(content)
        
        if tool_call:
            result = self._execute_tool(tool_call["name"], tool_call["arguments"])
            
            self._log(f"  [Tool Result] {json.dumps(result)[:500]}...")
            
            # Generate summary
            summary_prompt = RESULT_SUMMARY_PROMPT.format(
                question=user_input,
                result=json.dumps(result)
            )
            
            final_response = chat_api(self.model, [{"role": "user", "content": summary_prompt}], [])
            return final_response.get("message", {}).get("content", str(result))
        
        return content
    
    def get_status(self) -> Dict:
        return {
            "model": self.model,
            "skills": self.registry.list_skills(),
            "steps": self.state.step,
            "files_written": self.state.files_written,
            "trace_count": len(self.trace),
        }
    
    def test_skills(self) -> Dict[str, Dict]:
        """
        Test all loaded skills with predefined test cases.
        Returns dict of skill_name -> test_result.
        """
        # Predefined test cases for each skill
        test_cases = {
            "code-analysis": {
                "query": "Analyze the file agent_fc.py",
                "expected_tools": ["read_file"],
                "expected_content": "class",  # Should find class definitions
            },
            "file-operations": {
                "query": "List files in current directory",
                "expected_tools": ["list_directory", "run_shell_command"],
                "expected_content": "files",
            },
            "shell-execution": {
                "query": "Run echo hello",
                "expected_tools": ["run_shell_command"],
                "expected_content": "hello",
            },
            "web-search": {
                "query": "Search for Python latest version",
                "expected_tools": ["run_shell_command"],
                "expected_content": None,  # May vary
            },
            "pdf-processing": {
                "query": "List PDF tools available",
                "expected_tools": ["run_shell_command"],
                "expected_content": None,
            },
        }
        
        results = {}
        
        self._log(f"\n{'='*60}")
        self._log(f"  [SKILL TEST] Testing {len(self.registry)} skills...")
        self._log(f"{'='*60}\n")
        
        for skill_name in self.registry.list_skills():
            skill = self.registry.get(skill_name)
            if not skill:
                results[skill_name] = {"status": "ERROR", "message": "Skill not found in registry"}
                continue
            
            test_case = test_cases.get(skill_name, {
                "query": f"Test skill {skill_name}",
                "expected_tools": None,
                "expected_content": None,
            })
            
            self._log(f"\n  [TEST] Skill: {skill_name}")
            self._log(f"  [TEST] Query: {test_case['query']}")
            
            try:
                # Execute the skill
                result = self._execute_skill(skill, {"query": test_case["query"]})
                
                # Check result
                status = "PASS"
                messages = []
                
                # Check if auto-action was used
                if result.get("auto_action"):
                    messages.append(f"Auto-action: {result['auto_action']}")
                
                # Check if expected tools were used
                if test_case.get("expected_tools"):
                    used_tools = [t["tool"] for t in self.trace]
                    for expected in test_case["expected_tools"]:
                        if expected not in used_tools:
                            status = "WARN"
                            messages.append(f"Expected tool '{expected}' not used")
                
                # Check if expected content is in response
                response = result.get("response", "")
                if test_case.get("expected_content"):
                    if test_case["expected_content"].lower() not in response.lower():
                        status = "WARN"
                        messages.append(f"Expected content '{test_case['expected_content']}' not found")
                
                # Check for errors
                if "error" in result:
                    status = "FAIL"
                    messages.append(f"Error: {result['error']}")
                
                if not messages:
                    messages.append("Skill executed successfully")
                
                results[skill_name] = {
                    "status": status,
                    "response_preview": response[:200] + "..." if len(response) > 200 else response,
                    "messages": messages,
                }
                
                self._log(f"  [TEST] Status: {status}")
                for msg in messages:
                    self._log(f"  [TEST]   - {msg}")
                
            except Exception as e:
                results[skill_name] = {
                    "status": "ERROR",
                    "message": str(e),
                }
                self._log(f"  [TEST] Status: ERROR - {e}")
        
        # Summary
        passed = sum(1 for r in results.values() if r["status"] == "PASS")
        warned = sum(1 for r in results.values() if r["status"] == "WARN")
        failed = sum(1 for r in results.values() if r["status"] in ["FAIL", "ERROR"])
        
        self._log(f"\n{'='*60}")
        self._log(f"  [SKILL TEST] Results: {passed} PASS, {warned} WARN, {failed} FAIL")
        self._log(f"{'='*60}\n")
        
        return results


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
    parser.add_argument("--test-skills", action="store_true", help="Test all skills directly")
    parser.add_argument("--quiet", action="store_true", help="Reduce output verbosity")
    
    args = parser.parse_args()
    
    # Create agent
    agent = FunctionCallingAgent(
        model=args.model,
        skills_dirs=args.skills if args.skills else None,
        verbose=not args.quiet
    )
    
    # Test skills mode
    if args.test_skills:
        results = agent.test_skills()
        print("\n" + json.dumps({k: {"status": v["status"], "messages": v.get("messages", [])} 
                                for k, v in results.items()}, indent=2))
        sys.exit(0)
    
    # Test prompts mode
    test_queue = None
    if args.test:
        test_queue = [p.strip() for p in TEST_PROMPTS.strip().split('\n') if p.strip()]
    
    run_agent(
        model=args.model,
        skills_dirs=args.skills if args.skills else None,
        test_queue=test_queue,
        verbose=not args.quiet,
    )