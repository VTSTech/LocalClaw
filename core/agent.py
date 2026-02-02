import ollama
import json
import os
from datetime import datetime
from colorama import Fore, Style
from .tools import ToolManager
from .memory import Memory
from config import DEFAULT_MODEL

class LocalClawAgent:
    def __init__(self, model=DEFAULT_MODEL):
        self.model = model
        self.memory = Memory()
        self.tools = ToolManager(self.memory)
        self.history = []

    def _log(self, title, content):
        """Helper to print debug info in a distinct color"""
        print(f"\n{Fore.YELLOW}[DEBUG] {title}:{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}{content}{Style.RESET_ALL}\n")

    def _build_system_prompt(self):
        soul_content = self.memory.read_soul()
        current_env = self.tools.get_system_identity()
        
        prompt = f"""
{soul_content}

[CURRENT ENVIRONMENT]
OS: {current_env}
Current Time: {datetime.now().strftime("%Y-%m-%d %H:%M")}

[INSTRUCTIONS]
You are the agent described in the SOUL.md above. 
Use the 'run_shell' tool for system tasks.
Capture significant events by updating your memory files.
- write_file(filename|content): Use this to update IDENTITY.md, USER.md, or SOUL.md.
"""
        return prompt

    def chat(self, user_input, verbose=True):
        # 1. Prepare Messages with enhanced Bootstrap Verbosity
        if user_input == "INIT_BOOTSTRAP":
            # Giving the model a structured "Checklist" to follow verbosely
            instruction = """[INITIALIZATION SEQUENCE ACTIVATED]
You have just woken up in a new workspace. 
Follow the instructions in BOOTSTRAP.md to establish your identity.

Please be verbose in your thinking:
1. Acknowledge your surroundings.
2. Propose a Name, Nature, Vibe, and Emoji for yourself.
3. Ask the user for their name and preferences.
4. Once agreed, use the 'write_file' tool to create IDENTITY.md and USER.md.

Response Format: Talk to the user first, then include your JSON tool call if you are ready to write."""
            
            system_prompt = self._build_system_prompt()
            messages = [{"role": "system", "content": system_prompt}, 
                        {"role": "user", "content": instruction}]
        else:
            # Standard chat logic...
            self.history.append({"role": "user", "content": user_input})
            self.memory.add_log("user", user_input)
            system_prompt = self._build_system_prompt()
            messages = [{"role": "system", "content": system_prompt}] + self.history

        if verbose:
            self._log("Context Window (Last message)", messages[-1])
            self._log("System Prompt (Snippet)", system_prompt[:200] + "...")

        # 2. Call Ollama
        if verbose: print(f"{Fore.YELLOW}[DEBUG] Thinking...{Style.RESET_ALL}")
        response = ollama.chat(model=self.model, messages=messages)
        content = response['message']['content']

        if verbose:
            self._log("Raw Model Output", content)

        # 3. Check for Tool Usage
        clean_content = content.strip().replace("```json", "").replace("```", "")

        if clean_content.startswith("{") and "tool" in clean_content:
            try:
                command_data = json.loads(clean_content)
                tool_name = command_data.get("tool")
                args = command_data.get("args")
                
                if verbose:
                    self._log("Tool Detected", f"Function: {tool_name}\nArgs: {args}")

                # Execute Tool
                tool_result = self.tools.execute(tool_name, args)
                
                if verbose:
                    self._log("Tool Result", tool_result)
                
                # Logic: If Identity is written, delete Bootstrap
                if tool_name == "write_file" and "IDENTITY.md" in args:
                    bootstrap_path = os.path.join(self.memory.base_path, "BOOTSTRAP.md")
                    if os.path.exists(bootstrap_path):
                        try:
                            os.remove(bootstrap_path)
                            if verbose: 
                                self._log("Lifecycle Update", "BOOTSTRAP.md deleted. Ritual complete.")
                        except Exception as e:
                            if verbose:
                                self._log("Error", f"Could not delete bootstrap: {e}")

                # Feed tool result back to LLM
                tool_msg = f"Tool output: {tool_result}"
                self.history.append({"role": "assistant", "content": clean_content})
                self.history.append({"role": "system", "content": tool_msg})
                
                # Get final answer
                final_response = ollama.chat(model=self.model, messages=messages + self.history)
                return final_response['message']['content']
                
            except json.JSONDecodeError as e:
                if verbose: self._log("JSON Parse Error", str(e))
                pass 

        self.history.append({"role": "assistant", "content": content})
        self.memory.add_log("assistant", content)
        return content