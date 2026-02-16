# -*- coding: utf-8 -*-
"""
VTSBot R7 - Function Calling + Agent Skills

Architecture:
- Uses native function calling (no text parsing)
- Skills defined as SKILL.md files (agentskills.io spec)
- JSON mode for structured output
- Progressive disclosure for skill instructions

Agent Flow:
User Input ? LLM with Tools ? Function Call ? Execute ? Result
"""

import json
import re
import os
import platform
import getpass
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# Import components
from tools import run_shell
from state import AgentState
from ollama import chat_api, ToolCall
from prompts import WORKER_PROMPT, TEST_PROMPTS

# Import Agent Skills
from agent_skills.core.skill import SkillRegistry, Skill


# =============================================================================
# BUILT-IN TOOL DEFINITIONS
# =============================================================================

def get_builtin_tools() -> List[Dict]:
    """Get built-in tool definitions for function calling"""
    return [
        {
            "type": "function",
            "function": {
                "name": "chat",
                "description": "Answer questions, explain concepts, have conversations. Use for explanations, questions, and general discussion.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "response": {
                            "type": "string",
                            "description": "The response to provide to the user"
                        }
                    },
                    "required": ["response"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_local_info",
                "description": "Get system information like user, hostname, current directory, architecture. Use for simple system info queries.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "info_type": {
                            "type": "string",
                            "enum": ["user", "host", "cwd", "arch", "os", "all"],
                            "description": "Type of system info to retrieve"
                        }
                    },
                    "required": ["info_type"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "execute_command",
                "description": "Execute a shell command. Use for file operations, system tasks, running scripts. Commands are validated for safety.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The shell command to execute"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout in seconds (default: 30)"
                        }
                    },
                    "required": ["command"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read contents of a file. Use to examine file contents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to read"
                        },
                        "lines": {
                            "type": "string",
                            "description": "Line range to read (e.g., '1-20' or 'all')"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a file. Creates the file if it doesn't exist.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to write"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["write", "append"],
                            "description": "Write mode: 'write' (overwrite) or 'append'"
                        }
                    },
                    "required": ["path", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories. Use to explore directory contents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to list (default: current directory)"
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Glob pattern to filter files (e.g., '*.py')"
                        }
                    },
                    "required": []
                }
            }
        },
    ]


# =============================================================================
# SYSTEM CONTEXT
# =============================================================================

def get_system_context() -> str:
    """Get system information for context"""
    try:
        username = getpass.getuser()
        uname = os.uname()
    except Exception:
        username = os.environ.get("USER", "unknown")
        uname = type('obj', (object,), {'machine': 'unknown', 'release': 'unknown'})
    
    return (
        f"SYSTEM INFO:\n"
        f"- User: {username}\n"
        f"- Host: {platform.node()}\n"
        f"- OS: {platform.system()}\n"
        f"- Arch: {uname.machine}\n"
        f"- CWD: {os.getcwd()}\n"
        f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """You are VTSBot, an intelligent assistant with access to tools and skills.

# Your Capabilities

You have access to tools that let you:
- Chat and answer questions
- Get system information
- Execute shell commands (safely)
- Read and write files
- List directories
- Activate specialized skills

# Available Skills

{skills_context}

# How to Respond

1. Analyze the user's request
2. Choose the appropriate tool:
   - For questions/explanations ? use "chat"
   - For system info ? use "get_local_info"
   - For commands/operations ? use "execute_command"
   - For file reading ? use "read_file"
   - For file writing ? use "write_file"
   - For directory listing ? use "list_files"
   - For specialized tasks ? use the skill function
3. Call the tool with proper parameters
4. Report results clearly

# Safety Rules

- Never execute dangerous commands (rm -rf /, etc.)
- Validate file paths before operations
- Ask for clarification if the request is ambiguous
- Report errors clearly and suggest alternatives

# Current Environment

{env_context}
"""

SKILL_INSTRUCTION_PROMPT = """# Active Skill: {skill_name}

{skill_instructions}

---

Now help the user with their request using the skill guidelines above.
"""


# =============================================================================
# AGENT CLASS
# =============================================================================

class FunctionCallingAgent:
    """
    Agent using native function calling.
    
    Features:
    - No text parsing for routing
    - Structured tool parameters
    - SKILL.md skills integration
    - JSON mode for skill responses
    """
    
    def __init__(
        self,
        model: str = "qwen2.5:3b",
        skills_dirs: List[str] = None,
    ):
        self.model = model
        
        # Initialize skill registry
        self.registry = SkillRegistry()
        
        # Load built-in skills
        builtin_dir = Path(__file__).parent / "agent_skills" / "builtin"
        if builtin_dir.exists():
            loaded = self.registry.load_directory(builtin_dir)
            print(f"  [Skills] Loaded {len(loaded)} built-in skills: {', '.join(loaded)}")
        
        # Load additional skill directories
        if skills_dirs:
            for dir_path in skills_dirs:
                loaded = self.registry.load_directory(Path(dir_path))
                print(f"  [Skills] Loaded {len(loaded)} skills from {dir_path}")
        
        # System context
        self.system_context = get_system_context()
        
        # State
        self.state = AgentState(goal="Session Start")
        self.messages: List[Dict] = []
        self.trace: List[Dict] = []
    
    def _get_all_tools(self) -> List[Dict]:
        """Get all available tools (built-in + skills)"""
        tools = get_builtin_tools()
        # Add skills as tools
        tools.extend(self.registry.get_function_schemas(include_dangerous=True))
        return tools
    
    def _get_system_prompt(self) -> str:
        """Build system prompt with skills context"""
        skills_context = self.registry.get_skills_context()
        return SYSTEM_PROMPT.format(
            skills_context=skills_context,
            env_context=self.system_context
        )
    
    def _handle_tool_call(self, tool_call: ToolCall) -> Any:
        """Execute a tool call and return result"""
        name = tool_call.name
        args = tool_call.arguments
        
        print(f"  [Tool] {name}({args})")
        
        # Track in trace
        self.trace.append({
            "tool": name,
            "args": args,
            "timestamp": datetime.now().isoformat()
        })
        
        # Handle built-in tools
        if name == "chat":
            return {"status": "success", "response": args.get("response", "")}
        
        elif name == "get_local_info":
            info_type = args.get("info_type", "all")
            context = self.system_context
            
            if info_type == "all":
                return {"status": "success", "info": context}
            else:
                # Extract specific info
                lines = context.split('\n')
                for line in lines:
                    if info_type.lower() in line.lower():
                        return {"status": "success", "info": line}
                return {"status": "success", "info": f"No {info_type} info found"}
        
        elif name == "execute_command":
            command = args.get("command", "")
            timeout = args.get("timeout", 30)
            
            self.state.active_agent = "DevOps"
            result = run_shell(command)
            
            self.state.last_result = result
            self.state.step += 1
            
            return {
                "status": "success" if "Error" not in result and "Safety Violation" not in result else "error",
                "output": result[:2000],  # Limit output size
                "command": command
            }
        
        elif name == "read_file":
            path = args.get("path", "")
            lines = args.get("lines", "all")
            
            try:
                if not os.path.exists(path):
                    return {"status": "error", "error": f"File not found: {path}"}
                
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                return {
                    "status": "success",
                    "content": content[:5000],  # Limit size
                    "path": path
                }
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        elif name == "write_file":
            path = args.get("path", "")
            content = args.get("content", "")
            mode = args.get("mode", "write")
            
            try:
                write_mode = 'a' if mode == "append" else 'w'
                with open(path, write_mode, encoding='utf-8') as f:
                    f.write(content)
                
                self.state.files_written.append(path)
                return {"status": "success", "path": path, "bytes": len(content)}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        elif name == "list_files":
            path = args.get("path", ".")
            pattern = args.get("pattern", "*")
            
            try:
                from glob import glob
                search_path = os.path.join(path, pattern)
                files = glob(search_path)
                
                return {
                    "status": "success",
                    "files": files[:100],  # Limit count
                    "count": len(files)
                }
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        # Handle skill activation
        else:
            skill = self.registry.get(name)
            if skill:
                return self._handle_skill(skill, args)
            else:
                return {"status": "error", "error": f"Unknown tool: {name}"}
    
    def _handle_skill(self, skill: Skill, args: Dict) -> Dict:
        """Handle a skill activation"""
        query = args.get("query", "")
        
        print(f"  [Skill] Activating: {skill.name}")
        
        # Load skill instructions
        instructions = skill.get_full_context()
        
        # Use skill instructions to process the query
        system = SKILL_INSTRUCTION_PROMPT.format(
            skill_name=skill.name,
            skill_instructions=instructions
        )
        
        # Call LLM with skill context
        response = chat_api(
            self.model,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": query}
            ],
            []  # No tools for skill response
        )
        
        content = response.get("message", {}).get("content", "")
        
        return {
            "status": "success",
            "skill": skill.name,
            "response": content
        }
    
    def run(self, user_input: str) -> str:
        """
        Main execution method.
        
        Args:
            user_input: User's request
            
        Returns:
            Response string
        """
        # Build messages
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": user_input}
        ]
        
        # Add conversation history
        messages = self.messages + messages[1:]
        
        # Get all tools
        tools = self._get_all_tools()
        
        # Call LLM with tools
        response = chat_api(
            self.model,
            messages,
            tools=tools,
        )
        
        message = response.get("message", {})
        
        # Check for tool calls
        tool_calls = message.get("tool_calls", [])
        
        if tool_calls:
            # Process tool calls
            results = []
            for tc in tool_calls:
                tool_call = ToolCall.from_ollama(tc)
                result = self._handle_tool_call(tool_call)
                results.append(result)
                
                # Handle chat tool specially
                if tool_call.name == "chat":
                    return result.get("response", "")
                
                # Handle skill responses
                if "skill" in result:
                    return result.get("response", "")
            
            # If we have results, summarize them
            if results:
                # Check if any command was executed
                cmd_results = [r for r in results if "command" in r]
                if cmd_results:
                    # Use worker to summarize
                    summary = chat_api(
                        self.model,
                        [
                            {"role": "system", "content": WORKER_PROMPT},
                            {"role": "user", "content": f"Summarize these results: {results}"}
                        ],
                        []
                    )
                    return summary.get("message", {}).get("content", str(results))
                
                return str(results[0]) if len(results) == 1 else str(results)
        
        # No tool calls - return text response
        content = message.get("content", "")
        
        # Save to history
        self.messages.append({"role": "user", "content": user_input})
        self.messages.append({"role": "assistant", "content": content})
        
        return content
    
    def get_status(self) -> Dict:
        """Get agent status"""
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
    print(f"\n{'='*70}")
    print(f"VTSBot R7 - Function Calling + Agent Skills")
    print(f"{'='*70}")
    print(f"Model: {model}")
    print(f"Skills: {skill_count}")
    print(f"{'='*70}\n")


def run_agent(
    model: str = "qwen2.5:3b",
    skills_dirs: List[str] = None,
    test_queue: List[str] = None,
):
    """
    Run the function-calling agent.
    """
    agent = FunctionCallingAgent(
        model=model,
        skills_dirs=skills_dirs,
    )
    
    banner(model, len(agent.registry))
    print(f"  [SYSTEM] Environment synchronized.\n")
    
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
            print("[SYSTEM] Goodbye!")
            break
        
        # Handle slash commands
        if user.startswith('/'):
            if user == "/skills":
                print("\n" + agent.registry.get_skills_context())
                continue
            elif user == "/status":
                import json as json_mod
                print("\n" + json_mod.dumps(agent.get_status(), indent=2))
                continue
            elif user == "/help":
                print("\nCommands: /skills /status /help /exit")
                continue
            elif user == "/trace":
                print("\n--- Tool Call Trace ---")
                for t in agent.trace[-10:]:
                    print(f"  {t}")
                continue
        
        # Run agent
        response = agent.run(user)
        print(f"\n{response}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="VTSBot R7 - Function Calling Agent")
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