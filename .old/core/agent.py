import ollama
import json
from .tools import ToolManager
from .memory import Memory

class LocalClawAgent:
    def __init__(self, model="llama3"):
        self.model = model
        self.tools = ToolManager()
        self.memory = Memory()
        self.history = []

    def _build_system_prompt(self):
        soul = self.memory.get_soul()
        prompt = f"""
        You are {soul['agent_name']}, a local AI assistant running on {self.tools.get_os_info()}.
        
        YOUR SOUL / FACTS KNOWN:
        User Name: {soul['user_name']}
        Memories: {json.dumps(soul['facts'])}
        
        CAPABILITIES:
        You have access to the following tools:
        {self.tools.get_tool_descriptions()}
        
        INSTRUCTIONS:
        1. If the user asks a question, answer directly.
        2. If you need to use a tool, respond ONLY with a JSON object: {{"tool": "tool_name", "args": "arguments"}}
        3. Do not fake tool usage. 
        """
        return prompt

    def chat(self, user_input):
        # 1. Add User Input to History
        self.history.append({"role": "user", "content": user_input})
        self.memory.add_log("user", user_input)

        # 2. Construct Messages
        messages = [{"role": "system", "content": self._build_system_prompt()}] + self.history

        # 3. Call Ollama
        response = ollama.chat(model=self.model, messages=messages)
        content = response['message']['content']

        # 4. Check for Tool Usage (Basic JSON parsing)
        if content.strip().startswith("{") and "tool" in content:
            try:
                command_data = json.loads(content)
                tool_name = command_data.get("tool")
                args = command_data.get("args")
                
                print(f"?? Executing {tool_name} with {args}...")
                tool_result = self.tools.execute(tool_name, args)
                
                # Feed tool result back to LLM
                tool_msg = f"Tool output: {tool_result}"
                self.history.append({"role": "assistant", "content": content})
                self.history.append({"role": "system", "content": tool_msg})
                
                # Get final answer
                final_response = ollama.chat(model=self.model, messages=messages + self.history)
                return final_response['message']['content']
                
            except json.JSONDecodeError:
                pass # Failed to parse tool, return raw text

        self.history.append({"role": "assistant", "content": content})
        self.memory.add_log("assistant", content)
        return content