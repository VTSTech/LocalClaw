import ollama
import json
import os
import re
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
        path = os.path.join(self.memory.base_path, filename)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding='utf-8', errors='ignore') as f:
                    content = f.read().strip()
                if not content or "*(pick something" in content or len(content) < 10:
                    return f"NONE (File {filename} is empty)"
                return content
            except Exception as e:
                return f"ERROR: {str(e)}"
        return "MISSING"

    def _build_system_prompt(self):
        id_raw = self._get_workspace_file("IDENTITY.md")
        user_raw = self._get_workspace_file("USER.md")

        ai_identity = "VTSBot (Adventurous Agent)" if "NONE" in id_raw or "MISSING" in id_raw else id_raw
        human_identity = "VTSTech (System Architect)" if "NONE" in user_raw or "MISSING" in user_raw else user_raw

        prompt = f"""
### MANDATORY IDENTITY
- YOU ARE: {ai_identity}
- TALKING TO: {human_identity}

### OPERATIONAL RULES
1. You are a resident agent. Speak as {ai_identity}.
2. Always address the human as {human_identity}.
3. Use RUN_WRITE: filename | content to save data.
4. Use RUN_READ: filename to view logs.

### COMMANDS
- To SAVE a file: RUN_WRITE: filename | content
- To READ a file: RUN_READ: filename
- To RUN SHELL: RUN_SHELL: command
	
### GOAL
Assist {human_identity} with system tasks and maintain your resident persona.
"""
        print(f"{Fore.CYAN}[INTERNAL PROMPT CHECK]{Style.RESET_ALL}\n{prompt}")
        return prompt

    def chat(self, user_input, verbose=True):
        if user_input == "INIT_BOOTSTRAP":
            instruction = "Waking up. Introduce yourself as VTSBot and greet VTSTech."
            messages = [{"role": "system", "content": self._build_system_prompt()}, {"role": "user", "content": instruction}]
        else:
            self.history.append({"role": "user", "content": user_input})
            self.memory.add_log("user", user_input)
            messages = [{"role": "system", "content": self._build_system_prompt()}] + self.history

        if verbose: print(f"{Fore.YELLOW}[DEBUG] Thinking...{Style.RESET_ALL}")
        response = ollama.chat(model=self.model, messages=messages)
        content = response['message']['content']
        if verbose: self._log("Raw Model Output", content)

        write_match = re.search(r'RUN_WRITE:\s*(.*?)\s*\|\s*(.*)', content, re.DOTALL | re.IGNORECASE)
        read_match = re.search(r'RUN_READ:\s*(.*)', content, re.IGNORECASE)

        if write_match:
            filename = write_match.group(1).strip()
            file_data = write_match.group(2).strip()
            result = self.tools.execute("write_file", f"{filename}|{file_data}")
            if verbose: self._log("Action", f"Executed RUN_WRITE for {filename}")
            
            if "IDENTITY.md" in filename or "USER.md" in filename:
                bp_path = os.path.join(self.memory.base_path, "BOOTSTRAP.md")
                if os.path.exists(bp_path):
                    os.remove(bp_path)
            
            return f"Action complete. I have saved your data to {filename}."

        if read_match:
            filename = read_match.group(1).strip()
            result = self.tools.execute("read_file", filename)
            self.history.append({"role": "assistant", "content": content})
            self.history.append({"role": "system", "content": f"FILE CONTENT OF {filename}:\n{result}"})
            final_resp = ollama.chat(model=self.model, messages=messages + self.history)
            return final_resp['message']['content']
        # Search for RUN_SHELL: command
        shell_match = re.search(r'RUN_SHELL:\s*(.*)', content, re.IGNORECASE)

        if shell_match:
            command = shell_match.group(1).strip()
            # Execute the shell tool
            result = self.tools.run_shell(command)
            if verbose: self._log("Action", f"Executed Shell: {command}")
            
            # Feed the output back to the model
            self.history.append({"role": "assistant", "content": content})
            self.history.append({"role": "system", "content": f"SHELL OUTPUT:\n{result}"})
            final_resp = ollama.chat(model=self.model, messages=messages + self.history)
            return final_resp['message']['content']
            
        self.history.append({"role": "assistant", "content": content})
        self.memory.add_log("assistant", content)
        return content