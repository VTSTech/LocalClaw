import ollama
import json
from colorama import Fore, Style
from .tools import ToolManager
from .memory import Memory
from config import DEFAULT_MODEL  # <--- Import here

class LocalClawAgent:
    def __init__(self, model=DEFAULT_MODEL):
        self.model = model
        self.memory = Memory()  # 1. Create Memory first
        self.tools = ToolManager(self.memory) # 2. Pass it to Tools
        self.history = []

    def _log(self, title, content):
        """Helper to print debug info in a distinct color"""
        print(f"\n{Fore.YELLOW}[DEBUG] {title}:{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}{content}{Style.RESET_ALL}\n")

    def _build_system_prompt(self):
        soul = self.memory.get_soul()
        prompt = f"""
[IDENTITY]
AI Name: {soul['agent_name']}
Human Name: {soul['user_name']}

[MEMORY]
Last Known Facts: {json.dumps(soul['facts'])}

[TOOLS]
{self.tools.get_tool_descriptions()}

[RULES]
1. If the Human gives their name, you MUST use 'remember_fact'. 
   Example: {{"tool": "remember_fact", "args": "The user's name is VTSTech"}}
2. After a tool runs, use the 'Tool output' to give a natural response.
3. If the Human's name is in [IDENTITY], use it!
"""
        return prompt

    def chat(self, user_input, verbose=True):
        # 1. Add User Input to History
        self.history.append({"role": "user", "content": user_input})
        self.memory.add_log("user", user_input)

        # 2. Construct Messages
        system_prompt = self._build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}] + self.history

        if verbose:
            self._log("Context Window (Last message)", messages[-1])
            self._log("System Prompt (Snippet)", system_prompt[:200] + "...")

        # 3. Call Ollama
        if verbose: print(f"{Fore.YELLOW}[DEBUG] Thinking...{Style.RESET_ALL}")
        response = ollama.chat(model=self.model, messages=messages)
        content = response['message']['content']

        if verbose:
            self._log("Raw Model Output", content)

        # 4. Check for Tool Usage
        # We clean the content to handle cases where small models add Markdown formatting like ```json ... ```
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
                
                # Feed tool result back to LLM
                tool_msg = f"Tool output: {tool_result}"
                self.history.append({"role": "assistant", "content": clean_content})
                self.history.append({"role": "system", "content": tool_msg})
                
                # Get final answer
                final_response = ollama.chat(model=self.model, messages=messages + self.history)
                return final_response['message']['content']
                
            except json.JSONDecodeError as e:
                if verbose: self._log("JSON Parse Error", str(e))
                pass # Failed to parse, return raw text

        self.history.append({"role": "assistant", "content": content})
        self.memory.add_log("assistant", content)
        return content