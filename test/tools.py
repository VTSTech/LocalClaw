import subprocess
import os
import shlex

DANGEROUS = [
    "rm ", "mv ", "chmod", "chown",
    "shutdown", "reboot", "poweroff",
    ":(){", "mkfs", "dd "
]

def run_shell(command: str) -> str:
    if isinstance(command, str):
        command = command.replace('{"command":', '').replace('}', '').strip('" ')
    if not command:
        return "Error: No command provided."

    cmd = command.strip()

    if any(x in cmd for x in DANGEROUS):
        return "Safety Violation: Restricted command."

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        output = (result.stdout + result.stderr).strip()
        return output if output else "(no output)"
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
            f.write(content or "")
        return f"SUCCESS: wrote {len(content or '')} bytes to {filename}"
    except Exception as e:
        return f"Write Error: {e}"
