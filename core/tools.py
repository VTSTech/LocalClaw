import subprocess
import platform
import os

class ToolManager:
    def __init__(self):
        self.tools = {
            "run_shell": self.run_shell,
            "get_os_info": self.get_os_info
        }

    def get_tool_descriptions(self):
        return """
        - run_shell(command): Executes a command in the system shell. Use cautiously.
        - get_os_info(): Returns information about the current operating system.
        """

    def run_shell(self, command):
        """Executes shell commands with a safety check."""
        forbidden = ["rm -rf /", "format c:"] # Basic safety
        if any(f in command for f in forbidden):
            return "Error: Command blocked for safety."
        
        try:
            # shell=True is required for complex commands, but risky.
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True,
                cwd=os.getcwd() # Run in current directory
            )
            return result.stdout if result.stdout else result.stderr
        except Exception as e:
            return str(e)

    def get_os_info(self):
        return f"{platform.system()} {platform.release()}"

    def execute(self, tool_name, args):
        if tool_name in self.tools:
            return self.tools[tool_name](args)
        return "Error: Tool not found."