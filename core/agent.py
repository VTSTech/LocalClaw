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
                # Check if it's just the template or actually has data
                if not content or "*(pick something" in content or len(content) < 10:
                    return f"DEBUG: {filename} exists but is empty or a template."
                return content
            except Exception as e:
                return f"DEBUG: Error reading {filename}: {str(e)}"
        return f"DEBUG: {filename} is missing."

    def _build_system_prompt(self):
        # Fetch current context
        soul_content = self.memory.read_soul()
        identity = self._get_workspace_file("IDENTITY.md")
        user_info = self._get_workspace_file("USER.md")
        current_env = self.tools.get_system_identity()
        
        # Determine state
        bootstrap_path = os.path.join(self.memory.base_path, "BOOTSTRAP.md")
        status = "INITIALIZING" if os.path.exists(bootstrap_path) else "OPERATIONAL"

        # Simplified "Loud" Instructions for 1B model
        prompt = f"""
### ROLE AND IDENTITY
- {identity}
- {user_info}

### OPERATIONAL TASKS
1. Greet the User by their [HUMAN_NAME].
2. Tell them your [AI_NAME].
3. Stop talking and wait for input.

### COMMANDS
- SAVE: RUN_WRITE: filename | content
- READ: RUN_READ: filename

### RESPONSE TEMPLATE
"Hello [HUMAN_NAME], I am [AI_NAME]. How can I help you?"
"""
        self._log("Injection Check", f"Agent sees: {prompt[-200:]}")
        print(f"{Fore.CYAN}[INTERNAL PROMPT CHECK]{Style.RESET_ALL}\n{prompt}")
        return prompt

    def chat(self, user_input, verbose=True):
        # 1. Handle Initialization Triggers
        if user_input == "INIT_BOOTSTRAP":
            instruction = "Waking up. Introduce yourself."
            messages = [{"role": "system", "content": self._build_system_prompt()}, {"role": "user", "content": instruction}]
        else:
            self.history.append({"role": "user", "content": user_input})
            self.memory.add_log("user", user_input)
            messages = [{"role": "system", "content": self._build_system_prompt()}] + self.history

        # 2. Get Model Response
        if verbose: print(f"{Fore.YELLOW}[DEBUG] Thinking...{Style.RESET_ALL}")
        response = ollama.chat(model=self.model, messages=messages)
        content = response['message']['content']
        if verbose: self._log("Raw Model Output", content)

        # 3. Process Triggers (1B-Friendly Regex)
        # Search for RUN_WRITE: filename | content
        write_match = re.search(r'RUN_WRITE:\s*(.*?)\s*\|\s*(.*)', content, re.DOTALL | re.IGNORECASE)
        # Search for RUN_READ: filename
        read_match = re.search(r'RUN_READ:\s*(.*)', content, re.IGNORECASE)

        # 4. Execute Actions
        if write_match:
            filename = write_match.group(1).strip()
            file_data = write_match.group(2).strip()
            
            # Execute the tool
            result = self.tools.execute("write_file", f"{filename}|{file_data}")
            if verbose: self._log("Action", f"Executed RUN_WRITE for {filename}")

            # Bootstrap Cleanup Logic
            if "IDENTITY.md" in filename or "USER.md" in filename:
                bp_path = os.path.join(self.memory.base_path, "BOOTSTRAP.md")
                if os.path.exists(bp_path):
                    os.remove(bp_path)
                    if verbose: self._log("Lifecycle", "Bootstrap removed. Agent is now resident.")

            return f"Action complete. I have saved your data to {filename}."

        if read_match:
            filename = read_match.group(1).strip()
            # If you added read_file to tools.py, this will work
            result = self.tools.execute("read_file", filename)
            
            # Feed content back to model for summary
            self.history.append({"role": "assistant", "content": content})
            self.history.append({"role": "system", "content": f"FILE CONTENT OF {filename}:\n{result}"})
            
            final_resp = ollama.chat(model=self.model, messages=messages + self.history)
            return final_resp['message']['content']

        # 5. Regular Conversation
        self.history.append({"role": "assistant", "content": content})
        self.memory.add_log("assistant", content)
        return content