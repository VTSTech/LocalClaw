import subprocess
import os

def run_shell(command: str) -> str:
    if not command:
        return "Error: No command provided."

    if any(x in command for x in ["rm ", "mv ", "chmod", "shutdown", "reboot"]):
        return "Safety Violation: Restricted command."

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        output = (result.stdout + result.stderr).strip()
        return output if output else "Command executed successfully (no output)."
    except Exception as e:
        return f"Shell Error: {e}"

def read_file(filename: str) -> str:
    if not os.path.exists(filename):
        return f"Error: File '{filename}' does not exist."
    try:
        with open(filename, "r") as f:
            return f.read()
    except Exception as e:
        return f"Read Error: {e}"

def write_file(filename: str, content: str) -> str:
    try:
        with open(filename, "w") as f:
            f.write(content)
        return f"SUCCESS: Wrote {len(content)} bytes to {filename}"
    except Exception as e:
        return f"Write Error: {e}"
