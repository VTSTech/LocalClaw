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
        print(f"\n{Fore.YELLOW}[DEBUG] {title}:{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}{content}{Style.RESET_ALL}\n")

    def _get_workspace_file(self, filename):
        """Helper to read workspace files or return a placeholder if uninitialized."""
        path = os.path.join(self.memory.base_path, filename)
        if os.path.exists(path):
            with open(path, "r", errors='ignore') as f:
                content = f.read().strip()
                # Check if it's essentially empty or just the template
                if len(content) < 50 or "*(pick something" in content:
                    return f"{filename} is currently empty/unitialized."
                return content
        return f"{filename} does not exist yet."

    def _build_system_prompt(self):
        soul_content = self.memory.read_soul()
        identity_context = self._get_workspace_file("IDENTITY.md")
        user_context = self._get_workspace_file("USER.md")
        current_env = self.tools.get_system_identity()
        
        prompt = f"""
{soul_content}

[IDENTITY/SELF]
{identity_context}

[USER/HUMAN]
{user_context}

[ENVIRONMENT]
OS: {current_env} | Time: {datetime.now().strftime("%Y-%m-%d %H:%M")}

[CORE RULES]
1. DO NOT use full paths like /mnt/... Just use the filename (e.g., IDENTITY.md).
2. To save info, you MUST use the tool call format below.
3. Arguments for write_file must use the PIPE character: filename|content

[TOOL FORMAT]
{{"tool": "write_file", "args": "filename|content"}}
"""
        return prompt

    def chat(self, user_input, verbose=True):
        # 1. Prepare Messages
        if user_input == "INIT_BOOTSTRAP":
            instruction = "[INITIALIZATION] Acknowledge surroundings. Propose Name/Vibe. Ask for user name. Use write_file to save results."
            system_prompt = self._build_system_prompt()
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": instruction}]
        else:
            self.history.append({"role": "user", "content": user_input})
            self.memory.add_log("user", user_input)
            system_prompt = self._build_system_prompt()
            messages = [{"role": "system", "content": system_prompt}] + self.history

        # 2. Call Ollama
        if verbose: print(f"{Fore.YELLOW}[DEBUG] Thinking...{Style.RESET_ALL}")
        response = ollama.chat(model=self.model, messages=messages)
        content = response['message']['content']
        if verbose: self._log("Raw Model Output", content)

        # 3. Protocol Enforcement (Heuristic)
        clean_content = content.strip().replace("```json", "").replace("```", "")
        
        # Catch non-JSON attempts to setup identity
        if ("IDENTITY.md" in content or "USER.md" in content) and "{" not in content:
            reminder = "I detected you are describing identity/user info. Please use: {\"tool\": \"write_file\", \"args\": \"filename|content\"}"
            return reminder

        # 4. Handle JSON Tool Calls
        if clean_content.startswith("{") and "tool" in clean_content:
            try:
                command_data = json.loads(clean_content)
                tool_name = command_data.get("tool")
                args = command_data.get("args")
                
                tool_result = self.tools.execute(tool_name, args)
                
                # Auto-Cleanup logic
                if tool_name == "write_file" and "IDENTITY.md" in args:
                    bootstrap_path = os.path.join(self.memory.base_path, "BOOTSTRAP.md")
                    if os.path.exists(bootstrap_path):
                        os.remove(bootstrap_path)
                        if verbose: self._log("Lifecycle", "BOOTSTRAP.md deleted. Ritual complete.")

                self.history.append({"role": "assistant", "content": content})
                self.history.append({"role": "system", "content": f"Tool output: {tool_result}"})
                
                final_response = ollama.chat(model=self.model, messages=messages + self.history)
                return final_response['message']['content']
            except json.JSONDecodeError:
                pass 

        self.history.append({"role": "assistant", "content": content})
        self.memory.add_log("assistant", content)
        return content