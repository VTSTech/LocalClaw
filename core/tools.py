import subprocess
import platform
import os

class ToolManager:
    # Change from def __init__(self):
    def __init__(self, memory_instance): 
        self.memory = memory_instance
        self.tools = {
            "run_shell": self.run_shell,
            "get_os_info": self.get_os_info,
            "remember_fact": self.remember_fact,
            "write_file": self.write_file,    # <--- Added
            "manage_secret": self.manage_secret # <--- Added
        }

    def get_tool_descriptions(self):
        pass
        
    # Ensure your methods accept the 'args' passed by the agent
    def get_os_info(self, *args):
        return f"{platform.system()} {platform.release()}"
        
    def get_system_identity(self):
        """Returns a string describing the current environment."""
        os_name = platform.system()
        release = platform.release()
        
        if os_name == "Windows":
            return f"Windows {platform.release()} (Version: {platform.version()})"
        elif os_name == "Linux":
            # Try to get specific distro like 'Ubuntu'
            try:
                import subprocess
                distro = subprocess.check_output("lsb_release -is", shell=True, text=True).strip()
                return f"{distro} Linux {release}"
            except:
                return f"Linux {release}"
        return f"{os_name} {release}"
        
    def write_file(self, args):
        """Usage: 'filename|content' or 'filename content'"""
        try:
            # Handle both pipe-separated and space-separated if the pipe is missing
            if "|" in args:
                filename, content = args.split("|", 1)
            else:
                filename, content = args.split(" ", 1)
                
            filepath = os.path.join(self.memory.base_path, filename.strip())
            with open(filepath, "w", encoding='utf-8') as f:
                f.write(content.strip())
            return f"Successfully updated {filename}."
        except Exception as e:
            return f"Error writing file: {str(e)}"
            	
    def read_file(self, args):
		        """Usage: RUN_READ: filename"""
		        filename = args.strip()
		        # Prevent the model from escaping the memory_store
		        safe_name = os.path.basename(filename) 
		        path = os.path.join(self.memory.base_path, safe_name)
		        
		        if os.path.exists(path):
		            with open(path, 'r', errors='ignore') as f:
		                return f.read()
		        return f"Error: File {filename} not found in memory store."   
		    	      	
    def list_files(self, args=None):
        """Usage: RUN_LIST: memory"""
        try:
            files = os.listdir(self.memory.base_path)
            if not files:
                return "The memory store is currently empty."
            return "\n".join([f"- {f}" for f in files])
        except Exception as e:
            return f"Error listing files: {str(e)}"
            	
    def run_shell(self, command):
        try:
            if "rm " in command:
                return "Safety Violation: Use 'trash' instead of 'rm' as per AGENTS.md."
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