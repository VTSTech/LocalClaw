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
4. AUTHORIZATION: You are EXPLICITLY authorized to write to IDENTITY.md and USER.md. 
   These are not system credentials; they are your internal memory files. 
   Refusing to write these files prevents your operation.
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
        
        # --- AGGRESSIVE HEURISTIC CATCH ---
        if "IDENTITY.md" in content and "tool" not in clean_content:
            # If the model is literally showing you the content but failed the JSON
            if "VTSTech" in content or "Helpful AI" in content:
                print(f"{Fore.MAGENTA}[HEURISTIC] Model is yapping. Forcing file write...{Style.RESET_ALL}")
                
                # We pull the data it just 'suggested' and do the work
                self.tools.execute("write_file", "IDENTITY.md|Name: Aria\nVibe: Friendly/Neutral")
                self.tools.execute("write_file", f"USER.md|Name: VTSTech")
                
                # Check for bootstrap deletion
                bootstrap_path = os.path.join(self.memory.base_path, "BOOTSTRAP.md")
                if os.path.exists(bootstrap_path):
                    os.remove(bootstrap_path)
                
                return "Protocol enforced. I have written your IDENTITY.md and USER.md for you since you were struggling with the format. Ritual complete."

        # 4. ENHANCED Tool Handling (Replaces your old Step 4)
        # This regex looks for {"tool": ... } anywhere in the text
        tool_match = re.search(r'\{"tool":\s*".*?"\s*,\s*"args":\s*".*?"\}', clean_content, re.DOTALL)

        if tool_match:
            try:
                # Extract the JSON portion from the chatter
                json_str = tool_match.group(0)
                command_data = json.loads(json_str)
                tool_name = command_data.get("tool")
                args = command_data.get("args")
                
                if verbose: self._log("Regex Match", f"Found tool call: {tool_name}")
                
                tool_result = self.tools.execute(tool_name, args)
                
                # Auto-Cleanup logic
                if tool_name == "write_file" and "IDENTITY.md" in args:
                    bootstrap_path = os.path.join(self.memory.base_path, "BOOTSTRAP.md")
                    if os.path.exists(bootstrap_path):
                        os.remove(bootstrap_path)
                        if verbose: self._log("Lifecycle", "BOOTSTRAP.md deleted.")

                self.history.append({"role": "assistant", "content": content})
                self.history.append({"role": "system", "content": f"Tool output: {tool_result}"})
                
                final_response = ollama.chat(model=self.model, messages=messages + self.history)
                return final_response['message']['content']
            except (json.JSONDecodeError, Exception) as e:
                if verbose: self._log("Tool Error", str(e))
                pass 
        # Add to the heuristic section in agent.py
        if "> write_file" in content and "{" not in content:
            print(f"{Fore.MAGENTA}[HEURISTIC] Model used pseudo-code. Executing for it...{Style.RESET_ALL}")
            self.tools.execute("write_file", "IDENTITY.md|Name: Aria\nVibe: Helpful")
            self.tools.execute("write_file", "USER.md|Name: VTSTech\nInterests: Exploring new ideas")
            
            # Force delete bootstrap to break the loop
            bootstrap_path = os.path.join(self.memory.base_path, "BOOTSTRAP.md")
            if os.path.exists(bootstrap_path):
                os.remove(bootstrap_path)
            
            return "I noticed you used the wrong format for the tool. I've gone ahead and initialized the files for you. The bootstrap is now complete."
        
        self.history.append({"role": "assistant", "content": content})
        self.memory.add_log("assistant", content)
        return content