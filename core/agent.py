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

    def _read_md_safe(self, filename, default="Not yet established."):
        """Helper to read workspace files without crashing if they are missing"""
        path = os.path.join(self.memory.base_path, filename)
        if os.path.exists(path):
            with open(path, 'r') as f:
                content = f.read().strip()
                # If it's just the template, treat as empty
                if len(content) < 50 or "*(pick something" in content:
                    return default
                return content
        return default

    def _build_system_prompt(self):
        soul_content = self.memory.read_soul()
        identity = self._read_md_safe("IDENTITY.md", "Identity: Initializing...")
        user_info = self._read_md_safe("USER.md", "User: Unknown (Waiting for bootstrap)")
        current_env = self.tools.get_system_identity()
        
        prompt = f"""
{soul_content}

[MY IDENTITY]
{identity}

[USER PROFILE]
{user_info}

[ENVIRONMENT]
OS: {current_env} | Time: {datetime.now().strftime("%Y-%m-%d %H:%M")}

[INSTRUCTIONS]
You are the agent described above. 
- Use 'write_file(filename|content)' to save your identity and user info.
- If IDENTITY.md or USER.md are 'Not yet established', your priority is to complete the bootstrap ritual.
- To write a file, you MUST use: {{"tool": "write_file", "args": "filename|content"}}
"""
        return prompt

    def chat(self, user_input, verbose=True):
        # 1. Prepare Messages
        if user_input == "INIT_BOOTSTRAP":
            # Directing the agent to follow the birth ritual in BOOTSTRAP.md
            instruction = """[INITIALIZATION SEQUENCE]
Acknowledge your surroundings. Propose your Name and Vibe. 
Ask for the user's name. Once confirmed, use 'write_file' to create IDENTITY.md and USER.md."""
            
            system_prompt = self._build_system_prompt()
            messages = [{"role": "system", "content": system_prompt}, 
                        {"role": "user", "content": instruction}]
        else:
            self.history.append({"role": "user", "content": user_input})
            self.memory.add_log("user", user_input)
            system_prompt = self._build_system_prompt()
            messages = [{"role": "system", "content": system_prompt}] + self.history

        if verbose:
            self._log("Context Window (Last message)", messages[-1])

        # 2. Call Ollama
        if verbose: print(f"{Fore.YELLOW}[DEBUG] Thinking...{Style.RESET_ALL}")
        response = ollama.chat(model=self.model, messages=messages)
        content = response['message']['content']

        if verbose:
            self._log("Raw Model Output", content)

        # --- ADD TO agent.py Chat Method ---
        # 3. Check for Tool Usage
        clean_content = content.strip().replace("```json", "").replace("```", "")

        # If it's verbalizing the setup but forgot the tool format
        if "IDENTITY.md" in content and "{" not in content:
            return "I see you are describing your identity. Please use the JSON tool format to save it: {\"tool\": \"write_file\", \"args\": \"IDENTITY.md|content...\"}"

        if clean_content.startswith("{") and "tool" in clean_content:
            try:
                command_data = json.loads(clean_content)
                tool_name = command_data.get("tool")
                args = command_data.get("args")
                
                # Execute Tool
                tool_result = self.tools.execute(tool_name, args)
                
                # Logic: If Identity is written, delete Bootstrap as per AGENTS.md
                if tool_name == "write_file" and "IDENTITY.md" in args:
                    bootstrap_path = os.path.join(self.memory.base_path, "BOOTSTRAP.md")
                    if os.path.exists(bootstrap_path):
                        os.remove(bootstrap_path)
                        if verbose: self._log("Lifecycle", "BOOTSTRAP.md deleted. Ritual complete.")

                # Feed tool result back to LLM to close the loop
                self.history.append({"role": "assistant", "content": content})
                self.history.append({"role": "system", "content": f"Tool output: {tool_result}"})
                
                final_response = ollama.chat(model=self.model, messages=messages + self.history)
                return final_response['message']['content']
                
            except json.JSONDecodeError:
                pass 

        self.history.append({"role": "assistant", "content": content})
        self.memory.add_log("assistant", content)
        return content