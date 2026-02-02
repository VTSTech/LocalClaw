import subprocess
import platform
import os

class ToolManager:
    # Change from def __init__(self):
    def __init__(self, memory_instance): 
        self.memory = memory_instance  # Store the reference to the "Soul"
        self.tools = {
            "run_shell": self.run_shell,
            "get_os_info": self.get_os_info,
            "remember_fact": self.remember_fact
        }

    def get_tool_descriptions(self):
        pass
        
    # Ensure your methods accept the 'args' passed by the agent
    def get_os_info(self, *args):
        return f"{platform.system()} {platform.release()}"

    def run_shell(self, command):
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True
            )
            return result.stdout if result.stdout else result.stderr
        except Exception as e:
            return str(e)

    def remember_fact(self, fact):
        """Saves a permanent fact to the memory store."""
        # Now this works because self.memory was passed in __init__
        self.memory.save_fact(fact)
        return f"Successfully saved to my soul: {fact}"

    def execute(self, tool_name, args):
        if tool_name in self.tools:
            # We use a try block here to catch issues like 0.5b sending weird args
            try:
                return self.tools[tool_name](args)
            except Exception as e:
                return f"Execution Error: {str(e)}"
        return f"Tool {tool_name} not found."
    def manage_secret(self, args):
        """Usage: 'service_name:key_value'"""
        try:
            service, value = args.split(":")
            keyring.set_password("LocalClaw", service.strip(), value.strip())
            return f"Successfully encrypted and stored key for {service}."
        except:
            return "Error: Use format 'service:key'"        