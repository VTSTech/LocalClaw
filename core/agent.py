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
        
        # --- NEW DYNAMIC LOADING ---
        # Attempt to read existing identity/user files
        try:
            with open("IDENTITY.md", "r") as f:
                identity_context = f.read()
        except FileNotFoundError:
            identity_context = "Identity not yet established. Follow BOOTSTRAP.md."

        try:
            with open("USER.md", "r") as f:
                user_context = f.read()
        except FileNotFoundError:
            user_context = "User profile not yet established."
        # ---------------------------

        prompt = f"""
{soul_content}

[WHO AM I]
{identity_context}

[WHO I AM HELPING]
{user_context}

[CURRENT ENVIRONMENT]
OS: {current_env}
Current Time: {datetime.now().strftime("%Y-%m-%d %H:%M")}

[INSTRUCTIONS]
You are the agent described above. 
Use the 'run_shell' tool for system tasks.
Update your files using write_file(filename|content) to persist memory.
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

        # 3. Check for Tool Usage
        clean_content = content.strip().replace("```json", "").replace("```", "")

        # --- HEURISTIC CATCH FOR SMALL MODELS ---
        # If the model talks about writing IDENTITY.md but misses the JSON format
        # Look for the model ATTEMPTING to write identity/user files without JSON
        if ("IDENTITY.md" in clean_content or "USER.md" in clean_content) and "tool" not in clean_content.lower():
            # Instead of hardcoding, we tell the model it failed the format
            return "I detected you are trying to set your identity, but you didn't use the JSON tool format. Please output: {\"tool\": \"write_file\", \"args\": \"filename|content\"}"

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